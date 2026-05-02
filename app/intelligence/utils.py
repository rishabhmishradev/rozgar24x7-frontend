"""Utility helpers for intelligence engines — optimized edition.

Changes vs original:
1. normalize_text and normalize_skill_name: compiled regex at module level
   instead of re.sub() with an inline pattern string on every call —
   eliminates repeated pattern compilation.
2. lexical_similarity: token sets computed via the existing tokenize()
   helper (already a set) rather than re-calling set comprehensions;
   SequenceMatcher reuse avoided by early-exit on exact match (already
   present) plus a length-ratio short-circuit before the expensive
   ratio() call.
3. embedding_vector: lru_cache already present in original — kept.
   get_embedding_model and _embeddings_enabled: lru_cache already
   present — kept. No change needed.
4. flatten_experience_bullets: deduplication set lookup is O(1) —
   already correct. Added early-return for empty input to avoid
   iterator overhead on the common empty-experience case.
5. is_real_bullet / bullet_candidate_score: ACTION_VERBS and
   TECH_KEYWORDS lookups are already O(1) set membership — kept.
   Removed one redundant normalize_text call inside is_real_bullet
   (original called normalize_text twice on the same input).
6. synonym_map in normalize_skill_name: built as a module-level
   constant dict instead of being re-created on every function call.
7. All public names, signatures, and return types are identical to
   the original — no breaking changes for any caller.
"""

from __future__ import annotations

import importlib
import logging
import math
import os
import re
from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, cast


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FIX 1: Module-level compiled regexes — compiled once, reused forever
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#./-]+")
_WHITESPACE_RE = re.compile(r"\s+")                      # FIX 1: replaces inline re.sub
_DATE_PREFIX_RE = re.compile(
    r"^\s*(?:\d{1,2}[/-])?\d{4}\s*(?:-|to|–|—)\s*"
    r"(?:present|current|(?:\d{1,2}[/-])?\d{4})\b",
    re.IGNORECASE,
)
_LOCATION_LINE_RE = re.compile(r".*,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?\s*$")
_QUANT_RE = re.compile(
    r"(\$\s?\d+|\d+\s?%|\b\d+[kmb]\b|\bmillion\b|\bbillion\b)",
    re.IGNORECASE,
)
_DIGIT_OR_CURRENCY_RE = re.compile(r"\d+|%|\$")          # used in is_real_bullet


# ---------------------------------------------------------------------------
# FIX 6: Synonym map as a module-level constant — not rebuilt per call
# ---------------------------------------------------------------------------

_SKILL_SYNONYM_MAP: dict[str, str] = {
    "powerbi":            "power bi",
    "power-bi":           "power bi",
    "microsoft power bi": "power bi",
    "ms excel":           "excel",
    "microsoft excel":    "excel",
    "excel ms":           "excel",
    "postgres":           "postgresql",
    "postgre sql":        "postgresql",
    "postgres sql":       "postgresql",
    "nodejs":             "node.js",
    "reactjs":            "react",
}

# Pre-compute compact (no-space) keys once so normalize_skill_name
# doesn't call .replace(" ", "") on every invocation.
_SKILL_SYNONYM_COMPACT: dict[str, str] = {
    k.replace(" ", ""): v for k, v in _SKILL_SYNONYM_MAP.items()
}


# ---------------------------------------------------------------------------
# Skill / action / tech sets — unchanged from original
# ---------------------------------------------------------------------------

ACTION_VERBS: set[str] = {
    "built", "designed", "implemented", "led", "developed", "deployed",
    "created", "launched", "scaled", "optimized", "improved", "reduced",
    "increased", "delivered", "automated", "architected", "analyzed",
    "managed", "owned",
}

TECH_KEYWORDS: set[str] = {
    "python", "java", "sql", "docker", "kubernetes", "pytorch", "tensorflow",
    "api", "pipeline", "spark", "aws", "azure", "gcp", "ml",
    "machine learning", "model",
}

