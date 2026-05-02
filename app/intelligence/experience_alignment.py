"""Experience alignment with role-aware hybrid matching and debug visibility."""

from __future__ import annotations

import functools
import logging
import re
from datetime import datetime
from typing import Any

from .role_taxonomy import ROLE_TAXONOMY
from .text_normalization import (
    VERB_NORMALIZATION_MAP,
    normalize_action_verbs,
    normalize_text_basic,
    soft_phrase_overlap,
    token_set,
)
from .utils import (
    clamp01,
    embedding_similarity,
    flatten_experience_bullets,
    impact_label,
    semantic_similarity,
    to_jd_skill_map,
)


logger = logging.getLogger(__name__)

DEFAULT_COVERED_THRESHOLD = 0.65
DEFAULT_PARTIAL_THRESHOLD = 0.45

JD_INTENTS: dict[str, list[str]] = {
    "ml_models": ["machine learning", "model", "algorithm", "neural", "deep learning", "training"],
    "deployment": ["deploy", "serving", "production", "kubernetes", "docker", "container"],
    "pipeline": ["pipeline", "data pipeline", "etl", "processing", "workflow"],
    "scaling": ["scalable", "distributed", "scale", "parallel", "performance"],
    "cloud": ["aws", "gcp", "azure", "cloud", "infrastructure"],
    "data": ["data", "database", "sql", "query", "analytics"],
    "api": ["api", "rest", "graphql", "endpoint", "integration"],
    "frontend": ["frontend", "ui", "react", "javascript", "css", "html"],
    "backend": ["backend", "server", "service", "services", "framework", "python", "java", "api", "apis"],
    "testing": ["testing", "test", "quality", "coverage", "qa"],
    "automation": ["automation", "automate", "ci/cd", "devops", "release"],
    "mentorship": ["mentor", "mentored", "coaching", "coach", "junior", "lead", "led"],
}

RESPONSIBILITY_VARIANTS: dict[str, list[str]] = {
    "build ml models": ["build models", "train models", "develop ml system", "create machine learning models"],
    "deploy models": ["model deployment", "deploy ml system", "productionize models", "serve models"],
    "optimize pipelines": ["improve pipelines", "optimize data pipeline", "streamline workflow", "enhance etl"],
    "deploy backend services": ["deploy backend systems", "deploy production apis", "release backend services"],
    "deploy applications to production": ["deploy production applications", "deploy web applications to production"],
    "lead technical reviews": ["lead architecture reviews", "conduct technical design reviews", "run architecture review rituals"],
    "analyze business data": [
        "analyze operational data",
        "analyze market data",
        "business data analysis",
        "analyze datasets",
        "analyze primary and secondary data",
        "analyze social media trends",
        "market analysis",
        "process business data",
        "analyze market trends",
    ],
    "build dashboards and reports": [
        "create dashboards",
        "build reports",
        "reporting dashboards",
        "visualize metrics",
        "prepare performance reports",
        "deliver weekly reports",
        "excel charts and reports",
        "excel dashboards",
        "create data visualizations",
    ],
    "communicate actionable insights": [
        "present insights",
        "report actionable insights",
        "communicate recommendations",
        "inform strategic decision making",
        "share recommendations with stakeholders",
        "translate analysis into decisions",
    ],
}


def _normalize_alignment_phrase(text: str) -> str:
    value = str(text or "")
    value = (
        value.replace("\ufb00", "ff")
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
    )
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)
    value = value.strip()
    value = re.sub(r"^(?:[-*\u2022\u25cf\u25e6]+|\d+[.)])\s*", "", value)
    value = re.sub(r"[.,;:!?]+$", "", value)
    return normalize_text_basic(value)


def _resolve_role_key(role: str | None) -> str:
    normalized_role = normalize_text_basic(role or "")
    if not normalized_role:
        return ""
    if normalized_role in ROLE_TAXONOMY:
        return normalized_role
    for role_name in ROLE_TAXONOMY:
        if role_name in normalized_role or normalized_role in role_name:
            return role_name
    return normalized_role


