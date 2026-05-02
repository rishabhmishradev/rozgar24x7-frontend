"""Job description parsing utilities for skills and keywords."""

from __future__ import annotations

import importlib
import re
from typing import Any, cast

from .entity_extractor import CORE_SKILLS, SKILL_GRAPH, normalize_skill
from app.intelligence.utils import semantic_similarity


RESPONSIBILITY_VERBS = {
    "develop",
    "design",
    "build",
    "deploy",
    "architect",
    "optimize",
    "maintain",
    "implement",
    "lead",
    "collaborate",
}

OPTIONAL_MARKERS = ("nice to have", "preferred", "bonus", "plus")
EMPHASIS_MARKERS = ("must", "required", "strong", "mandatory", "expert")

SECTION_HEADER_RE = re.compile(r"^[A-Z\s/&:-]{3,}$")
LINE_SPLIT_RE = re.compile(r"\r?\n")
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
INLINE_BULLET_SPLIT_RE = re.compile(r"\s+(?:[-*•])\s+")
NOUN_PHRASE_RE = re.compile(r"\b[a-z][a-z0-9+#./-]*(?:\s+[a-z][a-z0-9+#./-]*){0,3}\b", re.IGNORECASE)

SECTION_REQUIRED_MARKERS = (
    "requirements",
    "must have",
    "required",
    "qualifications",
    "what we're looking for",
)
SECTION_OPTIONAL_MARKERS = (
    "nice to have",
    "preferred",
    "bonus",
    "plus",
    "good to have",
)

SKILL_STOPWORDS = {
    "required",
    "optional",
    "requirements",
    "qualification",
    "qualifications",
    "responsibilities",
    "role",
    "team",
    "experience",
    "candidate",
    "ability",
    "skills",
    "job description",
    "key responsibilities",
}

RESPONSIBILITY_INTENT_PATTERNS: dict[str, dict[str, Any]] = {
    "stakeholder_communication": {
        "intent": "Communicate technical findings in business language",
        "patterns": (
            r"\bcommunicat(?:e|ed|ing)\b.*\b(insight|finding|recommendation)\b",
            r"\b(stakeholder|leadership|executive|product team)\b",
            r"\bactionable insights?\b",
        ),
        "mapped_skills": (
            "data storytelling",
            "stakeholder communication",
            "business communication",
        ),
    },
    "analytics_interpretation": {
        "intent": "Turn raw analysis into decisions",
        "patterns": (
            r"\banaly[sz](?:e|ed|ing|es|sis)\b.*\b(trend|behavior|cohort|segment|pattern)\b",
            r"\b(customer|user|market)\b.*\b(trend|behavior|retention|conversion)\b",
            r"\binsight\b.*\bdecision\b",
        ),
        "mapped_skills": (
            "business insights",
            "analytical thinking",
            "decision support",
        ),
    },
    "product_impact_execution": {
        "intent": "Deliver measurable product or business outcomes",
        "patterns": (
            r"\b(retention|conversion|growth|revenue|kpi|impact)\b",
            r"\boptimi[sz](?:e|ed|ing)\b.*\b(performance|outcome|business|process)\b",
            r"\bimprov(?:e|ed|ing)\b.*\b(retention|conversion|engagement|efficiency)\b",
        ),
        "mapped_skills": (
            "business impact",
            "kpi management",
            "product analytics",
        ),
    },
    "cross_functional_delivery": {
        "intent": "Collaborate across teams to ship outcomes",
        "patterns": (
            r"\bcross[-\s]?functional\b",
            r"\bcollaborat(?:e|ed|ing)\b",
            r"\bwork(?:ed|ing)?\b.*\b(product|engineering|design|business)\b",
        ),
        "mapped_skills": (
            "cross-functional collaboration",
            "stakeholder management",
            "project execution",
        ),
    },
}

EXTRA_JD_TECH_SKILLS = {
    "machine learning",
    "deep learning",
    "cnn",
    "rnn",
    "transformer",
    "transformers",
    "python",
    "pytorch",
    "tensorflow",
    "aws",
    "gcp",
    "azure",
}


