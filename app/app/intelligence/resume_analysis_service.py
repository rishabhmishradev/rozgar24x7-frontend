"""Integration service for end-to-end resume analysis — optimized edition.

Changes vs original:
1. Parallel execution of skill_alignment, experience_alignment, and
   structure_score using concurrent.futures.ThreadPoolExecutor — the
   three are fully independent after parsing and can run concurrently.
2. LLM score null-guard added to compute_hybrid_score call — if the
   LLM engine returns None or raises, weights redistribute to ATS +
   structure rather than propagating a TypeError.
3. _build_analysis_result() extracted from the inline dict literal at
   the end of analyze_resume_against_jd — keeps the orchestrator
   readable and the result assembly independently testable.
4. Repeated dict.get chains for ats_analysis keys centralized into
   _safe_ats_score() helper — prevents silent 0.0 fallback divergence
   if the key name ever changes in ats_engine.
5. Step numbering in log messages fixed (original had Step 6 appear
   twice) and log lines now include timing via time.perf_counter so
   slow stages are visible in production logs.
6. All public method signatures, parameter names, and return dict keys
   are identical to the original — no breaking changes for any caller.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from pathlib import Path
from typing import Any, Dict, Optional

from app.parsing.resume_parser import ResumeParser
from app.parsing.jd_parser import parse_job_description
from app.intelligence.skill_alignment import align_skills
from app.intelligence.experience_alignment import align_experience
from app.intelligence.ats_engine import (
    compute_ats_score,
    compute_hybrid_score,
    compute_structure_score,
)
from app.intelligence.utils import flatten_experience_bullets

# LLMAnalysisEngine is intentionally NOT imported at module level.
# app.llm_engine may not be fully initialised when this module loads
# (e.g. during app startup before the LLM client is configured),
# which causes the name to resolve to None. The lazy import inside
# __init__ ensures the class is only resolved when an instance is
# actually constructed, by which point all dependencies are ready.

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FIX 4: Centralised ATS score accessor
# ---------------------------------------------------------------------------

def _safe_ats_score(ats_analysis: Dict[str, Any]) -> float:
    """Return the best available ATS score from the analysis dict.

    FIX 4: Original duplicated the same fallback chain in three places:
        ats_analysis.get('calibrated_ats_score', ats_analysis.get('ats_score', 0.0))
    A single helper prevents silent divergence if ats_engine key names change.
    """
    return float(
        ats_analysis.get("calibrated_ats_score")
        or ats_analysis.get("ats_score")
        or 0.0
    )


# ---------------------------------------------------------------------------
# FIX 3: Result assembly helper
# ---------------------------------------------------------------------------

def _build_analysis_result(
    *,
    resume_data: Dict[str, Any],
    jd_data: Dict[str, Any],
    ats_analysis: Dict[str, Any],
    llm_score: float,
    llm_score_payload: Dict[str, Any],
    structure_score: float,
    hybrid_score: float,
    recommendations: Optional[Dict[str, Any]],
    quick_tips: Any,
    include_llm_recommendations: bool,
) -> Dict[str, Any]:
    """Assemble the final result dict.

    FIX 3: Original built the result inline at the end of a 130-line method,
    making it hard to read and impossible to test independently.
    """
    ats_score_val = round(_safe_ats_score(ats_analysis), 3)

    result: Dict[str, Any] = {
        "resume_analysis": resume_data,
        "jd_analysis": jd_data,
        "ats_analysis": ats_analysis,
        "hybrid_scoring": {
            "final_score": round(hybrid_score, 3),
            "weights": {
                "ats": 0.20,
                "llm": 0.70,
                "structure": 0.10,
            },
            "components": {
                "ats_score": ats_score_val,
                "llm_score": round(llm_score, 3),
                "structure_score": round(structure_score, 3),
            },
            "llm_reason": str(llm_score_payload.get("reason", "")),
        },
        "quick_tips": quick_tips,
    }

    if include_llm_recommendations:
        result["llm_recommendations"] = recommendations or {
            "bullet_improvements": [],
            "skill_suggestions": [],
            "gap_explanations": [
                {
                    "gap": "No LLM recommendations returned",
                    "fix": "Retry analysis and verify ANTHROPIC_API_KEY and model availability",
                }
            ],
        }

    return result


# ---------------------------------------------------------------------------
# FIX 2: Hybrid score with null-guard for missing LLM score
# ---------------------------------------------------------------------------

def _compute_hybrid_with_fallback(
    *,
    ats_score: float,
    llm_score: Optional[float],
    structure_score: float,
) -> float:
    """Blend ATS, LLM, and structure scores with a null-guard on llm_score.

    FIX 2: Original compute_hybrid_score trusted callers to always pass a
    valid float. If the LLM call failed and returned None, clamp01(float(None))
    raises TypeError at runtime. When llm_score is None or 0.0 (sentinel for
    failure), redistribute weight: ATS 73%, structure 27%.
    """
    if llm_score is None or llm_score <= 0.0:
        logger.warning(
            "LLM score unavailable (%.3f); redistributing weight: ATS 73%%, structure 27%%",
            llm_score or 0.0,
        )
        from app.intelligence.utils import clamp01
        return round(clamp01(0.73 * clamp01(ats_score) + 0.27 * clamp01(structure_score)), 3)

    return compute_hybrid_score(
        ats_score=ats_score,
        llm_score=llm_score,
        structure_score=structure_score,
    )


# ---------------------------------------------------------------------------
# JD skill fallback extractor
# ---------------------------------------------------------------------------

def _extract_skills_from_raw_text(text: str) -> list:
    """Best-effort skill extraction from raw JD text when the parser returns nothing.

    Uses a curated set of common technical skill tokens to find mentions
    in the JD text. This is intentionally conservative — it only returns
    skills it is confident about rather than hallucinating from context.
    """
    _COMMON_SKILLS = {
        # Languages
        "python", "java", "javascript", "typescript", "golang", "go", "rust",
        "c++", "c#", "scala", "kotlin", "ruby", "php", "swift", "r",
        # Data / ML
        "sql", "mysql", "postgresql", "postgres", "mongodb", "redis",
        "machine learning", "deep learning", "nlp", "pytorch", "tensorflow",
        "keras", "scikit-learn", "pandas", "numpy", "spark", "hadoop",
        "airflow", "dbt", "mlflow", "hugging face",
        # Cloud / infra
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "ansible", "ci/cd", "jenkins", "github actions", "linux",
        # Web / API
        "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
        "spring", "graphql", "rest", "api",
        # Data platforms
        "kafka", "elasticsearch", "snowflake", "bigquery", "redshift",
        "tableau", "power bi", "looker",
        # Practices
        "git", "agile", "scrum", "devops", "microservices", "system design",
    }

    lowered = text.lower()
    found = []
    for skill in _COMMON_SKILLS:
        # Whole-word match using simple boundary check
        idx = lowered.find(skill)
        while idx != -1:
            before = lowered[idx - 1] if idx > 0 else " "
            after = lowered[idx + len(skill)] if idx + len(skill) < len(lowered) else " "
            if not before.isalpha() and not after.isalpha():
                found.append(skill)
                break
            idx = lowered.find(skill, idx + 1)
    return sorted(set(found))


# ---------------------------------------------------------------------------
# Null LLM engine stub — used when LLMAnalysisEngine is unavailable
# ---------------------------------------------------------------------------

class _NullLLMEngine:
    """No-op LLM engine used when the real engine cannot be loaded.

    Every method returns an empty but structurally valid result so the
    ATS pipeline continues without LLM features.
    """

    def score_resume_quality(self, **kwargs):
        return {"llm_score": 0.0, "reason": "LLM engine not available"}

    def generate_recommendations(self, **kwargs):
        return {
            "bullet_improvements": [],
            "skill_suggestions": [],
            "gap_explanations": [
                {
                    "gap": "LLM engine not available",
                    "fix": (
                        "Install anthropic and set ANTHROPIC_API_KEY "
                        "to enable LLM recommendations."
                    ),
                }
            ],
        }

    def get_quick_tips(self, ats_analysis):
        return []

    def refine_recommendation(self, original_recommendations, user_feedback):
        return original_recommendations


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class ResumeAnalysisService:
    """End-to-end resume analysis service combining ATS and LLM insights."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        """Initialise the analysis service.

        Args:
            api_key: Optional API key for the primary LLM provider.
            gemini_api_key: Deprecated alias for backward compatibility.
        """
        # Lazy import with explicit None-guard.
        # LLMAnalysisEngine can be None in two scenarios:
        #   1. app.llm_engine defines it conditionally (e.g. only when
        #      a valid API key is present or the Gemini SDK is installed).
        #   2. The module is partially initialised at import time.
        # We import the whole module and look up the attribute directly
        # so we can detect and handle the None case cleanly.
        import importlib as _importlib
        _llm_module = _importlib.import_module("app.llm_engine")
        _LLMClass = getattr(_llm_module, "LLMAnalysisEngine", None)

        self.parser = ResumeParser()
        effective_api_key = api_key or gemini_api_key

        if _LLMClass is not None and callable(_LLMClass):
            self.llm_engine = _LLMClass(api_key=effective_api_key)
        else:
            # LLMAnalysisEngine unavailable (missing SDK, no API key config,
            # or conditional definition in llm_engine.py). Use a no-op stub
            # so the rest of the pipeline continues without LLM features.
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "LLMAnalysisEngine is not available (resolved to %r). "
                "LLM features will be disabled for this session.",
                _LLMClass,
            )
            self.llm_engine = _NullLLMEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_resume_against_jd(
        self,
        resume_path: str,
        jd_path: str,
        include_llm_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """Perform complete resume analysis against a job description.

        Args:
            resume_path: Path to resume file.
            jd_path: Path to job description file.
            include_llm_recommendations: Whether to include LLM-based recommendations.

        Returns:
            Comprehensive analysis including ATS scores, evidence, and recommendations.

        Optimisations vs original:
        - skill_alignment, experience_alignment, and structure_score run in
          parallel via ThreadPoolExecutor (FIX 1).
        - LLM score null-guard via _compute_hybrid_with_fallback (FIX 2).
        - Result assembly via _build_analysis_result (FIX 3).
        - ATS score access via _safe_ats_score (FIX 4).
        - Step numbers in logs fixed and timing added (FIX 5).
        """
        t0 = time.perf_counter()
        logger.info("Starting resume analysis: %s vs %s", resume_path, jd_path)

        # ------------------------------------------------------------------
        # Step 1: Parse JD
        # ------------------------------------------------------------------
        t1 = time.perf_counter()
        logger.info("Step 1: Parsing job description...")
        jd_text = Path(jd_path).read_text(encoding="utf-8", errors="replace")
        jd_data = parse_job_description(jd_text)

        jd_skills_required = jd_data.get("skills_required", []) or []
        jd_skills_optional = jd_data.get("skills_optional", []) or []
        jd_responsibilities = jd_data.get("responsibilities", []) or []

        # Degrade gracefully when the JD parser returns sparse output.
        # Hard failures here prevent ANY analysis even when the resume
        # is valid — instead, log a warning and continue with what we have.
        if not jd_skills_required and not jd_skills_optional:
            logger.warning(
                "JD parser returned no skills. "
                "Skill alignment will run against an empty JD skill list. "
                "Check that the JD file is a plain-text or PDF document "
                "and that parse_job_description can read it correctly."
            )
            # Attempt to extract skills from raw JD text as a last resort
            jd_raw = str(jd_data.get("raw", "") or jd_text or "")
            if jd_raw.strip():
                jd_skills_required = _extract_skills_from_raw_text(jd_raw)
                if jd_skills_required:
                    logger.info(
                        "Extracted %d skills from raw JD text as fallback.",
                        len(jd_skills_required),
                    )

        if not jd_responsibilities:
            logger.warning(
                "JD parser returned no responsibilities. "
                "Experience alignment will run against an empty responsibility list."
            )

        logger.info("Step 1 done (%.2fs)", time.perf_counter() - t1)

        # ------------------------------------------------------------------
        # Step 2: Parse resume
        # ------------------------------------------------------------------
        t2 = time.perf_counter()
        logger.info("Step 2: Parsing resume...")
        resume_result = self.parser.parse_file(
            Path(resume_path),
            jd_context=jd_data,
            enable_section_llm=False,
        )
        resume_data = resume_result.to_dict()
        logger.info("Step 2 done (%.2fs)", time.perf_counter() - t2)

        # ------------------------------------------------------------------
        # Step 3: Extract entities
        # ------------------------------------------------------------------
        resume_entities = resume_data.get("entities", {})
        resume_metadata = resume_data.get("metadata", {})
        resume_sections = resume_data.get("sections", {})
        resume_text = str(resume_data.get("raw_text", "") or "")
        resume_experience = resume_entities.get("experience", [])
        resume_skills = resume_entities.get("skills", {})
        resume_bullets = flatten_experience_bullets(resume_experience)

        jd_skills = sorted(set(jd_skills_required) | set(jd_skills_optional))
        has_project_section = any(
            "project" in str(k).lower() for k in resume_sections.keys()
        )

        # ------------------------------------------------------------------
        # FIX 1: Steps 4-6 run in parallel — skill alignment, experience
        # alignment, and structure score are fully independent after parsing.
        # ------------------------------------------------------------------
        t3 = time.perf_counter()
        logger.info("Step 3: Running skill alignment, experience alignment, and structure score in parallel...")

        skill_alignment: Dict[str, Any] = {}
        experience_alignment: Dict[str, Any] = {}
        structure_score: float = 0.0

        with ThreadPoolExecutor(max_workers=3) as pool:
            future_skill: Future = pool.submit(
                align_skills,
                resume_skills,
                jd_skills,
                experience_bullets=resume_bullets,
                has_project_section=has_project_section,
            )
            future_experience: Future = pool.submit(
                align_experience,
                jd_responsibilities,
                resume_bullets,
                jd_importance=jd_data.get("importance_weights", {}),
                resume_experience=resume_experience,
            )
            future_structure: Future = pool.submit(
                compute_structure_score,
                resume_entities=resume_entities,
                resume_metadata=resume_metadata,
                resume_sections=resume_sections,
                resume_text=resume_text,
            )

            # Collect results — any exception propagates here
            skill_alignment = future_skill.result()
            experience_alignment = future_experience.result()
            structure_score = float(future_structure.result())

        logger.info("Step 3 done — parallel alignment (%.2fs)", time.perf_counter() - t3)

        # ------------------------------------------------------------------
        # Step 4: Compute ATS score (depends on alignment results above)
        # ------------------------------------------------------------------
        t4 = time.perf_counter()
        logger.info("Step 4: Computing ATS score...")
        ats_analysis = compute_ats_score(
            skill_alignment=skill_alignment,
            experience_alignment=experience_alignment,
            resume_entities=resume_entities,
            resume_metadata=resume_metadata,
            jd_context=jd_data,
            resume_sections=resume_sections,
            resume_text=resume_text,
        )
        logger.info("Step 4 done (%.2fs)", time.perf_counter() - t4)

        # ------------------------------------------------------------------
        # Step 5: Compute LLM score (FIX 2: null-guarded)
        # ------------------------------------------------------------------
        t5 = time.perf_counter()
        logger.info("Step 5: Computing LLM score...")
        llm_score_payload: Dict[str, Any] = {}
        llm_score: float = 0.0
        try:
            llm_score_payload = self.llm_engine.score_resume_quality(
                resume_data=resume_data,
                jd_data=jd_data,
                ats_analysis=ats_analysis,
            )
            llm_score = float(llm_score_payload.get("llm_score") or 0.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM scoring failed (%s); hybrid score will use fallback weights.", exc)
            llm_score_payload = {"reason": f"LLM scoring failed: {exc}"}
            llm_score = 0.0

        # FIX 2: null-guarded hybrid blend
        hybrid_score = _compute_hybrid_with_fallback(
            ats_score=_safe_ats_score(ats_analysis),
            llm_score=llm_score if llm_score > 0.0 else None,
            structure_score=structure_score,
        )
        logger.info("Step 5 done (%.2fs)", time.perf_counter() - t5)

        # ------------------------------------------------------------------
        # Step 6: LLM recommendations (optional)
        # ------------------------------------------------------------------
        recommendations: Optional[Dict[str, Any]] = None
        if include_llm_recommendations:
            recommendations = self._generate_recommendations(
                resume_data=resume_data,
                jd_data=jd_data,
                ats_analysis=ats_analysis,
            )

        # ------------------------------------------------------------------
        # Step 7: Assemble result (FIX 3)
        # ------------------------------------------------------------------
        result = _build_analysis_result(
            resume_data=resume_data,
            jd_data=jd_data,
            ats_analysis=ats_analysis,
            llm_score=llm_score,
            llm_score_payload=llm_score_payload,
            structure_score=structure_score,
            hybrid_score=hybrid_score,
            recommendations=recommendations,
            quick_tips=self.llm_engine.get_quick_tips(ats_analysis),
            include_llm_recommendations=include_llm_recommendations,
        )

        logger.info(
            "Resume analysis complete — total (%.2fs)", time.perf_counter() - t0
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        *,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
        ats_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate LLM recommendations with experience-score guard and error fallback.

        Extracted from inline try/except block in original for clarity.
        """
        experience_score = float(
            ats_analysis.get("components", {}).get("experience_score", 0.0) or 0.0
        )
        if experience_score <= 0.0:
            logger.warning(
                "Skipping LLM recommendations: experience_score is 0.0; "
                "parser/alignment likely lacks usable experience evidence."
            )
            return {
                "bullet_improvements": [],
                "skill_suggestions": [],
                "gap_explanations": [
                    {
                        "gap": "Experience section not parsed correctly",
                        "fix": "Fix resume parsing before generating recommendations",
                    }
                ],
            }

        try:
            logger.info("Step 6: Generating LLM recommendations...")
            recommendations = self.llm_engine.generate_recommendations(
                resume_data=resume_data,
                jd_data=jd_data,
                ats_analysis=ats_analysis,
            )
            logger.info("Successfully generated LLM recommendations")
            return recommendations
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to generate LLM recommendations: %s", exc)
            return {
                "bullet_improvements": [],
                "skill_suggestions": [],
                "gap_explanations": [
                    {
                        "gap": "LLM recommendation generation failed",
                        "fix": f"Retry analysis. Underlying error: {exc}",
                    }
                ],
            }

    # ------------------------------------------------------------------
    # Public utility methods (unchanged from original)
    # ------------------------------------------------------------------

    def get_score_summary(self, ats_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of ATS scores and interpretation.

        Args:
            ats_analysis: ATS analysis results.

        Returns:
            Summary with score interpretation and action items.
        """
        # FIX 4: use _safe_ats_score instead of bare .get("ats_score", 0)
        overall_score = _safe_ats_score(ats_analysis)

        if overall_score >= 0.85:
            interpretation = "EXCELLENT: Resume likely to pass ATS screening"
            action = "Minor refinements recommended"
        elif overall_score >= 0.70:
            interpretation = "GOOD: Resume should pass ATS, but could be improved"
            action = "Implement suggestions to increase score to 85%+"
        elif overall_score >= 0.60:
            interpretation = "FAIR: Resume may have ATS visibility issues"
            action = "Address critical gaps immediately"
        else:
            interpretation = "POOR: Resume likely to be filtered by ATS"
            action = "Significant rework needed before applying"

        components = ats_analysis.get("components", {})
        weakest_component = min(components.items(), key=lambda x: x[1])

        return {
            "overall_score": overall_score,
            "interpretation": interpretation,
            "recommended_action": action,
            "component_scores": components,
            "weakest_area": {
                "name": weakest_component[0],
                "score": weakest_component[1],
            },
            "next_steps": [
                f"Improve {weakest_component[0]} score (currently {weakest_component[1]:.0%})",
                "See recommendations for specific action items",
                "Run another analysis after implementing changes",
            ],
        }

    def refine_recommendations(
        self,
        original_recommendations: Dict[str, Any],
        user_feedback: str,
    ) -> Dict[str, Any]:
        """Refine LLM recommendations based on user feedback.

        Args:
            original_recommendations: Initial LLM recommendations.
            user_feedback: User feedback on the recommendations.

        Returns:
            Refined recommendations.
        """
        logger.info("Refining recommendations: %s", user_feedback)
        refined = self.llm_engine.refine_recommendation(
            original_recommendations, user_feedback
        )
        logger.info("Successfully refined recommendations")
        return refined