def _resolve_responsibility_importance(jd_point: str, importance_map: dict[str, float]) -> float:
    if not importance_map:
        return 0.6

    best = 0.0
    jd_lower = str(jd_point).lower()
    for keyword, value in importance_map.items():
        keyword_text = str(keyword).strip().lower()
        if keyword_text and keyword_text in jd_lower:
            best = max(best, float(value))
        similarity, _ = semantic_similarity(jd_point, keyword)
        best = max(best, similarity * float(value))
    return max(0.35, min(1.0, best))


def _temporal_weight(text: str) -> float:
    lowered = text.lower()
    years = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", lowered)]

    recency_weight = 0.85
    if years:
        latest_year = max(years)
        current_year = datetime.now().year
        age = current_year - latest_year
        if age <= 2:
            recency_weight = 1.0
        elif age <= 5:
            recency_weight = 0.9
        else:
            recency_weight = 0.75

    context_weight = 1.0
    if "intern" in lowered or "internship" in lowered:
        context_weight = 0.82
    elif "freelance" in lowered:
        context_weight = 0.9

    return max(0.6, min(1.05, recency_weight * context_weight))


def _expand_responsibility(jd_point: str) -> list[str]:
    text = normalize_action_verbs(jd_point)
    seen: set[str] = {text}
    expanded: list[str] = [text]
    for key, variants in RESPONSIBILITY_VARIANTS.items():
        if normalize_action_verbs(key) in text:
            for variant in variants:
                normalized_variant = normalize_action_verbs(variant)
                if normalized_variant not in seen:
                    seen.add(normalized_variant)
                    expanded.append(normalized_variant)
    return expanded


def _best_similarity(jd_point: str, bullet: str) -> tuple[float, str]:
    bullet_norm = normalize_action_verbs(bullet)
    best_score = 0.0
    best_method = "none"
    for phrase in _expand_responsibility(jd_point):
        if phrase and phrase in bullet_norm:
            return 1.0, "phrase_present_variant"
        score, method = semantic_similarity(phrase, bullet_norm)
        if score > best_score:
            best_score = score
            best_method = method
    return best_score, best_method


def _intent_score(source_text: str, target_text: str) -> float:
    source_lowered = normalize_action_verbs(source_text)
    target_lowered = normalize_action_verbs(target_text)

    source_intents = {
        intent
        for intent, keywords in JD_INTENTS.items()
        if any(normalize_action_verbs(keyword) in source_lowered for keyword in keywords)
    }
    if not source_intents:
        return 0.0
    target_intents = {
        intent
        for intent, keywords in JD_INTENTS.items()
        if any(normalize_action_verbs(keyword) in target_lowered for keyword in keywords)
    }
    return min(1.0, len(source_intents & target_intents) / max(1, len(source_intents)))


def _embedding_similarity_score(jd_point: str, bullet: str, *, exact_match: bool = False) -> float:
    if exact_match:
        return 1.0
    score = embedding_similarity(normalize_action_verbs(jd_point), normalize_action_verbs(bullet))
    return clamp01(float(score or 0.0))


def _keyword_overlap_score(jd_point: str, bullet: str) -> float:
    jd_tokens = token_set(jd_point)
    bullet_tokens = token_set(bullet)
    if not jd_tokens or not bullet_tokens:
        return 0.0
    overlap = len(jd_tokens & bullet_tokens) / max(1, len(jd_tokens))
    return clamp01(max(overlap, soft_phrase_overlap(jd_point, bullet)))


