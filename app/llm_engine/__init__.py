"""LLM Engine module for ATS Resume Analysis."""

from .schemas import (
    BulletImprovement,
    SkillSuggestion,
    GapExplanation,
    LLMAnalysisResponse,
    GeneratedResume,
)
from .gemini_client import GeminiAPIClient
from .claude_client import ClaudeSonnetClient
from .base_client import BaseLLMClient

try:
    from .llm_analysis_engine import LLMAnalysisEngine, LLMMode
    from .prompt_builder import PromptBuilder
    from .resume_validator import (
        APPROVED_ACTION_VERBS,
        validate_word_count,
        validate_action_verbs,
        validate_metrics,
        validate_bullet_count,
        validate_pronouns,
        validate_weak_verbs,
        validate_section_order,
        validate_skills_structure,
        validate_certifications,
        validate_dates,
        validate_experience_rules,
        validate_project_rules,
        validate_generated_resume,
    )
except Exception:  # pragma: no cover - optional stack may be missing in lightweight environments
    LLMAnalysisEngine = None  # type: ignore[assignment]
    LLMMode = None  # type: ignore[assignment]
    PromptBuilder = None  # type: ignore[assignment]
    APPROVED_ACTION_VERBS = set()  # type: ignore[assignment]

    def validate_word_count(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_action_verbs(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_metrics(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_bullet_count(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_pronouns(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_weak_verbs(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_section_order(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_skills_structure(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_certifications(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_dates(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_experience_rules(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_project_rules(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

    def validate_generated_resume(*args, **kwargs):  # type: ignore[no-redef]
        raise RuntimeError("llm_engine optional dependencies are not fully available")

__all__ = [
    "BulletImprovement",
    "SkillSuggestion",
    "GapExplanation",
    "LLMAnalysisResponse",
    "GeneratedResume",
    "BaseLLMClient",
    "ClaudeSonnetClient",
    "GeminiAPIClient",
    "LLMAnalysisEngine",
    "LLMMode",
    "PromptBuilder",
    "APPROVED_ACTION_VERBS",
    "validate_word_count",
    "validate_action_verbs",
    "validate_metrics",
    "validate_bullet_count",
    "validate_pronouns",
    "validate_weak_verbs",
    "validate_section_order",
    "validate_skills_structure",
    "validate_certifications",
    "validate_dates",
    "validate_experience_rules",
    "validate_project_rules",
    "validate_generated_resume",
]
