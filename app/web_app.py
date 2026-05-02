"""Streamlit web interface for resume and JD parsing."""

import os
import sys
import json
import base64
import re
from pathlib import Path
from typing import Any, cast

import streamlit as st

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.parsing.resume_parser import ResumeParser
from app.parsing.jd_parser import parse_job_description
from app.intelligence.skill_alignment import align_skills
from app.intelligence.experience_alignment import align_experience
from app.intelligence.gap_analysis import analyze_gaps
from app.intelligence.ats_engine import compute_ats_score, compute_resume_only_score
from app.intelligence.utils import flatten_experience_bullets
from app.intelligence.resume_analysis_service import ResumeAnalysisService
from app.intelligence.context_enrichment import enrich_jd_context
from app.llm_engine import LLMAnalysisEngine


st.set_page_config(
    page_title="Resume Parser",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📄 Resume & Job Description Parser")
st.markdown(
    "Upload your resume and job description to get intelligent parsing and matching insights."
)

# Sidebar
with st.sidebar:
    st.header("Parser Settings")
    parse_mode = st.radio(
        "What would you like to do?",
        ["Parse Resume", "Parse Job Description", "Compare Resume & JD", "Quick Resume Score", "LLM Recommendations"]
    )
    show_json = st.checkbox("Show detailed JSON output", value=False)


def _render_layer_tests(layer_key: str, title: str, checks: list[tuple[str, bool, str]]) -> None:
    """Render a click-to-run validation panel for each processing layer."""
    st.subheader(f"🧪 {title}")
    run_tests = st.button(f"Run {title}", key=f"run_tests_{layer_key}")
    if not run_tests:
        st.caption("Run these checks to validate required schema and output quality gates.")
        return

    total = len(checks)
    passed = sum(1 for _, ok, _ in checks if ok)
    failed = total - passed

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Passed", passed)
    with col2:
        st.metric("Failed", failed)
    with col3:
        st.metric("Coverage", f"{passed}/{total}")

    for check_name, ok, detail in checks:
        if ok:
            st.success(f"{check_name}: PASS - {detail}")
        else:
            st.error(f"{check_name}: FAIL - {detail}")


def _render_resume_parse_diagnostics(metadata: dict[str, Any], heading: str = "LLM Parse Diagnostics") -> None:
    """Render parser diagnostics so UIs can verify LLM section parsing behavior."""
    pipeline = str(metadata.get("pipeline", "") or "unknown")
    parsing_confidence = float(metadata.get("parsing_confidence", 0.0) or 0.0)
    completeness = float(metadata.get("completeness_score", 0.0) or 0.0)
    llm_status = metadata.get("llm_field_parse_status", {})
    status_map = cast(dict[str, Any], llm_status) if isinstance(llm_status, dict) else {}

    st.subheader(f"🧠 {heading}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Pipeline", pipeline)
    with c2:
        st.metric("Parse Confidence", f"{parsing_confidence:.0%}")
    with c3:
        st.metric("Completeness", f"{completeness:.0%}")

    if not status_map:
        st.info("No section-wise LLM diagnostics were provided for this parse path.")
        return

    rows: list[dict[str, Any]] = []
    for section, payload in status_map.items():
        item = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
        issues = item.get("issues", [])
        issues_text = " | ".join(str(x) for x in cast(list[Any], issues)) if isinstance(issues, list) else ""
        rows.append(
            {
                "section": str(section),
                "valid": bool(item.get("valid", False)),
                "attempts": int(item.get("attempts", 0) or 0),
                "schema_mode": bool(item.get("schema_mode_used", False)),
                "issues": issues_text,
            }
        )

    st.dataframe(rows, use_container_width=True)


def _display_pre_pdf_llm_output(generated_payload: dict[str, Any], panel_key: str) -> None:
    """Show manual-test view of LLM generation output before PDF bytes are consumed."""
    st.subheader("🔬 Pre-PDF LLM Output (Manual Testing)")
    st.caption("This is the generation output used before download/consumption of LaTeX-compiled PDF bytes.")

    include_binary = st.checkbox(
        "Include base64 binary fields (pdf_base64/docx_base64)",
        value=False,
        key=f"show_binary_{panel_key}",
    )

    safe_payload = dict(generated_payload)
    if not include_binary:
        if "pdf_base64" in safe_payload:
            safe_payload["pdf_base64"] = "<hidden: enable checkbox to inspect>"
        if "docx_base64" in safe_payload:
            safe_payload["docx_base64"] = "<hidden: enable checkbox to inspect>"

    with st.expander("View raw generated payload", expanded=False):
        st.json(safe_payload)

    with st.expander("View resume_json (structured pre-PDF content)", expanded=False):
        st.json(safe_payload.get("resume_json", {}))

    with st.expander("View LaTeX source used for PDF", expanded=False):
        st.code(str(generated_payload.get("latex_source", "") or ""), language="latex")


def _display_llm_input_payload(llm_input_payload: dict[str, Any], panel_key: str) -> None:
    """Show manual-test view of the input payload sent to LLM workflows."""
    st.subheader("🧾 LLM Input (Manual Testing)")
    st.caption("This payload represents the data sent into the LLM workflow before response generation.")

    include_raw_text = st.checkbox(
        "Include large raw_text fields",
        value=False,
        key=f"show_llm_raw_text_{panel_key}",
    )

    safe_input = dict(llm_input_payload)
    if not include_raw_text:
        for key in ("resume_data", "resume_analysis", "jd_data", "jd_analysis"):
            value = safe_input.get(key, {})
            if isinstance(value, dict) and "raw_text" in value:
                value = dict(value)
                value["raw_text"] = "<hidden: enable checkbox to inspect>"
                safe_input[key] = value

    with st.expander("View LLM input payload", expanded=False):
        st.json(safe_input)


def _sanitize_layer_output(
    value: Any,
    *,
    include_binary: bool,
    include_large_text: bool,
    parent_key: str = "",
) -> Any:
    """Prepare nested payloads for safe JSON rendering in observability panels."""
    key_lower = parent_key.lower()
    is_binary_field = any(
        token in key_lower for token in ("pdf_base64", "docx_base64", "pdf_bytes", "docx_bytes", "binary")
    )
    is_large_text_field = any(
        token in key_lower for token in ("raw_text", "resume_text", "latex_source", "full_text")
    )

    if isinstance(value, dict):
        return {
            str(k): _sanitize_layer_output(
                v,
                include_binary=include_binary,
                include_large_text=include_large_text,
                parent_key=str(k),
            )
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            _sanitize_layer_output(
                item,
                include_binary=include_binary,
                include_large_text=include_large_text,
                parent_key=parent_key,
            )
            for item in value
        ]

    if isinstance(value, (bytes, bytearray)):
        size = len(value)
        if include_binary:
            return f"<bytes:{size}>"
        return f"<hidden bytes:{size} - enable binary toggle>"

    if is_binary_field and isinstance(value, str) and value and not include_binary:
        return f"<hidden base64:{len(value)} chars - enable binary toggle>"

    if is_large_text_field and isinstance(value, str) and value and not include_large_text:
        return f"<hidden text:{len(value)} chars - enable large text toggle>"

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def _render_layer_observability_panel(
    panel_key: str,
    layers: list[tuple[str, Any]],
    heading: str = "Layer Output Observatory",
) -> None:
    """Render full layer outputs for testing and observability."""
    st.subheader(f"🔍 {heading}")
    st.caption("Expanded, layer-by-layer payloads for validation, testing, and debugging.")

    include_binary = st.checkbox(
        "Include binary/base64 fields",
        value=False,
        key=f"show_layer_binary_{panel_key}",
    )
    include_large_text = st.checkbox(
        "Include large text fields (raw_text, resume_text, latex_source)",
        value=True,
        key=f"show_layer_large_text_{panel_key}",
    )

    summary_rows: list[dict[str, Any]] = []
    for layer_name, layer_payload in layers:
        payload = layer_payload if isinstance(layer_payload, (dict, list)) else {"value": layer_payload}
        key_count = len(payload) if isinstance(payload, dict) else len(payload) if isinstance(payload, list) else 1
        summary_rows.append(
            {
                "layer": layer_name,
                "type": type(payload).__name__,
                "top_level_items": key_count,
            }
        )

    if summary_rows:
        st.dataframe(summary_rows, use_container_width=True)

    for layer_name, layer_payload in layers:
        payload = layer_payload if isinstance(layer_payload, (dict, list)) else {"value": layer_payload}
        rendered_payload = _sanitize_layer_output(
            payload,
            include_binary=include_binary,
            include_large_text=include_large_text,
        )
        with st.expander(f"View {layer_name}", expanded=True):
            st.json(rendered_payload)


def format_skill(skill: dict[str, Any]) -> str:
    """Format a skill object for display."""
    name = str(skill.get("name", "Unknown"))
    confidence = float(skill.get("confidence", 0) or 0)
    
    # Color code by confidence
    if confidence >= 0.8:
        badge = "🟢"
    elif confidence >= 0.6:
        badge = "🟡"
    else:
        badge = "🔴"
    
    return f"{badge} **{name}** ({confidence:.0%})"


def _skill_name(skill: object) -> str:
    """Return normalized skill name for either dict or string skill entries."""
    if isinstance(skill, dict):
        skill_map = cast(dict[str, Any], skill)
        name = skill_map.get("name", "")
        return str(name).strip().lower()
    return str(skill).strip().lower()


def _skill_confidence(skill: object) -> float:
    """Return confidence if present, else 0 for string-only skills."""
    if isinstance(skill, dict):
        try:
            skill_map = cast(dict[str, Any], skill)
            return float(skill_map.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _skill_display(skill: object) -> str:
    """Return display name for either dict or string skill entries."""
    if isinstance(skill, dict):
        skill_map = cast(dict[str, Any], skill)
        return str(skill_map.get("name", "Unknown"))
    return str(skill)


def _build_improved_resume_text(raw_text: str, recommendations: dict[str, Any]) -> str:
    """Apply bullet rewrites when possible and return downloadable improved resume text."""
    improved_text = str(raw_text or "")
    bullet_improvements = recommendations.get("bullet_improvements", [])
    if not isinstance(bullet_improvements, list):
        return improved_text

    unmatched: list[str] = []
    for item in bullet_improvements:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original", "")).strip()
        improved = str(item.get("improved", "")).strip()
        if not original or not improved or original == "insufficient_data" or improved == "insufficient_data":
            continue

        if original in improved_text:
            improved_text = improved_text.replace(original, improved, 1)
        else:
            unmatched.append(f"- Replace: {original}\n  With: {improved}")

    if unmatched:
        improved_text = (
            improved_text.rstrip()
            + "\n\nSUGGESTED BULLET REWRITES\n"
            + "\n".join(unmatched)
            + "\n"
        )

    return improved_text


def _categorize_skills_for_generation(raw_skills: list[str]) -> dict[str, list[str]]:
    """Map flat skill list into required generation categories."""
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
    raw_items = [line.lstrip("-•*\t ").strip() for line in normalized.splitlines() if line.strip()]

    label_only_tokens = set(_SKILL_CATEGORY_LABELS)
    label_only_tokens.add("business & management")

    def _canonical_label(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    skills: list[str] = []
    seen: set[str] = set()
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


def _resume_data_to_generation_input(resume_data: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    """Convert parsed resume payload into structured input expected by generate mode."""
    entities = cast(dict[str, Any], resume_data.get("entities", {}))
    sections = cast(dict[str, Any], resume_data.get("sections", {}))
    contact = cast(dict[str, Any], entities.get("contact", {}))

    def _extract_candidate_name() -> str:
        direct_name = str(contact.get("name") or "").strip()
        if direct_name:
            return direct_name

        raw_text = str(resume_data.get("raw_text", "") or "")
        for raw_line in raw_text.splitlines()[:8]:
            line = raw_line.strip()
            if not line:
                continue
            # Skip contact lines and noisy metadata rows.
            if re.search(r"@|https?://|www\\.|\\+?\\d[\\d\\s().-]{7,}", line, re.IGNORECASE):
                continue
            if len(line.split()) > 5:
                continue
            if any(token in line.lower() for token in ("linkedin", "github", "portfolio", "email")):
                continue
            return line

        cleaned_fallback = str(fallback_name or "").replace("_", " ").replace("-", " ").strip()
        return cleaned_fallback or "Candidate"

    name = _extract_candidate_name()

    parsed_experience = entities.get("experience", [])

    def _is_noisy_experience_line(value: str) -> bool:
        line = str(value or "").strip()
        if not line:
            return False
        if line.startswith(("-", "•", "*")):
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

    experience: list[dict[str, Any]] = []
    if isinstance(parsed_experience, list):
        for item in parsed_experience:
            if not isinstance(item, dict):
                continue
            bullets_raw = item.get("bullets", [])
            bullets: list[str] = []
            if isinstance(bullets_raw, list):
                bullets = [str(b).strip() for b in bullets_raw if str(b).strip()][:4]
            company = str(
                item.get("company")
                or item.get("company_name")
                or item.get("organization")
                or item.get("employer")
                or ""
            ).strip()
            experience.append(
                {
                    "title": str(item.get("role") or item.get("title") or "Professional Experience"),
                    "company": company,
                    "duration": str(item.get("duration") or "").strip(),
                    "bullets": bullets,
                }
            )

    def _extract_experience_from_section_text(section_text: str) -> list[dict[str, Any]]:
        import re

        lines = [line.strip() for line in str(section_text or "").splitlines() if line.strip()]
        date_range_pattern = re.compile(
            r"^(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*[-–]\s*(?:present|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})$",
            re.IGNORECASE,
        )
        rows: list[dict[str, Any]] = []
        i = 0
        while i < len(lines):
            title = lines[i]
            if i + 1 >= len(lines) or not date_range_pattern.match(lines[i + 1]):
                i += 1
                continue
            duration = lines[i + 1]
            company_text = lines[i + 2] if i + 2 < len(lines) and not date_range_pattern.match(lines[i + 2]) else ""
            location_text = lines[i + 3] if i + 3 < len(lines) and not date_range_pattern.match(lines[i + 3]) else ""

            if _is_noisy_experience_line(company_text):
                company_text = ""
            if _is_noisy_experience_line(location_text):
                location_text = ""

            row: dict[str, Any] = {
                "title": title,
                "company": company_text,
                "duration": duration,
                "bullets": [],
            }
            if location_text:
                row["location"] = location_text
            rows.append(row)
            i += 4 if location_text else 3
        return rows

    section_experience = _extract_experience_from_section_text(str(sections.get("experience") or ""))
    if section_experience and _section_experience_is_usable(section_experience) and (
        len(section_experience) > len(experience) or any(not str(r.get("company", "")).strip() for r in experience)
    ):
        existing_by_title = {
            str(row.get("title", "")).strip().lower(): row
            for row in experience
            if str(row.get("title", "")).strip()
        }
        merged_exp: list[dict[str, Any]] = []
        for row in section_experience:
            key = str(row.get("title", "")).strip().lower()
            source = existing_by_title.get(key, {})
            source_bullets = source.get("bullets", []) if isinstance(source, dict) else []
            hydrated = dict(row)
            hydrated["bullets"] = [str(b).strip() for b in source_bullets if str(b).strip()][:4] if isinstance(source_bullets, list) else []
            merged_exp.append(hydrated)
        experience = merged_exp

    # Preserve source truth: if resume has no experience section/data, keep it empty.

    def _extract_projects_from_lines(project_lines: list[str], max_projects: int = 20) -> list[dict[str, Any]]:
        import re

        projects_out: list[dict[str, Any]] = []
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
                bullets_out = list(current_bullets) if current_bullets else [m for m in current_meta[:2] if m]
                technologies_out: list[str] = []
                for meta in current_meta:
                    if "," in meta:
                        cleaned_meta = re.sub(r"^technologies\s*:\s*", "", meta, flags=re.IGNORECASE)
                        technologies_out.extend([part.strip() for part in cleaned_meta.split(",") if part.strip()])
                projects_out.append(
                    {
                        "name": parsed_name,
                        "duration": parsed_duration,
                        "bullets": bullets_out[:4],
                        "technologies": technologies_out[:8],
                    }
                )
            current_name = ""
            current_bullets = []
            current_meta = []

        for raw in project_lines:
            line = str(raw).strip()
            if not line:
                continue
            is_year = bool(_PROJECT_DATE_RANGE_PATTERN.fullmatch(line)) or (
                bool(year_pattern.search(line)) and len(line.split()) <= 3
            )
            is_bullet = line.startswith(("-", "•", "*")) or bool(bullet_verb_pattern.match(line))
            if is_bullet:
                bullet = line.lstrip("-•* ").strip()
                if bullet:
                    current_bullets.append(bullet)
                continue
            if is_year:
                if current_name:
                    current_meta.append(line)
                continue
            if current_name:
                if current_bullets:
                    flush_current()
                    if len(projects_out) >= max_projects:
                        break
                    current_name = line
                    continue
                current_meta.append(line)
                continue
            current_name = line

        if len(projects_out) < max_projects and current_name:
            flush_current()

        return projects_out[:max_projects]

    parsed_projects = entities.get("projects", [])
    projects: list[dict[str, Any]] = []
    if isinstance(parsed_projects, list) and parsed_projects and all(isinstance(item, str) for item in parsed_projects):
        projects = _extract_projects_from_lines([str(item) for item in parsed_projects], max_projects=20)
    elif isinstance(parsed_projects, list):
        for item in parsed_projects:
            if not isinstance(item, dict):
                continue
            proj_bullets_raw = item.get("bullets", [])
            proj_bullets: list[str] = []
            if isinstance(proj_bullets_raw, list):
                proj_bullets = [str(b).strip() for b in proj_bullets_raw if str(b).strip()][:4]
            if not proj_bullets and item.get("description"):
                proj_bullets = [str(item.get("description", "")).strip()]
            if not proj_bullets and item.get("text"):
                maybe_text = str(item.get("text", "")).strip()
                if maybe_text:
                    proj_bullets = [maybe_text]
            technologies = item.get("technologies", [])
            tech_list = [str(t).strip() for t in technologies] if isinstance(technologies, list) else []
            raw_name = str(item.get("name") or item.get("title") or item.get("project") or item.get("text") or "").strip()
            explicit_duration = str(item.get("duration") or item.get("date") or item.get("dates") or "").strip()
            if "|" in raw_name:
                parts = [p.strip() for p in raw_name.split("|") if p.strip()]
                if parts:
                    raw_name = parts[0]
                if len(parts) > 1 and not tech_list:
                    tech_list = [p.strip() for p in re.split(r",|/", parts[1]) if p.strip()]
            raw_name, derived_duration = _split_project_name_and_duration(raw_name)
            project_duration = explicit_duration or derived_duration
            projects.append(
                {
                    "name": raw_name or "Project",
                    "duration": project_duration,
                    "bullets": proj_bullets,
                    "technologies": [t for t in tech_list if t],
                }
            )

    if not projects:
        project_section_text = str(sections.get("projects") or sections.get("project") or "")
        fallback_projects = _extract_projects_from_lines(project_section_text.splitlines(), max_projects=20)
        projects = fallback_projects if fallback_projects else [{"name": "Project", "bullets": [], "technologies": []}]

    def _collect_skill_names() -> list[str]:
        collected: list[str] = []

        raw_skills = entities.get("skills", [])
        if isinstance(raw_skills, dict):
            category_label_tokens = set(_SKILL_CATEGORY_LABELS)
            for key, value in raw_skills.items():
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
                    for nested in value:
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
        elif isinstance(raw_skills, list):
            for item in raw_skills:
                if isinstance(item, dict):
                    candidate = str(item.get("name") or item.get("skill") or "").strip()
                    if candidate:
                        collected.append(candidate)
                else:
                    skill_text = str(item).strip()
                    if skill_text:
                        collected.append(skill_text)

        skill_names = entities.get("skill_names", [])
        if isinstance(skill_names, list):
            collected.extend(str(s).strip() for s in skill_names if str(s).strip())

        # De-duplicate while preserving order.
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
    raw_skills = section_skills if section_skills else _collect_skill_names()
    cleaned_skills: list[str] = []
    for skill in raw_skills:
        canonical = re.sub(r"[^a-z0-9]+", " ", str(skill).lower()).strip()
        if canonical in _SKILL_CATEGORY_LABELS:
            continue
        cleaned_skills.append(str(skill))

    skills_map = _categorize_skills_for_generation(cleaned_skills)

    education = str(sections.get("education") or entities.get("education") or "Education details available on request").strip()
    certifications_raw = entities.get("certifications", [])
    certifications = []
    if isinstance(certifications_raw, list):
        for item in certifications_raw:
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

    target_role = ""
    if experience:
        target_role = str(experience[0].get("title", "")).strip()
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
        "skills": skills_map,
        "projects": projects,
        "experience": experience,
        "certifications": certifications[:5],
        "extra_context": "Generated from uploaded resume for ATS optimization.",
    }


def extract_resume_bullets(text: str) -> list[str]:
    """Extract resume bullets using improved state-based multi-line aggregation.
    
    Rules:
    - Start new bullet on lines beginning with ●, •, or -
    - Stop bullet when encountering year patterns (19XX-20XX) which indicate dates/metadata
    - Strip residual location/company metadata from bullets
    """
    import re
    
    bullets: list[str] = []
    current_bullet: list[str] = []
    pending_bullet_start = False

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for line in lines:
        # Check if line contains a year pattern (date indicator)
        has_year_pattern = bool(re.search(r"\b(19\d{2}|20\d{2})\b", line))
        
        # Case 1: bullet marker on its own line.
        if line in {"●", "•", "-"}:
            if current_bullet:
                # Clean and save the bullet
                bullet_text = _clean_bullet_text(" ".join(current_bullet))
                if bullet_text:
                    bullets.append(bullet_text)
                current_bullet = []
            pending_bullet_start = True
            continue

        # Case 2: new bullet starts inline.
        if line.startswith(("●", "•", "-")):
            if current_bullet:
                # Clean and save the previous bullet
                bullet_text = _clean_bullet_text(" ".join(current_bullet))
                if bullet_text:
                    bullets.append(bullet_text)
            # Extract bullet content and clean metadata
            bullet_content = line.lstrip("●•- ").strip()
            current_bullet = [_clean_bullet_text(bullet_content)]
            # Keep only the clean part, discard if it's empty
            if current_bullet[0]:
                current_bullet = [current_bullet[0]]
            else:
                current_bullet = []
            pending_bullet_start = False
            continue

        # Case 2b: previous line had only a bullet marker; this starts the new bullet text.
        if pending_bullet_start:
            current_bullet = [line]
            pending_bullet_start = False
            continue

        # Case 3a: Stop accumulating if we hit a year pattern (indicates new section/metadata)
        if current_bullet and has_year_pattern:
            bullet_text = _clean_bullet_text(" ".join(current_bullet))
            if bullet_text:
                bullets.append(bullet_text)
            current_bullet = []
            continue

        # Case 3b: continuation line for current bullet.
        if current_bullet:
            current_bullet.append(line)

    if current_bullet:
        bullet_text = _clean_bullet_text(" ".join(current_bullet))
        if bullet_text:
            bullets.append(bullet_text)

    return bullets


def _clean_bullet_text(text: str) -> str:
    """Clean bullet text by removing residual metadata like locations and company names.
    
    Example: "Approved technical decisions ... Polyhire, London" -> "Approved technical decisions"
    """
    if not text:
        return ""
    
    import re
    
    # Pattern: "... CompanyName, CityName" or "Text ... Location" at the end
    # Remove trailing patterns that look like company/location info
    # Match: CapitalizedWord(s), CityName (e.g., "Polyhire, London")
    text = re.sub(r'\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*,\s+[A-Z][a-zA-Z]+\s*$', '', text)
    
    # Also remove standalone location patterns at the end (e.g., "London, UK")
    text = re.sub(r'\s+[A-Z][a-zA-Z]+,?\s+[A-Z]{2}\s*$', '', text)
    
    # Remove trailing "..." or "…"
    text = re.sub(r'\s+\.{2,}|…\s*$', '', text)
    
    return text.strip()


def _display_skill_alignment(result: dict[str, Any]) -> None:
    """Display skill alignment results in Streamlit."""
    matched = cast(list[dict[str, Any]], result.get("matched", []))
    weak = cast(list[dict[str, Any]], result.get("weak", []))
    missing = cast(list[dict[str, Any]], result.get("missing", []))
    insights = cast(list[Any], result.get("insights", []))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Matched Skills", len(matched))
    with col2:
        st.metric("⚠️ Weak Matches", len(weak))
    with col3:
        st.metric("❌ Missing Skills", len(missing))
    
    tab1, tab2, tab3, tab4 = st.tabs(["✅ Matched", "⚠️ Weak", "❌ Missing", "💡 Insights"])
    
    with tab1:
        if matched:
            for item in matched[:10]:
                jd_skill = item.get("jd_skill", "")
                resume_skill = item.get("resume_skill", "")
                score = item.get("weighted_score", 0)
                st.write(f"**⭐ {jd_skill}** (found: *{resume_skill}*) — confidence: {score:.1%}")
            if len(matched) > 10:
                st.caption(f"... and {len(matched) - 10} more")
        else:
            st.info("No matched skills")
    
    with tab2:
        if weak:
            for item in weak[:10]:
                jd_skill = item.get("jd_skill", "")
                resume_skill = item.get("resume_skill", "")
                score = item.get("weighted_score", 0)
                importance = item.get("jd_importance", 0)
                st.write(
                    f"**{jd_skill}** (found: *{resume_skill}*) — "
                    f"confidence: {score:.1%}, importance: {importance:.1%}"
                )
            if len(weak) > 10:
                st.caption(f"... and {len(weak) - 10} more")
        else:
            st.info("No weak matches")
    
    with tab3:
        if missing:
            for item in missing[:10]:
                jd_skill = item.get("jd_skill", "")
                importance = item.get("jd_importance", 0)
                st.write(f"❌ **{jd_skill}** — importance: {importance:.1%}")
            if len(missing) > 10:
                st.caption(f"... and {len(missing) - 10} more")
        else:
            st.success("All required skills are present!")

    with tab4:
        if insights:
            for insight in insights[:5]:
                if isinstance(insight, dict):
                    insight_map = cast(dict[str, Any], insight)
                    message = insight_map.get("suggestion")
                    if not message:
                        message = insight_map.get("issue")
                    if not message:
                        message = insight_map.get("fix")
                    if not message:
                        message = "No suggestion available"
                    st.info(str(message))
                else:
                    st.info(str(insight))
        else:
            st.info("No insights available")


def _display_resume_only_skill_alignment(result: dict[str, Any], role: str) -> None:
    """Display resume-only skill alignment with recommendation-first language."""
    matched = cast(list[dict[str, Any]], result.get("matched", []))
    weak = cast(list[dict[str, Any]], result.get("weak", []))
    recommended = cast(list[dict[str, Any]], result.get("recommended_skills", []))
    insights = cast(list[Any], result.get("insights", []))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Matched Skills", len(matched))
    with col2:
        st.metric("⚠️ Developing Skills", len(weak))
    with col3:
        st.metric(f"💡 Suggested Skills for {role.title()}", len(recommended))

    tab1, tab2, tab3, tab4 = st.tabs(["✅ Matched", "⚠️ Developing", "💡 Suggested", "🧭 Insights"])

    with tab1:
        if matched:
            for item in matched[:10]:
                st.write(f"**⭐ {item.get('jd_skill', '')}** (found: *{item.get('resume_skill', '')}*)")
        else:
            st.info("No strong benchmark matches found yet")

    with tab2:
        if weak:
            for item in weak[:10]:
                st.write(
                    f"**{item.get('jd_skill', '')}** (found: *{item.get('resume_skill', '')}*)"
                )
        else:
            st.info("No developing skills")

    with tab3:
        if recommended:
            for item in recommended[:10]:
                st.write(f"• {item.get('jd_skill', '')}")
        else:
            st.success("Skill coverage is strong for this benchmark profile")

    with tab4:
        if insights:
            for insight in insights[:8]:
                st.info(str(insight))
        else:
            st.info("No additional insights")


def _display_experience_alignment(result: dict[str, Any]) -> None:
    """Display experience alignment results in Streamlit."""
    covered = cast(list[dict[str, Any]], result.get("covered", []))
    partial = cast(list[dict[str, Any]], result.get("partial", []))
    missing = cast(list[dict[str, Any]], result.get("missing", []))
    insights = cast(list[dict[str, Any]], result.get("insights", []))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Covered", len(covered))
    with col2:
        st.metric("🟡 Partial", len(partial))
    with col3:
        st.metric("Missing Role Evidence", len(missing))
    
    tab1, tab2, tab3, tab4 = st.tabs(["✅ Covered", "🟡 Partial", "Missing Role Evidence", "💡 Insights"])
    
    with tab1:
        if covered:
            for item in covered[:8]:
                resp = item.get("jd_responsibility", "")[:80]
                bullet = item.get("evidence_bullet", "")[:80]
                score = item.get("weighted_score", 0)
                st.markdown(f"**Responsibility**: *{resp}...*")
                st.markdown(f"**Evidence**: *{bullet}...*")
                st.write(f"Similarity: {score:.1%}")
                st.divider()
        else:
            st.info("No covered responsibilities")
    
    with tab2:
        if partial:
            for item in partial[:8]:
                resp = item.get("jd_responsibility", "")[:80]
                score = item.get("weighted_score", 0)
                st.markdown(f"**Responsibility**: *{resp}...*")
                st.write(f"Coverage: {score:.1%} (partial match)")
                st.divider()
        else:
            st.info("No partial matches")
    
    with tab3:
        st.caption("Missing role evidence means expected responsibilities were not strongly proven by resume bullets. It does not mean the resume has no work experience.")
        if missing:
            for item in missing:
                resp = item.get("jd_responsibility", "")
                st.write(f"• {resp}")
        else:
            st.success("All responsibilities covered!")
    
    with tab4:
        if insights:
            for insight in insights[:5]:
                st.info(insight.get("suggestion", "No suggestion available"))
        else:
            st.info("No insights available")


def _display_gap_analysis(result: dict[str, Any]) -> None:
    """Display gap analysis results in Streamlit."""
    critical = cast(list[dict[str, Any]], result.get("critical_gaps", []))
    moderate = cast(list[dict[str, Any]], result.get("moderate_gaps", []))
    low = cast(list[dict[str, Any]], result.get("low_priority", []))
    insights = cast(list[dict[str, Any]], result.get("insights", []))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔴 Critical", len(critical))
    with col2:
        st.metric("🟡 Moderate", len(moderate))
    with col3:
        st.metric("🟢 Low Priority", len(low))
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔴 Critical", "🟡 Moderate", "🟢 Low Priority", "💡 Insights"])
    
    with tab1:
        if critical:
            for gap in critical:
                skill = gap.get("skill", "")
                impact = gap.get("impact", "medium")
                reason = gap.get("reason", "")
                st.markdown(f"### {skill}")
                st.write(f"**Impact**: {impact}")
                st.write(f"**Reason**: {reason}")
                st.divider()
        else:
            st.success("No critical gaps!")
    
    with tab2:
        if moderate:
            for gap in moderate:
                skill = gap.get("skill", "")
                impact = gap.get("impact", "medium")
                st.markdown(f"### {skill}")
                st.write(f"**Impact**: {impact}")
                st.divider()
        else:
            st.info("No moderate gaps")
    
    with tab3:
        if low:
            for gap in low:
                skill = gap.get("skill", "")
                st.markdown(f"• {skill}")
        else:
            st.info("No low-priority gaps")
    
    with tab4:
        if insights:
            for insight in insights[:10]:
                col_left, col_right = st.columns([1, 2])
                with col_left:
                    st.write(f"**Issue**: {insight.get('issue', '')}")
                with col_right:
                    st.write(f"**Why**: {insight.get('why_it_matters', '')}")
        else:
            st.info("No insights available")


def _display_ats_score(result: dict[str, Any]) -> None:
    """Display ATS scoring results in Streamlit."""
    decision = str(result.get("decision", "BORDERLINE") or "BORDERLINE").upper()
    confidence_score = float(result.get("confidence", 0.0) or 0.0)
    ats_score = float(result.get("ats_score", 0.0) or 0.0)
    score_100 = int(result.get("score", round(ats_score * 100)))
    percentile_raw = result.get("percentile")
    percentile = float(percentile_raw) if isinstance(percentile_raw, (int, float)) else None
    reasons = cast(list[Any], result.get("reasons", []))
    fail_reasons = cast(list[Any], result.get("fail_reasons", []))
    components = cast(dict[str, float], result.get("components", {}))
    penalties = cast(dict[str, Any], result.get("penalties", {}))
    confidence = cast(dict[str, float], result.get("module_confidence", {}))
    rule_engine = cast(dict[str, Any], result.get("rule_engine", {}))
    rule_details = cast(dict[str, Any], rule_engine.get("details", {}))
    
    # Primary decision display
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "ATS Decision",
            decision,
            delta="Proceed" if decision == "PASS" else ("Review manually" if decision == "BORDERLINE" else "Reject")
        )
    with col2:
        score_delta = f"Top {int(percentile)}%" if percentile is not None else "Continuous ranking"
        st.metric("ATS Score", f"{score_100}/100", delta=score_delta)
    with col3:
        st.metric("Decision Confidence", f"{confidence_score:.0%}")

    if reasons:
        st.write("**Decision Reasons**")
        for reason in reasons[:5]:
            st.write(f"- {reason}")
    if fail_reasons:
        st.write("**Fail Reasons**")
        for reason in fail_reasons[:5]:
            st.write(f"- {reason}")
    
    # Component breakdown
    with col2:
        st.write("**Component Scores**")
        for component, value in components.items():
            st.write(f"• {component.replace('_', ' ').title()}: {value:.1%}")
    
    # Penalties info
    with col3:
        st.write("**Penalty Info**")
        penalty_applied = penalties.get("critical_missing_applied", False)
        penalty_factor = penalties.get("penalty_factor", 1.0)
        st.write(f"• Applied: {penalty_applied}")
        if penalty_applied:
            st.write(f"• Factor: {penalty_factor:.1%}")
            st.write(f"• Reason: {penalties.get('reason', 'unknown')}")
    
    # Confidence scores
    st.write("**Model Confidence**")
    if confidence:
        conf_cols = st.columns(len(confidence))
        for i, (metric_name, value) in enumerate(confidence.items()):
            with conf_cols[i]:
                display_name = metric_name.replace("_", " ").replace(" confidence", "").title()
                st.metric(display_name, f"{value:.1%}")
    else:
        st.info("No confidence data available")

    # Score ceiling and bottleneck explainer
    st.write("**Score Ceiling Explainer**")
    evidence = cast(dict[str, Any], result.get("evidence", {}))
    skill_evidence = cast(dict[str, Any], evidence.get("skill_alignment", {}))
    exp_evidence = cast(dict[str, Any], evidence.get("experience_alignment", {}))
    recommended_skills = cast(list[Any], evidence.get("recommended_skills", []))
    weak_evidence_skills = cast(list[Any], evidence.get("weak_evidence_skills", []))

    skill_score = float(components.get("skill_score", 0.0) or 0.0)
    impact_score = float(components.get("impact_score", 0.0) or 0.0)
    experience_score = float(components.get("experience_score", 0.0) or 0.0)

    partial_count = len(cast(list[Any], exp_evidence.get("partial", [])))
    missing_count = len(cast(list[Any], skill_evidence.get("missing", [])))

    bottlenecks: list[str] = []
    projected_uplift = 0.0

    if skill_score < 0.45:
        bottlenecks.append("Skill evidence is currently a hard cap on total ATS.")
        projected_uplift += 0.08
    if impact_score < 0.40:
        bottlenecks.append("Impact is low because bullets are descriptive instead of measurable.")
        projected_uplift += 0.10
    if missing_count >= 2:
        bottlenecks.append("Missing trigger skills are applying direct penalty and reducing skill confidence.")
        projected_uplift += 0.06
    if len(weak_evidence_skills) > 0:
        bottlenecks.append("Claimed skills with weak proof are being discounted by cross-signal checks.")
        projected_uplift += 0.04
    if partial_count >= 2 and experience_score < 0.7:
        bottlenecks.append("Experience is close, but partial responsibilities still limit conversion to full matches.")
        projected_uplift += 0.03

    current_ceiling = min(0.95, ats_score + projected_uplift)
    ceil_col1, ceil_col2 = st.columns(2)
    with ceil_col1:
        st.metric("Current ATS", f"{ats_score:.1%}")
    with ceil_col2:
        st.metric("Estimated Ceiling (after fixes)", f"{current_ceiling:.1%}", delta=f"+{projected_uplift:.1%}")

    if bottlenecks:
        for item in bottlenecks:
            st.warning(item)
    else:
        st.success("No major scoring bottleneck detected. Focus on incremental bullet quality improvements.")

    if recommended_skills:
        st.write("**High-impact missing skills to add with proof**")
        for raw_skill in recommended_skills[:5]:
            skill_name = str(raw_skill).strip()
            if not skill_name:
                continue
            lowered = skill_name.lower()
            is_critical = lowered in {"docker", "kubernetes", "pytorch", "tensorflow", "model deployment"}
            skill_uplift = 0.015 if is_critical else 0.008
            st.write(f"• {skill_name} (estimated ATS uplift: +{skill_uplift:.1%} when supported by bullets)")

    if weak_evidence_skills:
        st.write("**Skills with weak evidence (rewrite bullets to include stack + outcome)**")
        for raw_skill in weak_evidence_skills[:5]:
            skill_name = str(raw_skill).strip()
            if not skill_name:
                continue
            st.write(
                f"• {skill_name}: Example rewrite -> Built feature using {skill_name} that improved latency by 25% on 10K+ requests/day."
            )

    if impact_score < 0.5:
        st.write("**Impact bullet uplift estimate**")
        st.write("• Rewrite 2 bullets with measurable outcomes (%/$/scale) to target an estimated +3% to +6% ATS increase.")
        st.write("• Anchor project pattern: PyTorch + Docker + deployment + traffic scale + latency/accuracy outcome.")

    # Rule violations and fixes panel
    st.write("**Rule Violations & Fixes**")
    if not rule_engine:
        st.info("Rule-engine diagnostics are not available for this result.")
    else:
        format_rule_score = float(rule_engine.get("format_rule_score", 0.0) or 0.0)
        language_score = float(rule_engine.get("language_quality_score", 0.0) or 0.0)

        rule_col1, rule_col2 = st.columns(2)
        with rule_col1:
            st.metric("Format Rules", f"{format_rule_score:.1%}")
        with rule_col2:
            st.metric("Language Quality", f"{language_score:.1%}")

        violations: list[str] = []

        section_presence = float(rule_details.get("section_presence_score", 1.0) or 1.0)
        section_order = float(rule_details.get("section_order_score", 1.0) or 1.0)
        bullet_limit = float(rule_details.get("bullet_limit_score", 1.0) or 1.0)
        per_job = float(rule_details.get("per_job_bullet_score", 1.0) or 1.0)
        single_column = float(rule_details.get("single_column_score", 1.0) or 1.0)

        action_ratio = float(rule_details.get("action_verb_ratio", 1.0) or 1.0)
        quantified_ratio = float(rule_details.get("quantified_bullet_ratio", 1.0) or 1.0)
        weak_ratio = float(rule_details.get("weak_phrase_ratio", 0.0) or 0.0)
        pronoun_hits = int(rule_details.get("pronoun_hits", 0) or 0)
        total_bullets = int(rule_details.get("total_bullets", 0) or 0)

        if section_presence < 0.8:
            violations.append("Missing key sections. Add Experience, Projects, Education, Skills, and Certifications headings.")
        if section_order < 0.8:
            violations.append("Section order is suboptimal. Reorder to Experience -> Projects -> Skills -> Education -> Certifications.")
        if bullet_limit < 0.85:
            violations.append(f"Too many bullets ({total_bullets}). Keep total bullets around 20 or fewer for ATS readability.")
        if per_job < 0.8:
            violations.append("Bullet count per job is inconsistent. Target 3 to 4 bullets per role.")
        if single_column < 0.9:
            violations.append("Layout may include tables, icons, or multi-column formatting. Use a plain single-column structure.")
        if action_ratio < 0.6:
            violations.append("Low action-verb usage. Start more bullets with strong action verbs like Built, Led, or Optimized.")
        if quantified_ratio < 0.5:
            violations.append("Few quantified achievements. Add metrics, percentages, or scale indicators in more bullets.")
        if weak_ratio > 0.2:
            violations.append("Weak phrasing detected (for example 'worked on' or 'responsible for'). Rewrite with concrete outcomes.")
        if pronoun_hits > 0:
            violations.append("First-person pronouns found. Remove I/we/my/our from bullets for ATS style consistency.")

        quality_warnings = rule_details.get("quality_warnings", [])
        if isinstance(quality_warnings, list):
            warning_items = cast(list[Any], quality_warnings)
            for warning in warning_items:
                warning_text = str(warning).strip()
                if warning_text:
                    violations.append(f"Parser warning: {warning_text}")

        if violations:
            for item in violations:
                st.error(item)
        else:
            st.success("No major ATS rule violations detected.")
    
    # Details expander
    with st.expander("📊 Full Details"):
        st.json(result)


def parse_resume_section():
    """Handle resume parsing."""
    st.header("Resume Parser")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx", "txt", "doc"],
            help="Supported formats: PDF, DOCX, TXT, DOC"
        )
    
    with col2:
        st.metric("Supported Formats", "5+", "PDF, DOCX, TXT, RTF, MD")
    
    if uploaded_file:
        try:
            # Save temp file
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(uploaded_file.getbuffer())
            
            # Parse
            with st.spinner("🔄 Parsing resume..."):
                parser = ResumeParser()
                result = parser.parse_file(temp_path, enable_section_llm=False)
                output = result.to_dict()
            
            # Display metadata
            st.success("✅ Resume parsed successfully!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                completeness = output["metadata"].get("completeness_score", 0)
                st.metric("Completeness", f"{completeness:.0%}")
            with col2:
                confidence = output["metadata"].get("parsing_confidence", 0)
                st.metric("Confidence", f"{confidence:.0%}")
            with col3:
                entities = output.get("entities", {})
                skill_count = len(entities.get("skills", []))
                st.metric("Skills Found", skill_count)

            metadata_for_diag = cast(dict[str, Any], output.get("metadata", {}))
            _render_resume_parse_diagnostics(metadata_for_diag, heading="Resume Parser Diagnostics")
            
            # Tabs for organized display
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["📧 Contact", "💼 Experience", "🎯 Skills", "🎓 Education", "📊 Details"]
            )
            
            with tab1:
                contact = entities.get("contact", {})
                if contact:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Name", value=contact.get("name", "N/A"), disabled=True)
                        st.text_input("Email", value=contact.get("email", "N/A"), disabled=True)
                    with col2:
                        st.text_input("Phone", value=contact.get("phone", "N/A"), disabled=True)
                        st.text_input("LinkedIn", value=contact.get("linkedin", "N/A"), disabled=True)
                else:
                    st.warning("No contact information found")
            
            with tab2:
                experience = entities.get("experience", [])
                if experience:
                    for exp in experience:
                        with st.expander(
                            f"**{exp.get('role', 'N/A')}** @ {exp.get('company', 'N/A')}"
                        ):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Duration:** {exp.get('duration', 'N/A')}")
                            with col2:
                                st.write(f"**End Date:** {exp.get('end_date', 'N/A')}")
                            
                            if exp.get("bullets"):
                                st.write("**Key Achievements:**")
                                for bullet in exp["bullets"]:
                                    st.write(f"• {bullet}")
                            
                            if exp.get("skills_inferred"):
                                st.write("**Inferred Skills:**")
                                skills = exp["skills_inferred"]
                                if isinstance(skills, list):
                                    skill_items = [str(item) for item in cast(list[Any], skills)]
                                    st.write(", ".join(skill_items))
                                else:
                                    st.write(str(skills))
                else:
                    st.warning("No experience entries found")
            
            with tab3:
                skills = entities.get("skills", [])
                if skills:
                    # Sort by confidence and show top 20
                    sorted_skills = sorted(
                        skills,
                        key=_skill_confidence,
                        reverse=True
                    )[:20]
                    
                    for skill_obj in sorted_skills:
                        if isinstance(skill_obj, dict):
                            skill_map = cast(dict[str, Any], skill_obj)
                            st.markdown(format_skill(skill_map))
                        else:
                            st.markdown(f"🟡 **{_skill_display(skill_obj)}**")
                        
                        # Show skill details if requested
                        skill_obj_value: object = cast(object, skill_obj)
                        skill_key = _skill_name(skill_obj_value) or _skill_display(skill_obj_value)
                        if st.checkbox("Show details", key=f"skill_{skill_key}"):
                            if isinstance(skill_obj, dict):
                                skill_map = cast(dict[str, Any], skill_obj)
                                det = float(skill_map.get("confidence", 0) or 0)
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Confidence", f"{det:.2f}")
                                with col2:
                                    st.metric("Frequency", int(skill_map.get("frequency", 0) or 0))
                                with col3:
                                    sources = skill_map.get("source", [])
                                    source_count = len(cast(list[Any], sources)) if isinstance(sources, list) else 0
                                    st.metric("Sources", source_count)

                                penalty_reasons = skill_map.get("penalty_reasons", [])
                                if isinstance(penalty_reasons, list) and penalty_reasons:
                                    st.warning(
                                        f"⚠️ Penalties: {', '.join(str(item) for item in cast(list[Any], penalty_reasons))}"
                                    )
                            else:
                                st.info("Detailed scoring not available for string-only skill entries.")
                else:
                    st.warning("No skills found")
            
            with tab4:
                education = entities.get("education", [])
                if education:
                    for edu in education:
                        with st.expander(
                            f"**{edu.get('degree', 'N/A')}** in {edu.get('field', 'N/A')}"
                        ):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**School:** {edu.get('school', 'N/A')}")
                            with col2:
                                st.write(f"**Year:** {edu.get('year', 'N/A')}")
                else:
                    st.info("No education entries found")
            
            with tab5:
                st.json(output["metadata"])

            metadata_map = cast(dict[str, Any], output.get("metadata", {}))
            entities_map = cast(dict[str, Any], output.get("entities", {}))
            experience_items = entities_map.get("experience", [])
            skills_items = entities_map.get("skills", [])
            raw_text = str(output.get("raw_text", "") or "")

            resume_checks = [
                ("Output payload", isinstance(output, dict), "Resume parser returned a dictionary payload."),
                (
                    "Metadata confidence",
                    "parsing_confidence" in metadata_map,
                    "Metadata contains parsing confidence score.",
                ),
                (
                    "Entities object",
                    isinstance(entities_map, dict),
                    "Entities object is available for downstream engines.",
                ),
                (
                    "Experience extraction",
                    isinstance(experience_items, list),
                    "Experience section is list-typed for alignment stages.",
                ),
                (
                    "Skills extraction",
                    isinstance(skills_items, list),
                    "Skills are available as list for matching.",
                ),
                (
                    "Raw text extraction",
                    len(raw_text.strip()) > 0,
                    "Raw text was extracted and is non-empty.",
                ),
            ]
            _render_layer_tests("resume_parser", "Resume Parser Layer Tests", resume_checks)
            
            # Download section
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                json_str = json.dumps(output, indent=2)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_str,
                    file_name="parsed_resume.json",
                    mime="application/json"
                )
            
            with col2:
                if show_json:
                    st.json(output)
        
        except Exception as e:
            st.error(f"❌ Error parsing resume: {str(e)}")