def _intent_group_match_score(jd_point: str, bullet: str, role: str) -> tuple[float, list[str]]:
    role_data = ROLE_TAXONOMY.get(role, {})
    intent_groups = role_data.get("intent_groups", {}) if isinstance(role_data, dict) else {}
    if not intent_groups:
        score = clamp01(max(_intent_score(jd_point, bullet), _keyword_overlap_score(jd_point, bullet) * 0.75))
        return score, []

    jd_norm = normalize_action_verbs(jd_point)
    bullet_norm = normalize_action_verbs(bullet)
    jd_groups: list[str] = []
    matched_groups: list[str] = []
    for group_name, keywords in intent_groups.items():
        normalized_keywords = [normalize_action_verbs(keyword) for keyword in keywords]
        if any(keyword in jd_norm for keyword in normalized_keywords):
            jd_groups.append(group_name)
            if any(keyword in bullet_norm for keyword in normalized_keywords):
                matched_groups.append(group_name)

    if not jd_groups:
        score = clamp01(max(_intent_score(jd_point, bullet), _keyword_overlap_score(jd_point, bullet) * 0.75))
        return score, []

    return clamp01(len(set(matched_groups)) / max(1, len(set(jd_groups)))), sorted(set(matched_groups))


def _extract_action_verbs(text: str) -> set[str]:
    tokens = normalize_action_verbs(text).split()
    return {VERB_NORMALIZATION_MAP[token] for token in tokens if token in VERB_NORMALIZATION_MAP}


def _action_verb_match_score(jd_point: str, bullet: str) -> float:
    jd_verbs = _extract_action_verbs(jd_point)
    bullet_verbs = _extract_action_verbs(bullet)
    if not jd_verbs:
        return 0.5 if bullet_verbs else 0.0
    if not bullet_verbs:
        return 0.0
    return clamp01(len(jd_verbs & bullet_verbs) / max(1, len(jd_verbs)))


def _is_substantive_bullet(text: str, jd_point: str) -> bool:
    value = str(text or "").strip().lower()
    jd_lower = str(jd_point or "").strip().lower()
    if not value:
        return False

    words = value.split()
    if len(words) < 5:
        return False

    action_terms = {
        "built", "designed", "implemented", "developed", "deployed",
        "optimized", "automated", "led", "mentored", "managed",
        "analyze", "analyzing", "analyzed", "reporting", "reported", "presenting", "presented", "derived", "extracting", "extracted",
    }
    has_action = any(term in value for term in action_terms)
    has_quant = bool(re.search(r"(\$\s?\d+|\d+\s?%|\b\d+[kmb]\b|\b\d+\b)", value, re.IGNORECASE))
    if has_action or has_quant:
        return True

    if ("mentor" in jd_lower or "lead" in jd_lower) and any(
        term in value for term in {"junior", "mentor", "mentored", "coached"}
    ):
        return True

    return False


