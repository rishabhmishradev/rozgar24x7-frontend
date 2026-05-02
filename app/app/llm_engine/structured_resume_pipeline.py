"""Deterministic structured resume pipeline.

This module defines the source-of-truth resume schema and section-wise
enhancement helpers that keep structure fully controlled by user input.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import re
from typing import Any, Dict, List, TypedDict, cast

logger = logging.getLogger(__name__)


class ContactData(TypedDict):
    email: str
    phone: str
    linkedin: str
    github: str
    location: str


class ExperienceEntry(TypedDict):
    title: str
    company: str
    duration: str
    bullets: List[str]
    location: str


class ProjectEntry(TypedDict):
    name: str
    technologies: List[str]
    bullets: List[str]


class AdditionalSectionEntry(TypedDict):
    title: str
    body: str
    bullets: List[str]


class SkillsData(TypedDict):
    programming_languages: List[str]
    tools: List[str]
    data_science: List[str]
    data_visualization: List[str]
    databases: List[str]


class ResumeData(TypedDict):
    name: str
    contact: ContactData
    experience: List[ExperienceEntry]
    projects: List[ProjectEntry]
    education: str
    summary: str
    skills: SkillsData
    certifications: List[str]
    additional_sections: List[AdditionalSectionEntry]


RESUME_DATA_TEMPLATE: ResumeData = {
    "name": "",
    "contact": {
        "email": "",
        "phone": "",
        "linkedin": "",
        "github": "",
        "location": "",
    },
    "experience": [],
    "projects": [],
    "education": "",
    "summary": "",
    "skills": {
        "programming_languages": [],
        "tools": [],
        "data_science": [],
        "data_visualization": [],
        "databases": [],
    },
    "certifications": [],
    "additional_sections": [],
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    output: List[str] = []
    seen: set[str] = set()
    for item in cast(List[Any], values):
        text = _clean_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _coerce_section_bullets(value: Any) -> List[str]:
    if isinstance(value, list):
        return _clean_list(value)
    text = _clean_text(value)
    if not text:
        return []
    return [line.strip().lstrip("-•*").strip() for line in text.splitlines() if line.strip()]


def _extract_bullets_from_entry(data: Dict[str, Any]) -> List[str]:
    """Extract bullets from entry trying multiple key names (bullets, points, description, items).
    
    Handles upstream data format variations from parsers.
    """
    # Try standard "bullets" key first
    bullets = _clean_list(data.get("bullets", []))
    if bullets:
        return bullets
    
    # Try alternative names
    for alt_key in ["points", "items", "content"]:
        bullets = _clean_list(data.get(alt_key, []))
        if bullets:
            return bullets
    
    # Try description/summary as fallback (coerce to list)
    for desc_key in ["description", "summary", "details"]:
        bullets = _coerce_section_bullets(data.get(desc_key, ""))
        if bullets:
            return bullets
    
    return []


def _display_section_title(title: str) -> str:
    normalized = _clean_text(title).replace("_", " ").strip()
    mapping = {
        "achievements": "Achievements",
        "awards": "Awards",
        "certifications": "Certifications",
        "leadership": "Leadership",
        "publications": "Publications",
        "languages": "Languages",
        "interests": "Interests",
        "summary": "Professional Summary",
    }
    lowered = normalized.lower()
    if lowered in mapping:
        return mapping[lowered]
    return normalized.title() if normalized else "Additional Information"


def _get_skill_values(skills: Dict[str, Any], canonical_key: str) -> Any:
    alias_map: Dict[str, List[str]] = {
        "programming_languages": ["programming_languages", "programming languages"],
        "tools": ["tools"],
        "data_science": ["data_science", "data science"],
        "data_visualization": ["data_visualization", "data visualization"],
        "databases": ["databases"],
    }
    lowered = {str(k).strip().lower(): v for k, v in skills.items()}
    for alias in alias_map.get(canonical_key, [canonical_key]):
        if alias in lowered:
            return lowered[alias]
    return []


def normalize_resume_data(user_input: Dict[str, Any]) -> ResumeData:
    """Build deterministic source-of-truth resume structure from user input."""
    logger.debug("=" * 60)
    logger.debug("NORMALIZE_RESUME_DATA: START")
    logger.debug("=" * 60)
    logger.debug(f"Input has keys: {list(user_input.keys())}")
    
    result: ResumeData = deepcopy(RESUME_DATA_TEMPLATE)

    result["name"] = _clean_text(user_input.get("name"))
    logger.debug(f"Name normalized: {result['name']}")

    contact_raw = user_input.get("contact", {})
    if isinstance(contact_raw, dict):
        contact = cast(Dict[str, Any], contact_raw)
        result["contact"] = {
            "email": _clean_text(contact.get("email")),
            "phone": _clean_text(contact.get("phone")),
            "linkedin": _clean_text(contact.get("linkedin")),
            "github": _clean_text(contact.get("github")),
            "location": _clean_text(contact.get("location")),
        }
        logger.debug(f"Contact normalized: {result['contact']}")

    exp_raw = user_input.get("experience", [])
    if isinstance(exp_raw, list):
        logger.debug(f"Processing {len(exp_raw)} experience entries")
        for i, row in enumerate(cast(List[Any], exp_raw)):
            if not isinstance(row, dict):
                logger.warning(f"  Experience[{i}] is not dict, skipping")
                continue
            data = cast(Dict[str, Any], row)
            title = _clean_text(data.get("title") or data.get("role"))
            company = _clean_text(data.get("company"))
            duration = _clean_text(data.get("duration"))
            bullets = _extract_bullets_from_entry(data)
            if not (title or company or duration or bullets):
                continue
            
            logger.debug(f"  Exp[{i}]: {title} @ {company} ({len(bullets)} bullets)")
            result["experience"].append(
                {
                    "title": title,
                    "company": company,
                    "duration": duration,
                    "bullets": bullets,
                    "location": _clean_text(data.get("location") or data.get("city") or data.get("place")),
                }
            )

    proj_raw = user_input.get("projects", [])
    if isinstance(proj_raw, list):
        logger.debug(f"Processing {len(proj_raw)} projects")
        for i, row in enumerate(cast(List[Any], proj_raw)):
            if not isinstance(row, dict):
                logger.warning(f"  Project[{i}] is not dict, skipping")
                continue
            data = cast(Dict[str, Any], row)
            name = _clean_text(data.get("name"))
            tech = _clean_list(data.get("technologies", []))
            bullets = _extract_bullets_from_entry(data)
            if not (name or tech or bullets):
                continue
            
            logger.debug(f"  Proj[{i}]: {name} - {tech} ({len(bullets)} bullets)")
            result["projects"].append(
                {
                    "name": name,
                    "technologies": tech,
                    "bullets": bullets,
                }
            )

    result["education"] = _clean_text(user_input.get("education"))
    logger.debug(f"Education: {result['education']}")
    
    result["summary"] = _clean_text(user_input.get("summary"))
    logger.debug(f"Summary length: {len(result['summary'])}")

    additional_raw = user_input.get("additional_sections", [])
    if isinstance(additional_raw, dict):
        additional_map = cast(Dict[str, Any], additional_raw)
        additional_items: List[Any] = [
            {
                "title": str(key),
                "body": value,
                "bullets": _coerce_section_bullets(value),
            }
            for key, value in additional_map.items()
        ]
    elif isinstance(additional_raw, list):
        additional_items = cast(List[Any], additional_raw)
    else:
        additional_items = []

    logger.debug(f"Processing {len(additional_items)} additional sections")
    for item in additional_items:
        if isinstance(item, dict):
            data = cast(Dict[str, Any], item)
            title = _display_section_title(_clean_text(data.get("title") or data.get("name")))
            bullets = _coerce_section_bullets(data.get("bullets", []))
            body = _clean_text(data.get("body"))
            if not bullets and body:
                bullets = _coerce_section_bullets(body)
            logger.debug(f"  Additional section: {title} ({len(bullets)} bullets)")
            if title and (bullets or body):
                result["additional_sections"].append({"title": title, "body": body, "bullets": bullets})
        else:
            text = _clean_text(item)
            if text:
                logger.debug(f"  Additional section (string): {text}")
                result["additional_sections"].append(
                    {"title": "Additional Information", "body": text, "bullets": [text]}
                )

    skills_raw = user_input.get("skills", {})
    if isinstance(skills_raw, dict):
        skills = cast(Dict[str, Any], skills_raw)
        result["skills"] = {
            "programming_languages": _clean_list(_get_skill_values(skills, "programming_languages")),
            "tools": _clean_list(_get_skill_values(skills, "tools")),
            "data_science": _clean_list(_get_skill_values(skills, "data_science")),
            "data_visualization": _clean_list(_get_skill_values(skills, "data_visualization")),
            "databases": _clean_list(_get_skill_values(skills, "databases")),
        }
        logger.debug(f"Skills: {result['skills']}")

    result["certifications"] = _clean_list(user_input.get("certifications", []))[:5]

    if not result["name"]:
        result["name"] = "Candidate"

    return result


def parse_bullet_lines(response_text: str, fallback: List[str]) -> List[str]:
    """Convert LLM bullet response into clean bullet list deterministically."""
    lines = [line.strip() for line in str(response_text or "").splitlines()]
    parsed: List[str] = []
    seen: set[str] = set()

    for line in lines:
        if not line:
            continue
        cleaned = re.sub(r"^[-*\u2022\d\.)\s]+", "", line).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed.append(cleaned)

    if not parsed:
        return list(fallback)
    return parsed


def improve_experience_bullets(experience_entry: ExperienceEntry, llm_client: Any) -> List[str]:
    """Improve bullets for a single experience entry while preserving structure."""
    original = experience_entry.get("bullets", [])
    if not original:
        return ["Performed role responsibilities and contributed to team objectives"]

    prompt = f"""
