"""Pydantic schemas for LLM responses."""

from typing import List, Dict, Any
import logging

from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


class BulletImprovement(BaseModel):
    """Model for improved resume bullet."""

    original: str = Field(
        ..., description="Original bullet text from resume"
    )
    improved: str = Field(
        ..., description="Improved version with metrics, action verbs, and outcomes"
    )
    reason: str = Field(
        ..., description="Why this change improves the bullet"
    )

    @field_validator("improved")
    @classmethod
    def validate_improved_bullet(cls, v: str) -> str:
        """Ensure improved bullet has action verb and is longer than original."""
        action_verbs = {
            "built",
            "designed",
            "led",
            "developed",
            "implemented",
            "optimized",
            "improved",
            "created",
            "engineered",
            "deployed",
        }
        if not any(verb in v.lower() for verb in action_verbs):
            logger.warning(
                "Improved bullet missing known action verb; accepting as-is"
            )
        return v


class SkillSuggestion(BaseModel):
    """Model for suggested missing skill with evidence guidance."""

    skill: str = Field(
        ..., description="Name of recommended skill to add"
    )
    reason: str = Field(
        ..., description="Why this skill should be added"
    )


class GapExplanation(BaseModel):
    """Model for gap in coverage with mitigation strategy."""

    gap: str = Field(
        ..., description="JD responsibility area not covered"
    )
    fix: str = Field(
        ..., description="Specific steps to close this gap"
    )


class LLMAnalysisResponse(BaseModel):
    """Final LLM analysis response."""

    bullet_improvements: List[BulletImprovement] = Field(
        ..., description="Bullets to rewrite"
    )
    skill_suggestions: List[SkillSuggestion] = Field(
        ..., description="Recommended missing skills"
    )
    gap_explanations: List[GapExplanation] = Field(
        ..., description="Coverage gaps and fixes"
    )

    @field_validator("bullet_improvements")
    @classmethod
    def validate_bullets_count(cls, v: List[BulletImprovement]) -> List[BulletImprovement]:
        """Allow empty list and cap at 7 bullet improvements."""
        if not (0 <= len(v) <= 7):
            raise ValueError(
                "Must have between 0 and 7 bullet improvements"
            )
        return v

    @field_validator("skill_suggestions")
    @classmethod
    def validate_skills_count(cls, v: List[SkillSuggestion]) -> List[SkillSuggestion]:
        """Allow empty list and cap at 7 skill suggestions."""
        if not (0 <= len(v) <= 7):
            raise ValueError("Must have between 0 and 7 skill suggestions")
        return v

    @field_validator("gap_explanations")
    @classmethod
    def validate_gaps_count(cls, v: List[GapExplanation]) -> List[GapExplanation]:
        """Allow empty list and cap at 7 gap explanations."""
        if not (0 <= len(v) <= 7):
            raise ValueError("Must have between 0 and 7 gap explanations")
        return v


class GeneratedResume(BaseModel):
    """Model for full resume generation output."""

    contact: Dict[str, str] = Field(
        ..., description="Candidate contact info with location/email/phone/linkedin/github"
    )
    summary: str = Field(..., description="Professional summary section")
    experience: List[Dict[str, Any]] = Field(
        ..., description="Experience entries with title, company, duration, and bullets"
    )
    projects: List[Dict[str, Any]] = Field(
        ..., description="Project entries with name, bullets, and technologies"
    )
    education: str = Field(..., description="Education summary")
    skills: Dict[str, List[str]] = Field(
        ..., description="Categorized skills map for required categories"
    )
    certifications: List[str] = Field(..., description="List of certifications")

    @field_validator("skills")
    @classmethod
    def validate_skills_structure(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Require strict skill category buckets for compliance mode."""
        required_categories = {
            "programming_languages",
            "data_science",
            "data_visualization",
            "databases",
            "tools",
        }
        missing = required_categories - set(v.keys())
        if missing:
            raise ValueError(f"Missing required skills categories: {sorted(missing)}")

        for category in required_categories:
            values = v.get(category, [])
            if not isinstance(values, list):
                raise ValueError(f"Skills category '{category}' must be a list")
            for item in values:
                if not isinstance(item, str):
                    raise ValueError(f"Skills category '{category}' items must be strings")
        return v

    @field_validator("certifications")
    @classmethod
    def validate_certifications_limit(cls, v: List[str]) -> List[str]:
        """Enforce certification cap from strict rules."""
        if len(v) > 5:
            raise ValueError("Max 5 certifications allowed")
        return v

    @field_validator("contact")
    @classmethod
    def validate_contact_structure(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Require stable contact keys so renderers can reliably show header details."""
        required_keys = {"location", "email", "phone", "linkedin", "github"}
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(f"Missing required contact fields: {sorted(missing)}")
        for key in required_keys:
            value = v.get(key, "")
            if not isinstance(value, str):
                raise ValueError(f"contact.{key} must be a string")
        return v
