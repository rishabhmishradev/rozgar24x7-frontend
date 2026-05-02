"""FastAPI API layer for frontend integration.

This module exposes versioned HTTP endpoints while delegating to existing
parsing, intelligence, and LLM services without changing core business logic.
"""

from __future__ import annotations

import base64
from datetime import datetime
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.intelligence.ats_engine import compute_ats_score, compute_resume_only_score
from app.intelligence.context_enrichment import enrich_jd_context, enrich_resume_context
from app.intelligence.experience_alignment import align_experience
from app.intelligence.resume_analysis_service import ResumeAnalysisService
from app.intelligence.skill_alignment import align_skills
from app.intelligence.utils import flatten_experience_bullets
from app.llm_engine.llm_analysis_engine import LLMAnalysisEngine
from app.parsing.jd_parser import parse_job_description
from app.parsing.resume_parser import ParsingError, ResumeParser, SectionError
from app.parsing.text_extractor import ExtractionError, UnsupportedFileTypeError
from app.storage.ats_submission_store import AtsSubmissionStore
from app.storage.enhancement_submission_store import EnhancementSubmissionStore


Severity = Literal["Critical", "Major", "Minor"]
AnalyzeMode = Literal["jd", "resume_only"]
RewriteMode = Literal["ats_rewrite", "safe_fix"]

API_VERSION = "v1"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".rtf", ".md"}
DEFAULT_ATS_MAX_UPLOAD_MB = 10
PARSER_SECTION_LLM_ENABLED = False
REPO_JD_DIR = Path(__file__).resolve().parent / "JD"

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    version: str


class ParseJDRequest(BaseModel):
    jd_text: str = Field(default="", description="Raw job description text")
    jd_texts: list[str] = Field(default_factory=list, description="Optional additional raw JD texts")
    use_repo_jd_library: bool = Field(default=False, description="Include all .txt JD files from app/JD")


class ParseJDResponse(BaseModel):
    ok: bool
    jd_analysis: dict[str, Any]


class ParseResumeResponse(BaseModel):
    ok: bool
    filename: str
    resume_analysis: dict[str, Any]


class ImproveSubmitResponse(BaseModel):
    ok: bool
    candidate_id: str | None = None
    bucket_name: str | None = None
    object_key: str | None = None
    resume_link: str | None = None
    candidate_submitted_date: str | None = None


class BreakdownItem(BaseModel):
    id: str
    name: str
    score: int
    total: int
    desc: str


class IssueItem(BaseModel):
    severity: Severity
    text: str


class AtsAnalyzeResponse(BaseModel):
    ok: bool
    mode: AnalyzeMode
    target_role: str
    decision: str
    confidence: float
    score: int
    percentile: float | None = None
    reasons: list[str]
    fail_reasons: list[str]
    ats_score: int
    components: dict[str, Any]
    breakdown: list[BreakdownItem]
    issues: list[IssueItem]
    raw: dict[str, Any]
    resume_parse: dict[str, Any] = Field(default_factory=dict)


class FullAnalysisResponse(BaseModel):
    ok: bool
    result: dict[str, Any]


class GeneratedFileItem(BaseModel):
    format: Literal["txt", "pdf", "docx"]
    filename: str
    mime_type: str
    base64_data: str


class AtsFixResponse(BaseModel):
    ok: bool
    mode: AnalyzeMode
    rewrite_mode: RewriteMode
    target_role: str
    before_decision: str
    after_decision: str
    before_confidence: float
    after_confidence: float
    before_score: int
    after_score: int
    before_text: str
    optimized_text: str
    latex_source: str
    files: list[GeneratedFileItem]
    notes: list[str]
    resume_parse: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str


app = FastAPI(
    title="Resume Builder API",
    version="1.0.0",
    description="Versioned API wrappers for resume parsing and ATS analysis.",
)


def _frontend_origins() -> list[str]:
    raw = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UnsupportedFileTypeError)
