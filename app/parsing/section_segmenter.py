"""Production-grade section segmenter for layout-aware resume parsing.

Implements 9-point robust segmentation:
1. Spaced-heading normalization (word-boundary aware)
2. Score-based multi-signal header detection
3. Fuzzy section alias matching with guardrails
4. Buffer-flush section boundary enforcement
5. Reading-order reconstruction helpers
6. Block-level content-pattern fallback recovery
7. Section collapse prevention
8. Per-section confidence scoring
9. LayoutLMv3 prediction integration with heuristic override
"""

from __future__ import annotations

import logging
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .pdf_extractor import TokenLine

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
#  Section alias dictionary (50+ variants)
# ─────────────────────────────────────────────────────────────────────
SECTION_ALIASES: Dict[str, List[str]] = {
    "contact": [
        "contact", "contact information", "personal details", "personal information",
        "contact details",
    ],
    "summary": [
        "summary", "profile", "professional summary", "career objective",
        "objective", "about", "about me", "career summary", "executive summary",
        "professional profile", "overview",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies",
        "tools", "key skills", "technical proficiencies", "core skills",
        "tools and technologies", "technical expertise", "technology stack",
        "tech stack", "areas of expertise", "competencies", "proficiencies",
        "programming languages", "languages and tools",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "career history", "internship experience",
        "internships", "internship", "work history", "relevant experience",
        "prior experience", "career experience", "employment", "positions held",
        "professional background", "industry experience",
    ],
    "projects": [
        "projects", "personal projects", "academic projects", "key projects",
        "project experience", "selected projects", "project work",
        "projects and research", "side projects", "open source projects",
        "notable projects",
    ],
    "education": [
        "education", "academic background", "qualifications",
        "educational background", "academic qualifications",
        "academic credentials", "degrees",
    ],
    "certifications": [
        "certifications", "certificates", "licenses",
        "licenses and certifications", "professional certifications",
        "credentials", "courses", "training", "professional development",
    ],
    "achievements": [
        "achievements", "awards", "honors", "recognitions",
        "awards and honors", "accomplishments",
    ],
    "publications": [
        "publications", "research", "papers", "research publications",
    ],
    "leadership": [
        "leadership", "leadership experience", "activities",
        "extracurricular", "extracurricular activities", "volunteer",
        "volunteering", "community involvement",
    ],
    "languages": [
        "languages", "language skills",
    ],
    "interests": [
        "interests", "hobbies", "hobbies and interests",
    ],
    "references": [
        "references",
    ],
}

# Heading suffix tokens allowed after an alias for prefix matching
_HEADING_SUFFIX_TOKENS = frozenset({
    "and", "section", "details", "summary", "highlights",
    "overview", "history", "background", "information",
    "experience", "skills", "projects", "certifications",
    "achievements", "publications", "leadership",
    "&",
})

