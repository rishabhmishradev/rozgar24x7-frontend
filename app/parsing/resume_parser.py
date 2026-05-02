"""Orchestrator for end-to-end resume parsing."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast

from .entity_extractor import extract_entities
from .section_detector import detect_sections, detect_sections_with_confidence
from .text_extractor import TextExtractor


logger = logging.getLogger(__name__)


class ParsingError(RuntimeError):
    """Raised when parsing fails at orchestration level."""


class SectionError(RuntimeError):
    """Raised when section detection yields invalid output."""


def _default_metadata() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class ResumeParseResult:
    raw_text: str
    sections: dict[str, str]
    entities: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=_default_metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "sections": self.sections,
            "entities": self.entities,
            "metadata": self.metadata,
        }


class ResumeParser:
    """Coordinates extraction, section detection, and entity extraction."""

    def __init__(
        self,
        text_extractor: TextExtractor | None = None,
        section_detector: Callable[[str], dict[str, str]] = detect_sections,
        entity_extractor: Callable[..., dict[str, Any]] = extract_entities,
        llm_fallback_parser: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.text_extractor = text_extractor or TextExtractor()
        self.section_detector = section_detector
        self.entity_extractor = entity_extractor
        self.llm_fallback_parser = llm_fallback_parser

    def parse_file(
        self,
        file_path: str | Path,
        jd_context: dict[str, Any] | None = None,
        enable_section_llm: bool = False,
    ) -> ResumeParseResult:
        path = Path(file_path)
        suffix = path.suffix.lower()

        # For PDF and DOCX: try the layout-aware pipeline first
        if suffix in (".pdf", ".docx"):
            try:
                return self._parse_file_layout_aware(path, jd_context, enable_section_llm=enable_section_llm)
            except Exception as exc:
                logger.warning(
                    "Layout-aware pipeline failed for %s, falling back to text pipeline: %s",
                    path.name,
                    exc,
                )

        # Fallback / original text-based pipeline for all formats
        text = self.text_extractor.extract(file_path)
        return self.parse_text(text, jd_context=jd_context)

    def _parse_file_layout_aware(
        self,
        file_path: Path,
        jd_context: dict[str, Any] | None = None,
        enable_section_llm: bool = False,
    ) -> ResumeParseResult:
        """Run the layout-aware pipeline and wrap the result in ResumeParseResult."""
        from .pipeline import LayoutAwareResumeParser

        layout_parser = LayoutAwareResumeParser(enable_section_llm=enable_section_llm)
        pipeline_output = layout_parser.parse(file_path)

        raw_text = pipeline_output["raw_text"]
        sections = pipeline_output["sections"]
        entities = pipeline_output["entities"]
        per_section_confidence = pipeline_output.get("section_confidence", {})
        llm_field_parse_status = pipeline_output.get("llm_field_parse_status", {})

        # If jd_context was provided, re-run skill extraction with it
        if jd_context:
            try:
                entities_with_jd = self.entity_extractor(raw_text, sections, jd_context)
                # Merge: prefer layout pipeline's experience/education/projects/contact
                # but use the jd-context-aware skills
                entities["skills"] = entities_with_jd.get("skills", entities["skills"])
                entities["skill_names"] = entities_with_jd.get("skill_names", entities.get("skill_names", []))
            except Exception:
                pass  # keep pipeline-extracted skills

        # Compute overall section confidence from per-section scores
        if per_section_confidence:
            section_confidence = sum(per_section_confidence.values()) / len(per_section_confidence)
            section_confidence_available = True
        else:
            section_confidence = 0.2
            section_confidence_available = False

        metadata = self._build_metadata(
            raw_text,
            sections,
            entities,
            section_confidence,
            section_confidence_available=section_confidence_available,
        )
        metadata["pipeline"] = "layout_aware"
        metadata["section_confidence_detail"] = per_section_confidence
        if llm_field_parse_status:
            metadata["llm_field_parse_status"] = llm_field_parse_status
            invalid_count, total_count = ResumeParser._llm_parse_stats(llm_field_parse_status)
            valid_ratio = (total_count - invalid_count) / total_count if total_count > 0 else 1.0
            metadata["llm_field_valid_ratio"] = round(valid_ratio, 3)
            if invalid_count > 0:
                existing = float(metadata.get("parsing_confidence", 0.0) or 0.0)
                penalty = min(0.35, 0.12 * invalid_count)
                metadata["parsing_confidence"] = round(max(0.0, existing - penalty), 2)
                metadata.setdefault("quality_warnings", []).append(
                    f"{invalid_count}/{total_count} LLM section parses failed validation; confidence reduced."
                )

        logger.info(
            "Layout-aware parsing complete: sections=%d skills=%d confidence=%.2f",
            len(sections),
            len(entities.get("skills", [])),
            metadata["parsing_confidence"],
        )

        return ResumeParseResult(
            raw_text=raw_text,
            sections=sections,
            entities=entities,
            metadata=metadata,
        )


    def parse_text(
        self,
        text: str,
        jd_context: dict[str, Any] | None = None,
    ) -> ResumeParseResult:
        if not text or len(text.strip()) < 20:
            raise ValueError("Input text is too short for reliable resume parsing.")

        try:
            if self.section_detector is detect_sections:
                sections, section_confidence = detect_sections_with_confidence(text)
                section_confidence_available = True
            else:
                sections = self.section_detector(text)
                section_confidence = 0.35
                section_confidence_available = False
        except Exception as exc:
            raise SectionError("Section detection failed.") from exc

        try:
            try:
                entities = self.entity_extractor(text, sections, jd_context)
            except TypeError:
                entities = self.entity_extractor(text, sections)
        except Exception as exc:
            raise ParsingError("Entity extraction failed.") from exc

        metadata = self._build_metadata(
            text,
            sections,
            entities,
            section_confidence,
            section_confidence_available=section_confidence_available,
        )

        if metadata["completeness_score"] < 0.5 and self.llm_fallback_parser is not None:
            logger.info(
                "Completeness %.2f is low, invoking LLM fallback parser",
                metadata["completeness_score"],
            )
            fallback_entities = self.llm_fallback_parser(text)
            entities = fallback_entities
            metadata = self._build_metadata(
                text,
                sections,
                entities,
                section_confidence,
                section_confidence_available=section_confidence_available,
            )
            metadata["fallback_used"] = "llm"

        if metadata["completeness_score"] < 0.5 and self.llm_fallback_parser is None:
            metadata["fallback_used"] = "none"
            metadata["quality_warnings"].append("Low completeness and no LLM fallback parser configured.")

        logger.info(
            "Parsing complete: sections=%d skills=%d confidence=%.2f",
            len(sections),
            len(entities.get("skills", [])),
            metadata["parsing_confidence"],
        )

        return ResumeParseResult(
            raw_text=text,
            sections=sections,
            entities=entities,
            metadata=metadata,
        )

    @staticmethod
    def _build_metadata(
        text: str,
        sections: dict[str, str],
        entities: dict[str, Any],
        section_confidence: float,
        *,
        section_confidence_available: bool = True,
    ) -> dict[str, Any]:
        words = re.findall(r"\w+", text)
        explicit_years = float(ResumeParser._estimate_years_experience(text))
        parsed_months = int(entities.get("total_experience_months", 0) or 0)
        parsed_years_float = float(
            entities.get("total_experience_years_float", entities.get("total_experience_years", 0)) or 0.0
        )
        estimated_months = parsed_months or int(round(explicit_years * 12))
        estimated_years_float = parsed_years_float or explicit_years
        if explicit_years and estimated_years_float:
            estimated_years_float = max(explicit_years, estimated_years_float)
        warnings = ResumeParser._quality_warnings(text, sections, entities)
        if not section_confidence_available:
            warnings.append("Section confidence unavailable; parsing confidence conservatively downgraded.")
        completeness = ResumeParser._completeness_score(sections, entities)

        return {
            "parsing_version": "1.3.0",
            "word_count": len(words),
            "section_count": len(sections),
            "skill_count": ResumeParser._skill_count(entities.get("skills", {})),
            "experience_item_count": len(entities.get("experience", [])),
            "estimated_experience_months": estimated_months,
            "estimated_experience_years_float": round(estimated_years_float, 2),
            "estimated_experience_years": round(estimated_years_float, 2),
            "estimated_seniority": ResumeParser._estimate_seniority(estimated_years_float),
            "completeness_score": completeness,
            "parsing_confidence": ResumeParser._parsing_confidence(
                sections,
                entities,
                section_confidence,
                section_confidence_available=section_confidence_available,
            ),
            "section_confidence": round(section_confidence, 3),
            "section_confidence_available": section_confidence_available,
            "section_weights": {
                "experience": 0.4,
                "skills": 0.3,
                "education": 0.2,
                "summary": 0.1,
            },
            "quality_warnings": warnings,
        }

    @staticmethod
    def _estimate_years_experience(text: str) -> int:
        matches = re.findall(r"(\d{1,2})\+?\s+years?", text.lower())
        if not matches:
            return 0
        return max(int(match) for match in matches)

    @staticmethod
    def _estimate_seniority(years: float) -> str:
        if years >= 10:
            return "principal"
        if years >= 7:
            return "senior"
        if years >= 3:
            return "mid"
        if years > 0:
            return "junior"
        return "unknown"

    @staticmethod
    def _quality_warnings(text: str, sections: dict[str, str], entities: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if len(text.split()) < 180:
            warnings.append("Resume appears short; extraction or input quality may be limited.")
        if not entities.get("contact", {}).get("email"):
            warnings.append("Email not detected.")
        if not sections.get("experience"):
            warnings.append("Experience section not detected.")
        if not sections.get("skills"):
            warnings.append("Skills section not detected.")
        return warnings

    @staticmethod
    def _completeness_score(sections: dict[str, str], entities: dict[str, Any]) -> float:
        contact_quality = ResumeParser._contact_quality(entities.get("contact", {}))
        experience_depth = ResumeParser._experience_depth(entities.get("experience", []))
        skill_richness = ResumeParser._skill_richness(entities.get("skills", []))
        bullet_quality = ResumeParser._bullet_quality(entities.get("experience", []))
        project_presence = 1.0 if entities.get("projects") else 0.0

        score = (
            0.25 * contact_quality
            + 0.30 * experience_depth
            + 0.20 * skill_richness
            + 0.15 * bullet_quality
            + 0.10 * project_presence
        )
        return round(min(score, 1.0), 3)

    @staticmethod
    def _parsing_confidence(
        sections: dict[str, str],
        entities: dict[str, Any],
        section_confidence: float,
        *,
        section_confidence_available: bool = True,
    ) -> float:
        section_signal = max(0.0, min(section_confidence, 1.0))

        score = 0.0
        if sections.get("experience"):
            score += 0.15
        if entities.get("skills"):
            score += 0.15
        if entities.get("contact", {}).get("email"):
            score += 0.15
        if len(entities.get("experience", [])) > 1:
            score += 0.15
        if sections.get("education"):
            score += 0.05
        if ResumeParser._skill_count(entities.get("skills", {})) >= 3:
            score += 0.10

        score += 0.40 * section_signal

        # Section presence alone should not pass parseability without reliable confidence.
        if not section_confidence_available or section_signal < 0.5:
            score = min(score, 0.69)

        if not sections.get("experience") or not sections.get("skills"):
            score = min(score, 0.65)

        return round(min(score, 1.0), 2)

    @staticmethod
    def _contact_quality(contact: dict[str, Any]) -> float:
        score = 0.0
        score += 0.4 if contact.get("email") else 0.0
        score += 0.2 if contact.get("phone") else 0.0
        score += 0.2 if contact.get("linkedin") else 0.0
        score += 0.2 if contact.get("name") else 0.0
        return min(score, 1.0)

    @staticmethod
    def _experience_depth(experience: list[dict[str, Any]]) -> float:
        if not experience:
            return 0.0
        count_score = min(len(experience) / 3, 1.0)
        bullet_count = sum(len(entry.get("bullets", [])) for entry in experience)
        bullet_score = min(bullet_count / 8, 1.0)
        duration_score = 1.0 if any(entry.get("duration") for entry in experience) else 0.4
        return min(0.35 * count_score + 0.4 * bullet_score + 0.25 * duration_score, 1.0)

    @staticmethod
    def _skill_richness(skills: list[str]) -> float:
        count = ResumeParser._skill_count(skills)
        return min(count / 12, 1.0)

    @staticmethod
    def _skill_count(skills: Any) -> int:
        if isinstance(skills, Mapping):
            skills_map = cast(Mapping[str, Any], skills)
            return len(skills_map)
        if isinstance(skills, Sequence) and not isinstance(skills, (str, bytes, bytearray)):
            skills_seq = cast(Sequence[Any], skills)
            return len(skills_seq)
        return 0

    @staticmethod
    def _bullet_quality(experience: list[dict[str, Any]]) -> float:
        number_re = re.compile(r"\b\d+(?:\.\d+)?%?\b|\$\d+[\dkKmM]*")
        result_markers = {
            "increased",
            "reduced",
            "improved",
            "boosted",
            "saved",
            "cut",
            "achieved",
            "delivered",
            "grew",
            "optimized",
        }
        tool_markers = {
            "python",
            "pytorch",
            "tensorflow",
            "fastapi",
            "django",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "postgresql",
            "mysql",
            "mongodb",
            "spark",
        }

        bullets: list[str] = []
        for entry in experience:
            bullets.extend([value.strip().lower() for value in entry.get("bullets", []) if value.strip()])
        if not bullets:
            return 0.0

        number_hits = sum(1 for bullet in bullets if number_re.search(bullet))
        result_hits = sum(1 for bullet in bullets if any(marker in bullet for marker in result_markers))
        tool_hits = sum(
            1
            for bullet in bullets
            if any(re.search(rf"\b{re.escape(tool)}\b", bullet) for tool in tool_markers)
        )

        number_score = number_hits / len(bullets)
        result_score = result_hits / len(bullets)
        tool_score = tool_hits / len(bullets)
        return round(min(0.4 * number_score + 0.35 * result_score + 0.25 * tool_score, 1.0), 3)

    @staticmethod
    def _llm_parse_stats(status_map: Any) -> tuple[int, int]:
        if not isinstance(status_map, Mapping):
            return 0, 0

        statuses = cast(Mapping[str, Any], status_map)
        invalid = 0
        total = 0
        for value in statuses.values():
            if not isinstance(value, Mapping):
                continue
            row = cast(Mapping[str, Any], value)
            valid = bool(row.get("valid", False))
            total += 1
            if not valid:
                invalid += 1
        return invalid, total
