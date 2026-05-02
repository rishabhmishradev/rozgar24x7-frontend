"""Section-wise LLM field extraction for resume parsing.

This module parses only field-level content after deterministic section segmentation.
It intentionally does NOT perform section detection, layout understanding, or full-resume prompts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, cast

from app.llm_engine.base_client import BaseLLMClient
from app.llm_engine.claude_client import ClaudeSonnetClient
from app.llm_engine.gemini_client import GeminiAPIClient
from app.llm_engine.json_utils import extract_json_object
from app.parsing.structured_utils import normalize_certification_entry, normalize_project_entry

logger = logging.getLogger(__name__)

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
DATE_PATTERN_RE = re.compile(
    r"(?:"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{2,4}"
    r"|\d{1,2}/\d{2,4}"
    r"|(?:19|20)\d{2}"
    r")\s*(?:-|to|–|—)\s*(?:present|current|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{2,4}|"
    r"\d{1,2}/\d{2,4}|(?:19|20)\d{2})",
    re.IGNORECASE,
)
BULLET_PREFIX_RE = re.compile(r"^\s*[•●▪▸\-*]+\s*")
SPLIT_LINES_RE = re.compile(r"\r?\n")
YEAR_TOKEN_RE = re.compile(r"\b(?:19|20)\d{2}\b")
ROLE_TOKEN_RE = re.compile(
    r"\b(?:engineer|developer|analyst|manager|consultant|architect|intern|lead|director|officer|vice president)\b",
    re.IGNORECASE,
)
COMPANY_TOKEN_RE = re.compile(
    r"\b(?:inc\.?|llc|ltd\.?|corp\.?|bank|technologies|technology|systems|solutions|university|pvt\.?|group)\b",
    re.IGNORECASE,
)
DATE_VALUE_RE = re.compile(
    r"^(?:present|current|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{2,4}|\d{1,2}/\d{2,4}|(?:19|20)\d{2})$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SectionParseStatus:
    section: str
    valid: bool
    attempts: int
    issues: List[str]
    schema_mode_used: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section": self.section,
            "valid": self.valid,
            "attempts": self.attempts,
            "issues": list(self.issues),
            "schema_mode_used": self.schema_mode_used,
        }


class ResumeSectionLLMParser:
    """LLM-backed section parser with strict validation and retries."""

    TARGET_SECTIONS = ("experience", "education", "projects", "certifications")

    @staticmethod
    def _resolve_parsing_api_key() -> Optional[str]:
        """Resolve dedicated parsing-layer Anthropic API key when configured."""
        raw = os.getenv("PARSING_ANTHROPIC_API_KEY") or ""
        key = str(raw).strip().strip('"').strip("'")
        return key or None

    @staticmethod
    def _resolve_parsing_model_name() -> Optional[str]:
        """Resolve dedicated parsing-layer Claude model override when configured."""
        raw = os.getenv("PARSING_CLAUDE_MODEL") or ""
        model_name = str(raw).strip().strip('"').strip("'")
        return model_name or None

    def __init__(
        self,
        client: BaseLLMClient | None = None,
        max_retries: int = 3,
    ) -> None:
        self.max_retries = max(1, int(max_retries))
        self.client: BaseLLMClient | None = client
        self.enabled = True

        if self.client is None:
            try:
                # Parsing layer can use dedicated Anthropic credentials while other app paths keep their own defaults.
                self.client = ClaudeSonnetClient(
                    api_key=self._resolve_parsing_api_key(),
                    model_name=self._resolve_parsing_model_name(),
                )
            except Exception as exc:
                self.enabled = False
                logger.warning(
                    "LLM section parser disabled (Claude unavailable or unconfigured): %s",
                    exc,
                )

        self._set_deterministic_generation()

    def parse_sections(
        self,
        sections_text: Dict[str, str],
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, SectionParseStatus]]:
        parsed: Dict[str, List[Dict[str, Any]]] = {
            "experience": [],
            "education": [],
            "projects": [],
            "certifications": [],
        }
        statuses: Dict[str, SectionParseStatus] = {}

        if not self.enabled or self.client is None:
            for section in self.TARGET_SECTIONS:
                statuses[section] = SectionParseStatus(
                    section=section,
                    valid=False,
                    attempts=0,
                    issues=["llm_parser_disabled"],
                    schema_mode_used=False,
                )
            return parsed, statuses

        global_unavailable_issue: Optional[str] = None

        for section in self.TARGET_SECTIONS:
            if global_unavailable_issue:
                statuses[section] = SectionParseStatus(
                    section=section,
                    valid=False,
                    attempts=0,
                    issues=[f"llm_skipped_due_to_global_unavailable: {global_unavailable_issue}"],
                    schema_mode_used=False,
                )
                parsed[section] = []
                continue

            source = self._clean_source_text(sections_text.get(section, ""))
            expected_min = self._estimate_expected_min_count(section, source)
            entries, status = self._parse_section_with_retry(
                section=section,
                source_text=source,
                expected_min=expected_min,
            )
            parsed[section] = entries
            statuses[section] = status

            if (
                not status.valid
                and status.issues
                and any(self._is_fast_fail_text(issue) for issue in status.issues)
            ):
                global_unavailable_issue = status.issues[0]

        return parsed, statuses

    def _parse_section_with_retry(
        self,
        section: str,
        source_text: str,
        expected_min: int,
    ) -> Tuple[List[Dict[str, Any]], SectionParseStatus]:
        if not source_text.strip():
            return [], SectionParseStatus(
                section=section,
                valid=True,
                attempts=0,
                issues=[],
                schema_mode_used=False,
            )

        prior_issues: List[str] = []
        last_entries: List[Dict[str, Any]] = []
        used_schema_any = False
        attempts_made = 0

        for attempt in range(1, self.max_retries + 1):
            attempts_made = attempt
            strictness = attempt - 1
            prompt = self._build_prompt(
                section=section,
                section_text=source_text,
                expected_min=expected_min,
                strictness=strictness,
                previous_issues=prior_issues,
            )

            logger.info(
                "LLM section input [%s] attempt=%d chars=%d",
                section,
                attempt,
                len(source_text),
            )

            try:
                raw_output, payload, used_schema = self._invoke_llm(prompt=prompt, section=section)
            except Exception as exc:
                prior_issues = [f"llm_call_failed: {exc}"]
                logger.warning("LLM call failed for section=%s attempt=%d: %s", section, attempt, exc)
                if self._should_fast_fail_error(exc):
                    # Further retries are unlikely to succeed within the same window.
                    break
                continue

            used_schema_any = used_schema_any or used_schema
            logger.info(
                "LLM raw output [%s] attempt=%d: %s",
                section,
                attempt,
                (raw_output or "")[:1200],
            )

            section_items = self._extract_section_items(payload, section)
            normalized, issues = self._normalize_and_validate(
                section=section,
                items=section_items,
                source_text=source_text,
                expected_min=expected_min,
            )
            last_entries = normalized

            logger.info(
                "LLM validation [%s] attempt=%d valid=%s entries=%d issues=%s",
                section,
                attempt,
                not issues,
                len(normalized),
                issues,
            )

            if not issues:
                return normalized, SectionParseStatus(
                    section=section,
                    valid=True,
                    attempts=attempt,
                    issues=[],
                    schema_mode_used=used_schema_any,
                )

            prior_issues = issues

        return last_entries, SectionParseStatus(
            section=section,
            valid=False,
            attempts=attempts_made,
            issues=prior_issues or ["validation_failed"],
            schema_mode_used=used_schema_any,
        )

    @staticmethod
    def _should_fast_fail_error(exc: Exception) -> bool:
        return ResumeSectionLLMParser._is_fast_fail_text(str(exc or ""))

    @staticmethod
    def _is_fast_fail_text(text: str) -> bool:
        lowered = str(text or "").lower()
        quota_or_rate_limited = any(
            token in lowered
            for token in (
                "resource_exhausted",
                "quota exceeded",
                "rate limit",
                "429",
                "retryinfo",
            )
        )
        service_unavailable = any(
            token in lowered
            for token in (
                "503",
                "unavailable",
                "high demand",
                "temporarily unavailable",
            )
        )
        return quota_or_rate_limited or service_unavailable

    def _set_deterministic_generation(self) -> None:
        """Force deterministic generation settings where supported."""
        if self.client is None:
            return

        config = getattr(self.client, "generation_config", None)
        if isinstance(config, dict):
            config["temperature"] = 0
            if isinstance(self.client, GeminiAPIClient):
                config["top_p"] = 1
                config["top_k"] = 1
                config["candidate_count"] = 1

    def _invoke_llm(self, prompt: str, section: str) -> Tuple[str, Dict[str, Any], bool]:
        if self.client is None:
            raise RuntimeError("LLM client unavailable")

        # Use schema-based JSON generation when Gemini native client is available.
        if isinstance(self.client, GeminiAPIClient):
            schema_payload = self._invoke_gemini_json_mode(prompt, section)
            if schema_payload is not None:
                raw_text, payload = schema_payload
                return raw_text, payload, True

        if isinstance(self.client, ClaudeSonnetClient):
            parsed = self.client.analyze_resume(
                prompt,
                required_keys={section},
                defaults={section: []},
                key_types={section: list},
            )
            return json.dumps(parsed, ensure_ascii=True), parsed, False

        generator = getattr(self.client, "generate_text", None)
        if callable(generator):
            raw = str(generator(prompt)).strip()
            payload = extract_json_object(raw) or {}
            return raw, payload, False

        parsed = self.client.analyze_resume(
            prompt,
            required_keys={section},
            defaults={section: []},
            key_types={section: list},
        )
        return json.dumps(parsed, ensure_ascii=True), parsed, False

    def _invoke_gemini_json_mode(self, prompt: str, section: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Try Gemini response-schema mode and return parsed payload when successful."""
        if not isinstance(self.client, GeminiAPIClient):
            return None

        schema = self._json_schema_for_section(section)
        generation_config = getattr(self.client, "generation_config", None)
        if not isinstance(generation_config, dict):
            return None

        config_map = cast(Dict[str, Any], generation_config)

        original: Dict[str, Any] = dict(config_map)
        try:
            config_map.update(
                {
                    "temperature": 0,
                    "top_p": 1,
                    "top_k": 1,
                    "candidate_count": 1,
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                }
            )
            response = self.client.client.models.generate_content(
                model=self.client.model_name,
                contents=prompt,
                config=cast(Any, config_map),
            )
            raw_text = self._extract_model_response_text(response).strip()
            payload = extract_json_object(raw_text)
            if payload is None:
                return None
            return raw_text, payload
        except Exception as exc:
            logger.debug("Gemini schema mode failed for section=%s: %s", section, exc)
            return None
        finally:
            config_map.clear()
            config_map.update(original)

    @staticmethod
    def _extract_model_response_text(response: Any) -> str:
        """Collect text from Gemini response candidates without private client helpers."""
        text_chunks: List[str] = []

        direct_text = getattr(response, "text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return ""

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None)
            if not parts:
                continue
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_chunks.append(str(part_text))

        return "\n".join(text_chunks)

    @staticmethod
    def _extract_section_items(payload: Any, section: str) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        payload_map = cast(Dict[str, Any], payload)

        raw_items: Any = []
        if section in payload_map:
            raw_items = payload_map.get(section, [])
        elif "data" in payload_map and isinstance(payload_map.get("data"), dict):
            raw_items = cast(Dict[str, Any], payload_map["data"]).get(section, [])
        else:
            raw_items = []

        if isinstance(raw_items, list):
            output: List[Dict[str, Any]] = []
            for item in cast(List[Any], raw_items):
                if isinstance(item, dict):
                    output.append(cast(Dict[str, Any], item))
            return output
        return []

    def _normalize_and_validate(
        self,
        section: str,
        items: List[Dict[str, Any]],
        source_text: str,
        expected_min: int,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        if section == "experience":
            normalized = self._normalize_experience(items, source_text)
            issues = self._validate_experience(normalized, expected_min)
            return normalized, issues

        if section == "education":
            normalized = self._normalize_education(items, source_text)
            issues = self._validate_generic(section, normalized, expected_min)
            return normalized, issues

        if section == "projects":
            normalized = self._normalize_projects(items, source_text)
            issues = self._validate_generic(section, normalized, expected_min)
            return normalized, issues

        if section == "certifications":
            normalized = self._normalize_certifications(items, source_text)
            issues = self._validate_generic(section, normalized, expected_min)
            return normalized, issues

        return [], [f"unknown_section:{section}"]

    def _normalize_experience(self, items: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in items:
            job_title = self._sanitize_optional_text(item.get("job_title"), source_text)
            company = self._sanitize_optional_text(item.get("company"), source_text)
            start_date = self._sanitize_date(item.get("start_date"))
            end_date = self._sanitize_date(item.get("end_date"))
            description = self._normalize_bullet_list(item.get("description"), source_text)

            entry: Dict[str, Any] = {
                "job_title": job_title,
                "company": company,
                "start_date": start_date,
                "end_date": end_date,
                "description": description,
            }
            if self._is_null_only_entry(entry):
                continue
            normalized.append(entry)

        return normalized

    def _normalize_education(self, items: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in items:
            entry: Dict[str, Any] = {
                "degree": self._sanitize_optional_text(item.get("degree"), source_text),
                "institution": self._sanitize_optional_text(item.get("institution"), source_text),
                "start_date": self._sanitize_date(item.get("start_date")),
                "end_date": self._sanitize_date(item.get("end_date")),
                "grade": self._sanitize_optional_text(item.get("grade"), source_text),
            }
            if self._is_null_only_entry(entry):
                continue
            normalized.append(entry)
        return normalized

    def _normalize_projects(self, items: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in items:
            project_name = self._sanitize_optional_text(
                item.get("project_name", item.get("title")),
                source_text,
            )
            organization = self._sanitize_optional_text(item.get("organization"), source_text)
            technologies = self._normalize_technology_list(item.get("technologies", item.get("tools")), source_text)
            description = self._normalize_description_text(item.get("description", item.get("bullets")), source_text)

            normalized_entry = normalize_project_entry(
                {
                    "title": project_name,
                    "organization": organization,
                    "tools": technologies,
                    "bullets": description,
                }
            )
            entry: Dict[str, Any] = {
                "project_name": project_name,
                "technologies": technologies,
                "description": description,
            }
            if normalized_entry:
                entry.update(
                    {
                        "title": normalized_entry.get("title"),
                        "organization": normalized_entry.get("organization"),
                        "tools": normalized_entry.get("tools", []),
                        "bullets": normalized_entry.get("bullets", []),
                    }
                )
            if self._is_null_only_entry(entry):
                continue
            normalized.append(entry)
        return normalized

    def _normalize_certifications(self, items: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in items:
            normalized_entry = normalize_certification_entry(
                {
                    "name": self._sanitize_optional_text(item.get("name"), source_text),
                    "issuer": self._sanitize_optional_text(item.get("issuer"), source_text),
                    "year": self._sanitize_optional_text(item.get("year"), source_text),
                    "credential_id": self._sanitize_optional_text(item.get("credential_id"), source_text),
                }
            )
            entry: Dict[str, Any] = normalized_entry or {
                "name": self._sanitize_optional_text(item.get("name"), source_text),
                "issuer": self._sanitize_optional_text(item.get("issuer"), source_text),
                "year": self._sanitize_optional_text(item.get("year"), source_text),
                "credential_id": self._sanitize_optional_text(item.get("credential_id"), source_text),
            }
            if self._is_null_only_entry(entry):
                continue
            normalized.append(entry)
        return normalized

    def _validate_experience(self, entries: List[Dict[str, Any]], expected_min: int) -> List[str]:
        issues = self._validate_generic("experience", entries, expected_min)
        if expected_min > 0 and len(entries) < expected_min:
            issues.append(f"experience_count_too_low:{len(entries)}<{expected_min}")
        for idx, entry in enumerate(entries):
            if not isinstance(entry.get("description"), list):
                issues.append(f"experience[{idx}].description_not_list")
        issues.extend(self._detect_merged_experience_entries(entries))
        return list(dict.fromkeys(issues))

    def _detect_merged_experience_entries(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Detect likely multi-job merges inside a single experience entry."""
        issues: List[str] = []

        for idx, entry in enumerate(entries):
            description = entry.get("description", [])
            if not isinstance(description, list):
                continue

            desc_lines = [str(line or "").strip() for line in cast(List[Any], description) if str(line or "").strip()]
            if not desc_lines:
                continue

            embedded_date_ranges = 0
            embedded_year_only = 0
            embedded_headers = 0
            for line in desc_lines:
                has_range = bool(DATE_PATTERN_RE.search(line))
                has_year = bool(YEAR_TOKEN_RE.search(line))
                if has_range:
                    embedded_date_ranges += 1
                if has_year and not has_range:
                    embedded_year_only += 1
                if self._looks_like_embedded_job_header(line):
                    embedded_headers += 1

            if embedded_headers >= 1 and (embedded_date_ranges >= 1 or embedded_year_only >= 1):
                issues.append(f"experience[{idx}].possible_merged_jobs_in_description")
            elif embedded_headers >= 2:
                issues.append(f"experience[{idx}].multiple_embedded_job_headers")
            elif embedded_date_ranges >= 2:
                issues.append(f"experience[{idx}].multiple_embedded_date_ranges")

        return issues

    @staticmethod
    def _looks_like_embedded_job_header(text: str) -> bool:
        line = str(text or "").strip()
        if not line:
            return False

        has_role = bool(ROLE_TOKEN_RE.search(line))
        has_company = bool(COMPANY_TOKEN_RE.search(line) or "|" in line)
        has_time = bool(DATE_PATTERN_RE.search(line) or YEAR_TOKEN_RE.search(line))

        if line.count("|") >= 2 and (has_role or has_company):
            return True
        return has_role and has_company and has_time

    def _validate_generic(self, section: str, entries: List[Dict[str, Any]], expected_min: int) -> List[str]:
        issues: List[str] = []

        if expected_min > 1 and len(entries) < max(1, expected_min - 1):
            issues.append(f"{section}_count_too_low:{len(entries)}<{expected_min}")

        if any(self._is_null_only_entry(entry) for entry in entries):
            issues.append(f"{section}_contains_null_only_entries")

        required = self._required_fields(section)
        for idx, entry in enumerate(entries):
            for field in required:
                if field not in entry:
                    issues.append(f"{section}[{idx}].missing_field:{field}")

        return issues

    @staticmethod
    def _required_fields(section: str) -> List[str]:
        if section == "experience":
            return ["job_title", "company", "start_date", "end_date", "description"]
        if section == "education":
            return ["degree", "institution", "start_date", "end_date", "grade"]
        if section == "projects":
            return ["project_name", "technologies", "description"]
        if section == "certifications":
            return ["name", "issuer", "year"]
        return []

    @staticmethod
    def _is_null_only_entry(entry: Dict[str, Any]) -> bool:
        for value in entry.values():
            if isinstance(value, list) and any(str(v).strip() for v in cast(List[Any], value)):
                return False
            if isinstance(value, str) and value.strip():
                return False
            if value not in (None, "", []):
                return False
        return True

    def _build_prompt(
        self,
        section: str,
        section_text: str,
        expected_min: int,
        strictness: int,
        previous_issues: List[str],
    ) -> str:
        section_upper = section.upper()
        issues_text = "\n".join(f"- {issue}" for issue in previous_issues) if previous_issues else "- none"

        strict_addendum = ""
        if strictness > 0:
            strict_addendum = (
                "\nAdditional strict retry constraints:\n"
                "- Fix all prior validation issues listed below.\n"
                "- Return exactly one JSON object and no extra text.\n"
                "- Ensure every extracted item is explicit in source text.\n"
                "- Do not collapse multiple entries into one.\n"
            )

        schema_example = self._schema_example(section)

        return (
            "You are a strict resume information extraction engine.\n"
            f"Target section: {section_upper}\n"
            "Global hard rules:\n"
            "- Extract only facts explicitly present in provided section text.\n"
            "- Never hallucinate or infer missing values.\n"
            "- Never merge multiple entries into one.\n"
            "- Preserve original entry order.\n"
            "- If a field is missing, return null.\n"
            "- Output must be valid JSON only (no markdown or commentary).\n"
            f"- The section likely contains at least {expected_min} entries when text supports it.\n"
            f"{strict_addendum}"
            "Prior validation issues:\n"
            f"{issues_text}\n\n"
            "Return exactly this JSON shape:\n"
            f"{schema_example}\n\n"
            "Section text to parse:\n"
            "<SECTION_TEXT>\n"
            f"{section_text}\n"
            "</SECTION_TEXT>\n"
        )

    @staticmethod
    def _schema_example(section: str) -> str:
        if section == "experience":
            return (
                '{"experience":[{"job_title":null,"company":null,'
                '"start_date":null,"end_date":null,"description":[]}]}'
            )
        if section == "education":
            return (
                '{"education":[{"degree":null,"institution":null,'
                '"start_date":null,"end_date":null,"grade":null}]}'
            )
        if section == "projects":
            return (
                '{"projects":[{"project_name":null,"technologies":[],'
                '"description":null}]}'
            )
        return '{"certifications":[{"name":null,"issuer":null,"year":null}]}'

    @staticmethod
    def _json_schema_for_section(section: str) -> Dict[str, Any]:
        if section == "experience":
            item: Dict[str, Any] = {
                "type": "object",
                "properties": {
                    "job_title": {"type": ["string", "null"]},
                    "company": {"type": ["string", "null"]},
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "description": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["job_title", "company", "start_date", "end_date", "description"],
            }
            return {
                "type": "object",
                "properties": {"experience": {"type": "array", "items": item}},
                "required": ["experience"],
            }

        if section == "education":
            item: Dict[str, Any] = {
                "type": "object",
                "properties": {
                    "degree": {"type": ["string", "null"]},
                    "institution": {"type": ["string", "null"]},
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "grade": {"type": ["string", "null"]},
                },
                "required": ["degree", "institution", "start_date", "end_date", "grade"],
            }
            return {
                "type": "object",
                "properties": {"education": {"type": "array", "items": item}},
                "required": ["education"],
            }

        if section == "projects":
            item: Dict[str, Any] = {
                "type": "object",
                "properties": {
                    "project_name": {"type": ["string", "null"]},
                    "technologies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": {"type": ["string", "null"]},
                },
                "required": ["project_name", "technologies", "description"],
            }
            return {
                "type": "object",
                "properties": {"projects": {"type": "array", "items": item}},
                "required": ["projects"],
            }

        item: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "issuer": {"type": ["string", "null"]},
                "year": {"type": ["string", "null"]},
            },
            "required": ["name", "issuer", "year"],
        }
        return {
            "type": "object",
            "properties": {"certifications": {"type": "array", "items": item}},
            "required": ["certifications"],
        }

    @staticmethod
    def _clean_source_text(text: str) -> str:
        cleaned = ZERO_WIDTH_RE.sub("", str(text or ""))
        return cleaned.strip()

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _token_set(text: str) -> set[str]:
        return {tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 1}

    @classmethod
    def _contains_source_span(cls, candidate: str, source_text: str) -> bool:
        left = cls._normalize_spaces(candidate).lower()
        right = cls._normalize_spaces(source_text).lower()
        if not left or not right:
            return False

        if left in right:
            return True

        # Secondary normalized check strips punctuation differences but still requires contiguous span.
        left_compact = re.sub(r"[^a-z0-9]+", " ", left).strip()
        right_compact = re.sub(r"[^a-z0-9]+", " ", right).strip()
        if not left_compact or not right_compact:
            return False
        return left_compact in right_compact

    def _sanitize_optional_text(self, value: Any, source_text: str) -> Optional[str]:
        text = self._normalize_spaces(value)
        if not text:
            return None

        if self._contains_source_span(text, source_text):
            return text

        # Hallucinated field values are nulled instead of propagated.
        return None

    @staticmethod
    def _sanitize_date(value: Any) -> Optional[str]:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return None
        return text if DATE_VALUE_RE.match(text) else None

    def _normalize_bullet_list(self, value: Any, source_text: str) -> List[str]:
        lines: List[str] = []

        if isinstance(value, list):
            for item in cast(List[Any], value):
                text = self._normalize_spaces(item)
                if text:
                    lines.append(BULLET_PREFIX_RE.sub("", text).strip())
        elif isinstance(value, str):
            for raw in SPLIT_LINES_RE.split(value):
                text = self._normalize_spaces(raw)
                if text:
                    lines.append(BULLET_PREFIX_RE.sub("", text).strip())

        deduped: List[str] = []
        seen: set[str] = set()

        for line in lines:
            key = line.lower()
            if not line or key in seen:
                continue
            if not self._contains_source_span(line, source_text):
                continue
            seen.add(key)
            deduped.append(line)

        return deduped

    def _normalize_technology_list(self, value: Any, source_text: str) -> List[str]:
        items: List[str] = []

        if isinstance(value, list):
            items = [self._normalize_spaces(v) for v in cast(List[Any], value)]
        elif isinstance(value, str):
            chunks = re.split(r"[,|/;]", value)
            items = [self._normalize_spaces(chunk) for chunk in chunks]

        output: List[str] = []
        seen: set[str] = set()

        for item in items:
            if not item:
                continue
            token_key = item.lower()
            if token_key in seen:
                continue
            if not self._contains_source_span(item, source_text):
                continue
            seen.add(token_key)
            output.append(item)

        return output

    def _normalize_description_text(self, value: Any, source_text: str) -> Optional[str]:
        if isinstance(value, list):
            bullets = self._normalize_bullet_list(value, source_text)
            if not bullets:
                return None
            return "\n".join(bullets)

        text = self._normalize_spaces(value)
        if not text:
            return None

        if self._contains_source_span(text, source_text):
            return text

        return None

    def _estimate_expected_min_count(self, section: str, source_text: str) -> int:
        if not source_text.strip():
            return 0

        lines = [line.strip() for line in SPLIT_LINES_RE.split(source_text) if line.strip()]
        if not lines:
            return 0

        if section == "experience":
            date_lines = sum(1 for line in lines if DATE_PATTERN_RE.search(line))
            header_like = sum(
                1
                for line in lines
                if ("|" in line or " at " in line.lower())
                and not BULLET_PREFIX_RE.match(line)
            )
            estimate = max(date_lines, min(header_like, 8))
            if estimate == 0:
                estimate = 1
            return min(estimate, 8)

        if section == "education":
            institution_like = sum(
                1
                for line in lines
                if any(token in line.lower() for token in ("university", "institute", "college", "school"))
            )
            return max(1, institution_like) if lines else 0

        if section == "projects":
            project_like = sum(1 for line in lines if "|" in line or not BULLET_PREFIX_RE.match(line))
            return max(1, min(project_like, 6))

        cert_like = sum(1 for line in lines if BULLET_PREFIX_RE.match(line) or "cert" in line.lower())
        return max(1, min(cert_like, 6))