def _skill_catalog() -> set[str]:
    catalog: set[str] = set(normalize_skill(skill) for skill in CORE_SKILLS)
    for parent, data in SKILL_GRAPH.items():
        catalog.add(normalize_skill(parent))
        for item in data.get("related", []):
            catalog.add(normalize_skill(item))
        for item in data.get("tools", []):
            catalog.add(normalize_skill(item))
    for skill in EXTRA_JD_TECH_SKILLS:
        catalog.add(normalize_skill(skill))
    return catalog


def _extract_sentence_skills(sentence: str, catalog: set[str]) -> set[str]:
    lowered = sentence.lower()
    found: set[str] = set()
    for skill in catalog:
        if re.search(rf"\b{re.escape(skill)}\b", lowered):
            found.add(skill)
    return found


def _clean_line(line: str) -> str:
    line = BULLET_PREFIX_RE.sub("", line.strip())
    line = re.sub(r"\s+", " ", line)
    return line.strip(" -:\t")


def _is_section_header(line: str) -> bool:
    cleaned = _clean_line(line).lower().strip(":")
    if not cleaned:
        return True
    if SECTION_HEADER_RE.match(line.strip()):
        # Keep uppercase multi-word titles as headers, but avoid filtering acronym skills (e.g., AWS).
        if len(cleaned.split()) > 1:
            return True

    words = cleaned.split()
    if len(words) <= 6 and (
        any(marker in cleaned for marker in SECTION_REQUIRED_MARKERS)
        or any(marker in cleaned for marker in SECTION_OPTIONAL_MARKERS)
        or "responsibilities" in cleaned
        or "skills" in cleaned
    ):
        return True
    return False


def _extract_noun_chunks(text: str) -> list[str]:
    try:
        spacy = importlib.import_module("spacy")
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        return [normalize_skill(chunk.text) for chunk in doc.noun_chunks if chunk.text.strip()]
    except Exception:
        # Regex fallback if spaCy model is unavailable.
        phrases: list[str] = []
        for match in NOUN_PHRASE_RE.findall(text.lower()):
            phrase = normalize_skill(match)
            if 2 <= len(phrase) <= 50:
                phrases.append(phrase)
        return phrases


def _is_skill_candidate_phrase(candidate: str) -> bool:
    skill = normalize_skill(candidate)
    if not skill or skill in SKILL_STOPWORDS:
        return False

    tokens = skill.split()
    if not tokens or len(tokens) > 4:
        return False

    if re.search(r"[,;:.!?]", candidate):
        return False

    generic_tokens = {
        "experience",
        "ability",
        "team",
        "candidate",
        "role",
        "environment",
        "communication",
        "problem",
        "problems",
        "skills",
        "knowledge",
    }
    if all(token in generic_tokens for token in tokens):
        return False

    return True


def _map_candidates_to_catalog(
    candidates: list[str],
    catalog: set[str],
    *,
    allow_semantic_fallback: bool = True,
    semantic_threshold: float = 0.86,
) -> set[str]:
    mapped: set[str] = set()
    for candidate in candidates:
        if not _is_skill_candidate_phrase(candidate):
            continue
        skill = normalize_skill(candidate)
        if skill in catalog:
            mapped.add(skill)
            continue

        if not allow_semantic_fallback:
            continue

        # Embedding/semantic fallback for near matches and aliases.
        best_skill = ""
        best_score = 0.0
        for catalog_skill in catalog:
            similarity, _method = semantic_similarity(skill, catalog_skill)
            if similarity > best_score:
                best_score = similarity
                best_skill = catalog_skill
        if best_skill and best_score >= semantic_threshold:
            candidate_tokens = set(skill.split())
            best_tokens = set(best_skill.split())
            has_lexical_anchor = bool(candidate_tokens & best_tokens)
            has_technical_shape = any(char in skill for char in "+#./") or any(char.isdigit() for char in skill)
            if has_lexical_anchor or has_technical_shape:
                mapped.add(best_skill)

    return mapped


def _jd_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    for raw_line in LINE_SPLIT_RE.split(text):
        line = raw_line.strip()
        if not line:
            continue

        inline_parts = [p.strip() for p in INLINE_BULLET_SPLIT_RE.split(line) if p.strip()]
        for part in inline_parts:
            cleaned = _clean_line(part)
            if cleaned:
                fragments.append(cleaned)

    return fragments


