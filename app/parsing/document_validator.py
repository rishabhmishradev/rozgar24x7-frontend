"""Fast document-type validation to reject non-resume uploads early.

This module provides a lightweight, deterministic check that runs on raw
extracted text *before* any expensive layout analysis, OCR, or LLM calls.
The goal is to reject obviously non-resume files (e-books, legal contracts,
technical manuals) while being highly forgiving toward real resumes.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class InvalidDocumentError(ValueError):
    """Raised when an uploaded document does not appear to be a resume or CV."""


# ── regex patterns ───────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3})?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    r"|(?:\+?\d{1,3}[\s-]?)?[6-9]\d{4}[\s.-]?\d{5}"
)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/", re.IGNORECASE)

# Section headers commonly found in resumes (case-insensitive, word-boundary).
_SECTION_KEYWORDS = [
    "experience",
    "education",
    "skills",
    "summary",
    "projects",
    "objective",
    "qualifications",
    "certifications",
    "work history",
    "employment",
    "professional experience",
    "technical skills",
    "work experience",
    "achievements",
    "internships",
    "training",
]

# Document-level resume indicators near the top of the text.
_RESUME_TITLE_RE = re.compile(
    r"\b(?:resume|curriculum\s+vitae|c\.?\s*v\.?)\b",
    re.IGNORECASE,
)


def _count_contact_signals(text: str) -> int:
    """Count how many distinct contact-info types are present."""
    signals = 0
    if _EMAIL_RE.search(text):
        signals += 1
    # Only count phone if digits look long enough to be a real number.
    phone_matches = _PHONE_RE.findall(text)
    if any(len(re.sub(r"\D", "", m)) >= 10 for m in phone_matches):
        signals += 1
    if _LINKEDIN_RE.search(text):
        signals += 1
    if _GITHUB_RE.search(text):
        signals += 1
    return signals


def _count_section_keywords(text: str) -> int:
    """Count how many standard resume section headers appear."""
    lowered = text.lower()
    hits = 0
    for keyword in _SECTION_KEYWORDS:
        # Match keyword at the start of a line or after a newline (typical header position).
        pattern = rf"(?:^|\n)\s*{re.escape(keyword)}\s*(?:\n|$|:|\s{{2,}})"
        if re.search(pattern, lowered):
            hits += 1
    return hits


def _has_resume_title(text: str, top_chars: int = 500) -> bool:
    """Check if 'Resume', 'CV', or 'Curriculum Vitae' appears near the top."""
    return bool(_RESUME_TITLE_RE.search(text[:top_chars]))


def _estimate_page_count(text: str) -> int:
    """Rough page estimate based on word count (~350 words per page)."""
    words = len(re.findall(r"\w+", text))
    return max(1, words // 350)


def fast_validate_is_resume(text: str) -> tuple[bool, str]:
    """Determine whether *text* looks like a resume.

    Returns ``(True, "")`` if the document passes, or
    ``(False, reason)`` with a human-readable rejection reason.

    The logic is intentionally forgiving: a document passes if it meets
    **any one** of the following criteria:

    1. Contains ≥ 2 contact-info signals (email, phone, LinkedIn, GitHub).
    2. Contains ≥ 2 standard resume section headers.
    3. Contains "Resume" / "Curriculum Vitae" / "CV" near the top.

    Documents shorter than ~2 pages are always accepted (they could be
    minimal resumes from fresh graduates).
    """
    if not text or not text.strip():
        return False, "Document is empty or contains no readable text."

    estimated_pages = _estimate_page_count(text)

    # Very short documents get a pass — they might be minimal student resumes.
    if estimated_pages <= 2:
        logger.debug(
            "Document validation: short document (%d estimated pages), accepting.",
            estimated_pages,
        )
        return True, ""

    contact_signals = _count_contact_signals(text)
    section_keywords = _count_section_keywords(text)
    has_title = _has_resume_title(text)

    logger.debug(
        "Document validation: pages≈%d contact_signals=%d section_keywords=%d has_title=%s",
        estimated_pages,
        contact_signals,
        section_keywords,
        has_title,
    )

    # Pass if ANY criterion is met.
    if contact_signals >= 2:
        return True, ""
    if section_keywords >= 2:
        return True, ""
    if has_title:
        return True, ""

    reason = (
        f"Document does not appear to be a resume or CV. "
        f"Found {contact_signals} contact signal(s) and {section_keywords} resume section header(s) "
        f"in an estimated {estimated_pages}-page document. "
        f"Please upload a valid resume file."
    )
    return False, reason
