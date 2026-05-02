"""Resume section detection based on heading heuristics."""

from __future__ import annotations

import importlib
import re
from collections import defaultdict
from typing import Any


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "contact": ("contact", "personal details", "contact information"),
    "summary": (
        "summary",
        "profile",
        "professional summary",
        "career objective",
        "objective",
    ),
    "skills": ("skills", "technical skills", "core competencies", "technologies"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "internship experience",
        "internships",
        "internship",
        "career history",
    ),
    "projects": (
        "projects", 
        "project experience", 
        "key projects",
        "academic projects",
        "personal projects",
    ),
    "education": ("education", "academic background", "qualifications"),
    "certifications": ("certifications", "certificates", "licenses"),
    "achievements": ("achievements", "awards", "honors"),
    "publications": ("publications", "research", "papers"),
    "leadership": ("leadership", "leadership experience"),
}

_HEADING_SUFFIX_TOKENS = {
    "and",
    "section",
    "details",
    "summary",
    "highlights",
    "overview",
    "history",
    "background",
    "information",
    "experience",
    "skills",
    "projects",
    "certifications",
    "achievements",
    "publications",
    "leadership",
}


def _normalize_header_text(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"^\d+[.)-]\s*", "", lowered)
    lowered = lowered.strip(":")
    lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _canonical_section(header: str) -> str | None:
    normalized = _normalize_header_text(header)
    for canonical, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            alias_normalized = _normalize_header_text(alias)
            if normalized == alias_normalized:
                return canonical
            if normalized.startswith(f"{alias_normalized} "):
                suffix = normalized[len(alias_normalized) + 1 :]
                suffix_tokens = [token for token in suffix.split() if token]
                # Allow short heading extensions like "Experience Highlights",
                # but reject sentence-like lines such as "Education technology startup...".
                if (
                    suffix_tokens
                    and len(suffix_tokens) <= 3
                    and all(token in _HEADING_SUFFIX_TOKENS for token in suffix_tokens)
                ):
                    return canonical
    return None


def _is_probable_heading(line: str) -> bool:
    candidate = line.strip()
    if not candidate:
        return False

    if _canonical_section(candidate):
        return True

    words = _normalize_header_text(candidate).split()
    if len(words) > 7:
        return False

    alpha_ratio = sum(char.isalpha() for char in candidate) / max(len(candidate), 1)
    looks_like_sentence = candidate.endswith(".") or len(words) > 5
    if alpha_ratio < 0.6 or looks_like_sentence:
        return False

    is_upper = candidate.isupper() and len(words) <= 6
    has_colon = candidate.endswith(":") and len(words) <= 6
    return is_upper or has_colon


def detect_sections(text: str) -> dict[str, str]:
    sections, _confidence = detect_sections_with_confidence(text)
    return sections


def detect_sections_with_confidence(text: str) -> tuple[dict[str, str], float]:
    """Split resume text into canonical sections."""
    lines = text.splitlines()
    sections: dict[str, list[str]] = defaultdict(list)
    current = "unclassified"

    for line in lines:
        if _is_probable_heading(line):
            maybe_section = _canonical_section(line)
            if maybe_section:
                current = maybe_section
                continue
        sections[current].append(line)

    # Resume headers often place contact details before explicit headings.
    if "contact" not in sections and "unclassified" in sections:
        preamble = "\n".join(sections["unclassified"][:4])
        if re.search(r"@|linkedin\.com|github\.com|\+?\d", preamble, re.IGNORECASE):
            sections["contact"] = sections["unclassified"][:4]

    if "experience" not in sections:
        inferred_experience = heuristic_find_experience(text)
        if inferred_experience:
            sections["experience"] = inferred_experience.splitlines()

    confidence = _section_confidence(sections)
    if confidence < 0.55:
        ml_sections = _ml_classify_paragraphs(text)
        for section_name, content in ml_sections.items():
            if section_name not in sections and content.strip():
                sections[section_name] = content.splitlines()
        confidence = _section_confidence(sections)

    normalized = {
        key: "\n".join(value).strip()
        for key, value in sections.items()
        if "\n".join(value).strip()
    }
    return normalized, round(confidence, 3)


def heuristic_find_experience(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []
    for line in lines:
        if re.search(r"\b(19\d{2}|20\d{2})\b", line) and (
            "engineer" in line.lower()
            or "developer" in line.lower()
            or "analyst" in line.lower()
            or "manager" in line.lower()
        ):
            candidates.append(line)
    return "\n".join(candidates)


def _section_confidence(sections: dict[str, list[str]] | dict[str, str]) -> float:
    recognized = 0
    total = 0
    for section_name, value in sections.items():
        line_count = len(value) if isinstance(value, list) else len([line for line in value.splitlines() if line])
        total += line_count
        if section_name != "unclassified":
            recognized += line_count
    if total == 0:
        return 0.0
    return recognized / total


def _ml_classify_paragraphs(text: str) -> dict[str, str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if not paragraphs:
        return {}

    try:
        sentence_transformers = importlib.import_module(
            "sentence_transformers"
        )  # pyright: ignore[reportMissingImports]
        model_cls = getattr(sentence_transformers, "SentenceTransformer")
        util: Any = getattr(sentence_transformers, "util")
    except ImportError:
        return {}

    model = model_cls("all-MiniLM-L6-v2")
    labels = sorted(SECTION_ALIASES.keys())
    label_vectors = model.encode(labels, convert_to_tensor=True)
    paragraph_vectors = model.encode(paragraphs, convert_to_tensor=True)
    similarity = util.cos_sim(paragraph_vectors, label_vectors)

    classified: dict[str, list[str]] = defaultdict(list)
    for idx, paragraph in enumerate(paragraphs):
        row = similarity[idx]
        best_idx = int(row.argmax())
        score = float(row[best_idx])
        if score >= 0.35:
            classified[labels[best_idx]].append(paragraph)

    return {key: "\n\n".join(value) for key, value in classified.items() if value}