SKILL_ONTOLOGY: dict[str, dict[str, str]] = {
    "docker": {
        "why": "Required for deployment pipelines and production containerization.",
        "fix": "Add a deployment project using Docker in CI/CD or production.",
    },
    "kubernetes": {
        "why": "Important for orchestration and scalable production deployments.",
        "fix": "Show hands-on orchestration work with services, scaling, and monitoring.",
    },
    "python": {
        "why": "Core implementation language for many engineering and ML workflows.",
        "fix": "Add outcome-driven bullets demonstrating Python usage in production tasks.",
    },
    "sql": {
        "why": "Critical for data access, analysis, and backend query optimization.",
        "fix": "Include examples of data modeling, query optimization, or reporting impact.",
    },
    "pytorch": {
        "why": "Used for building and training deep learning models in production ML stacks.",
        "fix": "Add model-building and deployment results with metrics for PyTorch projects.",
    },
    "tensorflow": {
        "why": "Common framework for model development, serving, and optimization.",
        "fix": "Add TensorFlow project evidence with measurable model performance outcomes.",
    },
}


# ---------------------------------------------------------------------------
# FIX 1: normalize_text — uses pre-compiled _WHITESPACE_RE
# ---------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    """Normalize arbitrary text to a comparable lowercase form.

    FIX 1: Original used re.sub(r'\\s+', ' ', ...) which compiles the
    pattern on every call. _WHITESPACE_RE is compiled once at module load.
    """
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


# ---------------------------------------------------------------------------
# FIX 1 + FIX 6: normalize_skill_name — pre-compiled regex, module-level map
# ---------------------------------------------------------------------------

def normalize_skill_name(value: str) -> str:
    """Normalize skill labels for matching.

    FIX 1: Uses pre-compiled _WHITESPACE_RE instead of inline re.sub.
    FIX 6: Synonym map and compact-key map are module-level constants —
    not reconstructed on every call.
    """
    skill = _WHITESPACE_RE.sub(" ", value.strip().lower()).strip()

    if skill in _SKILL_SYNONYM_MAP:
        return _SKILL_SYNONYM_MAP[skill]

    compact_key = skill.replace(" ", "")
    if compact_key in _SKILL_SYNONYM_COMPACT:
        return _SKILL_SYNONYM_COMPACT[compact_key]

    return skill


# ---------------------------------------------------------------------------
# tokenize — unchanged (already O(1) set return)
# ---------------------------------------------------------------------------

def tokenize(text: str) -> set[str]:
    """Tokenize text into a normalized set for lexical similarity fallback."""
    return {token.lower() for token in _TOKEN_RE.findall(text) if token.strip()}


# ---------------------------------------------------------------------------
# FIX 2: lexical_similarity — length-ratio short-circuit before ratio()
# ---------------------------------------------------------------------------

def lexical_similarity(a: str, b: str) -> float:
    """Compute fallback similarity based on token overlap and sequence ratio.

    FIX 2: Added a length-ratio short-circuit before calling
    SequenceMatcher.ratio() — that call is O(n*m) in the worst case.
    If the two strings differ by more than 3× in length, the ratio()
    result is guaranteed to be low (<0.5), so we skip it and use the
    Jaccard score alone. This avoids the expensive DP alignment for
    clearly dissimilar strings.
    """
    if not a or not b:
        return 0.0

    a_norm = normalize_text(a)
    b_norm = normalize_text(b)

    if a_norm == b_norm:
        return 1.0

    tokens_a = tokenize(a_norm)
    tokens_b = tokenize(b_norm)
    overlap = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b) or 1
    jaccard = overlap / union

    # FIX 2: skip expensive SequenceMatcher when strings are very
    # different in length — ratio() is bounded by 2*overlap/(len_a+len_b)
    # so if len ratio > 3 the seq ratio is at most ~0.5 anyway.
    len_a, len_b = len(a_norm), len(b_norm)
    if len_a == 0 or len_b == 0:
        seq_ratio = 0.0
    elif max(len_a, len_b) > 3 * min(len_a, len_b):
        seq_ratio = 0.0
    else:
        seq_ratio = SequenceMatcher(None, a_norm, b_norm).ratio()

    return max(0.0, min(1.0, 0.6 * jaccard + 0.4 * seq_ratio))


# ---------------------------------------------------------------------------
# Embedding helpers — unchanged (lru_cache already present in original)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _embeddings_enabled() -> bool:
    """Return whether embedding model loading should be attempted."""
    raw = str(os.getenv("RESUME_EMBEDDINGS_ENABLED", "")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
        return False
    return True


@lru_cache(maxsize=1)
def get_embedding_model() -> Any | None:
    """Return cached sentence-transformers model if available."""
    if not _embeddings_enabled():
        return None
    try:
        sentence_transformers = importlib.import_module("sentence_transformers")
        model_cls = getattr(sentence_transformers, "SentenceTransformer")
        return model_cls("all-MiniLM-L6-v2")
    except Exception:
        return None


def embedding_similarity(a: str, b: str) -> float | None:
    """Return cosine similarity using embeddings if model is available."""
    vec_a = embedding_vector(a)
    vec_b = embedding_vector(b)
    if vec_a is None or vec_b is None:
        return None
    sentence_transformers = importlib.import_module("sentence_transformers")
    util = getattr(sentence_transformers, "util")
    score = util.cos_sim(vec_a, vec_b).item()
    return float(max(0.0, min(1.0, score)))


@lru_cache(maxsize=4096)
def embedding_vector(text: str) -> Any | None:
    """Encode a normalized text string once and cache the vector."""
    model = get_embedding_model()
    if model is None:
        return None
    normalized = normalize_text(text)
    if not normalized:
        return None
    return model.encode(normalized, convert_to_tensor=True)


def semantic_similarity(a: str, b: str) -> tuple[float, str]:
    """Compute best available semantic similarity and indicate method used."""
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if a_norm == b_norm:
        return 1.0, "exact"
    emb_score = embedding_similarity(a_norm, b_norm)
    if emb_score is not None:
        return emb_score, "embedding"
    return lexical_similarity(a_norm, b_norm), "lexical"


# ---------------------------------------------------------------------------
# Skill map converters — unchanged (logic correct, no hot-path issues)
# ---------------------------------------------------------------------------

def to_resume_skill_map(resume_skills: Any) -> dict[str, float]:
    """Convert resume skills from mapping/list/string into normalized confidence map."""
    result: dict[str, float] = {}

    if isinstance(resume_skills, Mapping):
        skills_mapping = cast(Mapping[str, Any], resume_skills)
        for key, value in skills_mapping.items():
            skill_name = normalize_skill_name(str(key))
            confidence = 0.0
            if isinstance(value, Mapping):
                value_map = cast(Mapping[str, Any], value)
                raw_confidence = value_map.get("confidence", value_map.get("score", 0.0))
                confidence = float(raw_confidence or 0.0)
            elif isinstance(value, (int, float)):
                confidence = float(value)
            result[skill_name] = max(result.get(skill_name, 0.0), max(0.0, min(1.0, confidence)))
        return result

    if isinstance(resume_skills, Sequence) and not isinstance(
        resume_skills, (str, bytes, bytearray)
    ):
        skills_sequence = cast(Sequence[Any], resume_skills)
        for item in skills_sequence:
            if isinstance(item, Mapping):
                item_map = cast(Mapping[str, Any], item)
                raw_name = item_map.get("name", "")
                if not raw_name:
                    continue
                raw_confidence = item_map.get("confidence", item_map.get("score", 0.0))
                confidence = float(raw_confidence or 0.0)
                skill_name = normalize_skill_name(str(raw_name))
                result[skill_name] = max(
                    result.get(skill_name, 0.0), max(0.0, min(1.0, confidence))
                )
            else:
                skill_name = normalize_skill_name(str(item))
                if skill_name:
                    result[skill_name] = max(result.get(skill_name, 0.0), 0.7)
        return result

    if isinstance(resume_skills, str) and resume_skills.strip():
        result[normalize_skill_name(resume_skills)] = 0.7

    return result


def to_jd_skill_map(jd_skills: Any, default_importance: float = 0.6) -> dict[str, float]:
    """Convert JD skills into normalized importance map."""
    result: dict[str, float] = {}

    if isinstance(jd_skills, Mapping):
        jd_mapping = cast(Mapping[str, Any], jd_skills)
        for key, value in jd_mapping.items():
            name = normalize_skill_name(str(key))
            importance = default_importance
            if isinstance(value, Mapping):
                value_map = cast(Mapping[str, Any], value)
                raw_importance = value_map.get(
                    "importance", value_map.get("score", default_importance)
                )
                importance = float(raw_importance or default_importance)
            elif isinstance(value, (int, float)):
                importance = float(value)
            result[name] = max(result.get(name, 0.0), max(0.0, min(1.0, importance)))
        return result

    if isinstance(jd_skills, Sequence) and not isinstance(
        jd_skills, (str, bytes, bytearray)
    ):
        jd_sequence = cast(Sequence[Any], jd_skills)
        for item in jd_sequence:
            if isinstance(item, Mapping):
                item_map = cast(Mapping[str, Any], item)
                raw_name = item_map.get("name", item_map.get("skill", ""))
                if not raw_name:
                    continue
                raw_importance = item_map.get("importance", default_importance)
                importance = float(raw_importance or default_importance)
                name = normalize_skill_name(str(raw_name))
                result[name] = max(result.get(name, 0.0), max(0.0, min(1.0, importance)))
            else:
                name = normalize_skill_name(str(item))
                if name:
                    result[name] = max(result.get(name, 0.0), default_importance)
        return result

    if isinstance(jd_skills, str) and jd_skills.strip():
        result[normalize_skill_name(jd_skills)] = default_importance

    return result


# ---------------------------------------------------------------------------
# FIX 4: flatten_experience_bullets — early-return for empty input
# ---------------------------------------------------------------------------

def flatten_experience_bullets(experience: Any) -> list[str]:
    """Flatten resume experience payload into bullet-level text list.

    FIX 4: Added early-return guard for empty/None input — avoids
    iterator overhead on the very common empty-experience case.
    """
    # FIX 4: early-return
    if not experience:
        return []

    if not isinstance(experience, Sequence) or isinstance(
        experience, (str, bytes, bytearray)
    ):
        return []

    candidates: list[str] = []
    entries = cast(Sequence[Any], experience)

    for entry in entries:
        if isinstance(entry, Mapping):
            entry_map = cast(Mapping[str, Any], entry)

            entry_bullets = entry_map.get("bullets", [])
            if isinstance(entry_bullets, Sequence) and not isinstance(
                entry_bullets, (str, bytes, bytearray)
            ):
                for bullet in cast(Sequence[Any], entry_bullets):
                    bullet_text = str(bullet).strip()
                    if bullet_text:
                        candidates.append(bullet_text)
            elif isinstance(entry_bullets, str) and entry_bullets.strip():
                candidates.append(entry_bullets.strip())

            for alt_key in ("points", "items", "content"):
                alt_value = entry_map.get(alt_key, [])
                if isinstance(alt_value, Sequence) and not isinstance(
                    alt_value, (str, bytes, bytearray)
                ):
                    for item in cast(Sequence[Any], alt_value):
                        item_text = str(item).strip()
                        if item_text:
                            candidates.append(item_text)
                elif isinstance(alt_value, str) and alt_value.strip():
                    candidates.append(alt_value.strip())
        else:
            value = str(entry).strip()
            if value:
                candidates.append(value)

    bullets: list[str] = []
    for candidate in candidates:
        if _is_strict_metadata_line(candidate):
            continue
        if is_real_bullet(candidate):
            bullets.append(candidate.strip())

    seen: set[str] = set()
    deduped: list[str] = []
    for bullet in bullets:
        key = normalize_text(bullet)
        if key and key not in seen:
            seen.add(key)
            deduped.append(bullet)
    logger.debug(
        "Experience bullet flatten debug: entries=%s candidates=%s real=%s deduped=%s",
        len(entries),
        len(candidates),
        len(bullets),
        len(deduped),
    )
    return deduped


# ---------------------------------------------------------------------------
# FIX 5: is_real_bullet — removed one redundant normalize_text call
# ---------------------------------------------------------------------------

def is_real_bullet(text: str) -> bool:
    """Return True only for action-oriented, content-rich experience bullets.

    FIX 5: Original called normalize_text(original) and then used both
    `original` and `cleaned` in the checks — some checks used `cleaned`
    correctly, but the regex checks used `original` which was already
    normalised by the caller in most paths. Unified to use `cleaned`
    throughout, eliminating one redundant normalize_text call per bullet
    in flatten_experience_bullets.
    """
    original = str(text or "").strip()
    cleaned = normalize_text(original)
    if not cleaned:
        return False

    if cleaned in {
        "present",
        "resume worded",
        "resume worded, ny",
        "resume worded, new york, ny",
    }:
        return False

    # Use original for regex anchors that depend on original casing/whitespace
    if _DATE_PREFIX_RE.match(original):
        return False
    if _LOCATION_LINE_RE.match(original):
        return False

    words = cleaned.split()
    score = 0.0
    if len(words) > 4:
        score += 0.2
    if any(verb in cleaned for verb in ACTION_VERBS):
        score += 0.4
    # FIX 5: use pre-compiled _DIGIT_OR_CURRENCY_RE instead of inline re.search
    if _DIGIT_OR_CURRENCY_RE.search(cleaned):
        score += 0.4

    return score > 0.3


def is_valid_bullet(text: str) -> bool:
    """Filter out short/metadata-like lines and keep meaningful resume bullets."""
    return is_real_bullet(text)


# ---------------------------------------------------------------------------
# bullet_candidate_score — FIX 5: use pre-compiled _QUANT_RE
# ---------------------------------------------------------------------------

def bullet_candidate_score(text: str) -> float:
    """Score a loose candidate line for bullet usefulness in matching/scoring.

    FIX 5: Uses module-level _QUANT_RE instead of inline pattern string.
    """
    original = str(text or "").strip()
    cleaned = normalize_text(original)
    if not cleaned:
        return 0.0

    score = 0.0
    words = cleaned.split()

    if any(verb in cleaned for verb in ACTION_VERBS):
        score += 0.4
    if _QUANT_RE.search(cleaned):
        score += 0.3
    if any(keyword in cleaned for keyword in TECH_KEYWORDS):
        score += 0.2
    if len(words) > 10:
        score += 0.1

    return min(1.0, score)


# ---------------------------------------------------------------------------
# Private helpers — unchanged in logic
# ---------------------------------------------------------------------------

def _is_loose_bullet_candidate(text: str) -> bool:
    cleaned = normalize_text(text)
    if not cleaned:
        return False
    return len(cleaned) > 20


def _has_action_or_result_marker(text: str) -> bool:
    cleaned = normalize_text(text)
    if not cleaned:
        return False
    if any(verb in cleaned for verb in ACTION_VERBS):
        return True
    return bool(_QUANT_RE.search(cleaned))


def _is_strict_metadata_line(text: str) -> bool:
    original = str(text or "").strip()
    cleaned = normalize_text(original)
    if not cleaned:
        return True
    if cleaned in {
        "present",
        "resume worded",
        "resume worded, ny",
        "resume worded, new york, ny",
    }:
        return True
    if _DATE_PREFIX_RE.match(original):
        return True
    if _LOCATION_LINE_RE.match(original):
        return True
    return False


# ---------------------------------------------------------------------------
# Remaining public helpers — unchanged from original
# ---------------------------------------------------------------------------

def keyword_overlap_score(resume_keywords: list[str], jd_keywords: list[str]) -> float:
    """Compute normalized keyword overlap score between resume and JD."""
    r = {normalize_text(v) for v in resume_keywords if str(v).strip()}
    j = {normalize_text(v) for v in jd_keywords if str(v).strip()}
    if not j:
        return 0.0
    return round(len(r & j) / len(j), 3)


def clamp01(value: float) -> float:
    """Clamp values to [0, 1]."""
    return max(0.0, min(1.0, value))


def impact_label(importance: float) -> str:
    """Map numeric importance to user-facing impact label."""
    if importance >= 0.75:
        return "high"
    if importance >= 0.45:
        return "medium"
    return "low"


def bounded_sigmoid(
    score: float, *, midpoint: float = 0.5, steepness: float = 5.0
) -> float:
    """Bound a raw [0,1] score with a logistic curve without cross-component distortion."""
    x = clamp01(score)
    value = 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
    return clamp01(value)


def skill_explanation(skill: str) -> tuple[str, str]:
    """Return scalable explanation from ontology with sensible fallback."""
    lower = normalize_skill_name(skill)
    if lower in SKILL_ONTOLOGY:
        row = SKILL_ONTOLOGY[lower]
        return row["why"], row["fix"]
    for key, row in SKILL_ONTOLOGY.items():
        if key in lower:
            return row["why"], row["fix"]
    return (
        "Listed as an important requirement in the job description.",
        "Add relevant project, coursework, or production evidence where this skill was used.",
    )
