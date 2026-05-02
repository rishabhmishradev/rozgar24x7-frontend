"""End-to-End Layout-Aware Resume Parsing Pipeline.

This module provides LayoutAwareResumeParser which:
1. Normalizes DOCX → PDF
2. Extracts lossless tokens with bounding boxes and hyperlinks via PyMuPDF
3. Detects layout complexity (single vs multi-column)
4. Routes complex layouts through LayoutLMv3 (or heuristic fallback)
5. Segments tokens into canonical resume sections
6. Parses field-level sections via section-wise LLM extraction with validation
7. Falls back to deterministic field parsers when LLM validation fails
8. Extracts contact, skills, keywords, and experience years deterministically
9. Returns output in the canonical ResumeParseResult shape expected by the rest of the project
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .normalizer import normalize_to_pdf
from .pdf_extractor import extract_tokens, Token, TokenLine, render_pages_as_images
from .layout_preprocessor import detect_layout_complexity, prep_lines_for_layout_model
from .layout_model import ResumeLayoutModel
from .section_segmenter import SectionSegmenter
from .experience_parser import ExperienceParser
from .llm_section_parser import ResumeSectionLLMParser
from .structured_utils import (
    clean_text_line,
    extract_validated_links,
    normalize_certification_entry,
    normalize_experience_entries,
    normalize_project_entry,
    parse_certification_lines,
    parse_project_section_lines,
    parse_skill_mentions,
    skill_display_label,
    summarize_total_experience,
)

logger = logging.getLogger(__name__)

_SPACY_MODEL: Any | None = None
_SPACY_LOAD_ATTEMPTED = False
_SPACY_WARNING_EMITTED = False


def _load_spacy_model_once() -> Any | None:
    """Load spaCy model once per process; return None when unavailable."""
    global _SPACY_MODEL, _SPACY_LOAD_ATTEMPTED, _SPACY_WARNING_EMITTED
    if _SPACY_LOAD_ATTEMPTED:
        return _SPACY_MODEL

    _SPACY_LOAD_ATTEMPTED = True
    try:
        import spacy  # type: ignore

        try:
            _SPACY_MODEL = spacy.load("en_core_web_sm")
        except Exception:
            # Some environments install the model as a package that must be loaded directly.
            import importlib

            model_pkg = importlib.import_module("en_core_web_sm")
            _SPACY_MODEL = model_pkg.load()
    except Exception:
        _SPACY_MODEL = None
        if not _SPACY_WARNING_EMITTED:
            logger.warning("spaCy en_core_web_sm unavailable; NER will be degraded.")
            _SPACY_WARNING_EMITTED = True

    return _SPACY_MODEL

# ── regex ────────────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3})?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    r"|(?:\+?\d{1,3}[\s-]?)?[6-9]\d{4}[\s.-]?\d{5}"
)
URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s]+", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s]+", re.I)
DATE_RANGE_RE = re.compile(
    r"\b(?P<start>19\d{2}|20\d{2})\s*(?:-|to|–|—)\s*(?P<end>present|current|19\d{2}|20\d{2})\b",
    re.I,
)
MONTH_RANGE_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|july?|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*\d{2,4}\s*"
    r"(?:-|to|–|—)\s*(?:present|current|(?:jan|feb|mar|apr|may|jun|july?|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*\d{2,4})\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Skills catalog (kept lightweight; the full catalog lives in entity_extractor)
CORE_SKILLS = {
    "python", "r", "java", "c++", "c#", "javascript", "typescript", "react",
    "next.js", "node.js", "fastapi", "django", "flask", "postgresql",
    "mysql", "mongodb", "redis", "docker", "kubernetes", "aws", "azure",
    "gcp", "pandas", "numpy", "scikit-learn", "sql", "rest", "graphql",
    "linux", "pytest", "ci/cd", "tensorflow", "pytorch", "html", "css",
    "git", "spark", "kafka", "airflow", "go", "rust", "swift", "kotlin",
    "angular", "vue", "spring boot", "express", "terraform", "jenkins",
    "machine learning", "deep learning", "nlp", "computer vision",
    "data science", "data engineering",
}

DEGREE_TOKENS = (
    "bachelor", "master", "phd", "b.tech", "m.tech", "mba", "bsc",
    "msc", "diploma", "associate", "b.e", "m.e", "b.s", "m.s",
    "post graduate", "postgraduate", "doctorate",
)


class LayoutAwareResumeParser:
    """Orchestrates the 10-step layout-aware parsing pipeline.

    Returns output in the same shape as the existing entity_extractor so that
    the web UI, API, CLI, and intelligence modules work without changes.
    """

    def __init__(self, model_checkpoint: str | None = None, enable_section_llm: bool = True):
        self.layout_model = ResumeLayoutModel(model_checkpoint=model_checkpoint)
        self.segmenter = SectionSegmenter()
        self.experience_parser = ExperienceParser()
        self.enable_section_llm = bool(enable_section_llm)
        self.section_llm_parser = ResumeSectionLLMParser() if self.enable_section_llm else None

        # spaCy NER (cached, warning emitted once when unavailable)
        self.nlp = _load_spacy_model_once()
        self._has_spacy = self.nlp is not None

    # ── public entry point ───────────────────────────────────────────────
    def parse(self, file_path: str | Path) -> Dict[str, Any]:
        """Run the full pipeline and return entities dict + sections dict + raw text."""
        file_path = Path(file_path)
        logger.info("Pipeline start: %s", file_path)

        # STEP 1 – normalise to PDF
        pdf_path = normalize_to_pdf(file_path)

        # STEP 2 – lossless extraction
        lines = extract_tokens(pdf_path)
        if not lines:
            raise ValueError(f"No text extracted from {file_path}")

        # Infer page dimensions from actual content bounding boxes
        page_width, page_height = self._infer_page_dims(lines)

        # STEP 3 – layout complexity
        complexity = detect_layout_complexity(lines, page_width=page_width)
        logger.info("Layout complexity: %s (%d lines)", complexity, len(lines))

        # STEP 4+5 – optional LayoutLMv3
        predictions: Optional[List[str]] = None
        if complexity == "complex" and not self.layout_model.use_heuristics:
            logger.info("Running layout model (or heuristic fallback)…")
            prepped = prep_lines_for_layout_model(lines, page_width, page_height)
            words = [p["text"] for p in prepped]
            boxes = [tuple(p["bbox"]) for p in prepped]
            predictions = self.layout_model.predict("", words, boxes)

        # STEP 6 – section segmentation (new API: returns sections + confidence)
        section_lines, section_confidence = self.segmenter.segment(
            lines, predictions=predictions, page_width=page_width
        )
        logger.info(
            "Sections detected: %s (confidence: %s)",
            list(section_lines.keys()),
            {k: f"{v:.0%}" for k, v in section_confidence.items()},
        )

        # Build flat text per section for downstream compatibility
        full_text = "\n".join(line.text for line in lines)
        sections_text: Dict[str, str] = {}
        for sec_name, sec_lines in section_lines.items():
            sections_text[sec_name] = "\n".join(line.text for line in sec_lines)

        # Collect all hyperlinks across all pages
        all_links = self._collect_hyperlinks(lines)

        # Some resumes use a research/publications section for project work.
        projects_text_for_llm = sections_text.get("projects", "")
        if sections_text.get("publications"):
            pub_text = sections_text.get("publications", "")
            projects_text_for_llm = f"{projects_text_for_llm}\n{pub_text}".strip()

        llm_input_sections = {
            "experience": sections_text.get("experience", ""),
            "education": sections_text.get("education", ""),
            "projects": projects_text_for_llm,
            "certifications": sections_text.get("certifications", ""),
        }
        if self.section_llm_parser is not None:
            llm_field_data, llm_status = self.section_llm_parser.parse_sections(llm_input_sections)
        else:
            llm_field_data = {
                "experience": [],
                "education": [],
                "projects": [],
                "certifications": [],
            }
            llm_status = {}

        # STEP 7 – field extraction (LLM first, deterministic fallback)
        experience = self._normalize_llm_experience(llm_field_data.get("experience", []))
        if (
            (not llm_status.get("experience") or not llm_status["experience"].valid)
            and section_lines.get("experience")
        ):
            logger.info("Experience LLM parsing invalid; using deterministic fallback.")
            experience = self._build_experience(section_lines.get("experience", []), all_links)
        elif not experience and section_lines.get("experience"):
            logger.info("Experience LLM parsing empty; using deterministic fallback.")
            experience = self._build_experience(section_lines.get("experience", []), all_links)

        experience = self._consolidate_experience_entries(experience)

        education = self._normalize_llm_education(llm_field_data.get("education", []))
        education_has_identity = any(
            str(entry.get("degree") or "").strip() or str(entry.get("institution") or "").strip()
            for entry in education
        )
        if (
            (not llm_status.get("education") or not llm_status["education"].valid)
            and section_lines.get("education")
        ):
            logger.info("Education LLM parsing invalid; using deterministic fallback.")
            education = self._extract_education(section_lines.get("education", []))
        elif section_lines.get("education") and not education_has_identity:
            logger.info("Education LLM parsing low quality; using deterministic fallback.")
            education = self._extract_education(section_lines.get("education", []))
        elif not education and section_lines.get("education"):
            logger.info("Education LLM parsing empty; using deterministic fallback.")
            education = self._extract_education(section_lines.get("education", []))

        project_lines = list(section_lines.get("projects", []))
        if section_lines.get("publications"):
            project_lines.extend(section_lines.get("publications", []))

        projects = self._normalize_llm_projects(llm_field_data.get("projects", []))
        if (
            (not llm_status.get("projects") or not llm_status["projects"].valid)
            and project_lines
        ):
            logger.info("Projects LLM parsing invalid; using deterministic fallback.")
            projects = self._extract_projects(project_lines, all_links)
        elif not projects and project_lines:
            logger.info("Projects LLM parsing empty; using deterministic fallback.")
            projects = self._extract_projects(project_lines, all_links)

        certifications = self._normalize_llm_certifications(llm_field_data.get("certifications", []))
        if (
            (not llm_status.get("certifications") or not llm_status["certifications"].valid)
            and sections_text.get("certifications", "").strip()
        ):
            logger.info("Certifications LLM parsing invalid; using deterministic fallback.")
            certifications = self._extract_certifications(sections_text)
        elif not certifications and sections_text.get("certifications", "").strip():
            logger.info("Certifications LLM parsing empty; using deterministic fallback.")
            certifications = self._extract_certifications(sections_text)

        # STEP 8 – deterministic contact/skills/keywords extraction
        contact = self._extract_contact(full_text, lines, all_links)
        skills_scored, skill_names = self._extract_skills(sections_text, full_text)
        keywords = self._extract_keywords(full_text)
        experience_summary = summarize_total_experience(experience)

        entities: Dict[str, Any] = {
            "contact": contact,
            "skills": skills_scored,
            "skill_names": skill_names,
            "education": education,
            "experience": experience,
            "projects": projects,
            "certifications": certifications,
            "keywords": keywords,
            **experience_summary,
        }

        return {
            "raw_text": full_text,
            "sections": sections_text,
            "entities": entities,
            "section_confidence": section_confidence,
            "llm_field_parse_status": {
                name: status.to_dict() for name, status in llm_status.items()
            },
        }

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _infer_page_dims(lines: List[TokenLine]) -> tuple[float, float]:
        """Best-effort page size from bounding boxes; fall back to US Letter."""
        max_x = max((t.bbox[2] for line in lines for t in line.tokens), default=612.0)
        max_y = max((t.bbox[3] for line in lines for t in line.tokens), default=792.0)
        return max(max_x, 612.0), max(max_y, 792.0)

    @staticmethod
    def _collect_hyperlinks(lines: List[TokenLine]) -> List[Dict[str, str]]:
        seen: set[str] = set()
        links: List[Dict[str, str]] = []
        for line in lines:
            for t in line.tokens:
                if t.is_link and t.link_target and t.link_target not in seen:
                    seen.add(t.link_target)
                    links.append({"text": t.text, "url": t.link_target})
        return links

    # ── contact ───────────────────────────────────────────────────────────

    def _extract_contact(
        self,
        full_text: str,
        lines: List[TokenLine],
        all_links: List[Dict[str, str]],
    ) -> Dict[str, Optional[str]]:
        email_m = EMAIL_RE.search(full_text)
        phone_m = PHONE_RE.search(full_text)
        links = extract_validated_links(full_text, [lnk["url"] for lnk in all_links])

        # Name extraction via spaCy on first few lines
        name = self._extract_name(lines)

        return {
            "name": name,
            "email": email_m.group(0) if email_m else None,
            "phone": phone_m.group(0).strip() if phone_m else None,
            "linkedin": links["linkedin"],
            "github": links["github"],
            "portfolio": links["portfolio"],
        }

    def _extract_name(self, lines: List[TokenLine]) -> Optional[str]:
        """Extract the candidate name from the first few lines."""
        candidates = [line.text.strip() for line in lines[:5] if line.text.strip()]
        for cand in candidates:
            # Skip lines with emails / urls / phone numbers
            if re.search(r"@|http|www\.|[6-9]\d{9}|\d{3}[-.]?\d{3}[-.]?\d{4}", cand, re.I):
                continue
            words = cand.split()
            if 1 <= len(words) <= 4:
                if self._has_spacy:
                    doc = self.nlp(cand)
                    for ent in doc.ents:
                        if ent.label_ == "PERSON":
                            return ent.text
                # Fallback: first short non-technical line is likely the name
                return cand
        return None

    # ── skills ────────────────────────────────────────────────────────────

    def _extract_skills(
        self, sections_text: Dict[str, str], full_text: str
    ) -> tuple[Dict[str, Dict[str, Any]], List[str]]:
        """Tries the rich entity_extractor; falls back to lightweight parsing."""
        skill_section = sections_text.get("skills", "")
        explicit_skill_map = parse_skill_mentions(skill_section)
        explicit_section_skills = set(explicit_skill_map.keys())
        lowered = full_text.lower()

        try:
            from .entity_extractor import _extract_skills as _legacy_extract_skills
            scored, skill_names = _legacy_extract_skills(sections_text, full_text)
            if explicit_section_skills:
                for skill in explicit_section_skills:
                    if skill in scored:
                        continue
                    scored[skill] = {
                        "score": 0.72,
                        "source": ["skills_section"],
                        "frequency": lowered.count(skill),
                        "confidence": 0.8,
                        "embedding_score": 0.0,
                        "section_weight": 1.0,
                        "penalty": 0.0,
                        "penalty_reasons": [],
                        "weights": {"embedding": 0.0, "frequency": 0.0, "section": 1.0},
                    }
                for skill_name, payload in scored.items():
                    explicit_meta = explicit_skill_map.get(skill_name, {})
                    payload["canonical_key"] = skill_name
                    payload["display_label"] = skill_display_label(skill_name)
                    payload["aliases"] = list(explicit_meta.get("aliases", []))
                    payload["child_skills"] = list(explicit_meta.get("child_skills", []))
                skill_names = sorted(scored.keys())
            return scored, skill_names
        except Exception:
            logger.debug("Legacy _extract_skills unavailable; using lightweight fallback.")

        # Lightweight fallback
        found: set[str] = set(explicit_section_skills)
        for token in re.split(r"[,\n|;•\-]+", skill_section):
            t = token.strip().lower()
            if t and 1 < len(t) < 40:
                found.add(t)
        # Also match from full text
        for skill in CORE_SKILLS:
            if re.search(rf"\b{re.escape(skill)}\b", lowered):
                found.add(skill)

        scored: Dict[str, Dict[str, Any]] = {}
        for s in sorted(found):
            scored[s] = {
                "score": 0.7,
                "source": ["skills_section" if s in skill_section.lower() else "global_text"],
                "frequency": lowered.count(s),
                "confidence": 0.7,
                "embedding_score": 0.0,
                "section_weight": 0.5,
                "penalty": 0.0,
                "penalty_reasons": [],
                "weights": {"embedding": 0.0, "frequency": 0.0, "section": 1.0},
                "canonical_key": s,
                "display_label": skill_display_label(s),
                "aliases": list(explicit_skill_map.get(s, {}).get("aliases", [])),
                "child_skills": list(explicit_skill_map.get(s, {}).get("child_skills", [])),
            }
        return scored, sorted(scored.keys())

    @staticmethod
    def _split_skill_items_outside_parentheses(text: str) -> List[str]:
        parts: List[str] = []
        current: List[str] = []
        depth = 0

        for char in text:
            if char == "(":
                depth += 1
                current.append(char)
                continue
            if char == ")":
                depth = max(0, depth - 1)
                current.append(char)
                continue
            if char in {",", ";", "|"} and depth == 0:
                token = "".join(current).strip()
                if token:
                    parts.append(token)
                current = []
                continue
            current.append(char)

        token = "".join(current).strip()
        if token:
            parts.append(token)
        return parts

    @classmethod
    def _extract_explicit_skills_from_section(cls, skill_section: str) -> set[str]:
        return set(parse_skill_mentions(skill_section).keys())

    # ── experience ────────────────────────────────────────────────────────

    def _build_experience(
        self, exp_lines: List[TokenLine], all_links: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        raw_entries = self.experience_parser.parse(exp_lines)
        if not raw_entries:
            return []
        normalized_entries = normalize_experience_entries(
            [
                {
                    "role": raw.get("job_title", ""),
                    "company": raw.get("company", ""),
                    "location": raw.get("location", ""),
                    "start_date": raw.get("start_date", ""),
                    "end_date": raw.get("end_date", ""),
                    "duration": raw.get("date_string", ""),
                    "bullets": raw.get("description", []),
                    "skills_inferred": self._infer_skills_from_text(" ".join(raw.get("description", []) or [])),
                }
                for raw in raw_entries
            ]
        )
        logger.debug(
            "Experience pipeline debug: raw_entries=%s normalized_entries=%s",
            raw_entries,
            normalized_entries,
        )
        return normalized_entries

    def _infer_skills_from_text(self, text: str) -> List[str]:
        lowered = text.lower()
        found: set[str] = set()
        for skill in CORE_SKILLS:
            if re.search(rf"\b{re.escape(skill)}\b", lowered):
                found.add(skill)
        return sorted(found)

    def _normalize_llm_experience(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return normalize_experience_entries(
            [
                {
                    "role": item.get("job_title"),
                    "company": item.get("company"),
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                    "bullets": item.get("description", []),
                    "skills_inferred": self._infer_skills_from_text(
                        " ".join(item.get("description", []) if isinstance(item.get("description", []), list) else [])
                    ),
                }
                for item in entries
            ]
        )

    def _consolidate_experience_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Merge fragmented adjacent entries produced by noisy layouts/LLM extraction."""
        if len(entries) < 2:
            return entries

        merged: List[Dict[str, Any]] = []
        i = 0
        while i < len(entries):
            current = dict(entries[i])

            if i + 1 < len(entries):
                nxt = entries[i + 1]

                current_has_timeline = bool(str(current.get("start_date") or "").strip())
                current_has_bullets = bool(current.get("bullets"))
                next_has_timeline = bool(str(nxt.get("start_date") or "").strip())
                next_has_bullets = bool(nxt.get("bullets"))
                next_company = str(nxt.get("company") or "").strip()
                next_role = str(nxt.get("role") or "").strip()

                if (
                    current_has_timeline
                    and not current_has_bullets
                    and not next_has_timeline
                    and next_has_bullets
                    and not next_company
                    and next_role
                ):
                    role = str(current.get("role") or "").strip()
                    if role and next_role.lower() not in role.lower():
                        role = f"{role} - {next_role}"
                    elif not role:
                        role = next_role

                    current["role"] = role
                    current["header"] = f"{role} | {current.get('company', '')}".strip(" |")
                    current["bullets"] = list(nxt.get("bullets") or [])
                    current["skills_inferred"] = self._infer_skills_from_text(" ".join(current["bullets"]))

                    merged.append(current)
                    i += 2
                    continue

            merged.append(current)
            i += 1

        return merged

    def _normalize_llm_education(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for item in entries:
            degree = str(item.get("degree") or "").strip()
            institution = str(item.get("institution") or "").strip()
            start_date = str(item.get("start_date") or "").strip()
            end_date = str(item.get("end_date") or "").strip()
            grade = str(item.get("grade") or "").strip()

            if not (degree or institution or start_date or end_date or grade):
                continue

            year_parts = [part for part in [start_date, end_date] if part]
            year = "-".join(year_parts) if year_parts else None

            text_parts = [part for part in [institution, degree, year, grade] if part]
            output.append(
                {
                    "text": " | ".join(text_parts),
                    "degree": degree or None,
                    "institution": institution or None,
                    "year": year,
                    "start_date": start_date or None,
                    "end_date": end_date or None,
                    "grade": grade or None,
                }
            )
        return output

    def _normalize_llm_projects(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for item in entries:
            normalized = normalize_project_entry(
                {
                    "title": item.get("title") or item.get("project_name"),
                    "organization": item.get("organization") or item.get("client"),
                    "tools": item.get("tools") or item.get("technologies", []),
                    "bullets": item.get("bullets") or item.get("description", []),
                }
            )
            if normalized:
                output.append(normalized)
        return output

    @staticmethod
    def _normalize_llm_certifications(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for item in entries:
            normalized = normalize_certification_entry(
                {
                    "name": item.get("name"),
                    "issuer": item.get("issuer"),
                    "year": item.get("year"),
                    "credential_id": item.get("credential_id"),
                }
            )
            if normalized:
                output.append(normalized)
        return output

    # ── education ─────────────────────────────────────────────────────────

    def _extract_education(self, edu_lines: List[TokenLine]) -> List[Dict[str, Any]]:
        if not edu_lines:
            return []

        entries: List[Dict[str, Any]] = []
        current_block: list[str] = []

        for line in edu_lines:
            text = line.text.strip()
            if not text:
                continue

            lowered = text.lower()
            inst_keywords = {"university", "institute", "school", "college", "academy", "iit", "iim"}
            is_inst = any(kw in lowered for kw in inst_keywords)

            # Start new block at institution keyword if we already have content
            if is_inst and current_block:
                entries.append(self._parse_edu_block(current_block))
                current_block = []

            current_block.append(text)

        if current_block:
            entries.append(self._parse_edu_block(current_block))

        return [e for e in entries if e.get("degree") or e.get("institution") or e.get("year")]

    @staticmethod
    def _parse_edu_block(lines: list[str]) -> Dict[str, Any]:
        institution = ""
        degree = ""
        year = ""
        cleaned_lines = [str(line).strip() for line in lines if str(line).strip()]
        full = " ".join(cleaned_lines)

        # Year extraction
        date_ranges = DATE_RANGE_RE.findall(full)
        if date_ranges:
            year = f"{date_ranges[0][0]}-{date_ranges[0][1]}"
        else:
            month_ranges = MONTH_RANGE_RE.findall(full)
            if month_ranges:
                years_from_months = YEAR_RE.findall(month_ranges[0])
                if len(years_from_months) >= 2:
                    year = f"{years_from_months[0]}-{years_from_months[-1]}"

        if not year:
            year_matches = YEAR_RE.findall(full)
            if year_matches:
                year = year_matches[-1]

        def _strip_date_and_score_tokens(value: str) -> str:
            cleaned = str(value or "")
            cleaned = re.sub(MONTH_RANGE_RE, "", cleaned)
            cleaned = re.sub(DATE_RANGE_RE, "", cleaned)
            cleaned = re.sub(r"\b(19\d{2}|20\d{2})\b", "", cleaned)
            cleaned = re.sub(r"\b(?:cgpa|gpa|percentage)\b\s*[:\-]?\s*[\d./%]+", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*/\s*10\b", "", cleaned)
            cleaned = re.sub(r"\b\d+(?:\.\d+)?%\b", "", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned)
            return cleaned.strip(" ,|-")

        def _looks_degree_text(value: str) -> bool:
            lowered = value.lower()
            if any(dt in lowered for dt in DEGREE_TOKENS):
                return True
            if "secondary education" in lowered or "senior secondary" in lowered or "higher secondary" in lowered:
                return True
            return bool(re.search(r"\b(class\s*(?:x|xi|xii|10|11|12)|10th|12th|hsc|ssc)\b", lowered))

        def _looks_location_only(value: str) -> bool:
            # Short city/state fragments are common between institution and degree lines.
            # Avoid assigning these as degree text.
            if _looks_degree_text(value):
                return False
            if re.search(r"\d", value):
                return False
            words = value.split()
            return 1 <= len(words) <= 4 and all(any(ch.isalpha() for ch in w) for w in words)

        info_lines = [_strip_date_and_score_tokens(line) for line in cleaned_lines]
        info_lines = [line for line in info_lines if line]

        # Parse delimiter-heavy lines first, e.g. "B.Tech ... | LNCTS, Bhopal".
        for line in info_lines:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 2:
                continue

            for part in parts:
                lowered_part = part.lower()
                inst_kw = {"university", "institute", "school", "college", "academy", "iit", "iim"}
                if not institution and any(kw in lowered_part for kw in inst_kw):
                    institution = part
                if not degree and _looks_degree_text(part):
                    degree = part

            # If institution keyword is absent (e.g., "LNCTS, Bhopal"),
            # use the non-degree side of the delimiter as institution fallback.
            if not institution:
                for part in parts:
                    if part == degree:
                        continue
                    if _looks_degree_text(part) or not _strip_date_and_score_tokens(part):
                        continue
                    institution = part
                    break

        # Then scan complete lines for explicit institution/degree signals.
        for line in info_lines:
            lowered = line.lower()
            inst_kw = {"university", "institute", "school", "college", "academy", "iit", "iim"}
            if not institution and any(kw in lowered for kw in inst_kw):
                institution = line
            if not degree and _looks_degree_text(line):
                degree = line

        # Fallback institution assignment from informative lines.
        if not institution:
            for line in info_lines:
                if line == degree:
                    continue
                if not _looks_location_only(line):
                    institution = line
                    break

        # Fallback degree assignment; avoid location-only fragments.
        if not degree:
            for line in info_lines:
                if line == institution:
                    continue
                if _looks_location_only(line):
                    continue
                degree = line
                break

        text_parts = [p for p in [institution, degree, year] if p]
        return {
            "text": " | ".join(text_parts) if text_parts else " ".join(lines),
            "degree": degree or None,
            "institution": institution or None,
            "year": year or None,
        }

    # ── projects ──────────────────────────────────────────────────────────

    def _extract_projects(
        self, proj_lines: List[TokenLine], all_links: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        del all_links
        return parse_project_section_lines([line.text for line in proj_lines])

    # ── certifications ────────────────────────────────────────────────────

    @staticmethod
    def _extract_certifications(sections_text: Dict[str, str]) -> List[Dict[str, Any]]:
        return parse_certification_lines(str(sections_text.get("certifications", "") or "").splitlines())

    # ── keywords ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(text: str, max_items: int = 25) -> List[str]:
        try:
            import importlib
            sklearn_text = importlib.import_module("sklearn.feature_extraction.text")
            vectorizer_cls = getattr(sklearn_text, "TfidfVectorizer")
            vectorizer = vectorizer_cls(stop_words="english", ngram_range=(1, 2), max_features=256)
            matrix = vectorizer.fit_transform([text])
            feature_names = vectorizer.get_feature_names_out()
            scores = matrix.toarray()[0]
            ranked = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)
            return [t for t, s in ranked if s > 0][:max_items]
        except Exception:
            from collections import Counter
            tokens = re.findall(r"[A-Za-z][A-Za-z+.#-]{2,}", text.lower())
            stopwords = {"and", "with", "from", "that", "this", "have", "will", "for", "the", "you", "are"}
            filtered = [t for t in tokens if t not in stopwords]
            return [w for w, _ in Counter(filtered).most_common(max_items)]

    # ── total experience years ────────────────────────────────────────────

    @staticmethod
    def _estimate_total_years(text: str) -> float:
        lines = [clean_text_line(line) for line in str(text or "").splitlines() if clean_text_line(line)]
        if not lines:
            return 0.0
        parser = ExperienceParser()
        token_lines = [
            TokenLine(
                tokens=[
                    Token(
                        text=line,
                        bbox=(0.0, float(idx * 12), 500.0, float(idx * 12 + 10)),
                        font_size=11.0,
                        page=0,
                    )
                ],
                page=0,
            )
            for idx, line in enumerate(lines)
        ]
        normalized = normalize_experience_entries(
            [
                {
                    "role": entry.get("job_title"),
                    "company": entry.get("company"),
                    "location": entry.get("location"),
                    "start_date": entry.get("start_date"),
                    "end_date": entry.get("end_date"),
                    "duration": entry.get("date_string"),
                    "bullets": entry.get("description", []),
                }
                for entry in parser.parse(token_lines)
            ]
        )
        return float(summarize_total_experience(normalized).get("total_experience_years_float", 0.0))