Improve the following experience bullets:

{chr(10).join(f"- {b}" for b in original)}

Rules:
- Use strong action verbs
- Add measurable impact where natural
- Avoid repetition
- Keep it realistic (do NOT hallucinate fake metrics)
- Return ONLY improved bullet points, one per line
""".strip()

    generator = getattr(llm_client, "generate_text", None)
    if not callable(generator):
        return list(original)

    try:
        response = str(generator(prompt)).strip()
        return parse_bullet_lines(response, list(original))
    except Exception:
        return list(original)


def improve_project_bullets(project: ProjectEntry, llm_client: Any) -> List[str]:
    """Improve bullets for a single project while preserving structure."""
    original = project.get("bullets", [])
    if not original:
        return []

    technologies = ", ".join(project.get("technologies", []))
    prompt = f"""
Improve the following project bullets:

Project: {project.get('name', '')}
Technologies: {technologies}

{chr(10).join(f"- {b}" for b in original)}

Rules:
- Use strong action verbs
- Add measurable impact where natural
- Avoid repetition
- Keep it realistic (do NOT hallucinate fake metrics)
- Return ONLY improved bullet points, one per line
""".strip()

    generator = getattr(llm_client, "generate_text", None)
    if not callable(generator):
        return list(original)

    try:
        response = str(generator(prompt)).strip()
        return parse_bullet_lines(response, list(original))
    except Exception:
        return list(original)


def improve_summary(resume_data: ResumeData, llm_client: Any) -> str:
    existing_summary = _clean_text(resume_data.get("summary", ""))
    summary_context = f"\nExisting Summary: {existing_summary}" if existing_summary else ""
    experience_roles = ", ".join(e.get("title", "") for e in resume_data.get("experience", [])[:3])
    prompt = f"""
