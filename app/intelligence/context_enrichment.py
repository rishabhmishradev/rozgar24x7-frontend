"""Context enrichment helpers for resume generation.

The goal is to preserve narrative signal from raw resume/JD text and produce
lightweight semantic hints for generation prompts.
"""

from __future__ import annotations

import re
from typing import Any

from app.parsing.entity_extractor import SKILL_GRAPH, normalize_skill


_RESUME_TEXT_INFERENCES: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = (
    (
        re.compile(r"\b(dashboard|tableau|power\s*bi|visuali[sz]e|reporting)\b", re.IGNORECASE),
        ("data visualization", "data storytelling"),
        "dashboard_reporting",
    ),
    (
        re.compile(r"\b(analy[sz]ed?|analysis|trend|cohort|segment|behavior)\b", re.IGNORECASE),
        ("business insights", "analytical thinking"),
        "analysis_trend_detection",
    ),
    (
        re.compile(r"\b(retention|conversion|kpi|growth|revenue|impact)\b", re.IGNORECASE),
        ("business impact", "decision support"),
        "kpi_impact",
    ),
    (
        re.compile(r"\b(stakeholder|cross-functional|product team|leadership)\b", re.IGNORECASE),
        ("stakeholder communication", "cross-functional collaboration"),
        "stakeholder_collaboration",
    ),
    (
        re.compile(r"\b(experiment|ab\s*test|hypothesis|statistical)\b", re.IGNORECASE),
        ("experimentation", "statistical analysis"),
        "experimentation",
    ),
)


_SKILL_HINT_EXPANSION: dict[str, tuple[str, ...]] = {
    "dashboard": ("data visualization", "data storytelling"),
    "tableau": ("data visualization", "data storytelling"),
    "power bi": ("data visualization", "business reporting"),
    "analysis": ("business insights", "analytical thinking"),
    "sql": ("data querying", "data analysis"),
    "python": ("data analysis", "automation"),
    "statistics": ("statistical analysis", "decision support"),
}


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_skill(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _expand_with_skill_graph(skills: list[str]) -> list[str]:
    expanded: list[str] = list(skills)
    known: set[str] = set(skills)

    for parent, data in SKILL_GRAPH.items():
        parent_norm = normalize_skill(parent)
        children = [normalize_skill(item) for item in data.get("related", []) + data.get("tools", [])]

        if parent_norm in known or any(child in known for child in children):
            if parent_norm not in known:
                expanded.append(parent_norm)
                known.add(parent_norm)
            for child in children:
                if child and child not in known:
                    expanded.append(child)
                    known.add(child)

    return expanded


def enrich_resume_context(raw_text: str, parsed_skills: list[str] | None = None) -> dict[str, Any]:
    """Infer implicit skills from raw narrative + parsed skill hints."""
    text_value = str(raw_text or "")
    lower_text = text_value.lower()

    inferred: list[str] = []
    evidence: list[dict[str, str]] = []

    for pattern, mapped_skills, signal in _RESUME_TEXT_INFERENCES:
        if not pattern.search(lower_text):
            continue
        for skill in mapped_skills:
            inferred.append(skill)
            evidence.append({"signal": signal, "mapped_skill": normalize_skill(skill)})

    for raw_skill in parsed_skills or []:
        normalized = normalize_skill(str(raw_skill or ""))
        inferred.append(normalized)
        for skill in _SKILL_HINT_EXPANSION.get(normalized, ()):
            inferred.append(skill)
            evidence.append({"signal": f"parsed_skill:{normalized}", "mapped_skill": normalize_skill(skill)})

    inferred = _dedupe(_expand_with_skill_graph(_dedupe(inferred)))

    return {
        "inferred_skills": inferred,
        "evidence": evidence[:40],
        "mode": "raw_text_plus_skill_hints",
    }


def enrich_jd_context(jd_context: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize semantic JD hints so prompts can consume them consistently."""
    context = dict(jd_context or {})

    intent_rows = context.get("responsibility_intents", [])
    intent_list = intent_rows if isinstance(intent_rows, list) else []

    inferred = context.get("skills_inferred_from_intent", [])
    inferred_list = _dedupe([str(item) for item in inferred]) if isinstance(inferred, list) else []

    if not inferred_list:
        for row in intent_list:
            if not isinstance(row, dict):
                continue
            mapped = row.get("mapped_skills", [])
            if isinstance(mapped, list):
                inferred_list.extend([str(item) for item in mapped])
        inferred_list = _dedupe(inferred_list)

    return {
        "responsibility_intents": intent_list,
        "skills_inferred_from_intent": inferred_list,
    }