# Content-pattern constants for fallback recovery
_DATE_RANGE_RE = re.compile(
    r"\b(?:"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{2,4}"
    r"|\d{1,2}/\d{2,4}"
    r"|(?:19|20)\d{2}"
    r")\s*(?:-|–|—|to)\s*(?:"
    r"present|current"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{2,4}"
    r"|\d{1,2}/\d{2,4}"
    r"|(?:19|20)\d{2}"
    r")\b",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*[•●▪▸\-\*](?:\s|\u200b)*")
_CERT_KW = re.compile(
    r"\b(?:certif(?:ied|ication|icate)|license[ds]?|credential|accreditation|"
    r"course(?:ra|work)?|training|aws\s+certified|google\s+cloud|azure\s+certified|"
    r"pmp|scrum\s+master|cisco)\b",
    re.I,
)
_DEGREE_KW = re.compile(
    r"\b(?:bachelor|master|ph\.?d|b\.?tech|m\.?tech|mba|bsc|msc|diploma|"
    r"associate|b\.?e\.?|m\.?e\.?|b\.?s\.?|m\.?s\.?|postgraduate|doctorate|"
    r"university|institute|college|school|academy)\b",
    re.I,
)
_EXP_ACTION_VERBS = re.compile(
    r"\b(?:led|built|developed|designed|managed|implemented|delivered|"
    r"optimized|created|deployed|engineered|architected|mentored|"
    r"spearheaded|collaborated|maintained|reduced|increased|improved)\b",
    re.I,
)
_SENTENCE_ENDING = re.compile(r"[.!?]\s*$")
_VERB_FIRST = re.compile(
    r"^(?:experience|skills?|education|projects?)\s+(?:with|in|at|on|for|using|as)\b",
    re.I,
)
_DECORATIVE_EDGE_RE = re.compile(r"^[\s\-_=~*#|\[\](){}<>•●▪▸·:]+|[\s\-_=~*#|\[\](){}<>•●▪▸·:]+$")

# ─────────────────────────────────────────────────────────────────────
#  1. Spaced-Heading Normalization
# ─────────────────────────────────────────────────────────────────────

def normalize_spaced_heading(text: str) -> str:
    """Collapse stylized spaced headings while preserving word boundaries.

    Examples:
        "P R O J E C T S"                                → "PROJECTS"
        "P R O F E S S I O N A L   E X P E R I E N C E"  → "PROFESSIONAL EXPERIENCE"
        "Built REST APIs"                                 → "Built REST APIs"  (untouched)
    """
    tokens = text.strip().split()
    if len(tokens) < 3:
        return text

    # Only collapse if >70% of tokens are single characters
    single_char_ratio = sum(1 for t in tokens if len(t) == 1) / len(tokens)
    if single_char_ratio < 0.7:
        return text

    # Preserve word boundaries: multi-space gaps indicate word breaks
    # Split on 2+ consecutive spaces in the original text
    words = re.split(r"\s{2,}", text.strip())
    collapsed_words: list[str] = []
    for word in words:
        chars = word.split()
        if all(len(c) == 1 for c in chars) and len(chars) > 1:
            collapsed_words.append("".join(chars))
        else:
            collapsed_words.append(word)

    result = " ".join(collapsed_words)

    # Edge case: if no multi-space gaps existed (single spaced-out word)
    # and all original tokens were single chars, just join everything
    if len(collapsed_words) == 1 and collapsed_words[0] == text.strip():
        # The split didn't find multi-space gaps -> treat as one word
        chars = text.strip().split()
        if all(len(c) == 1 for c in chars):
            return "".join(chars)

    return result


# ─────────────────────────────────────────────────────────────────────
#  2. Normalize & clean heading text
# ─────────────────────────────────────────────────────────────────────

def _normalize_heading_text(text: str) -> str:
    """Strip numbering, colons, special chars; lowercase; collapse whitespace."""
    t = text.lower().strip()
    t = re.sub(r"^\d+[.)\-]\s*", "", t)      # leading "1." or "1)"
    t = t.strip(":")
    t = re.sub(r"[^a-z0-9\s&]", "", t)       # keep alphanumeric + &
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _clean_heading_candidate(text: str) -> str:
    """Normalize stylized heading wrappers before alias/shape checks."""
    candidate = normalize_spaced_heading(text.strip())
    candidate = candidate.replace("\u2013", "-").replace("\u2014", "-")
    candidate = _DECORATIVE_EDGE_RE.sub("", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    return candidate


# ─────────────────────────────────────────────────────────────────────
#  3. Fuzzy Section Matching (with guardrails)
# ─────────────────────────────────────────────────────────────────────

def match_section_alias(raw_text: str) -> Optional[str]:
    """Return canonical section name if *raw_text* matches a known heading.

    Matching hierarchy (first hit wins):
      1. Exact match after normalization
      2. Prefix match with allowed suffix words
      3. Containment match (guarded: ≤4 words, no sentences, no bullets)
    """
    normalized = _normalize_heading_text(_clean_heading_candidate(raw_text))
    if not normalized:
        return None

    word_count = len(normalized.split())

    # ── exact match ──────────────────────────────────────────────
    for canonical, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if normalized == _normalize_heading_text(alias):
                return canonical

    # ── prefix match ─────────────────────────────────────────────
    for canonical, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            alias_norm = _normalize_heading_text(alias)
            if normalized.startswith(alias_norm + " "):
                remainder = normalized[len(alias_norm):].strip()
                suffix_tokens = remainder.split()
                if (
                    len(suffix_tokens) <= 2
                    and all(t in _HEADING_SUFFIX_TOKENS for t in suffix_tokens)
                ):
                    return canonical

    # ── guarded containment match ────────────────────────────────
    #    Only if: ≤5 words, not a sentence, and alias is multi-word.
    #    Single-word containment is too permissive and causes false positives,
    #    e.g., "Educational Trust" -> "education" or "Research Project" -> "research".
    if word_count <= 5 and not _is_sentence_like(raw_text):
        for canonical, aliases in SECTION_ALIASES.items():
            for alias in aliases:
                alias_norm = _normalize_heading_text(alias)
                if len(alias_norm.split()) < 2:
                    continue
                boundary_pattern = re.compile(
                    r"\\b" + re.escape(alias_norm).replace(r"\\ ", r"\\s+") + r"\\b"
                )
                if boundary_pattern.search(normalized):
                    return canonical

    return None


def _is_sentence_like(text: str) -> bool:
    """Returns True if *text* looks like a sentence or label-line rather than a heading."""
    stripped = text.strip()
    if _SENTENCE_ENDING.search(stripped):
        return True
    if _VERB_FIRST.match(stripped):
        return True
    if _BULLET_RE.match(stripped):
        return True
    # Label lines like "Languages: Python, JavaScript, SQL" are NOT headings
    if ":" in stripped:
        parts = stripped.split(":", 1)
        if len(parts) == 2 and len(parts[1].strip()) > 5:
            return True
    return False


def _is_date_like_line(text: str) -> bool:
    """Return True when a line is primarily a date/date-range marker."""
    stripped = text.strip()
    if not stripped:
        return False
    if _DATE_RANGE_RE.search(stripped):
        return True
    return bool(re.fullmatch(r"(?:19|20)\d{2}", stripped))


def _is_side_annotation_line(text: str) -> bool:
    """Right-side metadata like dates/locations that should not form a separate column."""
    stripped = text.strip()
    if not stripped:
        return False
    if _is_date_like_line(stripped):
        return True
    words = stripped.split()
    has_digit = any(ch.isdigit() for ch in stripped)
    return has_digit and len(words) <= 5


# ─────────────────────────────────────────────────────────────────────
#  4. Score-based header detection
# ─────────────────────────────────────────────────────────────────────

@dataclass
class _HeadingSignal:
    """Collected signals for a single candidate heading line."""
    alias_match: Optional[str] = None       # canonical section name or None
    alias_score: int = 0                    # +3 if alias matched
    font_score: int = 0                     # +2 if font > 1.15× body median
    bold_score: int = 0                     # +2 if bold
    caps_score: int = 0                     # +1 if ALL CAPS
    spacing_score: int = 0                  # +1 if large gap above

    @property
    def total(self) -> int:
        return (
            self.alias_score
            + self.font_score
            + self.bold_score
            + self.caps_score
            + self.spacing_score
        )

    @property
    def is_heading(self) -> bool:
        word_limit = 6
        return self.total >= 3


def _compute_heading_signal(
    line: TokenLine,
    prev_line: Optional[TokenLine],
    body_font_median: float,
    avg_line_gap: float,
) -> _HeadingSignal:
    """Compute heading score for a single line using multi-signal logic."""
    sig = _HeadingSignal()
    raw_text = line.text.strip()
    if not raw_text:
        return sig

    # ── Step A: normalize spaced headings FIRST ──────────────────
    # Must happen before word-count check because "E X P E R I E N C E"
    # has 10 raw words but normalizes to "EXPERIENCE" (1 word)
    normalized_text = _clean_heading_candidate(raw_text)
    norm_words = normalized_text.split()
    norm_word_count = len(norm_words)

    # Hard reject: too many words to be a heading (use NORMALIZED word count)
    if norm_word_count > 6:
        return sig

    # ── Step B: alias matching ───────────────────────────────────
    matched = match_section_alias(normalized_text)
    if matched:
        sig.alias_match = matched
        sig.alias_score = 3

    # ── Step C: font size signal ─────────────────────────────────
    if body_font_median > 0 and line.font_size > body_font_median * 1.15:
        sig.font_score = 2

    # ── Step D: bold signal ──────────────────────────────────────
    if line.is_bold:
        sig.bold_score = 2

    # ── Step E: ALL CAPS signal (check on normalized text) ───────
    alpha_chars = [c for c in normalized_text if c.isalpha()]
    if alpha_chars and all(c.isupper() for c in alpha_chars) and norm_word_count <= 6:
        sig.caps_score = 1

    # ── Step F: vertical spacing signal ──────────────────────────
    if prev_line and avg_line_gap > 0 and line.page == prev_line.page:
        gap = line.bbox[1] - prev_line.bbox[3]
        if gap > avg_line_gap * 1.5:
            sig.spacing_score = 1

    return sig


# ─────────────────────────────────────────────────────────────────────
#  5. Reading-order reconstruction
# ─────────────────────────────────────────────────────────────────────

def sort_reading_order(lines: List[TokenLine], page_width: float = 612.0) -> List[TokenLine]:
    """Sort token lines into reading order for multi-column resumes.

    Algorithm:
        1. Group lines by page
        2. For each page, detect column clusters via x0 histogram
        3. Sort each cluster by y0 (top-to-bottom)
        4. Concatenate: leftmost cluster first, then right
    """
    if not lines:
        return lines

    # Group by page
    by_page: Dict[int, List[TokenLine]] = defaultdict(list)
    for ln in lines:
        by_page[ln.page].append(ln)

    result: List[TokenLine] = []
    for page_num in sorted(by_page.keys()):
        page_lines = by_page[page_num]
        if len(page_lines) < 4:
            result.extend(sorted(page_lines, key=lambda l: l.bbox[1]))
            continue

        # Collect left-edge x0 values
        x0_values = [ln.bbox[0] for ln in page_lines]
        x0_min = min(x0_values)
        x0_max = max(x0_values)
        x_range = x0_max - x0_min

        # If the x-spread is < 40% of page width -> single column
        if x_range < page_width * 0.35:
            result.extend(sorted(page_lines, key=lambda l: l.bbox[1]))
            continue

        # Multi-column: split at the midpoint gap
        midpoint = x0_min + x_range * 0.45
        left_col = [ln for ln in page_lines if ln.bbox[0] < midpoint]
        right_col = [ln for ln in page_lines if ln.bbox[0] >= midpoint]

        # Guard against false multi-column detection caused by centered headings.
        right_ratio = len(right_col) / max(len(page_lines), 1)
        min_right_lines = max(3, int(len(page_lines) * 0.14))
        if len(right_col) < min_right_lines or right_ratio < 0.14:
            result.extend(sorted(page_lines, key=lambda l: l.bbox[1]))
            continue

        # Guard against side-date annotations on the right edge of a single-column resume.
        side_annotation_ratio = (
            sum(1 for ln in right_col if _is_side_annotation_line(ln.text))
            / max(len(right_col), 1)
        )
        if side_annotation_ratio >= 0.5:
            result.extend(sorted(page_lines, key=lambda l: l.bbox[1]))
            continue

        left_col.sort(key=lambda l: l.bbox[1])
        right_col.sort(key=lambda l: l.bbox[1])

        result.extend(left_col)
        result.extend(right_col)

    return result


# ─────────────────────────────────────────────────────────────────────
#  6. Block-level content-pattern fallback recovery
# ─────────────────────────────────────────────────────────────────────

@dataclass
class _ContentBlock:
    """A group of consecutive lines belonging to one logical block."""
    lines: List[TokenLine] = field(default_factory=list)
    start_idx: int = 0

    @property
    def text_lines(self) -> List[str]:
        return [ln.text.strip() for ln in self.lines if ln.text.strip()]

    @property
    def bullet_count(self) -> int:
        return sum(1 for t in self.text_lines if _BULLET_RE.match(t))

    @property
    def bullet_density(self) -> float:
        total = len(self.text_lines)
        if total == 0:
            return 0.0
        return self.bullet_count / total

    @property
    def has_date_range(self) -> bool:
        return any(_DATE_RANGE_RE.search(t) for t in self.text_lines)

    def full_text(self) -> str:
        return "\n".join(self.text_lines)


def _split_into_blocks(lines: List[TokenLine], gap_multiplier: float = 1.8) -> List[_ContentBlock]:
    """Split lines into blocks using Y-gap analysis."""
    if not lines:
        return []

    # Compute average gap
    gaps: list[float] = []
    for i in range(1, len(lines)):
        if lines[i].page == lines[i - 1].page:
            g = lines[i].bbox[1] - lines[i - 1].bbox[3]
            if g > 0:
                gaps.append(g)
    avg_gap = statistics.median(gaps) if gaps else 12.0
    threshold = avg_gap * gap_multiplier

    blocks: list[_ContentBlock] = []
    current = _ContentBlock(start_idx=0)

    for i, line in enumerate(lines):
        if i > 0 and line.page == lines[i - 1].page:
            g = line.bbox[1] - lines[i - 1].bbox[3]
            if g > threshold and current.lines:
                blocks.append(current)
                current = _ContentBlock(start_idx=i)
        current.lines.append(line)

    if current.lines:
        blocks.append(current)

    return blocks


def _detect_experience_block(block: _ContentBlock) -> bool:
    """True if block has structure consistent with an experience entry."""
    if len(block.text_lines) < 3:
        return False
    if not block.has_date_range:
        return False
    if block.bullet_count < 1:
        return False
    return block.bullet_density >= 0.3


def _detect_project_block(block: _ContentBlock) -> bool:
    """True if block looks like a project entry."""
    if len(block.text_lines) < 2:
        return False
    ft = block.full_text()
    has_tech = bool(re.search(
        r"\b(?:python|java|react|node|docker|kubernetes|aws|api|database|"
        r"tensorflow|pytorch|flask|django|fastapi|streamlit|sql)\b",
        ft, re.I,
    ))
    has_action = bool(_EXP_ACTION_VERBS.search(ft))
    # Must NOT look like employment (no date-range-to-present pattern)
    has_employment_dates = bool(re.search(
        r"\b(?:19|20)\d{2}\s*(?:-|–|to)\s*(?:present|current|(?:19|20)\d{2})\b",
        ft, re.I,
    ))
    if has_employment_dates:
        return False  # More likely experience
    return has_tech and has_action and block.bullet_density >= 0.3


def _detect_cert_block(block: _ContentBlock) -> bool:
    """True if block has certification keywords and list-like structure."""
    ft = block.full_text()
    if not _CERT_KW.search(ft):
        return False
    # Should be short / list-like
    return len(block.text_lines) <= 10


def _detect_education_block(block: _ContentBlock) -> bool:
    """True if block contains degree/institution keywords."""
    ft = block.full_text()
    return bool(_DEGREE_KW.search(ft)) and len(block.text_lines) <= 10


def _recover_sections_from_bloated(
    lines: List[TokenLine],
) -> Dict[str, List[TokenLine]]:
    """Analyse a bloated section (usually summary) and try to split it
    into correctly classified sub-sections using content patterns."""
    blocks = _split_into_blocks(lines, gap_multiplier=1.5)
    recovered: Dict[str, List[TokenLine]] = defaultdict(list)
    unclassified: List[TokenLine] = []

    for block in blocks:
        if _detect_experience_block(block):
            recovered["experience"].extend(block.lines)
        elif _detect_cert_block(block):
            recovered["certifications"].extend(block.lines)
        elif _detect_education_block(block):
            recovered["education"].extend(block.lines)
        elif _detect_project_block(block):
            recovered["projects"].extend(block.lines)
        else:
            unclassified.extend(block.lines)

    if unclassified:
        recovered["summary"] = unclassified

    return dict(recovered)


# ─────────────────────────────────────────────────────────────────────
#  7. Confidence scoring
# ─────────────────────────────────────────────────────────────────────

def compute_section_confidence(
    sections: Dict[str, List[TokenLine]],
    heading_scores: Dict[str, int],
    model_agreed: Dict[str, bool],
) -> Dict[str, float]:
    """Compute per-section confidence based on detection method and content."""
    confidences: Dict[str, float] = {}

    for name, lines in sections.items():
        conf = 0.0

        # Heading detection strength
        h_score = heading_scores.get(name, 0)
        if h_score >= 5:
            conf += 0.40
        elif h_score >= 3:
            conf += 0.25
        elif h_score > 0:
            conf += 0.10

        # Content pattern match
        ft = "\n".join(ln.text for ln in lines)
        if name == "experience" and _DATE_RANGE_RE.search(ft) and _BULLET_RE.search(ft):
            conf += 0.30
        elif name == "skills" and len(lines) >= 2:
            conf += 0.25
        elif name == "education" and _DEGREE_KW.search(ft):
            conf += 0.30
        elif name == "certifications" and _CERT_KW.search(ft):
            conf += 0.30
        elif name == "projects" and _EXP_ACTION_VERBS.search(ft):
            conf += 0.25
        elif name == "summary":
            conf += 0.20

        # Structure check (bullets for experience)
        if name in ("experience", "projects"):
            n_bullets = sum(1 for ln in lines if _BULLET_RE.match(ln.text))
            if n_bullets >= 2:
                conf += 0.20

        # Model agreement
        if model_agreed.get(name, False):
            conf += 0.10

        confidences[name] = round(min(conf, 1.0), 2)

    return confidences


# ─────────────────────────────────────────────────────────────────────
#  MAIN SEGMENTER CLASS
# ─────────────────────────────────────────────────────────────────────

class SectionSegmenter:
    """Groups TokenLines into a dictionary of canonical sections.

    Uses score-based multi-signal heading detection, spaced-heading
    normalization, fuzzy alias matching, block-level fallback recovery,
    and collapse prevention.
    """

    def segment(
        self,
        lines: List[TokenLine],
        predictions: Optional[List[str]] = None,
        page_width: float = 612.0,
    ) -> Tuple[Dict[str, List[TokenLine]], Dict[str, float]]:
        """Segment *lines* into canonical sections.

        Returns:
            (sections_dict, confidence_dict)
        """
        if not lines:
            return {}, {}

        # ── A. Sort into reading order (handles multi-column) ────
        lines = sort_reading_order(lines, page_width=page_width)

        # ── B. Compute layout statistics ─────────────────────────
        body_font_median = self._body_font_median(lines)
        avg_gap = self._avg_line_gap(lines)

        # ── C. Build prediction lookup (LayoutLMv3) ──────────────
        pred_sections = self._resolve_predictions(lines, predictions)

        # ── D. Main heading-detection pass ────────────────────────
        sections: Dict[str, List[TokenLine]] = defaultdict(list)
        heading_scores: Dict[str, int] = {}
        model_agreed: Dict[str, bool] = {}
        current_section = "summary"

        for i, line in enumerate(lines):
            text = line.text.strip()
            if not text:
                continue

            prev_line = lines[i - 1] if i > 0 else None

            # 1) Compute heading signal
            sig = _compute_heading_signal(line, prev_line, body_font_median, avg_gap)

            # 2) Check LayoutLMv3 prediction for this line
            pred_section = pred_sections.get(i)

            # 3) Resolve: heuristic wins when confident, model assists when uncertain
            detected: Optional[str] = None
            final_score = sig.total

            if sig.is_heading and sig.alias_match:
                detected = sig.alias_match

                # Check model agreement
                if pred_section and pred_section == detected:
                    model_agreed[detected] = True
                    final_score += 1  # bonus for agreement

            elif pred_section and not sig.is_heading:
                # Model says header but heuristic is unsure
                # Only accept if model section differs from current
                # and the text is short (likely a heading)
                heading_candidate = _clean_heading_candidate(text)
                if (
                    pred_section != current_section
                    and len(heading_candidate.split()) <= 5
                    and not _is_sentence_like(heading_candidate)
                    and not _BULLET_RE.match(heading_candidate)
                    and not _is_date_like_line(heading_candidate)
                ):
                    detected = pred_section
                    final_score = 2  # lower confidence

            # 4) Section switch with buffer flush
            if detected and detected != current_section:
                current_section = detected
                heading_scores[current_section] = max(
                    heading_scores.get(current_section, 0), final_score
                )
                # Heading line itself is NOT added to section body
                continue

            # 5) Append line to current section
            sections[current_section].append(line)

        sections = dict(sections)

        # ── E. Collapse prevention: oversized summary ────────────
        sections, heading_scores = self._prevent_collapse(
            sections, heading_scores
        )

        # ── F. Fallback recovery for missing critical sections ───
        sections, heading_scores = self._fallback_recovery(
            sections, heading_scores
        )

        # ── G. Compute confidence ────────────────────────────────
        confidences = compute_section_confidence(
            sections, heading_scores, model_agreed
        )

        return sections, confidences

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _body_font_median(lines: List[TokenLine]) -> float:
        """Median font size of all non-empty lines (approximates body text)."""
        sizes = [ln.font_size for ln in lines if ln.text.strip()]
        if not sizes:
            return 10.0
        return statistics.median(sizes)

    @staticmethod
    def _avg_line_gap(lines: List[TokenLine]) -> float:
        """Median Y gap between consecutive same-page lines."""
        gaps: list[float] = []
        for i in range(1, len(lines)):
            if lines[i].page == lines[i - 1].page:
                g = lines[i].bbox[1] - lines[i - 1].bbox[3]
                if g > 0:
                    gaps.append(g)
        return statistics.median(gaps) if gaps else 8.0

    @staticmethod
    def _resolve_predictions(
        lines: List[TokenLine],
        predictions: Optional[List[str]],
    ) -> Dict[int, str]:
        """Map LayoutLMv3 word-level predictions to line-level canonical labels."""
        if not predictions:
            return {}

        result: Dict[int, str] = {}
        pred_idx = 0
        for line_idx, line in enumerate(lines):
            n_tokens = len(line.tokens)
            if n_tokens == 0:
                continue
            line_preds = predictions[pred_idx: pred_idx + n_tokens]
            pred_idx += n_tokens

            # Majority vote for line label
            valid = [p for p in line_preds if p != "O"]
            if not valid:
                continue
            majority = max(set(valid), key=valid.count)
            # Canonicalize: strip B-/I- prefix, lowercase
            canon = majority
            if canon.startswith("B-") or canon.startswith("I-"):
                canon = canon[2:]
            canon = canon.lower()
            result[line_idx] = canon

        return result

    # ── collapse prevention ──────────────────────────────────────

    @staticmethod
    def _prevent_collapse(
        sections: Dict[str, List[TokenLine]],
        heading_scores: Dict[str, int],
    ) -> Tuple[Dict[str, List[TokenLine]], Dict[str, int]]:
        """If SUMMARY is oversized and contains mixed patterns, split it."""
        summary_lines = sections.get("summary", [])
        if len(summary_lines) <= 25:
            return sections, heading_scores

        # Check if summary contains date ranges (likely merged experience)
        full = "\n".join(ln.text for ln in summary_lines)
        has_dates = bool(_DATE_RANGE_RE.search(full))
        has_bullets = bool(_BULLET_RE.search(full))

        if not (has_dates or has_bullets):
            return sections, heading_scores

        logger.info(
            "Summary has %d lines with date/bullet patterns — running collapse recovery",
            len(summary_lines),
        )
        recovered = _recover_sections_from_bloated(summary_lines)

        for sec_name, sec_lines in recovered.items():
            if sec_name == "summary":
                sections["summary"] = sec_lines
            elif sec_name not in sections or not sections[sec_name]:
                sections[sec_name] = sec_lines
                heading_scores.setdefault(sec_name, 1)
            else:
                # Merge into existing
                sections[sec_name].extend(sec_lines)

        return sections, heading_scores

    # ── fallback recovery ────────────────────────────────────────

    @staticmethod
    def _fallback_recovery(
        sections: Dict[str, List[TokenLine]],
        heading_scores: Dict[str, int],
    ) -> Tuple[Dict[str, List[TokenLine]], Dict[str, int]]:
        """If critical sections are still missing, scan large sections
        for recoverable blocks."""
        critical_missing = []
        for needed in ("experience", "education"):
            if needed not in sections or not sections[needed]:
                critical_missing.append(needed)

        if not critical_missing:
            return sections, heading_scores

        # Find the largest section to scan
        largest_name = max(sections, key=lambda k: len(sections[k]))
        largest_lines = sections[largest_name]

        if len(largest_lines) < 5:
            return sections, heading_scores

        logger.info(
            "Missing critical sections %s — scanning '%s' (%d lines)",
            critical_missing, largest_name, len(largest_lines),
        )

        recovered = _recover_sections_from_bloated(largest_lines)

        for sec_name, sec_lines in recovered.items():
            if sec_name in critical_missing and sec_lines:
                sections[sec_name] = sec_lines
                heading_scores.setdefault(sec_name, 1)
                critical_missing.remove(sec_name)

        # Update the scanned section to keep only unclassified content
        if "summary" in recovered and largest_name != "summary":
            sections[largest_name] = recovered.get("summary", [])
        elif largest_name == "summary" and "summary" in recovered:
            sections["summary"] = recovered["summary"]

        return sections, heading_scores
