"""Gap Analysis Engine — optimized edition.

Changes vs original:
1. _dedupe_records and _dedupe_insights merged into a single generic
   _dedupe_by_key() function — eliminates duplicated dedup logic.
2. Required/optional set lookups converted from repeated linear scans
   to O(1) frozenset membership tests built once before the loops.
3. _top_percentile_threshold replaced with a single-pass O(n) partial
   sort using heapq.nlargest instead of a full O(n log n) sort.
4. Gap routing for missing skills extracted into _route_missing_skill()
   — removes the nested if/elif/else inline in analyze_gaps, making
   each routing rule independently testable.
5. All public return keys and types are identical to the original —
   no breaking changes for ats_engine or any other caller.
"""

from __future__ import annotations

import heapq
from typing import Any

from .utils import impact_label, normalize_skill_name


# ---------------------------------------------------------------------------
# FIX 3: O(n) threshold via heapq instead of full O(n log n) sort
# ---------------------------------------------------------------------------

def _top_percentile_threshold(values: list[float], top_percent: float) -> float:
    """Return the lowest value in the top-N percent of the list.

    FIX 3: Original sorted the full list — O(n log n).
    heapq.nlargest is O(n log k) where k = ceil(n * top_percent),
    which is faster when top_percent is small (the common case).
    For the typical gap analysis payload (10-30 skills) the difference
    is negligible, but for large skill sets it matters.
    """
    if not values:
        return 0.7
    count = max(1, int(len(values) * top_percent + 0.9999))  # ceil without math import
    top_values = heapq.nlargest(count, values)
    return float(top_values[-1])


# ---------------------------------------------------------------------------
# FIX 1: Single generic dedup helper replaces two identical functions
# ---------------------------------------------------------------------------