def parse_jd_section():
    """Handle job description parsing."""
    st.header("Job Description Parser")
    
    # Upload or paste JD
    jd_input = st.radio("How would you like to input the JD?", ["Upload File", "Paste Text"])
    
    jd_text = ""
    
    if jd_input == "Upload File":
        uploaded_file = st.file_uploader(
            "Upload job description",
            type=["txt"],
            key="jd_upload"
        )
        if uploaded_file:
            jd_text = uploaded_file.getvalue().decode("utf-8")
    else:
        jd_text = st.text_area(
            "Paste job description here",
            height=300,
            placeholder="Paste the job description text..."
        )
    
    if jd_text:
        try:
            with st.spinner("🔄 Analyzing job description..."):
                result = parse_job_description(jd_text)
            
            st.success("✅ Job description parsed successfully!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Seniority Level", result.get("seniority", "N/A"))
            with col2:
                st.metric("Required Skills", len(result.get("skills_required", [])))
            with col3:
                st.metric("Optional Skills", len(result.get("skills_optional", [])))
            
            tab1, tab2, tab3, tab4 = st.tabs(
                ["🔴 Required Skills", "🟡 Optional Skills", "✅ Responsibilities", "📊 Full Analysis"]
            )
            
            with tab1:
                skills = result.get("skills_required", [])
                if skills:
                    for skill in skills[:15]:
                        st.write(f"• **{skill}**")
                    if len(skills) > 15:
                        st.info(f"... and {len(skills) - 15} more")
                else:
                    st.info("No required skills found")
            
            with tab2:
                skills = result.get("skills_optional", [])
                if skills:
                    for skill in skills[:15]:
                        st.write(f"• {skill}")
                    if len(skills) > 15:
                        st.info(f"... and {len(skills) - 15} more")
                else:
                    st.info("No optional skills found")
            
            with tab3:
                responsibilities = result.get("responsibilities", [])
                if responsibilities:
                    for resp in responsibilities[:10]:
                        st.write(f"• {resp}")
                    if len(responsibilities) > 10:
                        st.info(f"... and {len(responsibilities) - 10} more")
                else:
                    st.info("No responsibilities found")
            
            with tab4:
                st.json(result)

            jd_checks = [
                ("Output payload", isinstance(result, dict), "JD parser returned a dictionary payload."),
                (
                    "Seniority detected",
                    bool(str(result.get("seniority", "")).strip()),
                    "Seniority value is present.",
                ),
                (
                    "Required skills list",
                    isinstance(result.get("skills_required", []), list),
                    "Required skills are list-typed.",
                ),
                (
                    "Optional skills list",
                    isinstance(result.get("skills_optional", []), list),
                    "Optional skills are list-typed.",
                ),
                (
                    "Responsibilities list",
                    isinstance(result.get("responsibilities", []), list),
                    "Responsibilities are list-typed for experience matching.",
                ),
                (
                    "Importance weights",
                    isinstance(result.get("importance_weights", {}), dict),
                    "Importance weights are available for weighted scoring.",
                ),
            ]
            _render_layer_tests("jd_parser", "JD Parser Layer Tests", jd_checks)
            
            # Download
            json_str = json.dumps(result, indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name="parsed_jd.json",
                mime="application/json"
            )
        
        except Exception as e:
            st.error(f"❌ Error parsing JD: {str(e)}")


