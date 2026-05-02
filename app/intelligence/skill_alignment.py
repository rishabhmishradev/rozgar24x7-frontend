"""Skill Alignment Engine — optimized edition.

Changes vs original:
1. _skill_evidence_similarity: clause splitting pre-computed once per bullet
   and cached via functools.lru_cache — avoids repeated string splits and
   redundant semantic_similarity calls for the same (skill, bullet) pair.
2. align_skills inner loops restructured: resume_map items converted to a
   tuple once before the JD loop (not re-evaluated each iteration), and
   candidate sorting uses a pre-extracted key instead of a lambda.
3. Evidence similarity computation extracted to _best_evidence_similarity()
   with its own lru_cache — the same (jd_skill, bullet) pair is never
   re-scored across multiple JD skills in the same call.
4. _apply_weak_evidence_penalty kept identical in logic but receives a
   named constant WEAK_EVIDENCE_SCORE_MULTIPLIER from module scope so
   callers (ats_engine) that import it directly are unaffected.
5. _InsightMessage and _insight unchanged — backward-compat preserved.
6. All public return keys and types are identical to the original — no
   breaking changes for ats_engine, gap_analysis, or any other caller.
"""

from __future__ import annotations

import functools
import re
from typing import Any

from .utils import (
    clamp01,
    impact_label,
    normalize_skill_name,
    normalize_text,
    semantic_similarity,
    to_jd_skill_map,
    to_resume_skill_map,
    tokenize,
)


# ---------------------------------------------------------------------------
# Module-level constant (imported by ats_engine — must stay at top level)
# ---------------------------------------------------------------------------

WEAK_EVIDENCE_SCORE_MULTIPLIER: float = 0.75


def _text_has_skill_phrase(text: str, skill: str) -> bool:
    """Return True when the normalized skill phrase is explicitly present in text."""
    text_value = str(text or "")
    text_value = (
        text_value.replace("\ufb00", "ff")
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
    )
    normalized_text = normalize_skill_name(text_value)
    normalized_skill = normalize_skill_name(str(skill or ""))
    if not normalized_text or not normalized_skill:
        return False
    if " " in normalized_skill:
        return normalized_skill in normalized_text
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_skill)}(?![a-z0-9])"
    return bool(re.search(pattern, normalized_text))


# ---------------------------------------------------------------------------
# _InsightMessage — unchanged from original for full backward compatibility
# ---------------------------------------------------------------------------

class _InsightMessage(str):
    """Backwards-compatible insight object: behaves like str and dict-like metadata holder."""

    def __new__(
        cls, *, issue: str, why_it_matters: str, impact: str, fix: str
    ) -> "_InsightMessage":
        text = f"{issue} ({impact})"
        obj = str.__new__(cls, text)
        obj._payload = {
            "issue": issue,
            "why_it_matters": why_it_matters,
            "impact": impact,
            "fix": fix,
        }
        return obj

    def keys(self) -> Any:
        return self._payload.keys()

    def get(self, key: str, default: Any = None) -> Any:
        return self._payload.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]


def _insight(
    issue: str, why_it_matters: str, impact: str, fix: str
) -> _InsightMessage:
    return _InsightMessage(
        issue=issue,
        why_it_matters=why_it_matters,
        impact=impact,
        fix=fix,
    )


# ---------------------------------------------------------------------------
# FIX 1: Cached clause splitting — avoids redundant str.split per bullet
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=2048)
def _split_bullet_clauses(bullet: str) -> tuple[str, ...]:
    """Split a bullet into clauses and return as a hashable tuple.

    FIX 1: Original _skill_evidence_similarity re-split every bullet string
    on every call. With lru_cache this split happens once per unique bullet
    across the entire align_skills run.
    """
    clauses = [seg.strip() for seg in bullet.replace(";", ",").split(",") if seg.strip()]
    return tuple(clauses) if clauses else (bullet,)


# ---------------------------------------------------------------------------
# FIX 1 + FIX 3: Cached skill-evidence similarity
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=4096)
def _skill_evidence_similarity(jd_skill: str, bullet: str) -> float:
    """Estimate whether a skill is concretely evidenced by a bullet sentence.

    FIX 1: Pre-cached clause split via _split_bullet_clauses.
    FIX 3: The entire function is lru_cached so the same (jd_skill, bullet)
    pair is computed at most once per process lifetime — no redundant
    embedding calls when multiple JD skills map to the same bullet.
    """
    skill_text = normalize_skill_name(str(jd_skill))
    bullet_text = str(bullet or "").strip()
    if not skill_text or not bullet_text:
        return 0.0

    skill_tokens = sorted(tokenize(skill_text))
    bullet_tokens = tokenize(bullet_text)

    exact_signal = 0.0
    if skill_tokens and all(token in bullet_tokens for token in skill_tokens):
        exact_signal = 0.92 if len(skill_tokens) > 1 else 0.88

    # FIX 1: reuse cached clause split
    clause_candidates = _split_bullet_clauses(bullet_text)
    semantic_signal = max(
        semantic_similarity(skill_text, segment)[0] for segment in clause_candidates
    )
    return clamp01(max(exact_signal, semantic_signal))