def _sentence_units(fragment: str) -> list[str]:
    units = [u.strip() for u in re.split(r"(?<=[.!?])\s+", fragment) if u.strip()]
    return units if units else [fragment]


def _importance_weighting(text: str, skills: set[str]) -> dict[str, float]:
    lowered = text.lower()
    raw_importance: dict[str, float] = {}
    for skill in skills:
        frequency = len(re.findall(rf"\b{re.escape(skill)}\b", lowered))
        emphasis_bonus = 0.0

        for sentence in re.split(r"(?<=[.!?])\s+", text):
            line = sentence.lower()
            if re.search(rf"\b{re.escape(skill)}\b", line) and any(marker in line for marker in EMPHASIS_MARKERS):
                emphasis_bonus += 1.0

        raw_importance[skill] = float(frequency) + emphasis_bonus

    if not raw_importance:
        return {}

    max_value = max(raw_importance.values()) or 1.0
    return {skill: round(value / max_value, 3) for skill, value in raw_importance.items()}


def _extract_tools(skills: set[str]) -> list[str]:
    tools: set[str] = set()
    for _parent, data in SKILL_GRAPH.items():
        for tool in data.get("tools", []):
            tool_norm = normalize_skill(tool)
            if tool_norm in skills:
                tools.add(tool_norm)
    return sorted(tools)