def compare_resume_jd_section():
    """Handle resume and JD comparison with intelligence analysis."""
    st.header("Resume & Job Description Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Resume")
        resume_file = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx", "txt"],
            key="resume_compare"
        )
    
    with col2:
        st.subheader("Job Description")
        jd_input = st.radio("Input JD via", ["Upload", "Paste"], key="jd_input_method")
        if jd_input == "Upload":
            jd_file = st.file_uploader(
                "Upload job description",
                type=["txt"],
                key="jd_compare"
            )
            jd_text = jd_file.getvalue().decode("utf-8") if jd_file else ""
        else:
            jd_text = st.text_area(
                "Paste job description",
                height=200,
                key="jd_paste"
            )
    
    if resume_file and jd_text:
        try:
            with st.spinner("🔄 Processing resume and analyzing against job description..."):
                jd_result = parse_job_description(jd_text)
                st.session_state["latest_scoring_jd_context"] = jd_result
                jd_skills_required = jd_result.get("skills_required", [])
                jd_skills_optional = jd_result.get("skills_optional", [])
                jd_responsibilities = jd_result.get("responsibilities", [])
                if not jd_skills_required and not jd_skills_optional:
                    raise ValueError("JD parsing produced no skills_required/skills_optional. Fix JD input or parser before scoring.")
                if not jd_responsibilities:
                    raise ValueError("JD parsing produced no responsibilities. Fix JD input or parser before scoring.")

                # Parse resume
                temp_path = Path(f"/tmp/{resume_file.name}")
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_bytes(resume_file.getbuffer())
                
                parser = ResumeParser()
                resume_result = parser.parse_file(
                    temp_path,
                    jd_context=cast(dict[str, Any], jd_result),
                    enable_section_llm=False,
                )
                resume_output = resume_result.to_dict()
                
                # Extract data for intelligence functions
                resume_entities = resume_output.get("entities", {})
                resume_metadata = resume_output.get("metadata", {})
                resume_sections = resume_output.get("sections", {})
                jd_importance = jd_result.get("importance_weights", {})
                resume_skills = resume_entities.get("skills", {})
                resume_experience = resume_entities.get("experience", [])
                resume_text = str(resume_output.get("raw_text", "") or "")

                resume_bullets = flatten_experience_bullets(resume_experience)
                jd_skills = sorted(set(jd_skills_required) | set(jd_skills_optional))
                has_project_section = any(
                    "project" in str(section_name).lower()
                    for section_name in resume_sections.keys()
                )
                
                # Run intelligence analysis
                skill_alignment_result = align_skills(
                    resume_skills=resume_skills,
                    jd_skills=jd_skills,
                    experience_bullets=resume_bullets,
                    has_project_section=has_project_section,
                )
                
                experience_alignment_result = align_experience(
                    jd_responsibilities=jd_responsibilities,
                    jd_importance=jd_importance,
                    resume_experience=resume_experience,
                    resume_bullets=resume_bullets,
                )
                
                gap_analysis_result = analyze_gaps(
                    skill_alignment_result,
                    experience_alignment_result,
                    jd_required=jd_skills_required,
                    jd_optional=jd_skills_optional
                )
                
                ats_score_result = compute_ats_score(
                    skill_alignment=skill_alignment_result,
                    experience_alignment=experience_alignment_result,
                    resume_entities=resume_entities,
                    resume_metadata=resume_metadata,
                    jd_context=jd_result,
                    resume_sections=cast(dict[str, str], resume_sections),
                    resume_text=resume_text,
                )
            
            st.success("✅ Analysis complete!")
            
            # Create tabs for different analysis sections
            tab_overview, tab_skills, tab_experience, tab_gaps, tab_ats = st.tabs([
                "📊 Overview",
                "🎯 Skill Alignment",
                "💼 Experience Alignment",
                "🔍 Gap Analysis",
                "📈 ATS Score"
            ])
            
            with tab_overview:
                st.subheader("Quick Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    skill_count = len(skill_alignment_result.get("matched", []))
                    st.metric("Matched Skills", skill_count)
                
                with col2:
                    missing_count = len(skill_alignment_result.get("missing", []))
                    st.metric("Missing Skills", missing_count)
                
                with col3:
                    covered_count = len(experience_alignment_result.get("covered", []))
                    st.metric("Covered Responsibilities", covered_count)
                
                with col4:
                    decision = str(ats_score_result.get("decision", "BORDERLINE") or "BORDERLINE").upper()
                    confidence = float(ats_score_result.get("confidence", 0.0) or 0.0)
                    score_100 = int(ats_score_result.get("score", round(float(ats_score_result.get("ats_score", 0.0) or 0.0) * 100)))
                    st.metric("ATS", f"{score_100}/100 • {decision}", delta=f"Confidence {confidence:.0%}")
                
                st.divider()
                st.subheader("Resume Information")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    completeness = resume_metadata.get("completeness_score", 0)
                    st.metric("Completeness", f"{completeness:.0%}")
                
                with col2:
                    confidence = resume_metadata.get("parsing_confidence", 0)
                    st.metric("Parse Confidence", f"{confidence:.0%}")
                
                with col3:
                    contact = resume_entities.get("contact", {})
                    st.metric("Contact Info", "Complete" if contact.get("email") else "Incomplete")

                _render_resume_parse_diagnostics(
                    cast(dict[str, Any], resume_metadata),
                    heading="Comparison Resume Parse Diagnostics",
                )
                
                st.divider()
                st.subheader("Job Description Information")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Required Skills", len(jd_skills_required))
                
                with col2:
                    st.metric("Optional Skills", len(jd_skills_optional))
                
                with col3:
                    st.metric("Responsibilities", len(jd_responsibilities))
            
            with tab_skills:
                st.subheader("Skill Alignment Analysis")
                _display_skill_alignment(skill_alignment_result)
            
            with tab_experience:
                st.subheader("Experience Alignment Analysis")
                _display_experience_alignment(experience_alignment_result)
            
            with tab_gaps:
                st.subheader("Gap Analysis")
                _display_gap_analysis(gap_analysis_result)
            
            with tab_ats:
                st.subheader("ATS Score Analysis")
                _display_ats_score(ats_score_result)

            ats_components = cast(dict[str, Any], ats_score_result.get("components", {}))
            pipeline_checks = [
                (
                    "Resume parse output",
                    isinstance(resume_entities, dict) and isinstance(resume_metadata, dict),
                    "Resume parse layer returned entities and metadata.",
                ),
                (
                    "JD parse output",
                    isinstance(jd_result, dict) and isinstance(jd_skills_required, list),
                    "JD parse layer returned required skills payload.",
                ),
                (
                    "Bullet extraction",
                    len(resume_bullets) > 0,
                    "At least one experience bullet is available for alignment.",
                ),
                (
                    "Skill alignment schema",
                    all(
                        key in skill_alignment_result
                        for key in ("matched", "weak", "missing")
                    ),
                    "Skill alignment contains matched/weak/missing groups.",
                ),
                (
                    "Experience alignment schema",
                    all(
                        key in experience_alignment_result
                        for key in ("covered", "partial", "missing")
                    ),
                    "Experience alignment contains covered/partial/missing groups.",
                ),
                (
                    "Gap analysis schema",
                    all(
                        key in gap_analysis_result
                        for key in ("critical_gaps", "moderate_gaps", "low_priority")
                    ),
                    "Gap analysis contains critical/moderate/low buckets.",
                ),
                (
                    "ATS range check",
                    0.0 <= float(ats_score_result.get("ats_score", 0.0) or 0.0) <= 1.0,
                    "ATS score is within the expected [0, 1] range.",
                ),
                (
                    "ATS components present",
                    all(
                        key in ats_components
                        for key in ("skill_score", "experience_score", "impact_score", "format_score")
                    ),
                    "ATS component scores are present for all major modules.",
                ),
            ]
            _render_layer_tests("comparison_pipeline", "Comparison Pipeline Layer Tests", pipeline_checks)
            
            # Export results section
            st.divider()
            st.subheader("📥 Export Results")
            
            col1, col2 = st.columns(2)
            with col1:
                combined_results = {
                    "skill_alignment": skill_alignment_result,
                    "experience_alignment": experience_alignment_result,
                    "gap_analysis": gap_analysis_result,
                    "ats_score": ats_score_result
                }
                json_str = json.dumps(combined_results, indent=2)
                st.download_button(
                    label="📥 Download Intelligence Report (JSON)",
                    data=json_str,
                    file_name="intelligence_report.json",
                    mime="application/json"
                )
            
            with col2:
                # Export as markdown summary
                markdown_report = f"""
# Resume vs Job Description Analysis Report

## ATS Score: {ats_score_result.get('ats_score', 0):.1%}

### Skill Alignment
- **Matched**: {len(skill_alignment_result.get('matched', []))}
- **Weak**: {len(skill_alignment_result.get('weak', []))}
- **Missing**: {len(skill_alignment_result.get('missing', []))}

### Experience Alignment
- **Covered**: {len(experience_alignment_result.get('covered', []))}
- **Partial**: {len(experience_alignment_result.get('partial', []))}
- **Missing**: {len(experience_alignment_result.get('missing', []))}

### Critical Gaps: {len(gap_analysis_result.get('critical_gaps', []))}
### Moderate Gaps: {len(gap_analysis_result.get('moderate_gaps', []))}
### Low Priority Gaps: {len(gap_analysis_result.get('low_priority', []))}
"""
                st.download_button(
                    label="📄 Download Summary (Markdown)",
                    data=markdown_report,
                    file_name="analysis_summary.md",
                    mime="text/markdown"
                )
        
        except Exception as e:
            st.error(f"❌ Error during comparison: {str(e)}")
            st.write("Stack trace (for debugging):")
            import traceback
            st.code(traceback.format_exc())


def quick_resume_score_section() -> None:
    """Handle resume-only benchmark scoring without a JD."""
    st.header("Quick Resume Score")
    st.caption("Resume-only benchmark mode with role inference and generic hiring heuristics.")

    resume_file = st.file_uploader(
        "Upload your resume",
        type=["pdf", "docx", "txt"],
        key="resume_quick_score",
    )

    if not resume_file:
        return

    try:
        with st.spinner("🔄 Parsing resume and computing benchmark score..."):
            temp_path = Path(f"/tmp/{resume_file.name}")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(resume_file.getbuffer())

            parser = ResumeParser()
            resume_result = parser.parse_file(temp_path, enable_section_llm=False)
            resume_output = resume_result.to_dict()

            resume_entities = cast(dict[str, Any], resume_output.get("entities", {}))
            resume_metadata = cast(dict[str, Any], resume_output.get("metadata", {}))
            resume_text = str(resume_output.get("raw_text", "") or "")

            quick_result = compute_resume_only_score(
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                resume_text=resume_text,
            )

        st.success("✅ Quick resume scoring complete!")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Quick ATS Score", f"{float(quick_result.get('ats_score', 0.0)):.1%}")
        with col2:
            st.metric("Inferred Role", str(quick_result.get("inferred_role", "unknown")).title())
        with col3:
            estimated_years = quick_result.get("evidence", {}).get("estimated_years", 0)
            st.metric("Estimated Experience", f"{float(estimated_years):.1f} yrs")

        _render_resume_parse_diagnostics(
            cast(dict[str, Any], resume_metadata),
            heading="Quick Score Resume Parse Diagnostics",
        )

        calibration = cast(dict[str, Any], quick_result.get("calibration", {}))
        percentile = float(calibration.get("percentile", 0.0) or 0.0)
        st.metric("Benchmark Percentile", f"{percentile:.1f}th")
        if bool(calibration.get("is_synthetic", False)):
            st.caption(str(calibration.get("note", "Percentile currently uses seeded benchmark data.")))

        components = cast(dict[str, Any], quick_result.get("components", {}))
        st.subheader("Component Breakdown")
        comp_cols = st.columns(4)
        labels = [
            ("Skill", "skill_score"),
            ("Experience Alignment", "experience_score"),
            ("Impact", "impact_score"),
            ("Format", "format_score"),
        ]
        for idx, (label, key) in enumerate(labels):
            with comp_cols[idx]:
                value = float(components.get(key, 0.0) or 0.0)
                st.metric(label, f"{value:.1%}")

        evidence = cast(dict[str, Any], quick_result.get("evidence", {}))
        skill_alignment = cast(dict[str, Any], evidence.get("skill_alignment", {}))
        experience_alignment = cast(dict[str, Any], evidence.get("experience_alignment", {}))
        rewrite_suggestions = cast(list[dict[str, Any]], evidence.get("rewrite_suggestions", []))

        tab1, tab2, tab3 = st.tabs(["🎯 Skills", "💼 Experience Alignment", "📊 Full JSON"])
        with tab1:
            _display_resume_only_skill_alignment(skill_alignment, str(quick_result.get("inferred_role", "target role")))
        with tab2:
            _display_experience_alignment(experience_alignment)
        with tab3:
            st.json(quick_result)

        quick_checks = [
            (
                "Resume parse output",
                isinstance(resume_entities, dict) and isinstance(resume_metadata, dict),
                "Resume parse layer produced entities and metadata.",
            ),
            (
                "Quick score payload",
                isinstance(quick_result, dict),
                "Quick ATS engine returned a dictionary payload.",
            ),
            (
                "ATS score range",
                0.0 <= float(quick_result.get("ats_score", 0.0) or 0.0) <= 1.0,
                "Quick ATS score is in the expected [0, 1] range.",
            ),
            (
                "Role inference",
                bool(str(quick_result.get("inferred_role", "")).strip()),
                "Inferred role is present.",
            ),
            (
                "Evidence payload",
                isinstance(evidence, dict) and "skill_alignment" in evidence and "experience_alignment" in evidence,
                "Evidence includes both skill and experience alignment modules.",
            ),
            (
                "Component scores",
                all(
                    key in components
                    for key in ("skill_score", "experience_score", "impact_score", "format_score")
                ),
                "All quick-score components are available.",
            ),
        ]
        _render_layer_tests("quick_resume_score", "Quick Resume Score Layer Tests", quick_checks)

        if rewrite_suggestions:
            st.subheader("✨ Actionable Rewrite Suggestions")
            for item in rewrite_suggestions[:5]:
                original = str(item.get("original", "")).strip()
                suggested = str(item.get("suggested", "")).strip()
                if not original or not suggested:
                    continue
                st.write("Original:")
                st.code(original)
                st.write("Suggested rewrite:")
                st.code(suggested)

    except Exception as e:
        st.error(f"❌ Error during quick scoring: {str(e)}")
        st.write("Stack trace (for debugging):")
        import traceback
        st.code(traceback.format_exc())


def _display_llm_recommendations(recommendations: dict[str, Any]) -> None:
    """Render standardized LLM recommendation sections."""
    print("FINAL RECOMMENDATIONS:", recommendations)

    st.subheader("🎯 LLM Recommendations")
    has_recommendation_content = any(
        recommendations.get(key)
        for key in ("bullet_improvements", "skill_suggestions", "gap_explanations")
    )
    if not has_recommendation_content:
        st.info("No targeted LLM recommendations were generated for this input.")

    if recommendations.get("bullet_improvements"):
        st.subheader("📝 Bullet Improvements")
        for i, improvement in enumerate(recommendations["bullet_improvements"], 1):
            with st.expander(f"Improvement #{i}"):
                st.write(f"**Original:** {improvement.get('original', 'N/A')}")
                st.write(f"**Improved:** {improvement.get('improved', 'N/A')}")
                st.write(f"**Reason:** {improvement.get('reason', 'N/A')}")

    if recommendations.get("skill_suggestions"):
        st.subheader("Skills to Add")
        for skill in recommendations["skill_suggestions"]:
            st.write(f"**{skill.get('skill', 'N/A')}**")
            st.write(skill.get('reason', 'N/A'))

    if recommendations.get("gap_explanations"):
        st.subheader("📊 Coverage Gaps")
        for i, gap in enumerate(recommendations["gap_explanations"], 1):
            with st.expander(f"Gap #{i}: {gap.get('gap', 'N/A')}"):
                st.write(f"**Gap:** {gap.get('gap', 'N/A')}")
                st.write(f"**Fix:** {gap.get('fix', 'N/A')}")


def _parse_multivalue_lines(text: str) -> list[str]:
    """Split a multiline text input into non-empty trimmed lines."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _display_generated_resume(generated_resume: dict[str, Any]) -> None:
    """Render generated resume sections in a readable format."""
    st.subheader("Experience")
    experience = generated_resume.get("experience", [])
    if isinstance(experience, list) and experience:
        for idx, item in enumerate(experience, 1):
            if not isinstance(item, dict):
                continue
            with st.expander(f"Experience #{idx}: {item.get('title', 'Role')}"):
                st.write(f"**Company:** {item.get('company', 'N/A')}")
                st.write(f"**Duration:** {item.get('duration', 'N/A')}")
                bullets = item.get("bullets", [])
                if isinstance(bullets, list):
                    for bullet in bullets:
                        st.write(f"- {bullet}")
    else:
        st.info("No experience entries returned.")

    st.subheader("Projects")
    projects = generated_resume.get("projects", [])
    if isinstance(projects, list) and projects:
        for idx, project in enumerate(projects, 1):
            if not isinstance(project, dict):
                continue
            with st.expander(f"Project #{idx}: {project.get('name', 'Project')}"):
                bullets = project.get("bullets", [])
                if isinstance(bullets, list):
                    for bullet in bullets:
                        st.write(f"- {bullet}")
                else:
                    st.write(str(project.get("description", "")))
                tech = project.get("technologies", [])
                if isinstance(tech, list) and tech:
                    st.caption(f"Tech: {', '.join(str(t) for t in tech)}")
    else:
        st.info("No projects returned.")

    st.subheader("Education")
    st.write(str(generated_resume.get("education", "")))

    st.subheader("Skills")
    skills = generated_resume.get("skills", {})
    if isinstance(skills, dict) and skills:
        labels = {
            "programming_languages": "Programming Languages",
            "data_science": "Data Science",
            "data_visualization": "Data Visualization",
            "databases": "Databases",
            "tools": "Tools",
        }
        for key in [
            "programming_languages",
            "data_science",
            "data_visualization",
            "databases",
            "tools",
        ]:
            values = skills.get(key, [])
            if isinstance(values, list) and values:
                st.write(f"- **{labels[key]}**: {', '.join(str(v) for v in values)}")
            else:
                st.write(f"- **{labels[key]}**: N/A")
    else:
        st.info("No skills returned.")

    st.subheader("Certifications")
    certifications = generated_resume.get("certifications", [])
    if isinstance(certifications, list) and certifications:
        for cert in certifications:
            if isinstance(cert, dict):
                cert = " | ".join(
                    str(cert.get(key) or "").strip()
                    for key in ("name", "issuer", "year")
                    if str(cert.get(key) or "").strip()
                )
            st.write(f"- {cert}")
    else:
        st.info("No certifications returned.")


def llm_recommendations_section() -> None:
    """Generate LLM-based resume optimization recommendations."""
    st.header("✨ LLM Resume Recommendations")
    st.caption("Choose a mode: Resume+JD optimization, Resume-only improvement, or Resume generation.")

    llm_mode = st.selectbox(
        "LLM Mode",
        [
            "Optimize with JD",
            "Resume-only Improvement",
            "Generate Resume",
        ],
        index=0,
        key="llm_mode_selector",
    )

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("⚠️ ANTHROPIC_API_KEY not found. Add it to the root .env file.")
        return

    if "llm_optimize_cache" not in st.session_state:
        st.session_state["llm_optimize_cache"] = None
    if "llm_resume_only_cache" not in st.session_state:
        st.session_state["llm_resume_only_cache"] = None
    if "latest_scoring_jd_context" not in st.session_state:
        st.session_state["latest_scoring_jd_context"] = None

    if llm_mode == "Optimize with JD":
        col1, col2 = st.columns(2)
        with col1:
            resume_file = st.file_uploader(
                "Upload your resume",
                type=["pdf", "docx", "txt"],
                key="resume_llm_rec",
            )

        with col2:
            jd_file = st.file_uploader(
                "Upload job description",
                type=["pdf", "docx", "txt"],
                key="jd_llm_rec",
            )

        if not resume_file or not jd_file:
            st.info("📋 Please upload both resume and job description to continue.")
            return

        optimize_signature = (
            f"{resume_file.name}:{getattr(resume_file, 'size', 0)}"
            f"|{jd_file.name}:{getattr(jd_file, 'size', 0)}"
        )
        run_optimize_clicked = st.button("🔍 Run Resume + JD Analysis", key="run_optimize_with_jd")

        try:
            cache_opt = cast(dict[str, Any] | None, st.session_state.get("llm_optimize_cache"))
            if run_optimize_clicked:
                with st.spinner("🔄 Analyzing resume against job description..."):
                    resume_path = Path(f"/tmp/resume_{resume_file.name}")
                    jd_path = Path(f"/tmp/jd_{jd_file.name}")

                    resume_path.parent.mkdir(parents=True, exist_ok=True)
                    resume_path.write_bytes(resume_file.getbuffer())
                    jd_path.write_bytes(jd_file.getbuffer())

                    service = ResumeAnalysisService(api_key=None)
                    analysis = service.analyze_resume_against_jd(
                        resume_path=str(resume_path),
                        jd_path=str(jd_path),
                        include_llm_recommendations=True,
                    )

                    # Also prepare optimized resume artifacts for direct download.
                    optimized_artifacts: dict[str, Any] = {}
                    try:
                        llm_engine = LLMAnalysisEngine(api_key=None)
                        generation_input = _resume_data_to_generation_input(
                            resume_data=cast(dict[str, Any], analysis.get("resume_analysis", {})),
                            fallback_name=Path(resume_file.name).stem,
                        )
                        jd_analysis = analysis.get("jd_analysis", {})
                        if isinstance(jd_analysis, dict):
                            target_role_hint = str(
                                jd_analysis.get("job_title")
                                or jd_analysis.get("target_role")
                                or ""
                            ).strip()
                            if target_role_hint:
                                generation_input["target_role"] = target_role_hint
                            generation_input["jd_context"] = jd_analysis
                            st.session_state["latest_scoring_jd_context"] = jd_analysis

                        generated = llm_engine.generate_resume(
                            user_input=generation_input,
                            jd_data=cast(dict[str, Any], jd_analysis) if isinstance(jd_analysis, dict) else None,
                        )
                        resume_text = str(generated.get("resume_text", "") or "")
                        pdf_base64 = str(generated.get("pdf_base64", "") or "")
                        docx_base64 = str(generated.get("docx_base64", "") or "")

                        optimized_artifacts = {
                            "resume_text": resume_text,
                            "pdf_bytes": base64.b64decode(pdf_base64) if pdf_base64 else b"",
                            "docx_bytes": base64.b64decode(docx_base64) if docx_base64 else b"",
                            "candidate_name": str(generation_input.get("name", "")).strip(),
                            "generation_input": generation_input,
                            "generated_payload": generated,
                        }
                    except Exception as gen_exc:
                        optimized_artifacts = {
                            "resume_text": "",
                            "pdf_bytes": b"",
                            "docx_bytes": b"",
                            "candidate_name": "",
                            "generation_error": str(gen_exc),
                            "generation_input": generation_input if "generation_input" in locals() else {},
                            "generated_payload": {},
                        }

                    st.session_state["llm_optimize_cache"] = {
                        "signature": optimize_signature,
                        "analysis": analysis,
                        "optimized_artifacts": optimized_artifacts,
                    }
                    cache_opt = cast(dict[str, Any], st.session_state["llm_optimize_cache"])

            if not cache_opt or cache_opt.get("signature") != optimize_signature:
                st.info("Run analysis once. Downloads will then work without re-running LLM.")
                return

            analysis = cast(dict[str, Any], cache_opt.get("analysis", {}))
            service = ResumeAnalysisService(api_key=None)

            st.success("✅ Analysis complete!")

            ats_analysis = analysis.get("ats_analysis", {})
            score_summary = service.get_score_summary(ats_analysis)

            st.subheader("ATS Score Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Overall ATS Score", f"{score_summary['overall_score']:.1%}")
            with col2:
                st.metric("Weakest Area", score_summary['weakest_area']['name'].title())
            with col3:
                st.metric("Weakest Score", f"{score_summary['weakest_area']['score']:.1%}")

            st.info(f"**{score_summary['interpretation']}** — {score_summary['recommended_action']}")

            st.subheader("Component Breakdown")
            comp_cols = st.columns(4)
            labels = [
                ("Skill", "skill_score"),
                ("Experience", "experience_score"),
                ("Impact", "impact_score"),
                ("Format", "format_score"),
            ]
            for idx, (label, key) in enumerate(labels):
                with comp_cols[idx]:
                    value = score_summary.get("component_scores", {}).get(key, 0)
                    st.metric(label, f"{value:.1%}")

            st.subheader("💡 Quick Tips")
            quick_tips = analysis.get("quick_tips", [])
            for i, tip in enumerate(quick_tips, 1):
                st.write(f"{i}. {tip}")

            recommendations = analysis.get("llm_recommendations") or {
                "bullet_improvements": [],
                "skill_suggestions": [],
                "gap_explanations": [
                    {
                        "gap": "LLM recommendations missing from response",
                        "fix": "Retry analysis and inspect backend logs for recommendation generation",
                    }
                ],
            }

            llm_opt_input_payload = {
                "workflow": "optimize_with_jd",
                "include_llm_recommendations": True,
                "resume_data": analysis.get("resume_analysis", {}),
                "jd_data": analysis.get("jd_analysis", {}),
                "ats_analysis": analysis.get("ats_analysis", {}),
            }
            _display_llm_input_payload(llm_opt_input_payload, panel_key="llm_optimize_with_jd")
            _display_llm_recommendations(cast(dict[str, Any], recommendations))

            # Optimized resume downloads (available in Optimize+JD mode).
            optimized_artifacts = cast(dict[str, Any], cache_opt.get("optimized_artifacts", {}))
            optimized_generation_input = cast(dict[str, Any], optimized_artifacts.get("generation_input", {}))
            optimized_generated_payload = cast(dict[str, Any], optimized_artifacts.get("generated_payload", {}))
            resume_analysis_payload = cast(dict[str, Any], analysis.get("resume_analysis", {}))
            raw_resume_text = str(resume_analysis_payload.get("raw_text", "") or "")
            fallback_optimized_text = _build_improved_resume_text(
                raw_text=raw_resume_text,
                recommendations=cast(dict[str, Any], recommendations),
            )
            optimized_resume_text = str(optimized_artifacts.get("resume_text", "") or "").strip()
            if not optimized_resume_text:
                optimized_resume_text = fallback_optimized_text

            candidate_name = str(optimized_artifacts.get("candidate_name", "") or "").strip()
            download_base_name = candidate_name.replace(" ", "_") if candidate_name else Path(resume_file.name).stem
            pdf_bytes = bytes(optimized_artifacts.get("pdf_bytes", b""))
            docx_bytes = bytes(optimized_artifacts.get("docx_bytes", b""))

            st.subheader("📄 Optimized Resume")
            st.caption("Download the optimized resume output generated from Resume + JD analysis.")

            with st.expander("Preview optimized resume text", expanded=False):
                st.text(optimized_resume_text)

            st.download_button(
                label="📄 Download Optimized Resume (TXT)",
                data=optimized_resume_text,
                file_name=f"{download_base_name}_optimized_resume.txt",
                mime="text/plain",
            )

            if pdf_bytes:
                st.download_button(
                    label="📄 Download Optimized Resume (PDF)",
                    data=pdf_bytes,
                    file_name=f"{download_base_name}_optimized_resume.pdf",
                    mime="application/pdf",
                )

            if docx_bytes:
                st.download_button(
                    label="📄 Download Optimized Resume (DOCX)",
                    data=docx_bytes,
                    file_name=f"{download_base_name}_optimized_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

            generation_error = str(optimized_artifacts.get("generation_error", "") or "").strip()
            if generation_error and not pdf_bytes and not docx_bytes:
                st.info(
                    "PDF/DOCX generation is currently unavailable for this run. "
                    "TXT optimized output is still available."
                )

            _render_layer_observability_panel(
                panel_key="llm_optimize_with_jd",
                heading="LLM Enhance Layers (Optimize with JD)",
                layers=[
                    ("Input Layer", llm_opt_input_payload),
                    ("Resume Parse Layer", analysis.get("resume_analysis", {})),
                    ("JD Parse Layer", analysis.get("jd_analysis", {})),
                    ("ATS Analysis Layer", analysis.get("ats_analysis", {})),
                    ("Hybrid Scoring Layer", analysis.get("hybrid_scoring", {})),
                    ("LLM Recommendation Layer", recommendations),
                    ("Generation Input Layer", optimized_generation_input),
                    ("Generation Output Layer", optimized_generated_payload),
                    ("Optimized Artifact Layer", optimized_artifacts),
                ],
            )

            st.download_button(
                label="📥 Download Full Recommendations (JSON)",
                data=json.dumps(recommendations, indent=2),
                file_name="llm_recommendations.json",
                mime="application/json"
            )

            st.download_button(
                label="📥 Download Full Analysis (JSON)",
                data=json.dumps(analysis, indent=2, default=str),
                file_name="full_analysis.json",
                mime="application/json"
            )

            llm_opt_checks = [
                (
                    "Analysis payload",
                    isinstance(analysis, dict) and len(analysis) > 0,
                    "LLM optimize pipeline returned a non-empty analysis object.",
                ),
                (
                    "ATS analysis present",
                    isinstance(ats_analysis, dict) and len(ats_analysis) > 0,
                    "ATS analysis payload is present inside LLM response.",
                ),
                (
                    "Score summary schema",
                    all(
                        key in score_summary
                        for key in ("overall_score", "component_scores", "weakest_area")
                    ),
                    "Score summary contains expected fields.",
                ),
                (
                    "Quick tips list",
                    isinstance(quick_tips, list),
                    "Quick tips are list-typed.",
                ),
                (
                    "LLM recommendations schema",
                    isinstance(recommendations, dict)
                    and all(
                        key in recommendations
                        for key in ("bullet_improvements", "skill_suggestions", "gap_explanations")
                    ),
                    "Recommendations include bullet, skill, and gap suggestion sections.",
                ),
            ]
            _render_layer_tests("llm_optimize_with_jd", "LLM Optimize+JD Layer Tests", llm_opt_checks)

        except ImportError as e:
            st.error(f"❌ Missing dependency: {str(e)}")
            st.info("Install anthropic: `pip install anthropic`")
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            st.write("Stack trace (for debugging):")
            import traceback
            st.code(traceback.format_exc())

    elif llm_mode == "Resume-only Improvement":
        resume_file = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx", "txt"],
            key="resume_llm_only",
        )
        scoring_jd_context = cast(dict[str, Any] | None, st.session_state.get("latest_scoring_jd_context"))
        if isinstance(scoring_jd_context, dict) and scoring_jd_context:
            st.caption("Using JD context from your latest ATS scoring run for targeted improvements.")

        if not resume_file:
            st.info("📋 Please upload a resume to continue.")
            return

        resume_only_pipeline_version = "retention-v3"
        resume_only_signature = f"{resume_only_pipeline_version}:{resume_file.name}:{getattr(resume_file, 'size', 0)}"
        run_resume_only_clicked = st.button("✨ Generate Resume-only Improvements", key="run_resume_only")

        try:
            cache_resume = cast(dict[str, Any] | None, st.session_state.get("llm_resume_only_cache"))
            if run_resume_only_clicked:
                with st.spinner("🔄 Generating general resume improvements..."):
                    temp_path = Path(f"/tmp/{resume_file.name}")
                    temp_path.parent.mkdir(parents=True, exist_ok=True)
                    temp_path.write_bytes(resume_file.getbuffer())

                    parser = ResumeParser()
                    resume_result = parser.parse_file(temp_path, enable_section_llm=False)
                    resume_data = resume_result.to_dict()
                    resume_entities = cast(dict[str, Any], resume_data.get("entities", {}))
                    resume_metadata = cast(dict[str, Any], resume_data.get("metadata", {}))
                    raw_resume_text = str(resume_data.get("raw_text", "") or "")

                    before_analysis = compute_resume_only_score(
                        resume_entities=resume_entities,
                        resume_metadata=resume_metadata,
                        resume_text=raw_resume_text,
                    )

                    llm_engine = LLMAnalysisEngine(api_key=None)
                    generation_input = _resume_data_to_generation_input(
                        resume_data=resume_data,
                        fallback_name=Path(resume_file.name).stem,
                    )
                    generation_input["_omit_summary"] = True
                    generation_input["summary"] = ""

                    # Build synthetic JD context from the inferred role's benchmark profile
                    # so the LLM knows which skills/responsibilities to optimize for.
                    inferred_role = str(before_analysis.get("inferred_role", "")).strip()
                    benchmark_profile = before_analysis.get("benchmark_profile", {})
                    effective_jd_context: dict[str, Any] | None = None
                    if isinstance(benchmark_profile, dict) and benchmark_profile:
                        synthetic_jd_context: dict[str, Any] = {
                            "job_title": inferred_role,
                            "skills_required": list(benchmark_profile.get("skills", [])),
                            "responsibilities": list(benchmark_profile.get("responsibilities", [])),
                        }
                        synthetic_jd_context.update(enrich_jd_context(synthetic_jd_context))
                        generation_input["jd_context"] = synthetic_jd_context
                        effective_jd_context = synthetic_jd_context
                        if not str(generation_input.get("target_role", "")).strip() and inferred_role:
                            generation_input["target_role"] = inferred_role
                    elif isinstance(scoring_jd_context, dict) and scoring_jd_context:
                        # Fallback: use JD context from a previous ATS scoring run if available.
                        generation_input["jd_context"] = scoring_jd_context
                        effective_jd_context = scoring_jd_context
                        if not str(generation_input.get("target_role", "")).strip():
                            fallback_role = str(
                                scoring_jd_context.get("job_title")
                                or scoring_jd_context.get("target_role")
                                or ""
                            ).strip()
                            if fallback_role:
                                generation_input["target_role"] = fallback_role

                    # Extract the actual candidate name from generation_input
                    candidate_name = str(generation_input.get("name", "Candidate")).strip()

                    generated = llm_engine.generate_resume(
                        user_input=generation_input,
                        jd_data=effective_jd_context,
                    )
                    resume_text = str(generated.get("resume_text", "") or "")
                    pdf_base64 = str(generated.get("pdf_base64", "") or "")
                    pdf_bytes = base64.b64decode(pdf_base64) if pdf_base64 else b""
                    after_analysis: dict[str, Any] = {}
                    optimized_resume_parse: dict[str, Any] = {}
                    non_regression_applied = False

                    try:
                        optimized_parse = parser.parse_text(resume_text)
                        optimized_dict = optimized_parse.to_dict()
                        optimized_resume_parse = optimized_dict
                        after_analysis = compute_resume_only_score(
                            resume_entities=cast(dict[str, Any], optimized_dict.get("entities", {})),
                            resume_metadata=cast(dict[str, Any], optimized_dict.get("metadata", {})),
                            resume_text=resume_text,
                        )

                        before_score = float(before_analysis.get("ats_score", 0.0) or 0.0)
                        after_score = float(after_analysis.get("ats_score", 0.0) or 0.0)
                        if after_score < before_score:
                            non_regression_applied = True
                            resume_text = raw_resume_text
                            pdf_bytes = b""
                            after_analysis = before_analysis
                    except Exception:
                        after_analysis = before_analysis

                    st.session_state["llm_resume_only_cache"] = {
                        "signature": resume_only_signature,
                        "resume_parse": resume_data,
                        "generation_input": generation_input,
                        "generated_payload": generated,
                        "resume_text": resume_text,
                        "pdf_bytes": pdf_bytes,
                        "candidate_name": candidate_name,
                        "before_analysis": before_analysis,
                        "after_analysis": after_analysis,
                        "optimized_resume_parse": optimized_resume_parse,
                        "non_regression_applied": non_regression_applied,
                    }
                    cache_resume = cast(dict[str, Any], st.session_state["llm_resume_only_cache"])

            if not cache_resume or cache_resume.get("signature") != resume_only_signature:
                st.info("Generate improvements once. Downloads will then work without re-running LLM.")
                return

            improved_resume_text = str(cache_resume.get("resume_text", "") or "").strip()
            cached_candidate_name = str(cache_resume.get("candidate_name", "Candidate")).strip()
            pdf_bytes = bytes(cache_resume.get("pdf_bytes", b""))
            generated_payload = cast(dict[str, Any], cache_resume.get("generated_payload", {}))
            generation_input_payload = cast(dict[str, Any], cache_resume.get("generation_input", {}))
            resume_parse_payload = cast(dict[str, Any], cache_resume.get("resume_parse", {}))
            optimized_resume_parse_payload = cast(dict[str, Any], cache_resume.get("optimized_resume_parse", {}))
            before_analysis = cast(dict[str, Any], cache_resume.get("before_analysis", {}))
            after_analysis = cast(dict[str, Any], cache_resume.get("after_analysis", {}))
            non_regression_applied = bool(cache_resume.get("non_regression_applied", False))

            st.success("✅ Resume regenerated with improvements!")

            if before_analysis and after_analysis:
                col_before, col_after, col_delta = st.columns(3)
                before_score = float(before_analysis.get("ats_score", 0.0) or 0.0)
                after_score = float(after_analysis.get("ats_score", 0.0) or 0.0)
                with col_before:
                    st.metric("ATS Before", f"{before_score:.1%}")
                with col_after:
                    st.metric("ATS After", f"{after_score:.1%}")
                with col_delta:
                    st.metric("Delta", f"{(after_score - before_score):+.1%}")

            if non_regression_applied:
                st.warning(
                    "Generated version scored lower in resume-only ATS re-check, so original resume text was retained (non-regression guard)."
                )

            st.subheader("Improved Resume Preview")
            st.text(improved_resume_text)

            if generation_input_payload:
                _display_llm_input_payload(
                    {
                        "workflow": "resume_only_improvement",
                        "user_input": generation_input_payload,
                    },
                    panel_key="llm_resume_only",
                )

            if generated_payload:
                _display_pre_pdf_llm_output(generated_payload, panel_key="llm_resume_only")

            _render_layer_observability_panel(
                panel_key="llm_resume_only",
                heading="LLM Enhance Layers (Resume-only)",
                layers=[
                    ("Resume Parse Layer", resume_parse_payload),
                    ("Resume-only ATS Before Layer", before_analysis),
                    ("Generation Input Layer", generation_input_payload),
                    ("Generation Output Layer", generated_payload),
                    ("Optimized Parse Layer", optimized_resume_parse_payload),
                    ("Resume-only ATS After Layer", after_analysis),
                ],
            )

            # Use candidate name for file downloads, or fall back to resume filename
            download_base_name = cached_candidate_name.replace(" ", "_") if cached_candidate_name and cached_candidate_name != "Candidate" else Path(resume_file.name).stem
            
            if pdf_bytes:
                st.download_button(
                    label="📄 Download Improved Resume (PDF)",
                    data=pdf_bytes,
                    file_name=f"{download_base_name}_improved_resume.pdf",
                    mime="application/pdf",
                )

            st.download_button(
                label="📄 Download Improved Resume (TXT)",
                data=improved_resume_text,
                file_name=f"{download_base_name}_improved_resume.txt",
                mime="text/plain",
            )

            llm_resume_only_checks = [
                (
                    "Cache payload",
                    isinstance(cache_resume, dict) and len(cache_resume) > 0,
                    "Resume-only mode cache is populated.",
                ),
                (
                    "Generation input",
                    isinstance(cache_resume.get("generation_input", {}), dict),
                    "Structured generation input was built from parsed resume.",
                ),
                (
                    "Pre-PDF payload",
                    isinstance(generated_payload, dict) and "resume_json" in generated_payload,
                    "Generated payload includes structured pre-PDF resume content.",
                ),
                (
                    "Improved text output",
                    len(improved_resume_text) > 0,
                    "Improved resume text is non-empty.",
                ),
                (
                    "Candidate identity",
                    bool(cached_candidate_name),
                    "Candidate name is available for output naming.",
                ),
                (
                    "PDF output optional",
                    isinstance(pdf_bytes, (bytes, bytearray)),
                    "PDF bytes field is present (can be empty when PDF is unavailable).",
                ),
            ]
            _render_layer_tests("llm_resume_only", "LLM Resume-only Layer Tests", llm_resume_only_checks)

        except ImportError as e:
            st.error(f"❌ Missing dependency: {str(e)}")
            st.info("Install anthropic: `pip install anthropic`")
        except Exception as e:
            st.error(f"❌ Error during resume-only improvement: {str(e)}")
            st.write("Stack trace (for debugging):")
            import traceback
            st.code(traceback.format_exc())

    else:  # Generate Resume
        st.subheader("Input Profile Data")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", key="gen_name")
            target_role = st.text_input("Target Role", key="gen_target_role")
            education = st.text_area("Education", key="gen_education", height=100)
            st.markdown("**Skills Categories (one per line)**")
            programming_languages_text = st.text_area(
                "Programming Languages",
                key="gen_skills_programming",
                height=90,
            )
            data_science_text = st.text_area(
                "Data Science",
                key="gen_skills_datascience",
                height=90,
            )
        with col2:
            data_visualization_text = st.text_area(
                "Data Visualization",
                key="gen_skills_visualization",
                height=90,
            )
            databases_text = st.text_area(
                "Databases",
                key="gen_skills_databases",
                height=90,
            )
            tools_text = st.text_area(
                "Tools",
                key="gen_skills_tools",
                height=90,
            )
            certifications_text = st.text_area(
                "Certifications (one per line, max 5)",
                key="gen_certifications",
                height=90,
            )
            projects_text = st.text_area(
                "Projects (one per line, format: Name | Bullet1; Bullet2; Bullet3 | Tech1,Tech2)",
                key="gen_projects",
                height=160,
            )
            experience_text = st.text_area(
                "Experience (one role per line, format: Title | Company | Duration | Bullet1; Bullet2; Bullet3)",
                key="gen_experience",
                height=160,
            )
            extra_context = st.text_area(
                "Optional Extra Context",
                key="gen_extra",
                height=80,
            )

        generate_clicked = st.button("🚀 Generate Resume", key="generate_resume_button")
        if not generate_clicked:
            return

        if not full_name.strip() or not target_role.strip():
            st.warning("Please provide at least Full Name and Target Role.")
            return

        try:
            skills_map: dict[str, list[str]] = {
                "programming_languages": _parse_multivalue_lines(programming_languages_text),
                "data_science": _parse_multivalue_lines(data_science_text),
                "data_visualization": _parse_multivalue_lines(data_visualization_text),
                "databases": _parse_multivalue_lines(databases_text),
                "tools": _parse_multivalue_lines(tools_text),
            }
            certifications = _parse_multivalue_lines(certifications_text)[:5]

            projects: list[dict[str, Any]] = []
            for line in _parse_multivalue_lines(projects_text):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    continue
                technologies = []
                if len(parts) >= 3:
                    technologies = [tech.strip() for tech in parts[2].split(",") if tech.strip()]
                project_bullets = [b.strip() for b in parts[1].split(";") if b.strip()]
                projects.append(
                    {
                        "name": parts[0],
                        "bullets": project_bullets,
                        "technologies": technologies,
                    }
                )

            experience: list[dict[str, Any]] = []
            for line in _parse_multivalue_lines(experience_text):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 4:
                    continue
                bullets = [b.strip() for b in parts[3].split(";") if b.strip()]
                experience.append(
                    {
                        "title": parts[0],
                        "company": parts[1],
                        "duration": parts[2],
                        "bullets": bullets,
                    }
                )

            user_input: dict[str, Any] = {
                "name": full_name.strip(),
                "target_role": target_role.strip(),
                "education": education.strip(),
                "skills": skills_map,
                "projects": projects,
                "experience": experience,
                "certifications": certifications,
                "extra_context": extra_context.strip(),
                "_omit_summary": True,
                "summary": "",
            }

            with st.spinner("🔄 Generating full resume..."):
                llm_engine = LLMAnalysisEngine(api_key=None)
                generated = llm_engine.generate_resume(user_input=user_input)
                resume_text = str(generated.get("resume_text", "") or "")
                pdf_base64 = str(generated.get("pdf_base64", "") or "")
            pdf_bytes = base64.b64decode(pdf_base64) if pdf_base64 else b""

            st.success("✅ Resume generated successfully!")

            st.subheader("Resume Preview")
            st.text(resume_text)
            _display_llm_input_payload(
                {
                    "workflow": "generate_resume",
                    "user_input": user_input,
                },
                panel_key="llm_generate",
            )
            _display_pre_pdf_llm_output(generated, panel_key="llm_generate")
            _render_layer_observability_panel(
                panel_key="llm_generate",
                heading="LLM Enhance Layers (Generate Resume)",
                layers=[
                    ("Input Layer", {"workflow": "generate_resume", "user_input": user_input}),
                    ("Generation Output Layer", generated),
                    (
                        "Rendered Output Layer",
                        {
                            "resume_text": resume_text,
                            "pdf_bytes": pdf_bytes,
                        },
                    ),
                ],
            )

            # Download options - PDF and plain text
            st.subheader("📥 Download Your Resume")

            if pdf_bytes:
                st.download_button(
                    label="Download Resume (PDF)",
                    data=pdf_bytes,
                    file_name=f"{full_name.strip().replace(' ', '_')}_resume.pdf",
                    mime="application/pdf",
                )
            else:
                st.warning("⚠️ Could not generate PDF bytes from engine response.")

            st.download_button(
                label="📄 Download as Text",
                data=resume_text,
                file_name=f"{full_name.strip().replace(' ', '_')}_resume.txt",
                mime="text/plain",
            )

            llm_generate_checks = [
                (
                    "Input payload",
                    isinstance(user_input, dict) and len(user_input) > 0,
                    "Generate mode input payload was assembled.",
                ),
                (
                    "Required identity fields",
                    bool(user_input.get("name")) and bool(user_input.get("target_role")),
                    "Name and target role are present before generation.",
                ),
                (
                    "LLM generated payload",
                    isinstance(generated, dict) and len(generated) > 0,
                    "LLM engine returned a structured payload.",
                ),
                (
                    "Resume text output",
                    len(resume_text.strip()) > 0,
                    "Generated resume text is non-empty.",
                ),
                (
                    "Skills map schema",
                    isinstance(user_input.get("skills", {}), dict),
                    "Skills were passed as categorized map.",
                ),
            ]
            _render_layer_tests("llm_generate", "LLM Generate Layer Tests", llm_generate_checks)

        except ImportError as e:
            st.error(f"❌ Missing dependency: {str(e)}")
            st.info("Install anthropic: `pip install anthropic`")
        except Exception as e:
            st.error(f"❌ Error during resume generation: {str(e)}")
            st.write("Stack trace (for debugging):")
            import traceback
            st.code(traceback.format_exc())


# Main content based on selected mode
if parse_mode == "Parse Resume":
    parse_resume_section()
elif parse_mode == "Parse Job Description":
    parse_jd_section()
elif parse_mode == "Compare Resume & JD":
    compare_resume_jd_section()
elif parse_mode == "Quick Resume Score":
    quick_resume_score_section()
else:  # LLM Recommendations
    llm_recommendations_section()

# Footer
st.divider()
st.markdown(
    "🔧 **Resume & JD Parser** | Built with Streamlit | "
    "[GitHub](https://github.com) | [Documentation](https://docs.example.com)"
)