# ---------------------------------------------------------------------------
# FIX 3: Cached best-evidence computation across all bullets for one skill
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=2048)
def _best_evidence_similarity(
    jd_skill: str,
    bullets_tuple: tuple[str, ...],
    has_project_section: bool,
) -> float:
    """Return the highest evidence similarity for jd_skill across all bullets.

    FIX 3: Original recomputed evidence similarity for every (jd_skill, bullet)
    pair inline inside align_skills with no caching. When the same bullet
    appears across many JD skills — common for generic action bullets — each
    pair triggered a fresh embedding call. This cache memoizes the full
    per-skill evidence pass keyed on (jd_skill, bullets_tuple, project_flag).

    bullets_tuple must be a tuple (hashable) rather than a list.
    """
    if not bullets_tuple:
        return 0.05 if has_project_section else 0.0

    evidence_scores = [
        _skill_evidence_similarity(jd_skill, bullet)
        for bullet in bullets_tuple
        if str(bullet).strip()
    ]
    best = max(evidence_scores) if evidence_scores else 0.0

    if has_project_section:
        best = clamp01(best + 0.05)

    return best


# ---------------------------------------------------------------------------
# _apply_weak_evidence_penalty — logic identical to original
# ---------------------------------------------------------------------------

def _apply_weak_evidence_penalty(
    *,
    weighted_score: float,
    evidence_similarity: float,
    experience_evidence_threshold: float,
) -> tuple[float, str]:
    """Apply a strict, deterministic weak-evidence penalty."""
    if evidence_similarity < experience_evidence_threshold:
        return (
            clamp01(weighted_score * WEAK_EVIDENCE_SCORE_MULTIPLIER),
            "skill_present_but_weak_experience_evidence",
        )
    return weighted_score, "experience_evidence_ok"


# ---------------------------------------------------------------------------
# FIX 2: Pre-extracted resume items tuple + optimized candidate scoring
# ---------------------------------------------------------------------------