def _has_strong_evidence(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False

    strong_actions = {
        "built", "designed", "implemented", "developed", "deployed",
        "optimized", "automated", "led", "managed", "scaled",
        "analyze", "analyzing", "analyzed", "reporting", "reported", "presenting", "presented", "derived", "extracting", "extracted",
    }
    action_hits = sum(1 for term in strong_actions if term in value)
    has_quant = bool(re.search(r"(\$\s?\d+|\d+\s?%|\b\d+[kmb]\b|\b\d+\b)", value, re.IGNORECASE))
    has_tech_context = any(
        term in value
        for term in {"aws", "docker", "kubernetes", "prometheus", "etl", "pipeline", "production", "dashboard", "report"}
    )
    return has_quant or action_hits >= 2 or (action_hits >= 1 and has_tech_context)


def _evidence_strength_score(jd_point: str, bullet: str) -> float:
    value = normalize_text_basic(bullet)
    if not value:
        return 0.0
    score = 0.0
    if _is_substantive_bullet(bullet, jd_point):
        score += 0.45
    if _has_strong_evidence(bullet):
        score += 0.35
    if re.search(r"(\$\s?\d+|\d+\s?%|\b\d+[kmb]\b|\b\d+\b)", value, re.IGNORECASE):
        score += 0.20
    return clamp01(score)


@functools.lru_cache(maxsize=4096)
def _score_bullet_for_point(jd_point: str, bullet: str, role: str) -> dict[str, float | str | list[str]]:
    semantic_sim, method = _best_similarity(jd_point, bullet)
    normalized_jd = _normalize_alignment_phrase(jd_point)
    normalized_bullet = _normalize_alignment_phrase(bullet)
    exact_match = bool(normalized_jd) and normalized_jd == normalized_bullet
    phrase_match = bool(normalized_jd) and bool(normalized_bullet) and normalized_jd in normalized_bullet
    phrase_overlap = soft_phrase_overlap(jd_point, bullet)
    keyword_overlap = _keyword_overlap_score(jd_point, bullet)
    intent_group_match, matched_groups = _intent_group_match_score(jd_point, bullet, role)
    action_verb_match = _action_verb_match_score(jd_point, bullet)
    evidence_strength = _evidence_strength_score(jd_point, bullet)

    semantic_component = max(semantic_sim, phrase_overlap)
    if exact_match or phrase_match:
        semantic_component = 1.0
        keyword_overlap = max(keyword_overlap, 1.0)
        action_verb_match = max(action_verb_match, 1.0)
        evidence_strength = max(evidence_strength, 0.85)
        if matched_groups:
            intent_group_match = max(intent_group_match, 1.0)

    final_score = clamp01(
        (0.35 * semantic_component)
        + (0.25 * intent_group_match)
        + (0.20 * keyword_overlap)
        + (0.10 * evidence_strength)
        + (0.10 * action_verb_match)
    )
    temporal_similarity = clamp01(final_score * (0.9 + (0.1 * _temporal_weight(bullet))))
    return {
        "semantic_similarity": round(semantic_component, 3),
        "embedding_similarity": round(_embedding_similarity_score(jd_point, bullet, exact_match=exact_match), 3),
        "intent_group_match": round(intent_group_match, 3),
        "keyword_overlap": round(keyword_overlap, 3),
        "evidence_strength": round(evidence_strength, 3),
        "action_verb_match": round(action_verb_match, 3),
        "final_score": round(final_score, 3),
        "similarity": round(final_score, 3),
        "temporal_similarity": round(temporal_similarity, 3),
        "match_type": "exact_normalized" if exact_match else ("phrase_present" if phrase_match else method),
        "matched_intent_groups": matched_groups,
        "soft_phrase_overlap": round(phrase_overlap, 3),
    }


def align_experience(
    jd_responsibilities: list[str],
    resume_bullets: list[str] | None = None,
    *,
    role: str | None = None,
    resume_experience: Any | None = None,
    jd_importance: dict[str, float] | None = None,
    top_k_bullets: int = 3,
    covered_threshold: float = DEFAULT_COVERED_THRESHOLD,
    partial_threshold: float = DEFAULT_PARTIAL_THRESHOLD,
) -> dict[str, Any]:
    jd_points = [point.strip() for point in jd_responsibilities if str(point).strip()]
    if resume_bullets is not None:
        bullets = [bullet.strip() for bullet in resume_bullets if str(bullet).strip()]
    else:
        bullets = flatten_experience_bullets(resume_experience)
    bullets = list(dict.fromkeys(bullets))

    covered: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    importance_map = to_jd_skill_map(jd_importance or {}, default_importance=0.6)
    role_key = _resolve_role_key(role)

    for jd_point in jd_points:
        point_importance = _resolve_responsibility_importance(jd_point, importance_map)
        bullet_candidates: list[dict[str, Any]] = []
        for bullet in bullets:
            scores = _score_bullet_for_point(jd_point, bullet, role_key)
            bullet_candidates.append(
                {
                    "bullet": bullet,
                    "best_bullet": bullet,
                    "semantic_similarity": scores["semantic_similarity"],
                    "embedding_similarity": scores["embedding_similarity"],
                    "intent_group_match": scores["intent_group_match"],
                    "keyword_overlap": scores["keyword_overlap"],
                    "evidence_strength": scores["evidence_strength"],
                    "action_verb_match": scores["action_verb_match"],
                    "final_score": scores["final_score"],
                    "similarity": scores["similarity"],
                    "temporal_similarity": scores["temporal_similarity"],
                    "match_type": scores["match_type"],
                    "matched_intent_groups": scores["matched_intent_groups"],
                    "soft_phrase_overlap": scores["soft_phrase_overlap"],
                }
            )

        bullet_candidates.sort(
            key=lambda item: (float(item["final_score"]), float(item["temporal_similarity"])),
            reverse=True,
        )
        top_evidence = bullet_candidates[: max(1, top_k_bullets)]
        best = top_evidence[0] if top_evidence else None
        best_similarity = float(best.get("final_score", 0.0) or 0.0) if best else 0.0
        best_bullet = str(best.get("bullet", "")) if best else ""
        best_method = str(best.get("match_type", "none")) if best else "none"
        weighted_score = best_similarity * point_importance
        impact = impact_label(point_importance)

        label = "missing"
        if best_similarity >= covered_threshold:
            label = "covered"
        elif best_similarity >= partial_threshold:
            label = "partial"

        result_item: dict[str, Any] = {
            "jd_responsibility": jd_point,
            "resume_bullet": best_bullet if best_bullet else None,
            "best_bullet": best_bullet if best_bullet else None,
            "similarity": round(best_similarity, 3),
            "final_score": round(best_similarity, 3),
            "importance": round(point_importance, 3),
            "weighted_score": round(weighted_score, 3),
            "match_type": best_method,
            "impact": impact,
            "label": label,
            "evidence_bullets": top_evidence,
            "semantic_similarity": float(best.get("semantic_similarity", 0.0) or 0.0) if best else 0.0,
            "embedding_similarity": float(best.get("embedding_similarity", 0.0) or 0.0) if best else 0.0,
            "intent_group_match": float(best.get("intent_group_match", 0.0) or 0.0) if best else 0.0,
            "keyword_overlap": float(best.get("keyword_overlap", 0.0) or 0.0) if best else 0.0,
            "evidence_strength": float(best.get("evidence_strength", 0.0) or 0.0) if best else 0.0,
            "action_verb_match": float(best.get("action_verb_match", 0.0) or 0.0) if best else 0.0,
        }

        debug_rows.append(
            {
                "responsibility": jd_point,
                "best_bullet": result_item["best_bullet"],
                "similarity_score": result_item["final_score"],
                "embedding_similarity": result_item["embedding_similarity"],
                "final_label": label,
            }
        )
        logger.debug(
            "Experience alignment debug: role=%s responsibility=%s best_bullet=%s semantic=%s embedding=%s final=%s label=%s",
            role_key or None,
            jd_point,
            result_item["best_bullet"],
            result_item["semantic_similarity"],
            result_item["embedding_similarity"],
            result_item["final_score"],
            label,
        )

        if label == "covered":
            covered.append(result_item)
        elif label == "partial":
            result_item["reason"] = "Partially covered responsibility; strengthen project evidence."
            partial.append(result_item)
            insights.append(
                {
                    "issue": f"Partial coverage for responsibility: {jd_point[:60]}",
                    "why_it_matters": "The JD expects clearer evidence for this responsibility.",
                    "impact": impact,
                    "fix": "Add a bullet with measurable outcome directly tied to this responsibility.",
                }
            )
        else:
            result_item["reason"] = "Required responsibility not sufficiently evidenced in resume bullets."
            missing.append(result_item)
            insights.append(
                {
                    "issue": f"Missing responsibility coverage: {jd_point[:60]}",
                    "why_it_matters": "This responsibility is core to role performance.",
                    "impact": impact,
                    "fix": "Include a recent bullet showing direct ownership and execution in this area.",
                }
            )

    covered.sort(key=lambda item: item["weighted_score"], reverse=True)
    partial.sort(key=lambda item: item["weighted_score"], reverse=True)
    return {
        "covered": covered,
        "partial": partial,
        "missing": missing,
        "insights": insights,
        "debug": {
            "role": role_key or None,
            "jd_responsibilities": jd_points,
            "resume_bullets": bullets,
            "matches": debug_rows,
        },
    }