async def unsupported_file_handler(_request: Any, exc: UnsupportedFileTypeError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ExtractionError)
async def extraction_handler(_request: Any, exc: ExtractionError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(SectionError)
async def section_handler(_request: Any, exc: SectionError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ParsingError)
async def parsing_handler(_request: Any, exc: ParsingError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def _validate_extension(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'. Allowed: {allowed}")
    return suffix


async def _write_upload_to_temp(upload: UploadFile, suffix: str) -> Path:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(data)
        return Path(temp.name)


def _percent(value: Any) -> int:
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return 0


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return cast(list[Any], value)
    return []


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _normalize_rewrite_mode(raw: str) -> RewriteMode:
    value = str(raw or "").strip().lower()
    if value in {"safe_fix", "safe", "edit", "edit_mode"}:
        return "safe_fix"
    return "ats_rewrite"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _decision_payload(ats_analysis: dict[str, Any]) -> tuple[str, float, list[str], list[str]]:
    decision = str(ats_analysis.get("decision", "")).strip().upper()
    if decision not in {"PASS", "BORDERLINE", "FAIL"}:
        score = _safe_float(ats_analysis.get("ats_score", 0.0), 0.0)
        if score >= 0.7:
            decision = "PASS"
        elif score >= 0.5:
            decision = "BORDERLINE"
        else:
            decision = "FAIL"

    confidence = _safe_float(ats_analysis.get("confidence", 0.0), 0.0)
    reasons = [str(item) for item in _coerce_list(ats_analysis.get("reasons")) if str(item).strip()]
    fail_reasons = [str(item) for item in _coerce_list(ats_analysis.get("fail_reasons")) if str(item).strip()]
    return decision, confidence, reasons, fail_reasons


def _score_payload(ats_analysis: dict[str, Any]) -> tuple[int, float | None]:
    score_raw = ats_analysis.get("score")
    if isinstance(score_raw, (int, float)):
        score = int(max(0, min(100, round(float(score_raw)))))
    else:
        score = _percent(ats_analysis.get("ats_score", 0.0))

    percentile_raw = ats_analysis.get("percentile")
    percentile: float | None = None
    if isinstance(percentile_raw, (int, float)):
        percentile = float(max(0.0, min(100.0, float(percentile_raw))))
    else:
        calibration = _coerce_dict(ats_analysis.get("calibration", {}))
        cal_percentile = calibration.get("percentile")
        if isinstance(cal_percentile, (int, float)):
            percentile = float(max(0.0, min(100.0, float(cal_percentile))))

    return score, percentile


def _build_resume_parse_diagnostics(resume_dict: dict[str, Any]) -> dict[str, Any]:
    """Build stable parser diagnostics payload for frontend and streamlit consumers."""
    metadata = _coerce_dict(resume_dict.get("metadata", {}))
    return {
        "pipeline": str(metadata.get("pipeline", "") or ""),
        "parsing_confidence": _safe_float(metadata.get("parsing_confidence", 0.0), 0.0),
        "completeness_score": _safe_float(metadata.get("completeness_score", 0.0), 0.0),
        "section_confidence": _safe_float(metadata.get("section_confidence", 0.0), 0.0),
        "section_confidence_detail": _coerce_dict(metadata.get("section_confidence_detail", {})),
        "llm_field_parse_status": _coerce_dict(metadata.get("llm_field_parse_status", {})),
    }


def _validate_jd_for_scoring(jd_data: dict[str, Any]) -> None:
    required = _coerce_list(jd_data.get("skills_required"))
    optional = _coerce_list(jd_data.get("skills_optional"))
    responsibilities = _coerce_list(jd_data.get("responsibilities"))
    warnings = _coerce_list(jd_data.get("parse_warnings"))

    if not required and not optional:
        warning_text = "; ".join(str(item) for item in warnings if str(item).strip())
        detail = "JD parsing did not extract any skills_required/skills_optional."
        if warning_text:
            detail = f"{detail} warnings={warning_text}"
        raise HTTPException(status_code=422, detail=detail)

    if not responsibilities:
        warning_text = "; ".join(str(item) for item in warnings if str(item).strip())
        detail = "JD parsing did not extract responsibilities."
        if warning_text:
            detail = f"{detail} warnings={warning_text}"
        raise HTTPException(status_code=422, detail=detail)


def _dedupe_strings(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _load_repo_jd_texts() -> list[str]:
    if not REPO_JD_DIR.exists() or not REPO_JD_DIR.is_dir():
        return []

    texts: list[str] = []
    for file_path in sorted(REPO_JD_DIR.glob("*.txt")):
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        if raw_text.strip():
            texts.append(raw_text)
    return texts


def _collect_jd_text_inputs(
    jd_text: str,
    jd_texts: list[str] | None = None,
    *,
    use_repo_jd_library: bool = False,
) -> list[str]:
    # Preserve original JD content exactly; only trim for non-empty checks and dedupe keys.
    inputs: list[str] = []
    seen: set[str] = set()

    def _push(raw: str) -> None:
        marker = str(raw or "").strip()
        if not marker:
            return
        key = marker.lower()
        if key in seen:
            return
        seen.add(key)
        inputs.append(raw)

    _push(jd_text)
    for entry in jd_texts or []:
        _push(str(entry))

    if use_repo_jd_library:
        for repo_jd_text in _load_repo_jd_texts():
            _push(repo_jd_text)

    return inputs


def _merge_jd_payloads(jd_text_inputs: list[str]) -> dict[str, Any]:
    if not jd_text_inputs:
        return {}

    all_required: list[str] = []
    all_optional: list[str] = []
    all_responsibilities: list[str] = []
    all_tools: list[str] = []
    all_intent_skills: list[str] = []
    all_intent_clusters: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    merged_importance: dict[str, float] = {}
    seniority_rank = {"unknown": 0, "junior": 1, "senior": 2, "lead": 3}
    merged_seniority = "unknown"

    for index, jd_text_value in enumerate(jd_text_inputs, start=1):
        parsed = parse_job_description(jd_text_value)

        required = [str(item) for item in _coerce_list(parsed.get("skills_required")) if str(item).strip()]
        optional = [str(item) for item in _coerce_list(parsed.get("skills_optional")) if str(item).strip()]
        responsibilities = [
            str(item)
            for item in _coerce_list(parsed.get("responsibilities"))
            if str(item).strip()
        ]
        tools = [str(item) for item in _coerce_list(parsed.get("tools")) if str(item).strip()]
        intent_skills = [
            str(item)
            for item in _coerce_list(parsed.get("skills_inferred_from_intent"))
            if str(item).strip()
        ]
        intent_clusters = [
            _coerce_dict(item)
            for item in _coerce_list(parsed.get("responsibility_intents"))
            if _coerce_dict(item)
        ]
        warnings = [str(item) for item in _coerce_list(parsed.get("parse_warnings")) if str(item).strip()]

        all_required.extend(required)
        all_optional.extend(optional)
        all_responsibilities.extend(responsibilities)
        all_tools.extend(tools)
        all_intent_skills.extend(intent_skills)
        all_intent_clusters.extend(intent_clusters)
        all_warnings.extend([f"jd_{index}: {warning}" for warning in warnings])

        importance_weights = _coerce_dict(parsed.get("importance_weights"))
        for skill, weight in importance_weights.items():
            skill_key = str(skill).strip().lower()
            if not skill_key:
                continue
            weight_value = _safe_float(weight, 0.0)
            if skill_key not in merged_importance or weight_value > merged_importance[skill_key]:
                merged_importance[skill_key] = weight_value

        current_seniority = str(parsed.get("seniority") or "unknown").strip().lower()
        if seniority_rank.get(current_seniority, 0) > seniority_rank.get(merged_seniority, 0):
            merged_seniority = current_seniority

    merged_required = _dedupe_strings(all_required)
    required_keys = {item.lower() for item in merged_required}
    merged_optional = [item for item in _dedupe_strings(all_optional) if item.lower() not in required_keys]
    merged_intent_skills = [
        item for item in _dedupe_strings(all_intent_skills) if item.lower() not in required_keys
    ]
    optional_keys = {item.lower() for item in merged_optional}
    for skill in merged_intent_skills:
        if skill.lower() not in optional_keys:
            merged_optional.append(skill)
            optional_keys.add(skill.lower())

    deduped_clusters: list[dict[str, Any]] = []
    seen_clusters: set[tuple[str, str]] = set()
    for row in all_intent_clusters:
        cluster_name = str(row.get("cluster", "")).strip().lower()
        intent_text = str(row.get("intent", "")).strip().lower()
        if not cluster_name and not intent_text:
            continue
        key = (cluster_name, intent_text)
        if key in seen_clusters:
            continue
        seen_clusters.add(key)
        deduped_clusters.append(row)

    return {
        "skills_required": merged_required,
        "skills_optional": merged_optional,
        "skills_inferred_from_intent": merged_intent_skills,
        "responsibility_intents": deduped_clusters,
        "parse_warnings": _dedupe_strings(all_warnings),
        "importance": merged_importance,
        "importance_weights": merged_importance,
        "responsibilities": _dedupe_strings(all_responsibilities),
        "tools": _dedupe_strings(all_tools),
        "seniority": merged_seniority,
        "raw": "\n\n".join(jd_text_inputs),
        "source_jd_count": len(jd_text_inputs),
        "source_jd_texts": jd_text_inputs,
    }


def _build_scoring_jd_context(
    jd_text: str,
    jd_texts: list[str] | None = None,
    *,
    use_repo_jd_library: bool = False,
) -> dict[str, Any] | None:
    jd_inputs = _collect_jd_text_inputs(
        jd_text,
        jd_texts,
        use_repo_jd_library=use_repo_jd_library,
    )
    if not jd_inputs:
        return None
    if len(jd_inputs) == 1:
        return parse_job_description(jd_inputs[0])
    return _merge_jd_payloads(jd_inputs)


def _derive_issues_from_ats(ats_analysis: dict[str, Any]) -> list[IssueItem]:
    issues: list[IssueItem] = []

    evidence = _coerce_dict(ats_analysis.get("evidence", {}))
    skill_alignment = _coerce_dict(evidence.get("skill_alignment", {}))

    missing = _coerce_list(skill_alignment.get("missing"))
    weak = _coerce_list(skill_alignment.get("weak"))

    for item in missing[:3]:
        row = _coerce_dict(item)
        skill = str(row.get("jd_skill", "")).strip()
        if not skill:
            continue
        issues.append(IssueItem(severity="Critical", text=f"Missing required skill evidence for '{skill}'."))

    for item in weak[:3]:
        row = _coerce_dict(item)
        skill = str(row.get("jd_skill", "")).strip()
        if not skill:
            continue
        issues.append(IssueItem(severity="Major", text=f"Weak experience evidence for '{skill}'."))

    rule_engine = _coerce_dict(ats_analysis.get("rule_engine", {}))
    violations = _coerce_list(rule_engine.get("critical_violations"))
    for violation in violations[:3]:
        issues.append(IssueItem(severity="Major", text=str(violation)))

    if not issues:
        issues.append(
            IssueItem(
                severity="Minor",
                text="No major ATS blockers detected. Improve keyword depth and quantified impact.",
            )
        )

    return issues


def _build_breakdown_items(ats_analysis: dict[str, Any]) -> list[BreakdownItem]:
    components = _coerce_dict(ats_analysis.get("components", {}))
    labels = {
        "skill_score": "Skill Match",
        "experience_score": "Experience Match",
        "impact_score": "Impact & Metrics",
        "keyword_score": "Keyword Match",
        "format_score": "Formatting",
        "language_quality_score": "Language Quality",
    }

    items: list[BreakdownItem] = []
    for key, label in labels.items():
        if key not in components:
            continue
        items.append(
            BreakdownItem(
                id=key,
                name=label,
                score=_percent(components.get(key, 0)),
                total=100,
                desc=f"Derived from {label.lower()} signals in the backend ATS engine.",
            )
        )
    return items


def _categorize_skills_for_generation(raw_skills: list[str]) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "programming_languages": [],
        "data_science": [],
        "data_visualization": [],
        "databases": [],
        "tools": [],
    }

    language_tokens = {
        "python", "java", "javascript", "typescript", "c", "c++", "cpp", "c/c++", "c#", "go", "rust", "sql", "pl/sql", "php", "r"
    }
    data_science_tokens = {
        "machine learning", "deep learning", "nlp", "statistics", "statistical", "regression",
        "classification", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch"
    }
    visualization_tokens = {
        "power bi", "tableau", "matplotlib", "seaborn", "plotly", "excel", "dashboard"
    }
    database_tokens = {
        "mysql", "postgresql", "postgres", "mongodb", "sqlite", "oracle", "sql server", "redshift"
    }

    for raw in raw_skills:
        skill = str(raw).strip()
        lowered = skill.lower()
        if not skill:
            continue
        if lowered in language_tokens:
            categories["programming_languages"].append(skill)
        elif any(token in lowered for token in data_science_tokens):
            categories["data_science"].append(skill)
        elif any(token in lowered for token in visualization_tokens):
            categories["data_visualization"].append(skill)
        elif any(token in lowered for token in database_tokens):
            categories["databases"].append(skill)
        else:
            categories["tools"].append(skill)

    for key, values in categories.items():
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            marker = value.lower().strip()
            if not marker or marker in seen:
                continue
            seen.add(marker)
            deduped.append(value)
        categories[key] = deduped

    return categories


def _extract_resume_bullets(text: str) -> list[str]:
    import re

    bullets: list[str] = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    current_bullet: list[str] = []
    pending_bullet_start = False

    for line in lines:
        has_year_pattern = bool(re.search(r"\b(19\d{2}|20\d{2})\b", line))

        if line in {"●", "•", "-"}:
            if current_bullet:
                text_value = " ".join(current_bullet).strip()
                if text_value:
                    bullets.append(text_value)
                current_bullet = []
            pending_bullet_start = True
            continue

        if line.startswith(("●", "•", "-")):
            if current_bullet:
                text_value = " ".join(current_bullet).strip()
                if text_value:
                    bullets.append(text_value)
            current_bullet = [line.lstrip("●•- ").strip()]
            pending_bullet_start = False
            continue

        if pending_bullet_start:
            current_bullet = [line]
            pending_bullet_start = False
            continue

        if current_bullet and has_year_pattern:
            text_value = " ".join(current_bullet).strip()
            if text_value:
                bullets.append(text_value)
            current_bullet = []
            continue

        if current_bullet:
            current_bullet.append(line)

    if current_bullet:
        text_value = " ".join(current_bullet).strip()
        if text_value:
            bullets.append(text_value)

    return bullets


def _section_text_to_bullets(section_text: str) -> list[str]:
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    bullets: list[str] = []
    for line in lines:
        cleaned = line.lstrip("-•*\t ").strip()
        if cleaned:
            bullets.append(cleaned)
    return bullets


_SKILL_CATEGORY_LABELS = {
    "technical",
    "skills",
    "tools",
    "programming languages",
    "programming language",
    "languages",
    "data science",
    "data visualization",
    "databases",
    "business",
    "management",
    "business and management",
    "business management",
}


_PROJECT_DATE_RANGE_PATTERN = re.compile(
    r"(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*[-–]\s*(?:present|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})",
    re.IGNORECASE,
)


def _split_project_name_and_duration(raw_name: str) -> tuple[str, str]:
    text = str(raw_name or "").strip()
    if not text:
        return "", ""

    match = _PROJECT_DATE_RANGE_PATTERN.search(text)
    if not match:
        return text, ""

    duration = re.sub(r"\s*[-–]\s*", " - ", match.group(0).strip())
    remainder = (text[: match.start()] + " " + text[match.end() :]).strip(" |-\t")
    cleaned_name = re.sub(r"\s{2,}", " ", remainder).strip()
    return (cleaned_name or text), duration


def _extract_skills_from_section_text(section_text: str) -> list[str]:
    def _split_outside_parentheses(value: str) -> list[str]:
        parts: list[str] = []
        buffer: list[str] = []
        depth = 0
        for ch in value:
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            if ch in {",", ";", "|"} and depth == 0:
                token = "".join(buffer).strip()
                if token:
                    parts.append(token)
                buffer = []
                continue
            buffer.append(ch)
        tail = "".join(buffer).strip()
        if tail:
            parts.append(tail)
        return parts

    normalized = str(section_text or "")
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"(?<=[A-Za-z0-9)])\n(?=[A-Za-z0-9])", " ", normalized)

    raw_items = _section_text_to_bullets(normalized)
    skills: list[str] = []
    seen: set[str] = set()
    label_only_tokens = set(_SKILL_CATEGORY_LABELS)
    label_only_tokens.add("business & management")

    def _canonical_label(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    for item in raw_items:
        line = item.strip()
        if ":" in line:
            left, right = line.split(":", 1)
            if len(left.split()) <= 4:
                line = right.strip()
        parts = _split_outside_parentheses(line)
        for part in parts:
            skill = part.strip().strip("-•*")
            if ":" in skill:
                nested_left, nested_right = skill.split(":", 1)
                if nested_right.strip() and len(nested_left.split()) <= 3:
                    skill = nested_right.strip()
            lowered = skill.lower()
            if not skill or lowered in seen:
                continue
            canonical = _canonical_label(skill)
            if lowered in label_only_tokens or canonical in label_only_tokens:
                continue
            seen.add(lowered)
            skills.append(skill)
    return skills


def _extract_projects_from_lines(project_lines: list[str], max_projects: int = 8) -> list[dict[str, Any]]:
    import re

    projects: list[dict[str, Any]] = []
    current_name = ""
    current_bullets: list[str] = []
    current_meta: list[str] = []

    year_pattern = re.compile(r"\b(?:19|20)\d{2}\b")
    bullet_verb_pattern = re.compile(
        r"^(?:developed|built|implemented|designed|engineered|optimized|conducted|examined|integrated|created|led|delivered)\b",
        re.IGNORECASE,
    )

    def flush_current() -> None:
        nonlocal current_name, current_bullets, current_meta
        name = current_name.strip()
        if name:
            parsed_name, parsed_duration = _split_project_name_and_duration(name)
            bullets = list(current_bullets)
            if not bullets and current_meta:
                bullets = [m for m in current_meta[:2] if m]

            technologies: list[str] = []
            for meta in current_meta:
                if "," not in meta:
                    continue
                cleaned_meta = re.sub(r"^technologies\s*:\s*", "", meta, flags=re.IGNORECASE)
                parts = [part.strip() for part in cleaned_meta.split(",") if part.strip()]
                technologies.extend(parts)

            projects.append(
                {
                    "name": parsed_name,
                    "duration": parsed_duration,
                    "bullets": bullets[:4],
                    "technologies": technologies[:8],
                }
            )

        current_name = ""
        current_bullets = []
        current_meta = []

    for raw in project_lines:
        line = str(raw).strip()
        if not line:
            continue

        is_year_line = bool(_PROJECT_DATE_RANGE_PATTERN.fullmatch(line)) or (
            bool(year_pattern.search(line)) and len(line.split()) <= 3
        )
        is_bullet_line = line.startswith(("-", "•", "*")) or bool(bullet_verb_pattern.match(line))

        if is_bullet_line:
            bullet = line.lstrip("-•* ").strip()
            if bullet:
                current_bullets.append(bullet)
            continue

        if is_year_line:
            if current_name:
                current_meta.append(line)
            continue

        if current_name:
            if current_bullets:
                flush_current()
                if len(projects) >= max_projects:
                    break
                current_name = line
                continue

            current_meta.append(line)
            continue

        current_name = line

    if len(projects) < max_projects and current_name:
        flush_current()

    return projects[:max_projects]


def _is_noisy_experience_line(value: str) -> bool:
    line = str(value or "").strip()
    if not line:
        return False
    if line.startswith(("-", "•", "*")):
        return True
    if line.endswith("."):
        return True
    if len(line.split()) > 12:
        return True
    return bool(
        re.match(
            r"^(accomplished|achieved|developed|implemented|engineered|orchestrated|streamlined|"
            r"spearheaded|managed|led|delivered|optimized|scaled)\b",
            line,
            re.IGNORECASE,
        )
    )


def _section_experience_is_usable(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False

    usable = 0
    for row in rows:
        title = str(row.get("title", "") or "").strip()
        company = str(row.get("company", "") or "").strip()
        if not title or _is_noisy_experience_line(title):
            continue
        if company and _is_noisy_experience_line(company):
            continue
        usable += 1

    minimum_required = max(1, len(rows) // 2)
    return usable >= minimum_required


def _extract_experience_from_section_text(section_text: str) -> list[dict[str, Any]]:
    import re

    lines = [line.strip() for line in str(section_text or "").splitlines() if line.strip()]
    if not lines:
        return []

    date_range_pattern = re.compile(
        r"^(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*[-–]\s*(?:present|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})$",
        re.IGNORECASE,
    )

    def _split_title_company(header: str) -> tuple[str, str]:
        clean = str(header or "").strip().strip("|- ")
        if not clean:
            return "", ""
        if "|" in clean:
            parts = [p.strip() for p in clean.split("|") if p.strip()]
            if len(parts) >= 2:
                return parts[0], parts[1]
            return clean, ""
        parts = [p.strip() for p in clean.split(",") if p.strip()]
        if len(parts) >= 2:
            return ", ".join(parts[:-1]), parts[-1]
        return clean, ""

    entries: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        title_line = lines[i]
        if i + 1 >= len(lines) or not date_range_pattern.match(lines[i + 1]):
            i += 1
            continue

        duration = lines[i + 1]
        parsed_title, parsed_company = _split_title_company(title_line)
        company = lines[i + 2] if i + 2 < len(lines) and not date_range_pattern.match(lines[i + 2]) else ""
        location = lines[i + 3] if i + 3 < len(lines) and not date_range_pattern.match(lines[i + 3]) else ""

        if _is_noisy_experience_line(company):
            company = ""
        if _is_noisy_experience_line(location):
            location = ""

        row: dict[str, Any] = {
            "title": parsed_title or title_line,
            "company": parsed_company or company,
            "duration": duration,
            "bullets": [],
        }
        if location:
            row["location"] = location
        entries.append(row)

        i += 4 if location else 3

    return entries


def _display_section_name(section_name: str) -> str:
    mapping = {
        "achievements": "Achievements",
        "awards": "Awards",
        "certifications": "Certifications",
        "leadership": "Leadership",

        "publications": "Publications",
        "languages": "Languages",
        "interests": "Interests",
        "summary": "Professional Summary",
    }
    lowered = section_name.strip().lower().replace("_", " ")
    if lowered in mapping:
        return mapping[lowered]
    return " ".join(part.capitalize() for part in lowered.split()) if lowered else "Additional Information"


def _should_omit_summary_for_recent_undergrad(
    education_text: str,
    experience_rows: list[dict[str, Any]],
) -> bool:
    """Return True when summary should be removed for recent undergrad low-experience profiles."""
    normalized_education = str(education_text or "").strip().lower()
    if not normalized_education:
        return False

    undergraduate_markers = (
        "b.tech",
        "btech",
        "b.e",
        "bachelor",
        "undergraduate",
        "b.sc",
        "bca",
    )
    graduate_markers = ("m.tech", "mtech", "master", "mba", "phd", "doctorate")

    if not any(marker in normalized_education for marker in undergraduate_markers):
        return False
    if any(marker in normalized_education for marker in graduate_markers):
        return False

    current_year = datetime.now().year
    education_years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", normalized_education)]
    is_recent_education = (
        "present" in normalized_education
        or "current" in normalized_education
        or any(year >= current_year - 2 for year in education_years)
    )
    if not is_recent_education:
        return False

    meaningful_experience = [
        row
        for row in experience_rows
        if str(row.get("title", "") or "").strip() or str(row.get("company", "") or "").strip()
    ]
    if len(meaningful_experience) <= 2:
        return True

    total_years = 0.0
    for row in meaningful_experience:
        duration = str(row.get("duration", "") or "").lower()
        years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", duration)]
        if not years:
            continue
        start_year = min(years)
        end_year = current_year if "present" in duration else max(years)
        if end_year < start_year:
            continue
        total_years += float(end_year - start_year + 1)

    return total_years <= 2.5


def _resume_data_to_generation_input(resume_data: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    entities = _coerce_dict(resume_data.get("entities", {}))
    sections = _coerce_dict(resume_data.get("sections", {}))
    contact = _coerce_dict(entities.get("contact", {}))

    def _extract_candidate_name() -> str:
        direct_name = str(contact.get("name") or "").strip()
        if direct_name:
            return direct_name

        raw_text = str(resume_data.get("raw_text", "") or "")
        for raw_line in raw_text.splitlines()[:8]:
            line = raw_line.strip()
            if not line:
                continue
            if re.search(r"@|https?://|www\.|\+?\d[\d\s().-]{7,}", line, re.IGNORECASE):
                continue
            if len(line.split()) > 5:
                continue
            if any(token in line.lower() for token in ("linkedin", "github", "portfolio", "email")):
                continue
            return line

        cleaned_fallback = str(fallback_name or "").replace("_", " ").replace("-", " ").strip()
        return cleaned_fallback or "Candidate"

    name = _extract_candidate_name()

    parsed_experience = _coerce_list(entities.get("experience", []))

    def _duration_from_experience_row(row: dict[str, Any]) -> str:
        explicit = str(row.get("duration") or row.get("date") or row.get("tenure") or "").strip()
        if explicit:
            return re.sub(r"\s*-\s*", " - ", explicit)

        date_ranges = row.get("date_ranges", [])
        if isinstance(date_ranges, list):
            for item in date_ranges:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    start = str(item[0]).strip()
                    end = str(item[1]).strip()
                    if start and end:
                        return f"{start} - {end}"
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        return re.sub(r"\s*-\s*", " - ", text)

        years = row.get("years", [])
        if isinstance(years, list):
            year_tokens = [str(y).strip() for y in years if str(y).strip()]
            if len(year_tokens) >= 2:
                start = year_tokens[0]
                end = year_tokens[-1]
                return f"{start} - {end}"
            if len(year_tokens) == 1:
                return year_tokens[0]

        return ""

    def _location_from_experience_row(row: dict[str, Any]) -> str:
        return str(
            row.get("location")
            or row.get("city")
            or row.get("state")
            or row.get("country")
            or row.get("place")
            or ""
        ).strip()

    experience: list[dict[str, Any]] = []
    for item in parsed_experience:
        row = _coerce_dict(item)
        bullets_raw = _coerce_list(row.get("bullets", []))
        bullets = [str(b).strip() for b in bullets_raw if str(b).strip()][:4]
        company = str(
            row.get("company")
            or row.get("company_name")
            or row.get("organization")
            or row.get("employer")
            or ""
        ).strip()
        experience.append(
            {
                "title": str(row.get("role") or row.get("title") or "Professional Experience"),
                "company": company,
                "duration": _duration_from_experience_row(row),
                "location": _location_from_experience_row(row),
                "bullets": bullets,
            }
        )

    section_experience = _extract_experience_from_section_text(str(sections.get("experience") or ""))
    if section_experience and _section_experience_is_usable(section_experience):
        if len(section_experience) > len(experience) or any(not str(row.get("company", "")).strip() for row in experience):
            existing_by_title = {
                str(row.get("title", "")).strip().lower(): row
                for row in experience
                if str(row.get("title", "")).strip()
            }
            merged: list[dict[str, Any]] = []
            for row in section_experience:
                title_key = str(row.get("title", "")).strip().lower()
                original = existing_by_title.get(title_key, {})
                original_bullets = _coerce_list(original.get("bullets", []))
                hydrated = dict(row)
                hydrated["bullets"] = [str(b).strip() for b in original_bullets if str(b).strip()][:4]
                merged.append(hydrated)
            experience = merged

    # Preserve source truth: if resume has no experience section/data, keep it empty.

    parsed_projects = _coerce_list(entities.get("projects", []))
    projects: list[dict[str, Any]] = []
    if parsed_projects and all(isinstance(item, str) for item in parsed_projects):
        projects = _extract_projects_from_lines(
            [str(item) for item in parsed_projects],
            max_projects=20,
        )
    else:
        for item in parsed_projects:
            row = _coerce_dict(item)
            proj_bullets_raw = _coerce_list(row.get("bullets", []))
            proj_bullets = [str(b).strip() for b in proj_bullets_raw if str(b).strip()][:4]
            if not proj_bullets and row.get("description"):
                proj_bullets = [str(row.get("description", "")).strip()]
            if not proj_bullets and row.get("text"):
                maybe_text = str(row.get("text", "")).strip()
                if maybe_text:
                    proj_bullets = [maybe_text]
            technologies = [str(t).strip() for t in _coerce_list(row.get("technologies", []))]
            project_name = str(
                row.get("name")
                or row.get("title")
                or row.get("project")
                or row.get("text")
                or ""
            ).strip()
            explicit_duration = str(row.get("duration") or row.get("date") or row.get("dates") or "").strip()
            if "|" in project_name:
                parts = [p.strip() for p in project_name.split("|") if p.strip()]
                if parts:
                    project_name = parts[0]
                if len(parts) > 1 and not technologies:
                    technologies = [p.strip() for p in re.split(r",|/", parts[1]) if p.strip()]
            project_name, derived_duration = _split_project_name_and_duration(project_name)
            project_duration = explicit_duration or derived_duration
            if not project_name:
                continue
            projects.append(
                {
                    "name": project_name,
                    "duration": project_duration,
                    "bullets": proj_bullets,
                    "technologies": [t for t in technologies if t],
                }
            )

    if not projects:
        project_section_text = str(sections.get("projects") or sections.get("project") or "")
        fallback_projects = _extract_projects_from_lines(project_section_text.splitlines(), max_projects=20)
        if fallback_projects:
            projects = fallback_projects

    raw_skills: list[str] = []

    def _collect_skill_names() -> list[str]:
        collected: list[str] = []
        skills_value = entities.get("skills", [])

        if isinstance(skills_value, dict):
            category_label_tokens = set(_SKILL_CATEGORY_LABELS)
            for key, value in cast(dict[str, Any], skills_value).items():
                key_text = str(key).strip()
                key_canonical = re.sub(r"[^a-z0-9]+", " ", key_text.lower()).strip()
                if (
                    key_text
                    and isinstance(value, dict)
                    and any(metric_key in value for metric_key in ("score", "frequency", "weight", "count"))
                    and key_canonical not in category_label_tokens
                ):
                    collected.append(key_text)
                if isinstance(value, dict):
                    nested_name = str(value.get("name") or value.get("skill") or "").strip()
                    if nested_name:
                        collected.append(nested_name)
                elif isinstance(value, list):
                    for nested in cast(list[Any], value):
                        if isinstance(nested, dict):
                            nested_name = str(nested.get("name") or nested.get("skill") or "").strip()
                            if nested_name:
                                collected.append(nested_name)
                        else:
                            nested_text = str(nested).strip()
                            if nested_text:
                                collected.append(nested_text)
                elif isinstance(value, str):
                    collected.extend(part.strip() for part in value.split(",") if part.strip())
        elif isinstance(skills_value, list):
            for item in cast(list[Any], skills_value):
                if isinstance(item, dict):
                    candidate = str(item.get("name") or item.get("skill") or "").strip()
                    if candidate:
                        collected.append(candidate)
                else:
                    text_value = str(item).strip()
                    if text_value:
                        collected.append(text_value)

        skill_names = entities.get("skill_names", [])
        if isinstance(skill_names, list):
            collected.extend(str(s).strip() for s in skill_names if str(s).strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for skill in collected:
            key = skill.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(skill)
        return deduped

    section_skills = _extract_skills_from_section_text(str(sections.get("skills") or ""))
    if section_skills:
        raw_skills = section_skills
    else:
        raw_skills = _collect_skill_names()
        if raw_skills:
            raw_text_lower = str(resume_data.get("raw_text", "") or "").lower()
            filtered = [s for s in raw_skills if str(s).strip().lower() in raw_text_lower]
            if filtered:
                raw_skills = filtered

    cleaned_skills: list[str] = []
    for skill in raw_skills:
        canonical = re.sub(r"[^a-z0-9]+", " ", str(skill).lower()).strip()
        if canonical in _SKILL_CATEGORY_LABELS:
            continue
        cleaned_skills.append(str(skill))
    raw_skills = cleaned_skills

    skills_map = _categorize_skills_for_generation([s for s in raw_skills if s])

    education = str(sections.get("education") or entities.get("education") or "Education details available on request").strip()
    summary = str(sections.get("summary") or "").strip()
    certifications = []
    for item in _coerce_list(entities.get("certifications", [])):
        if isinstance(item, dict):
            cert_text = " | ".join(
                str(item.get(key) or "").strip()
                for key in ("name", "issuer", "year")
                if str(item.get(key) or "").strip()
            )
            if cert_text:
                certifications.append(cert_text)
            continue
        text = str(item).strip()
        if text:
            certifications.append(text)
    raw_resume_text = str(resume_data.get("raw_text", "") or "")
    context_enrichment = enrich_resume_context(raw_resume_text, raw_skills)

    if _should_omit_summary_for_recent_undergrad(education, experience):
        summary = ""

    core_section_names = {
        "contact",
        "experience",
        "projects",
        "education",
        "skills",
        "certifications",
        "summary",
        "unclassified",
    }
    additional_sections: list[dict[str, Any]] = []
    for section_name, section_text in sections.items():
        if section_name in core_section_names:
            continue
        bullets = _section_text_to_bullets(str(section_text))
        if not bullets:
            continue
        additional_sections.append(
            {
                "title": _display_section_name(section_name),
                "body": str(section_text).strip(),
                "bullets": bullets,
            }
        )

    target_role = str(experience[0].get("title", "")).strip() if experience else ""
    if not target_role:
        target_role = "Target Role"

    return {
        "name": name,
        "contact": {
            "location": str(contact.get("location") or "").strip(),
            "email": str(contact.get("email") or "").strip(),
            "phone": str(contact.get("phone") or "").strip(),
            "linkedin": str(contact.get("linkedin") or "").strip(),
            "github": str(contact.get("github") or "").strip(),
        },
        "target_role": target_role,
        "education": education,
        "summary": summary,
        "skills": skills_map,
        "projects": projects,
        "experience": experience,
        "certifications": certifications[:5],
        "additional_sections": additional_sections,
        "raw_resume_text": raw_resume_text,
        "resume_sections_raw": {str(k): str(v) for k, v in sections.items()},
        "parsed_skills_flat": raw_skills,
        "context_enrichment": context_enrichment,
        "generation_input_mode": "raw_text_plus_hints_v2",
        "extra_context": "Generated from uploaded resume for ATS optimization.",
    }


@app.get(f"/api/{API_VERSION}/health", response_model=HealthResponse)
def health_v1() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION)


@app.post(
    f"/api/{API_VERSION}/parse/jd",
    response_model=ParseJDResponse,
    responses={422: {"model": ErrorResponse}},
)
def parse_jd_v1(payload: ParseJDRequest) -> ParseJDResponse:
    jd_inputs = _collect_jd_text_inputs(
        payload.jd_text,
        payload.jd_texts,
        use_repo_jd_library=payload.use_repo_jd_library,
    )
    if not jd_inputs:
        raise HTTPException(status_code=400, detail="Provide at least one JD text in jd_text or jd_texts")

    if len(jd_inputs) == 1:
        parsed = parse_job_description(jd_inputs[0])
    else:
        parsed = _merge_jd_payloads(jd_inputs)

    parsed.update(enrich_jd_context(parsed))

    return ParseJDResponse(ok=True, jd_analysis=parsed)


@app.post(
    f"/api/{API_VERSION}/parse/resume",
    response_model=ParseResumeResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def parse_resume_v1(
    resume_file: UploadFile = File(...),
) -> ParseResumeResponse:
    parser = ResumeParser()
    temp_path: Path | None = None
    suffix = _validate_extension(resume_file)

    try:
        temp_path = await _write_upload_to_temp(resume_file, suffix)
        parsed = parser.parse_file(temp_path, enable_section_llm=PARSER_SECTION_LLM_ENABLED)
        return ParseResumeResponse(
            ok=True,
            filename=resume_file.filename or "resume",
            resume_analysis=parsed.to_dict(),
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)

@app.post(
    f"/api/{API_VERSION}/improve/submit",
    response_model=ImproveSubmitResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def improve_submit_v1(
    candidate_name: str = Form(...),
    candidate_email_address: str = Form(...),
    phone_number: str = Form(default=""),
    resume_file: UploadFile = File(...),
) -> ImproveSubmitResponse:
    temp_path: Path | None = None
    suffix = _validate_extension(resume_file)

    try:
        temp_path = await _write_upload_to_temp(resume_file, suffix)
        store = EnhancementSubmissionStore.from_env()
        stored = store.persist_submission(
            file_path=temp_path,
            original_filename=resume_file.filename or f"resume{suffix}",
            content_type=resume_file.content_type,
            candidate_name=candidate_name,
            candidate_email_address=candidate_email_address,
            phone_number=phone_number,
        )

        if stored is None:
            raise HTTPException(status_code=500, detail="Enhancement submission storage is not configured")

        return ImproveSubmitResponse(
            ok=True,
            candidate_id=stored.candidate_id,
            bucket_name=stored.bucket_name,
            object_key=stored.object_key,
            resume_link=stored.resume_link,
            candidate_submitted_date=stored.candidate_submitted_date,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit resume: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post(
    f"/api/{API_VERSION}/analyze/ats",
    response_model=AtsAnalyzeResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def analyze_ats_v1(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(default=""),
    job_description: str = Form(default=""),
    jd_texts: list[str] = Form(default=[]),
    use_repo_jd_library: bool = Form(default=False),
    target_role: str = Form(default=""),
    job_role: str = Form(default=""),
) -> AtsAnalyzeResponse:
    request_started = time.perf_counter()
    temp_path: Path | None = None
    suffix = _validate_extension(resume_file)

    parser = ResumeParser()

    try:
        effective_job_description = job_description.strip() or jd_text.strip()
        effective_job_role = job_role.strip() or target_role.strip()
        temp_path = await _write_upload_to_temp(resume_file, suffix)
        file_size = temp_path.stat().st_size if temp_path.exists() else 0
        raw_max_mb = str(os.getenv("ATS_MAX_UPLOAD_MB", str(DEFAULT_ATS_MAX_UPLOAD_MB))).strip()
        max_upload_mb = int(raw_max_mb) if raw_max_mb.isdigit() and int(raw_max_mb) > 0 else DEFAULT_ATS_MAX_UPLOAD_MB
        max_upload_bytes = max_upload_mb * 1024 * 1024
        if file_size > max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded file is too large ({round(file_size / (1024 * 1024), 2)} MB). Max allowed: {max_upload_mb} MB.",
            )

        jd_data = _build_scoring_jd_context(
            effective_job_description,
            jd_texts,
            use_repo_jd_library=use_repo_jd_library,
        )
        has_jd = jd_data is not None
        logger.info(
            "ATS analyze started filename=%s size_bytes=%d mode=%s",
            resume_file.filename or "resume",
            file_size,
            "jd" if has_jd else "resume_only",
        )

        if has_jd:
            _validate_jd_for_scoring(jd_data)

        parse_started = time.perf_counter()
        parsed = parser.parse_file(
            temp_path,
            jd_context=jd_data,
            enable_section_llm=PARSER_SECTION_LLM_ENABLED,
        )
        logger.info("ATS analyze parse completed in %.2fs", time.perf_counter() - parse_started)

        resume_dict = parsed.to_dict()
        resume_parse_diagnostics = _build_resume_parse_diagnostics(resume_dict)
        resume_entities = resume_dict.get("entities", {})
        resume_metadata = resume_dict.get("metadata", {})
        resume_sections = resume_dict.get("sections", {})
        resume_text = str(resume_dict.get("raw_text", "") or "")
        resume_experience = _coerce_list(resume_entities.get("experience"))
        resume_skills = resume_entities.get("skills", {})
        resume_bullets = flatten_experience_bullets(resume_experience)

        scoring_started = time.perf_counter()
        if has_jd:
            jd_payload = cast(dict[str, Any], jd_data or {})
            jd_skills_required = _coerce_list(jd_payload.get("skills_required"))
            jd_skills_optional = _coerce_list(jd_payload.get("skills_optional"))
            jd_skills = sorted(set(jd_skills_required) | set(jd_skills_optional))
            jd_responsibilities = _coerce_list(jd_payload.get("responsibilities"))

            skill_alignment = align_skills(
                resume_skills=resume_skills,
                jd_skills=jd_skills,
                experience_bullets=resume_bullets,
                has_project_section=any("project" in str(k).lower() for k in resume_sections.keys()),
            )
            experience_alignment = align_experience(
                jd_responsibilities=jd_responsibilities,
                jd_importance=jd_payload.get("importance_weights", {}),
                resume_experience=resume_experience,
                resume_bullets=resume_bullets,
            )
            ats_analysis = compute_ats_score(
                skill_alignment=skill_alignment,
                experience_alignment=experience_alignment,
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                jd_context=jd_payload,
                resume_sections=resume_sections,
                resume_text=resume_text,
            )
            mode: AnalyzeMode = "jd"
        else:
            ats_analysis = compute_resume_only_score(
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                resume_text=resume_text,
            )
            mode = "resume_only"

        logger.info("ATS analyze scoring completed in %.2fs", time.perf_counter() - scoring_started)
        logger.info("ATS analyze finished in %.2fs", time.perf_counter() - request_started)

        decision, confidence, reasons, fail_reasons = _decision_payload(ats_analysis)
        score, percentile = _score_payload(ats_analysis)
        stored_submission = AtsSubmissionStore.from_env().persist_submission(
            file_path=temp_path,
            original_filename=resume_file.filename or f"resume{suffix}",
            content_type=resume_file.content_type,
            target_role=effective_job_role,
            jd_text=effective_job_description,
        )
        if stored_submission is None:
            raise HTTPException(status_code=500, detail="ATS submission storage is not configured")

        return AtsAnalyzeResponse(
            ok=True,
            mode=mode,
            target_role=effective_job_role,
            decision=decision,
            confidence=confidence,
            score=score,
            percentile=percentile,
            reasons=reasons,
            fail_reasons=fail_reasons,
            ats_score=score,
            components=_coerce_dict(ats_analysis.get("components", {})),
            breakdown=_build_breakdown_items(ats_analysis),
            issues=_derive_issues_from_ats(ats_analysis),
            raw=ats_analysis,
            resume_parse=resume_parse_diagnostics,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ATS analyze failed after %.2fs", time.perf_counter() - request_started)
        raise HTTPException(status_code=500, detail=f"Failed to analyze resume: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post(
    f"/api/{API_VERSION}/analyze/ats/fix",
    response_model=AtsFixResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def fix_ats_with_ai_v1(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(default=""),
    jd_texts: list[str] = Form(default=[]),
    use_repo_jd_library: bool = Form(default=False),
    target_role: str = Form(default=""),
    rewrite_mode: str = Form(default="ats_rewrite"),
) -> AtsFixResponse:
    temp_path: Path | None = None
    suffix = _validate_extension(resume_file)
    parser = ResumeParser()

    try:
        jd_data = _build_scoring_jd_context(
            jd_text,
            jd_texts,
            use_repo_jd_library=use_repo_jd_library,
        )
        if jd_data is not None:
            _validate_jd_for_scoring(jd_data)

        temp_path = await _write_upload_to_temp(resume_file, suffix)
        parsed = parser.parse_file(
            temp_path,
            jd_context=jd_data,
            enable_section_llm=PARSER_SECTION_LLM_ENABLED,
        )
        resume_dict = parsed.to_dict()

        # Use the same canonical parse output for generation and scoring.
        generation_resume_dict = resume_dict
        resume_parse_diagnostics = _build_resume_parse_diagnostics(generation_resume_dict)

        before_text = str(resume_dict.get("raw_text", "") or "")
        resume_entities = _coerce_dict(resume_dict.get("entities", {}))
        resume_metadata = _coerce_dict(resume_dict.get("metadata", {}))
        resume_sections = _coerce_dict(resume_dict.get("sections", {}))
        resume_experience = _coerce_list(resume_entities.get("experience"))
        resume_skills = resume_entities.get("skills", {})
        resume_bullets = flatten_experience_bullets(resume_experience)

        if jd_data is not None:
            jd_skills_required = _coerce_list(jd_data.get("skills_required"))
            jd_skills_optional = _coerce_list(jd_data.get("skills_optional"))
            jd_skills = sorted(set(jd_skills_required) | set(jd_skills_optional))
            jd_responsibilities = _coerce_list(jd_data.get("responsibilities"))

            skill_alignment = align_skills(
                resume_skills=resume_skills,
                jd_skills=jd_skills,
                experience_bullets=resume_bullets,
                has_project_section=any("project" in str(k).lower() for k in resume_sections.keys()),
            )
            experience_alignment = align_experience(
                jd_responsibilities=jd_responsibilities,
                jd_importance=jd_data.get("importance_weights", {}),
                resume_experience=resume_experience,
                resume_bullets=resume_bullets,
            )
            before_analysis = compute_ats_score(
                skill_alignment=skill_alignment,
                experience_alignment=experience_alignment,
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                jd_context=jd_data,
                resume_sections=resume_sections,
                resume_text=before_text,
            )
            mode: AnalyzeMode = "jd"
        else:
            before_analysis = compute_resume_only_score(
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                resume_text=before_text,
            )
            mode = "resume_only"

        normalized_rewrite_mode = _normalize_rewrite_mode(rewrite_mode)

        generation_input = _resume_data_to_generation_input(
            resume_data=generation_resume_dict,
            fallback_name=Path(resume_file.filename or "resume").stem,
        )
        generation_input["rewrite_mode"] = normalized_rewrite_mode
        if target_role.strip():
            generation_input["target_role"] = target_role.strip()
        if isinstance(jd_data, dict) and jd_data:
            jd_generation_context = dict(jd_data)
            jd_generation_context.update(enrich_jd_context(jd_data))
            generation_input["jd_context"] = jd_generation_context
        elif mode == "resume_only" and isinstance(before_analysis, dict):
            # Build synthetic JD context from the inferred role's benchmark profile
            # so the LLM knows which skills/responsibilities to optimize for.
            benchmark_profile = _coerce_dict(before_analysis.get("benchmark_profile", {}))
            inferred_role = str(before_analysis.get("inferred_role", "")).strip()
            if benchmark_profile:
                synthetic_jd_context: dict[str, Any] = {
                    "job_title": inferred_role,
                    "skills_required": list(benchmark_profile.get("skills", [])),
                    "responsibilities": list(benchmark_profile.get("responsibilities", [])),
                }
                synthetic_jd_context.update(enrich_jd_context(synthetic_jd_context))
                generation_input["jd_context"] = synthetic_jd_context
                jd_data = synthetic_jd_context
                if not str(generation_input.get("target_role", "")).strip() and inferred_role:
                    generation_input["target_role"] = inferred_role

        llm_engine = LLMAnalysisEngine(api_key=None)
        generated = llm_engine.generate_resume(user_input=generation_input, jd_data=jd_data)
        optimized_text = str(generated.get("resume_text", "") or "").strip()
        latex_source = str(generated.get("latex_source", "") or "")
        if not optimized_text:
            raise HTTPException(status_code=500, detail="LLM returned empty optimized resume")

        # Re-parse optimized text so ATS recomputation is aligned with what users download.
        optimized_parse = parser.parse_text(
            optimized_text,
            jd_context=jd_data,
        )
        optimized_resume_dict = optimized_parse.to_dict()
        optimized_resume_entities = _coerce_dict(optimized_resume_dict.get("entities", {}))
        optimized_resume_metadata = _coerce_dict(optimized_resume_dict.get("metadata", {}))
        optimized_resume_sections = _coerce_dict(optimized_resume_dict.get("sections", {}))
        optimized_resume_experience = _coerce_list(optimized_resume_entities.get("experience"))
        optimized_resume_skills = optimized_resume_entities.get("skills", {})
        optimized_resume_bullets = flatten_experience_bullets(optimized_resume_experience)

        if mode == "jd":
            jd_payload = cast(dict[str, Any], jd_data or {})
            jd_skills_required = _coerce_list(jd_payload.get("skills_required"))
            jd_skills_optional = _coerce_list(jd_payload.get("skills_optional"))
            jd_skills = sorted(set(jd_skills_required) | set(jd_skills_optional))
            jd_responsibilities = _coerce_list(jd_payload.get("responsibilities"))

            optimized_skill_alignment = align_skills(
                resume_skills=optimized_resume_skills,
                jd_skills=jd_skills,
                experience_bullets=optimized_resume_bullets,
                has_project_section=any("project" in str(k).lower() for k in optimized_resume_sections.keys()),
            )
            optimized_experience_alignment = align_experience(
                jd_responsibilities=jd_responsibilities,
                jd_importance=jd_payload.get("importance_weights", {}),
                resume_experience=optimized_resume_experience,
                resume_bullets=optimized_resume_bullets,
            )
            after_analysis = compute_ats_score(
                skill_alignment=optimized_skill_alignment,
                experience_alignment=optimized_experience_alignment,
                resume_entities=optimized_resume_entities,
                resume_metadata=optimized_resume_metadata,
                jd_context=jd_payload,
                resume_sections=optimized_resume_sections,
                resume_text=optimized_text,
            )
        else:
            after_analysis = compute_resume_only_score(
                resume_entities=optimized_resume_entities,
                resume_metadata=optimized_resume_metadata,
                resume_text=optimized_text,
            )

        before_score, _before_percentile = _score_payload(before_analysis)
        after_score, _after_percentile = _score_payload(after_analysis)
        non_regression_applied = False
        if after_score < before_score:
            logger.warning(
                "ATS fix regression detected (%s -> %s). Returning baseline content to enforce non-regression.",
                before_score,
                after_score,
            )
            optimized_text = before_text
            after_analysis = before_analysis
            non_regression_applied = True

        candidate_name = str(generation_input.get("name", "Candidate")).strip() or "Candidate"
        pdf_base64 = str(generated.get("pdf_base64", "") or "")
        docx_base64 = str(generated.get("docx_base64", "") or "")
        if not pdf_base64:
            raise HTTPException(status_code=500, detail="LLM did not return PDF output")
        if not docx_base64:
            raise HTTPException(status_code=500, detail="LLM did not return DOCX output")
        pdf_bytes = base64.b64decode(pdf_base64)
        txt_bytes = optimized_text.encode("utf-8")
        base_name = candidate_name.replace(" ", "_") or "resume"

        files = [
            GeneratedFileItem(
                format="txt",
                filename=f"{base_name}_optimized_resume.txt",
                mime_type="text/plain",
                base64_data=base64.b64encode(txt_bytes).decode("utf-8"),
            ),
            GeneratedFileItem(
                format="pdf",
                filename=f"{base_name}_optimized_resume.pdf",
                mime_type="application/pdf",
                base64_data=pdf_base64,
            ),
            GeneratedFileItem(
                format="docx",
                filename=f"{base_name}_optimized_resume.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                base64_data=docx_base64,
            ),
        ]

        before_score, _before_percentile = _score_payload(before_analysis)
        after_score, _after_percentile = _score_payload(after_analysis)
        before_decision, before_confidence, _before_reasons, _before_fail = _decision_payload(before_analysis)
        after_decision, after_confidence, _after_reasons, _after_fail = _decision_payload(after_analysis)

        notes = [
            "Optimized resume generated with structured data and LaTeX rendering.",
            "Downloads include TXT, PDF, and DOCX formats.",
            f"Rewrite mode applied: {normalized_rewrite_mode}.",
        ]
        if non_regression_applied:
            notes.append("Optimization was reverted to baseline content to prevent ATS score regression.")

        return AtsFixResponse(
            ok=True,
            mode=mode,
            rewrite_mode=normalized_rewrite_mode,
            target_role=target_role.strip(),
            before_decision=before_decision,
            after_decision=after_decision,
            before_confidence=before_confidence,
            after_confidence=after_confidence,
            before_score=before_score,
            after_score=after_score,
            before_text=before_text,
            optimized_text=optimized_text,
            latex_source=latex_source,
            files=files,
            notes=notes,
            resume_parse=resume_parse_diagnostics,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to optimize resume with AI: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post(
    f"/api/{API_VERSION}/analyze/full",
    response_model=FullAnalysisResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def analyze_full_v1(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
    include_llm_recommendations: bool = Form(default=True),
) -> FullAnalysisResponse:
    if len(jd_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="jd_text must be at least 20 characters")

    resume_suffix = _validate_extension(resume_file)
    temp_resume_path: Path | None = None
    temp_jd_path: Path | None = None

    try:
        temp_resume_path = await _write_upload_to_temp(resume_file, resume_suffix)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as jd_file:
            jd_file.write(jd_text)
            temp_jd_path = Path(jd_file.name)

        service = ResumeAnalysisService()
        result = service.analyze_resume_against_jd(
            resume_path=str(temp_resume_path),
            jd_path=str(temp_jd_path),
            include_llm_recommendations=include_llm_recommendations,
        )
        return FullAnalysisResponse(ok=True, result=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed full analysis: {exc}") from exc
    finally:
        if temp_resume_path and temp_resume_path.exists():
            temp_resume_path.unlink(missing_ok=True)
        if temp_jd_path and temp_jd_path.exists():
            temp_jd_path.unlink(missing_ok=True)


# Backward-compatible aliases for existing frontend calls.
@app.get("/api/health", response_model=HealthResponse)
def health_legacy() -> HealthResponse:
    return health_v1()


@app.post("/api/ats/analyze", response_model=AtsAnalyzeResponse)
async def analyze_ats_legacy(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(default=""),
    job_description: str = Form(default=""),
    jd_texts: list[str] = Form(default=[]),
    use_repo_jd_library: bool = Form(default=False),
    target_role: str = Form(default=""),
    job_role: str = Form(default=""),
) -> AtsAnalyzeResponse:
    return await analyze_ats_v1(
        resume_file=resume_file,
        jd_text=jd_text,
        job_description=job_description,
        jd_texts=jd_texts,
        use_repo_jd_library=use_repo_jd_library,
        target_role=target_role,
        job_role=job_role,
    )


@app.post("/api/improve/submit", response_model=ImproveSubmitResponse)
async def improve_submit_legacy(
    candidate_name: str = Form(...),
    candidate_email_address: str = Form(...),
    phone_number: str = Form(default=""),
    resume_file: UploadFile = File(...),
) -> ImproveSubmitResponse:
    return await improve_submit_v1(
        candidate_name=candidate_name,
        candidate_email_address=candidate_email_address,
        phone_number=phone_number,
        resume_file=resume_file,
    )