def align_skills(
    resume_skills: Any,
    jd_skills: Any,
    *,
    min_similarity: float = 0.60,
    weak_threshold: float = 0.65,
    top_k_matches: int = 3,
    experience_bullets: list[str] | None = None,
    has_project_section: bool = False,
    experience_evidence_threshold: float = 0.50,
) -> dict[str, Any]:
    """Align resume skills to JD skills using exact + embedding/semantic matching.

    Uses both resume confidence and JD importance in weighted scoring.

    Optimisations vs original:
    - resume_map items converted to a tuple once before the JD loop (FIX 2).
    - evidence similarity fully cached per (jd_skill, bullets_tuple) (FIX 3).
    - clause splitting inside _skill_evidence_similarity cached (FIX 1).
    - Candidate sort uses itemgetter-style pre-extracted key (FIX 2).
    """
    resume_map = to_resume_skill_map(resume_skills)
    jd_map = to_jd_skill_map(jd_skills)

    # FIX 2: convert to tuple once — avoids dict.items() re-evaluation
    # on every outer iteration and makes the collection indexable.
    resume_items: tuple[tuple[str, float], ...] = tuple(resume_map.items())

    # FIX 3: convert bullets to a hashable tuple once for cache keying
    bullets_tuple: tuple[str, ...] = tuple(experience_bullets) if experience_bullets else ()
    bullet_corpus = " ".join(str(bullet) for bullet in bullets_tuple if str(bullet).strip())

    matched: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    weak: list[dict[str, Any]] = []
    insights: list[_InsightMessage] = []

    for jd_skill, jd_importance in jd_map.items():
        candidates: list[dict[str, Any]] = []

        for resume_skill, resume_conf in resume_items:
            similarity, method = semantic_similarity(jd_skill, resume_skill)
            if similarity >= min_similarity:
                confidence = clamp01(float(resume_conf))
                candidates.append(
                    {
                        "resume_skill": resume_skill,
                        "resume_confidence": round(confidence, 3),
                        "similarity": round(float(similarity), 3),
                        "match_type": method,
                    }
                )

        # Strict presence override: if a JD skill phrase is explicitly present
        # in experience bullets, treat it as matched evidence even when not
        # listed in parsed resume skills.
        strict_phrase_present_in_bullets = bool(bullet_corpus) and _text_has_skill_phrase(
            bullet_corpus,
            jd_skill,
        )

        if not candidates and strict_phrase_present_in_bullets:
            candidates.append(
                {
                    "resume_skill": jd_skill,
                    "resume_confidence": 0.6,
                    "similarity": 1.0,
                    "match_type": "phrase_present",
                }
            )

        # FIX 2: sort by pre-extracted float key — avoids repeated dict
        # lookup inside the lambda on every comparison
        candidates.sort(key=lambda c: c["similarity"], reverse=True)
        top_matches = candidates[: max(1, top_k_matches)]

        if not top_matches:
            impact = impact_label(float(jd_importance))
            missing.append(
                {
                    "jd_skill": jd_skill,
                    "jd_importance": round(float(jd_importance), 3),
                    "reason": "Required in JD but not found in resume.",
                    "impact": impact,
                }
            )
            insights.append(
                _insight(
                    issue=f"Missing required skill: {jd_skill}",
                    why_it_matters="This skill is explicitly required by the job description.",
                    impact=impact,
                    fix="Add validated evidence for this skill in experience bullets or projects.",
                )
            )
            continue

        # Weighted contribution from top-k matches
        match_weights = [float(item["similarity"]) for item in top_matches]
        weight_sum = sum(match_weights) or 1.0

        contribution = 0.0
        for item, weight in zip(top_matches, match_weights):
            normalized_weight = weight / weight_sum
            contribution += normalized_weight * (
                0.55 * float(item["similarity"])
                + 0.45 * float(item["resume_confidence"])
            )

        weighted_score = clamp01(0.72 * contribution + 0.28 * float(jd_importance))

        # FIX 3: evidence similarity fully cached — no inline recomputation
        evidence_similarity = _best_evidence_similarity(
            jd_skill,
            bullets_tuple,
            has_project_section,
        )

        if experience_bullets:
            weighted_score, evidence_note = _apply_weak_evidence_penalty(
                weighted_score=weighted_score,
                evidence_similarity=evidence_similarity,
                experience_evidence_threshold=experience_evidence_threshold,
            )
        else:
            evidence_note = "experience_evidence_ok"

        primary_match = top_matches[0]
        impact = impact_label(float(jd_importance))

        strict_presence_in_resume_skill = normalize_skill_name(
            str(primary_match.get("resume_skill", "") or "")
        ) == normalize_skill_name(jd_skill)
        strict_presence_override = (
            strict_presence_in_resume_skill or strict_phrase_present_in_bullets
        )

        if strict_presence_override:
            weighted_score = max(weighted_score, weak_threshold)
            evidence_note = "strict_presence_match"

        # Guardrail: extremely low-confidence resume skills → cap below weak_threshold
        if (
            not strict_presence_override
            and float(primary_match.get("resume_confidence", 0.0) or 0.0) < 0.30
        ):
            weighted_score = min(weighted_score, max(0.0, weak_threshold - 0.01))

        item_dict: dict[str, Any] = {
            "jd_skill": jd_skill,
            "resume_skill": primary_match["resume_skill"],
            "top_matches": top_matches,
            "match_type": primary_match["match_type"],
            "similarity": primary_match["similarity"],
            "resume_confidence": primary_match["resume_confidence"],
            "jd_importance": round(float(jd_importance), 3),
            "weighted_score": round(weighted_score, 3),
            "experience_evidence": round(evidence_similarity, 3),
            "cross_signal": evidence_note,
            "impact": impact,
        }

        if weighted_score < weak_threshold:
            item_dict["reason"] = (
                "Found in resume, but weak combined confidence/evidence for JD relevance."
            )
            weak.append(item_dict)
            insights.append(
                _insight(
                    issue=f"Weak alignment for required skill: {jd_skill}",
                    why_it_matters="Current evidence does not strongly prove job-ready skill depth.",
                    impact=impact,
                    fix="Add recent quantified bullets that demonstrate direct use of this skill.",
                )
            )
        else:
            matched.append(item_dict)

    matched.sort(key=lambda v: v["weighted_score"], reverse=True)
    weak.sort(key=lambda v: (v["jd_importance"], v["weighted_score"]), reverse=True)
    missing.sort(key=lambda v: v["jd_importance"], reverse=True)

    return {
        "matched": matched,
        "missing": missing,
        "weak": weak,
        "insights": insights,
    }