Write a concise 2-3 line professional summary for this candidate.
Use only the provided information, no new facts.

Name: {resume_data.get('name', '')}
Top Skills: {', '.join(resume_data.get('skills', {}).get('programming_languages', [])[:6])}
Experience Roles: {experience_roles}{summary_context}

Return ONLY summary text.
""".strip()

    generator = getattr(llm_client, "generate_text", None)
    if not callable(generator):
        return _fallback_summary(resume_data)

    try:
        generated = _clean_text(generator(prompt))
        return generated if generated else _fallback_summary(resume_data)
    except Exception:
        return _fallback_summary(resume_data)


def _fallback_summary(resume_data: ResumeData) -> str:
    primary_skill = ""
    for key in ("programming_languages", "tools", "data_science", "data_visualization", "databases"):
        values = resume_data.get("skills", {}).get(key, [])
        if values:
            primary_skill = values[0]
            break
    primary_role = ""
    if resume_data.get("experience"):
        primary_role = _clean_text(resume_data["experience"][0].get("title"))
    parts: List[str] = []
    if primary_role:
        parts.append(primary_role)
    if primary_skill:
        parts.append(primary_skill)
    if parts:
        return f"Results-driven professional with experience in {' and '.join(parts)} and a strong focus on measurable impact."
    return "Results-driven professional with a strong focus on measurable impact and continuous improvement."


def refine_skills(skills: SkillsData, llm_client: Any) -> SkillsData:
    """Optional deterministic skill cleanup (currently pass-through)."""
    _ = llm_client
    return {
        "programming_languages": _clean_list(skills.get("programming_languages", [])),
        "tools": _clean_list(skills.get("tools", [])),
        "data_science": _clean_list(skills.get("data_science", [])),
        "data_visualization": _clean_list(skills.get("data_visualization", [])),
        "databases": _clean_list(skills.get("databases", [])),
    }


def enforce_structure_integrity(original: ResumeData, modified: ResumeData) -> ResumeData:
    """
    CRITICAL DATA INTEGRITY FUNCTION.
    
    Restore all non-content fields to originals to prevent data loss.
    ONLY modified fields allowed: bullets, body
    LOCKED FIELDS: titles, companies, durations, technologies, skills, contact, name, education
    """
    logger.debug("=" * 60)
    logger.debug("ENFORCE_STRUCTURE_INTEGRITY: START")
    logger.debug("=" * 60)
    
    # LOCK EXPERIENCE: restore title, company, duration to originals
    logger.debug("LOCKING EXPERIENCE STRUCTURE")
    for i in range(len(original["experience"])):
        if i < len(modified["experience"]):
            orig_company = original["experience"][i]["company"]
            mod_company = modified["experience"][i]["company"]
            if orig_company != mod_company:
                logger.warning(f"  Exp[{i}]: Company changed '{mod_company}' → RESTORED to '{orig_company}'")
            
            modified["experience"][i]["title"] = original["experience"][i]["title"]
            modified["experience"][i]["company"] = original["experience"][i]["company"]
            modified["experience"][i]["duration"] = original["experience"][i]["duration"]
            # Ensure company is never "N/A" if original had value
            if not modified["experience"][i]["company"] or modified["experience"][i]["company"] == "N/A":
                modified["experience"][i]["company"] = original["experience"][i]["company"]

    # LOCK PROJECTS: restore name, technologies to originals
    logger.debug("LOCKING PROJECTS STRUCTURE")
    for i in range(len(original["projects"])):
        if i < len(modified["projects"]):
            orig_name = original["projects"][i]["name"]
            mod_name = modified["projects"][i]["name"]
            if orig_name != mod_name:
                logger.warning(f"  Proj[{i}]: Name changed '{mod_name}' → RESTORED to '{orig_name}'")
            
            modified["projects"][i]["name"] = original["projects"][i]["name"]
            modified["projects"][i]["technologies"] = original["projects"][i]["technologies"]

    # LOCK SKILLS: NEVER send to LLM, preserve exactly
    logger.debug("LOCKING SKILLS")
    if modified["skills"] != original["skills"]:
        logger.warning("  Skills were modified! Restoring to original.")
    modified["skills"] = deepcopy(original["skills"])

    # LOCK CONTACT: preserve exactly
    logger.debug("LOCKING CONTACT")
    modified["contact"] = deepcopy(original["contact"])

    # LOCK NAME: preserve exactly
    logger.debug("LOCKING NAME")
    modified["name"] = original["name"]

    # LOCK EDUCATION: preserve exactly
    logger.debug("LOCKING EDUCATION")
    modified["education"] = original["education"]

    logger.debug("=" * 60)
    logger.debug("ENFORCE_STRUCTURE_INTEGRITY: COMPLETE")
    logger.debug("=" * 60)

    return modified


def apply_section_enhancement_pipeline(resume_data: ResumeData, llm_client: Any) -> Dict[str, Any]:
    """Apply section-wise LLM enhancement without changing structure fields.
    
    CRITICAL RULE: Only modify bullets and body text.
    All structural fields (titles, companies, technologies, skills, contact) are immutable.
    """
    original: ResumeData = deepcopy(resume_data)
    data: ResumeData = deepcopy(resume_data)

    # ENHANCEMENT ONLY (BULLETS ONLY)
    for entry in data["experience"]:
        entry["bullets"] = improve_experience_bullets(entry, llm_client)

    for project in data["projects"]:
        project["bullets"] = improve_project_bullets(project, llm_client)

    summary = improve_summary(data, llm_client)
    # NOTE: Skills are NOT sent to LLM - we lock them down explicitly below

    # ENFORCE STRUCTURAL INTEGRITY: restore all non-content fields
    data = enforce_structure_integrity(original, data)

    return {
        "resume_data": data,
        "summary": summary,
    }


def render_plain_text_resume(resume_data: ResumeData, summary: str = "") -> str:
    """Deterministic plain text renderer from structured resume data."""
    lines: List[str] = []
    lines.append(resume_data.get("name", "Candidate"))

    contact = resume_data.get("contact", {})
    contact_parts = [
        _clean_text(contact.get("email")),
        _clean_text(contact.get("phone")),
        _clean_text(contact.get("linkedin")),
        _clean_text(contact.get("github")),
        _clean_text(contact.get("location")),
    ]
    contact_line = " | ".join([p for p in contact_parts if p])
    if contact_line:
        lines.append(contact_line)

    if resume_data.get("experience"):
        lines.append("")
        lines.append("EXPERIENCE")
        for exp in resume_data["experience"]:
            lines.append(f"{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('duration', '')}".strip(" |"))
            for bullet in exp.get("bullets", []):
                lines.append(f"- {bullet}")

    if resume_data.get("projects"):
        lines.append("")
        lines.append("PROJECTS")
        for proj in resume_data["projects"]:
            lines.append(proj.get("name", ""))
            for bullet in proj.get("bullets", []):
                lines.append(f"- {bullet}")
            tech = ", ".join(proj.get("technologies", []))
            if tech:
                lines.append(f"Technologies: {tech}")

    if resume_data.get("education"):
        lines.append("")
        lines.append("EDUCATION")
        lines.append(resume_data["education"])

    additional_sections = resume_data.get("additional_sections", [])
    if additional_sections:
        for section in additional_sections:
            title = _display_section_title(str(section.get("title", "Additional Information")))
            bullets = [str(item).strip() for item in section.get("bullets", []) if str(item).strip()]
            if not bullets and section.get("body"):
                bullets = [line.strip() for line in str(section.get("body", "")).splitlines() if line.strip()]
            if not bullets:
                continue
            lines.append("")
            lines.append(title.upper())
            for bullet in bullets:
                lines.append(f"- {bullet}")

    skills = resume_data.get("skills", {})
    if skills:
        lines.append("")
        lines.append("SKILLS")
        for key in ("programming_languages", "tools", "data_science", "databases"):
            values = skills.get(key, [])
            if values:
                label = key.replace("_", " ").title()
                lines.append(f"{label}: {', '.join(values)}")

    certs = resume_data.get("certifications", [])
    if certs:
        lines.append("")
        lines.append("CERTIFICATIONS")
        for cert in certs:
            lines.append(f"- {cert}")

    return "\n".join(lines).strip() + "\n"