def _extract_responsibilities(text: str, sentences: list[str]) -> list[str]:
    responsibilities: list[str] = []

    # Prefer explicit bullet lines when present.
    in_responsibility_section = False
    for raw_line in LINE_SPLIT_RE.split(text):
        stripped = raw_line.strip()
        if not stripped:
            continue

        cleaned_header = _clean_line(stripped).lower().strip(":")
        if _is_section_header(stripped):
            in_responsibility_section = "responsibilities" in cleaned_header
            continue

        if not BULLET_PREFIX_RE.match(stripped):
            continue
        cleaned = _clean_line(stripped)
        lowered = cleaned.lower()
        has_action_verb = any(re.search(rf"\b{verb}\b", lowered) for verb in RESPONSIBILITY_VERBS)
        if cleaned and not _is_section_header(cleaned) and (in_responsibility_section or has_action_verb):
            responsibilities.append(cleaned)

    if responsibilities:
        seen_bullets: set[str] = set()
        deduped_bullets: list[str] = []
        for item in responsibilities:
            key = item.lower()
            if key in seen_bullets:
                continue
            seen_bullets.add(key)
            deduped_bullets.append(item)
        return deduped_bullets

    for fragment in _jd_fragments(text):
        if _is_section_header(fragment):
            continue
        for unit in _sentence_units(fragment):
            lowered = unit.lower()
            if any(re.search(rf"\b{verb}\b", lowered) for verb in RESPONSIBILITY_VERBS):
                responsibilities.append(unit)

    if not responsibilities:
        for sentence in sentences:
            lowered = sentence.lower()
            if any(re.search(rf"\b{verb}\b", lowered) for verb in RESPONSIBILITY_VERBS):
                responsibilities.append(sentence.strip())

    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for item in responsibilities:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_responsibility_intents(
    responsibilities: list[str],
    text: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Map responsibility phrasing to semantic intent and implied skills."""
    corpus: list[str] = [item for item in responsibilities if str(item).strip()]
    if not corpus:
        corpus = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ]

    clusters: dict[str, dict[str, Any]] = {}
    inferred_skills: set[str] = set()

    for sentence in corpus:
        normalized = sentence.lower()
        for cluster_key, config in RESPONSIBILITY_INTENT_PATTERNS.items():
            patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.get("patterns", ())]
            if not any(pattern.search(normalized) for pattern in patterns):
                continue

            cluster = clusters.setdefault(
                cluster_key,
                {
                    "cluster": cluster_key,
                    "intent": str(config.get("intent", "")).strip(),
                    "evidence": [],
                    "mapped_skills": [],
                },
            )

            evidence = cast(list[str], cluster["evidence"])
            if sentence not in evidence and len(evidence) < 4:
                evidence.append(sentence)

            mapped = cast(list[str], cluster["mapped_skills"])
            for skill in config.get("mapped_skills", ()):  # type: ignore[arg-type]
                normalized_skill = normalize_skill(str(skill))
                if normalized_skill and normalized_skill not in mapped:
                    mapped.append(normalized_skill)
                    inferred_skills.add(normalized_skill)

    intent_rows: list[dict[str, Any]] = []
    for cluster_key in sorted(clusters.keys()):
        row = clusters[cluster_key]
        row["mapped_skills"] = sorted(cast(list[str], row.get("mapped_skills", [])))
        intent_rows.append(row)

    return intent_rows, inferred_skills


def parse_job_description(text: str) -> dict[str, Any]:
    lowered = text.lower()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    catalog = _skill_catalog()

    skills_required: set[str] = set()
    skills_optional: set[str] = set()
    parse_warnings: list[str] = []

    current_section = "required"
    fragments = _jd_fragments(text)

    for fragment in fragments:
        normalized_fragment = fragment.lower().strip(":")
        if _is_section_header(fragment):
            if any(marker in normalized_fragment for marker in SECTION_OPTIONAL_MARKERS):
                current_section = "optional"
            elif any(marker in normalized_fragment for marker in SECTION_REQUIRED_MARKERS):
                current_section = "required"
            continue

        for unit in _sentence_units(fragment):
            normalized_unit = unit.lower().strip(":")
            sentence_skills = _extract_sentence_skills(unit, catalog)
            noun_candidates = [value for value in _extract_noun_chunks(unit) if _is_skill_candidate_phrase(value)]
            mapped_noun_skills = _map_candidates_to_catalog(
                noun_candidates,
                catalog,
                allow_semantic_fallback=False,
            )
            unit_skills = sentence_skills | mapped_noun_skills

            # Strict fallback: only accept direct catalog hits from the full unit text.
            if not unit_skills:
                unit_skills |= _map_candidates_to_catalog(
                    [normalized_unit],
                    catalog,
                    allow_semantic_fallback=False,
                )

            if not unit_skills:
                continue

            has_optional_marker = any(marker in normalized_unit for marker in OPTIONAL_MARKERS)
            has_required_marker = any(marker in normalized_unit for marker in EMPHASIS_MARKERS)
            is_optional = (current_section == "optional" or has_optional_marker) and not has_required_marker
            if is_optional:
                skills_optional |= unit_skills
            else:
                skills_required |= unit_skills

    # Global fallback if section-level extraction fails.
    if not skills_required and not skills_optional:
        noun_candidates = [value for value in _extract_noun_chunks(text) if _is_skill_candidate_phrase(value)]
        fallback_skills = _map_candidates_to_catalog(
            noun_candidates,
            catalog,
            allow_semantic_fallback=False,
        )
        skills_required |= fallback_skills
        if fallback_skills:
            parse_warnings.append("skills_extracted_via_global_noun_fallback")
        else:
            parse_warnings.append("skills_required_extraction_low_confidence")

    seniority = "unknown"
    if "senior" in lowered or "7+ years" in lowered:
        seniority = "senior"
    elif "lead" in lowered or "principal" in lowered:
        seniority = "lead"
    elif "junior" in lowered or "entry" in lowered:
        seniority = "junior"

    all_skills = skills_required | skills_optional
    responsibilities = _extract_responsibilities(text, sentences)
    responsibility_intents, intent_skills = _extract_responsibility_intents(
        responsibilities,
        text,
    )
    skills_optional |= {
        skill for skill in intent_skills if skill and skill not in skills_required
    }
    all_skills = skills_required | skills_optional
    importance = _importance_weighting(text, all_skills)

    return {
        "skills_required": sorted(skills_required),
        "skills_optional": sorted(skills_optional),
        "skills_inferred_from_intent": sorted(intent_skills),
        "responsibility_intents": responsibility_intents,
        "parse_warnings": parse_warnings,
        "importance": importance,
        "importance_weights": importance,
        "responsibilities": responsibilities,
        "tools": _extract_tools(all_skills),
        "seniority": seniority,
        "raw": text,
    }