def _dedupe_by_key(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate dicts by a stable serialized key, preserving insertion order.

    FIX 1: Original had _dedupe_records and _dedupe_insights with identical
    bodies. Unified into one function; both callers now use this.
    """
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = "|".join(f"{k}:{record.get(k)}" for k in sorted(record.keys()))
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


# Backward-compatible aliases so any external caller still works
_dedupe_records = _dedupe_by_key
_dedupe_insights = _dedupe_by_key


# ---------------------------------------------------------------------------
# FIX 4: Extracted skill routing logic
# ---------------------------------------------------------------------------

def _route_missing_skill(
    item: dict[str, Any],
    jd_skill: str,
    required_set: frozenset[str],
    optional_set: frozenset[str],
    critical_threshold: float,
) -> tuple[str, dict[str, Any]]:
    """Determine which gap bucket a missing skill belongs to.

    FIX 4: Original had a nested if/elif/else block inline inside
    analyze_gaps making it impossible to unit-test routing in isolation.
    Returns ('critical' | 'moderate' | 'low', gap_dict).
    """
    importance = float(item.get("jd_importance", 0.0) or 0.0)
    gap: dict[str, Any] = {
        "type": "skill_missing",
        "skill": jd_skill,
        "jd_importance": importance,
        "reason": "Required in JD but not found in resume.",
        "impact": impact_label(importance),
    }

    # FIX 2: O(1) frozenset membership test instead of linear scan
    if not required_set or jd_skill in required_set:
        return "critical", gap

    if jd_skill in optional_set:
        return "low", gap

    # Route by relative importance ranking
    if importance >= critical_threshold:
        return "critical", gap
    if importance >= max(0.25, critical_threshold * 0.6):
        return "moderate", gap
    return "low", gap


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_gaps(
    skill_alignment: dict[str, list[dict[str, Any]]],
    experience_alignment: dict[str, list[dict[str, Any]]],
    *,
    jd_required: list[str] | None = None,
    jd_optional: list[str] | None = None,
) -> dict[str, Any]:
    """Classify gaps into critical, moderate, and low-priority buckets.

    Optimisations vs original:
    - required_set / optional_set built as frozensets once (FIX 2).
    - _top_percentile_threshold uses heapq.nlargest (FIX 3).
    - Missing-skill routing extracted to _route_missing_skill (FIX 4).
    - Dedup uses unified _dedupe_by_key (FIX 1).

    Public return contract (critical_gaps / moderate_gaps / low_priority /
    insights) is identical to the original.
    """
    # FIX 2: build O(1) lookup sets once before both loops
    required_set: frozenset[str] = frozenset(
        normalize_skill_name(s) for s in (jd_required or []) if str(s).strip()
    )
    optional_set: frozenset[str] = frozenset(
        normalize_skill_name(s) for s in (jd_optional or []) if str(s).strip()
    )

    critical_gaps: list[dict[str, Any]] = []
    moderate_gaps: list[dict[str, Any]] = []
    low_priority: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []

    # FIX 3: O(n log k) threshold instead of O(n log n) full sort
    all_importances = [
        float(item.get("jd_importance", 0.0) or 0.0)
        for item in skill_alignment.get("missing", []) + skill_alignment.get("weak", [])
    ]
    critical_threshold = _top_percentile_threshold(all_importances, top_percent=0.30)

    # --- Missing skills (FIX 4: routing delegated to _route_missing_skill) ---
    for item in skill_alignment.get("missing", []):
        jd_skill = normalize_skill_name(str(item.get("jd_skill", "")))
        bucket, gap = _route_missing_skill(
            item, jd_skill, required_set, optional_set, critical_threshold
        )

        if bucket == "critical":
            critical_gaps.append(gap)
            insights.append(
                {
                    "issue": f"Missing {jd_skill}",
                    "why_it_matters": "Required by the role and directly impacts ability to perform core tasks.",
                    "impact": gap["impact"],
                    "fix": "Add a concrete project bullet or certification demonstrating this skill.",
                }
            )
        elif bucket == "moderate":
            moderate_gaps.append(gap)
        else:
            low_priority.append(gap)

    # --- Weak skills (unchanged routing) ---
    for item in skill_alignment.get("weak", []):
        importance = float(item.get("jd_importance", 0.0) or 0.0)
        moderate_gaps.append(
            {
                "type": "skill_weak",
                "skill": normalize_skill_name(str(item.get("jd_skill", ""))),
                "weighted_score": item.get("weighted_score", 0.0),
                "jd_importance": importance,
                "reason": "Skill found, but confidence/evidence is weak for JD expectations.",
                "impact": impact_label(importance),
            }
        )

    # --- Missing responsibilities ---
    for item in experience_alignment.get("missing", []):
        importance = float(item.get("importance", 0.6) or 0.6)
        critical_gaps.append(
            {
                "type": "responsibility_missing",
                "responsibility": item.get("jd_responsibility", ""),
                "similarity": item.get("similarity", 0.0),
                "importance": importance,
                "reason": "Key JD responsibility lacks resume evidence.",
                "impact": impact_label(importance),
            }
        )
        insights.append(
            {
                "issue": "Missing responsibility coverage",
                "why_it_matters": "Core JD responsibility lacks resume evidence.",
                "impact": impact_label(importance),
                "fix": "Add a recent achievement bullet showing ownership and measurable outcomes for this responsibility.",
            }
        )

    # --- Partial responsibilities ---
    for item in experience_alignment.get("partial", []):
        importance = float(item.get("importance", 0.6) or 0.6)
        moderate_gaps.append(
            {
                "type": "responsibility_partial",
                "responsibility": item.get("jd_responsibility", ""),
                "similarity": item.get("similarity", 0.0),
                "importance": importance,
                "reason": "Responsibility is partially covered; stronger quantified bullets recommended.",
                "impact": impact_label(importance),
            }
        )

    # --- Optional missing skills (explicit optional list) ---
    if optional_set:
        for item in skill_alignment.get("missing", []):
            jd_skill = normalize_skill_name(str(item.get("jd_skill", "")))
            if jd_skill in optional_set:  # FIX 2: O(1) frozenset lookup
                low_priority.append(
                    {
                        "type": "optional_skill_missing",
                        "skill": jd_skill,
                        "jd_importance": item.get("jd_importance", 0.0),
                        "reason": "Optional JD skill not found; useful but not mandatory.",
                        "impact": "low",
                    }
                )

    # FIX 1: unified dedup function for all three buckets and insights
    return {
        "critical_gaps": _dedupe_by_key(critical_gaps),
        "moderate_gaps": _dedupe_by_key(moderate_gaps),
        "low_priority": _dedupe_by_key(low_priority),
        "insights": _dedupe_by_key(insights),
    }