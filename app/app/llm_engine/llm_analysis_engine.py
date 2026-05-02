"""LLM-based analysis engine for resume optimization.

Generation architecture:
  Structured Data
        -> Optional deterministic pre-rewriter (safe mode only)
    -> Section-wise LLM enhancement
    -> LaTeX rendering
    -> PDF / DOCX export

Rule-Based ATS layer (new):
  Scores keyword density, bullet quality, section completeness, and format
  signals deterministically before any LLM call.  The blended final score is
    0.30 × rule_composite + 0.70 × llm_score.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple, cast
import logging

from app.llm_engine.prompt_builder import PromptBuilder
from app.llm_engine.claude_client import ClaudeSonnetClient
from app.llm_engine.base_client import BaseLLMClient
from app.llm_engine.json_utils import dumps_pretty_json
from app.intelligence.context_enrichment import enrich_jd_context
from app.llm_engine.structured_resume_pipeline import (
    ResumeData,
    normalize_resume_data,
    render_plain_text_resume,
)
from app.llm_engine.latex_renderer import (
    LATEX_TEMPLATE,
    compile_latex_to_pdf,
    fill_latex_template,
    render_certifications,
    render_experience,
    render_other_block,
    render_projects,
    render_skills,
)
from app.llm_engine.resume_formatter import (
    generate_text_docx_bytes,
    generate_text_pdf_bytes,
)
def clamp01(value: float) -> float:
    """Clamp a float to [0.0, 1.0]. Inlined to avoid circular app.intelligence import."""
    return max(0.0, min(1.0, float(value)))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — action verb set is a strict superset of
# resume_validator.APPROVED_ACTION_VERBS so both modules agree.
# ---------------------------------------------------------------------------

PLACEHOLDER_SECTION_KEYS: Tuple[str, ...] = (
    "summary",
    "experience_block",
    "projects_block",
    "education_block",
    "skills_block",
    "other_block",
)

_ATS_ACTION_VERBS: Set[str] = {
    "accelerated", "achieved", "administered", "analyzed", "architected",
    "assessed", "assigned", "attained", "authored", "automated",
    "built", "championed", "coached", "collaborated", "communicated",
    "completed", "consolidated", "constructed", "contributed", "coordinated",
    "counseled", "created", "cultivated", "debugged", "decreased",
    "delegated", "delivered", "demonstrated", "deployed", "designed",
    "developed", "devised", "diagnosed", "directed", "discovered",
    "doubled", "drafted", "drove", "eliminated", "enabled",
    "engineered", "enhanced", "established", "evaluated", "examined",
    "exceeded", "executed", "expanded", "expedited", "extracted",
    "facilitated", "formulated", "founded", "generated", "grew",
    "guided", "identified", "implemented", "improved", "increased",
    "initiated", "innovated", "instituted", "instructed", "integrated",
    "introduced", "invented", "investigated", "launched", "led",
    "liaised", "maintained", "managed", "mastered", "mediated",
    "mentored", "migrated", "minimized", "monitored", "motivated",
    "negotiated", "operated", "optimized", "orchestrated", "organized",
    "originated", "overhauled", "owned", "partnered", "performed",
    "persuaded", "pioneered", "planned", "prepared", "presented",
    "prioritized", "produced", "programmed", "promoted", "proposed",
    "recruited", "reduced", "refactored", "refined", "released",
    "researched", "resolved", "restructured", "revitalized", "reviewed",
    "scaled", "scheduled", "secured", "simplified", "solved",
    "spearheaded", "standardized", "started", "streamlined", "strengthened",
    "supervised", "taught", "tested", "trained", "transformed",
    "tripled", "unified", "upgraded", "utilized", "validated",
}

_WEAK_OPENERS: Set[str] = {
    "assisted", "helped", "worked", "was responsible for", "duties included",
    "responsible for", "participated in", "involved in", "handled", "did",
    "tried", "attempted", "tasked with", "assigned to", "supported",
}

# Penalty: (compiled pattern, issue label, weight)
_FORMAT_ANTI_PATTERNS: List[Tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"[^\x00-\x7F]"),                               "non_ascii_chars",              0.05),
    (re.compile(r"\btable[s]?\b", re.I),                        "tables_mentioned",             0.15),
    (re.compile(r"(?i)(header|footer)\s+(image|graphic|logo)"), "header_footer_image",          0.20),
    (re.compile(r"\bcolumn[s]?\b.*\bcolumn[s]?\b", re.I),       "multi_column_layout",          0.20),
    (re.compile(r"\.pdf|\.docx|\.doc\b", re.I),                 "file_extension_in_text",       0.05),
    (re.compile(r"(?i)references\s+available\s+upon\s+request"),"references_filler",            0.10),
    (re.compile(r"\bobject(?:ive)?\s*:", re.I),                 "objective_instead_of_summary", 0.10),
]

_STOP_WORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "out", "off", "over", "under", "again", "then", "once", "that",
    "this", "these", "those", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "it", "they", "their", "what", "which", "who",
    "when", "where", "why", "how", "all", "both", "each", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "s", "t", "just", "now",
}

# Aligned with resume_validator metric_pattern.
_METRIC_RE = re.compile(
    r"""
    (?:
        \$[\d,]+(?:\.\d+)?[kKmMbB]?
      | \u20B9[\d,]+(?:\.\d+)?[kKlL]?
      | \d+(?:\.\d+)?[xX]\b
      | \d+(?:,\d{3})*(?:\.\d+)?%
      | \b\d{1,3}(?:,\d{3})+\b
      | \b\d+\+\b
      | \b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|
             eleven|twelve|fifteen|twenty|thirty|forty|fifty|
             hundred|thousand|million)\b
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_REQUIRED_SECTIONS: Tuple[str, ...] = ("experience", "education", "skills")
_PREFERRED_SECTIONS: Tuple[str, ...] = ("summary", "projects", "certifications")
_MIN_BULLET_WORDS = 8
_MAX_BULLET_WORDS = 40


# ---------------------------------------------------------------------------
# Rule-Based ATS Scorer
# ---------------------------------------------------------------------------

@dataclass
class ATSRuleScore:
    """All sub-scores and diagnostics from the rule-based layer."""

    keyword_score: float = 0.0
    bullet_score: float = 0.0
    section_score: float = 0.0
    format_score: float = 1.0
    composite: float = 0.0

    missing_keywords: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    weak_bullets: List[str] = field(default_factory=list)
    unquantified_bullets: List[str] = field(default_factory=list)
    format_issues: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    keyword_coverage_pct: float = 0.0


class ATSRuleScorer:
    """
    Stateless rule-based ATS scorer.

    Blend weights
    -------------
    keyword  40%  (most impactful for real ATS systems)
    bullet   30%  (verb quality + quantification + length)
    section  20%  (required / preferred presence)
    format   10%  (absence of ATS-hostile signals)
    """

    WEIGHTS: Dict[str, float] = {
        "keyword": 0.40,
        "bullet": 0.30,
        "section": 0.20,
        "format": 0.10,
    }

    @classmethod
    def score(
        cls,
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
    ) -> ATSRuleScore:
        result = ATSRuleScore()
        resume_text = cls._flatten_resume_text(resume_data)

        if jd_data:
            jd_kw = cls._extract_jd_keywords(jd_data)
            if jd_kw:
                result.keyword_score, result.matched_keywords, result.missing_keywords = (
                    cls._score_keyword_coverage(resume_text, jd_kw)
                )
                result.keyword_coverage_pct = round(
                    len(result.matched_keywords) / max(len(jd_kw), 1) * 100, 1
                )
            else:
                result.keyword_score = cls._score_skills_richness(resume_data)
                result.keyword_coverage_pct = round(result.keyword_score * 100, 1)
        else:
            result.keyword_score = cls._score_skills_richness(resume_data)
            result.keyword_coverage_pct = round(result.keyword_score * 100, 1)

        all_bullets = cls._collect_all_bullets(resume_data)
        result.bullet_score, result.weak_bullets, result.unquantified_bullets = (
            cls._score_bullet_quality(all_bullets)
        )

        result.section_score, result.missing_sections = (
            cls._score_section_completeness(resume_data)
        )
        result.format_score, result.format_issues = (
            cls._score_format_signals(resume_text)
        )

        result.composite = round(
            clamp01(
                cls.WEIGHTS["keyword"] * result.keyword_score
                + cls.WEIGHTS["bullet"] * result.bullet_score
                + cls.WEIGHTS["section"] * result.section_score
                + cls.WEIGHTS["format"] * result.format_score
            ),
            4,
        )
        return result

    # --- private helpers ---------------------------------------------------

    @staticmethod
    def _flatten_resume_text(resume_data: Dict[str, Any]) -> str:
        parts: List[str] = []

        def _add(val: Any) -> None:
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, (list, tuple)):
                for item in val:
                    _add(item)
            elif isinstance(val, dict):
                for v in val.values():
                    _add(v)

        for key in ("summary", "experience", "projects", "education",
                    "skills", "certifications", "additional_sections"):
            _add(resume_data.get(key, ""))
        return " ".join(parts).lower()

    @staticmethod
    def _stem(word: str) -> str:
        w = word.lower().strip()
        for suffix, replacement in [
            ("ization", "ize"), ("isation", "ize"), ("ations", "ate"),
            ("ation", "ate"), ("ating", "ate"), ("ated", "ate"),
            ("ities", "ity"), ("ness", ""), ("ment", ""),
            ("ings", ""), ("ically", "ic"), ("ies", "y"),
            ("ied", "y"), ("ers", ""), ("ing", ""), ("ed", ""),
            ("ly", ""), ("ful", ""), ("less", ""), ("al", ""),
            ("ous", ""), ("ive", ""), ("ize", ""), ("ise", ""),
            ("er", ""), ("est", ""), ("s", ""),
        ]:
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                w = w[: len(w) - len(suffix)] + replacement
                break
        return w

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        raw = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.]*\b", text.lower())
        return [t for t in raw if t not in _STOP_WORDS and len(t) >= 3]

    @classmethod
    def _extract_bigrams(cls, tokens: List[str]) -> Set[str]:
        return {f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)}

    @classmethod
    def _extract_jd_keywords(cls, jd_data: Dict[str, Any]) -> Set[str]:
        parts: List[str] = []
        for field_name in (
            "title", "required_skills", "preferred_skills",
            "responsibilities", "qualifications", "description",
            "keywords", "skills", "skills_required", "skills_optional",
        ):
            val = jd_data.get(field_name, "")
            if isinstance(val, list):
                parts.extend(str(v) for v in val)
            elif isinstance(val, str):
                parts.append(val)
        tokens = cls._tokenize(" ".join(parts).lower())
        return {cls._stem(t) for t in tokens} | cls._extract_bigrams(tokens)

    @classmethod
    def _score_keyword_coverage(
        cls, resume_text: str, jd_keywords: Set[str]
    ) -> Tuple[float, List[str], List[str]]:
        tokens = cls._tokenize(resume_text)
        vocab = {cls._stem(t) for t in tokens} | cls._extract_bigrams(tokens)
        matched = sorted(kw for kw in jd_keywords if kw in vocab)
        missing = sorted(kw for kw in jd_keywords if kw not in vocab)
        if not jd_keywords:
            return 1.0, [], []
        raw = len(matched) / len(jd_keywords)
        freq_bonus = min(
            sum(min(resume_text.count(kw) - 1, 2) * 0.005 for kw in matched), 0.05
        )
        return round(clamp01(raw + freq_bonus), 4), matched, missing

    @classmethod
    def _score_skills_richness(cls, resume_data: Dict[str, Any]) -> float:
        skills = resume_data.get("skills", {})
        if not isinstance(skills, dict):
            return 0.5
        count = sum(
            1 for v in cast(Dict[str, Any], skills).values()
            if isinstance(v, list)
            for s in v if str(s).strip()
        )
        return round(clamp01(0.2 + 0.7 * (1 - math.exp(-count / 12))), 4)

    @classmethod
    def _collect_all_bullets(cls, resume_data: Dict[str, Any]) -> List[str]:
        bullets: List[str] = []
        for section in ("experience", "projects"):
            for row in resume_data.get(section, []):
                if isinstance(row, dict):
                    for b in row.get("bullets", []):
                        text = str(b).strip()
                        if text:
                            bullets.append(text)
        return bullets

    @classmethod
    def _score_bullet_quality(
        cls, bullets: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        if not bullets:
            return 0.5, [], []

        verb_s: List[float] = []
        metric_s: List[float] = []
        length_s: List[float] = []
        weak: List[str] = []
        unquantified: List[str] = []

        for bullet in bullets:
            words = bullet.strip().split()
            if not words:
                continue
            first = re.sub(r"[^a-zA-Z]", "", words[0]).lower()
            is_strong = first in _ATS_ACTION_VERBS
            is_weak = any(bullet.lower().startswith(w) for w in _WEAK_OPENERS)
            verb_s.append(1.0 if is_strong else (0.3 if is_weak else 0.6))
            if not is_strong:
                weak.append(bullet[:80])

            has_metric = bool(_METRIC_RE.search(bullet))
            metric_s.append(1.0 if has_metric else 0.0)
            if not has_metric:
                unquantified.append(bullet[:80])

            wc = len(words)
            length_s.append(
                0.3 if wc < _MIN_BULLET_WORDS
                else 0.7 if wc > _MAX_BULLET_WORDS
                else 1.0
            )

        def _avg(lst: List[float]) -> float:
            return sum(lst) / len(lst) if lst else 0.5

        composite = (
            0.30 * _avg(verb_s) + 0.50 * _avg(metric_s) + 0.20 * _avg(length_s)
        )
        return round(clamp01(composite), 4), weak[:10], unquantified[:10]

    @classmethod
    def _score_section_completeness(
        cls, resume_data: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        missing: List[str] = []
        req_hit = 0
        pref_hit = 0

        def _has(key: str) -> bool:
            val = resume_data.get(key)
            if val is None:
                return False
            if isinstance(val, str):
                return bool(val.strip())
            return bool(val)

        for sec in _REQUIRED_SECTIONS:
            if _has(sec):
                req_hit += 1
            else:
                missing.append(sec)
        for sec in _PREFERRED_SECTIONS:
            if _has(sec):
                pref_hit += 1

        score = clamp01(
            0.80 * (req_hit / len(_REQUIRED_SECTIONS))
            + 0.20 * (pref_hit / len(_PREFERRED_SECTIONS))
        )
        return round(score, 4), missing

    @classmethod
    def _score_format_signals(
        cls, resume_text: str
    ) -> Tuple[float, List[str]]:
        issues: List[str] = []
        penalty = 0.0
        for pattern, label, weight in _FORMAT_ANTI_PATTERNS:
            if pattern.search(resume_text):
                issues.append(label)
                penalty += weight
        return round(clamp01(1.0 - penalty), 4), issues

    @classmethod
    def build_ats_recommendations(cls, rs: ATSRuleScore) -> List[str]:
        tips: List[str] = []
        if rs.keyword_coverage_pct < 60:
            sample = ", ".join(f'"{k}"' for k in rs.missing_keywords[:6])
            tips.append(
                f"Keyword gap ({rs.keyword_coverage_pct:.0f}% covered): "
                f"add {sample or 'key JD terms'} to skills or bullets."
            )
        elif rs.keyword_coverage_pct < 80:
            sample = ", ".join(f'"{k}"' for k in rs.missing_keywords[:4])
            tips.append(
                f"Boost keyword coverage: weave {sample or 'missing JD terms'} into bullets."
            )
        if rs.unquantified_bullets:
            tips.append(
                f"{len(rs.unquantified_bullets)} bullet(s) lack numbers. "
                "Add measurable outcomes (%, $, counts, time saved)."
            )
        if rs.weak_bullets:
            tips.append(
                f"{len(rs.weak_bullets)} bullet(s) start with weak openers. "
                "Replace with strong action verbs (Engineered, Scaled, Reduced, etc.)."
            )
        if rs.missing_sections:
            tips.append(
                f"Missing ATS-critical section(s): {', '.join(rs.missing_sections)}."
            )
        for issue in rs.format_issues:
            tips.append(
                f"Format issue detected ({issue.replace('_', ' ')}) — "
                "ATS parsers may misread this."
            )
        if not tips:
            tips.append(
                "Resume passes all rule-based ATS checks. "
                "Fine-tune further with JD-specific keywords."
            )
        return tips[:7]


# ---------------------------------------------------------------------------
# Bullet pre-rewriter
# ---------------------------------------------------------------------------

class BulletPreRewriter:
    """
    Deterministic bullet rewriter applied before any LLM call.
    Only bullet text is modified — structural fields are never touched.
    """

    # Longest patterns first so multi-word phrases match before single words.
    _WEAK_MAP: List[Tuple[str, str]] = [
        ("was responsible for", "Owned"),
        ("responsible for", "Owned"),
        ("participated in", "Contributed to"),
        ("involved in", "Contributed to"),
        ("tasked with", "Executed"),
        ("assigned to", "Led"),
        ("worked on", "Developed"),
        ("worked with", "Collaborated on"),
        ("assisted with", "Supported"),
        ("assisted", "Supported"),
        ("helped", "Enabled"),
        ("handled", "Managed"),
        ("tried to", "Pursued"),
    ]

    @classmethod
    def rewrite_resume_bullets(cls, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        output = dict(resume_data)
        for section_key in ("experience", "projects"):
            rows = output.get(section_key, [])
            if not isinstance(rows, list):
                continue
            new_rows: List[Dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    new_rows.append(row)
                    continue
                rc = dict(cast(Dict[str, Any], row))
                bullets = rc.get("bullets", [])
                if isinstance(bullets, list):
                    rc["bullets"] = [
                        cls._rewrite(str(b))
                        for b in cast(List[Any], bullets)
                        if str(b).strip()
                    ]
                new_rows.append(rc)
            output[section_key] = new_rows
        return output

    @classmethod
    def _rewrite(cls, bullet: str) -> str:
        text = bullet.strip()
        if not text:
            return text
        lower = text.lower()
        for weak, strong in cls._WEAK_MAP:
            pattern = re.compile(r"^" + re.escape(weak) + r"\b", re.IGNORECASE)
            if pattern.match(lower):
                text = pattern.sub(strong, text, count=1)
                break
        text = re.sub(
            r"\s*(?:in order to|so as to)\s+(?:ensure|provide|support|help).*$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        return text[0].upper() + text[1:] if text else text


# ---------------------------------------------------------------------------
# Helpers: parse_llm_sections, generate_pdf_bytes, generate_docx_bytes
# ---------------------------------------------------------------------------

def parse_llm_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {k: "" for k in PLACEHOLDER_SECTION_KEYS}
    current: Optional[str] = None
    header_map: Dict[str, str] = {
        "summary": "summary",
        "professional_summary": "summary",
        "professional summary": "summary",
        "experience_block": "experience_block",
        "experience block": "experience_block",
        "experience": "experience_block",
        "projects_block": "projects_block",
        "projects block": "projects_block",
        "projects": "projects_block",
        "education_block": "education_block",
        "education block": "education_block",
        "education": "education_block",
        "skills_block": "skills_block",
        "skills block": "skills_block",
        "skills": "skills_block",
        "other_block": "other_block",
        "other block": "other_block",
        "certifications_block": "other_block",
        "certifications block": "other_block",
        "certifications": "other_block",
        "other": "other_block",
    }

    def _normalize_header(candidate: str) -> str:
        cleaned = str(candidate or "").strip().strip("` ")
        cleaned = re.sub(r"^#+\s*", "", cleaned)
        cleaned = re.sub(r"\*+", "", cleaned)
        cleaned = cleaned.rstrip(":").strip().lower()
        return cleaned

    def _resolve_header(candidate: str) -> Optional[str]:
        base = _normalize_header(candidate)
        if not base:
            return None

        variants: Set[str] = {
            base,
            base.replace("-", "_"),
            base.replace("-", " "),
            re.sub(r"\s+", "_", base),
            re.sub(r"\s+", " ", base),
        }

        expanded: Set[str] = set(variants)
        for key in variants:
            if key.endswith("_section"):
                expanded.add(key[: -len("_section")])
            if key.endswith(" section"):
                expanded.add(key[: -len(" section")])

        for key in expanded:
            mapped = header_map.get(key)
            if mapped:
                return mapped
        return None

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue

        # Support inline section headers like "SUMMARY: ...".
        inline = re.match(r"^([A-Za-z][A-Za-z _\-]{2,})\s*:\s*(.*)$", line)
        if inline:
            resolved_inline = _resolve_header(inline.group(1))
            if resolved_inline:
                current = resolved_inline
                tail = inline.group(2).strip()
                if tail:
                    existing = sections[current]
                    sections[current] = f"{existing}\n{tail}".strip() if existing else tail
                continue

        resolved = _resolve_header(line)
        if resolved:
            current = resolved
            continue
        if current and line:
            existing = sections[current]
            sections[current] = f"{existing}\n{line}".strip() if existing else line
    return sections


def generate_pdf_bytes(resume: Dict[str, Any], candidate_name: str) -> bytes:
    resume_text = render_plain_text_resume(
        cast(ResumeData, resume),
        summary=str(resume.get("summary", "")),
    )
    latex_source = str(resume.get("_latex_source", "") or "")
    if latex_source:
        try:
            return compile_latex_to_pdf(latex_source)
        except (FileNotFoundError, RuntimeError) as exc:
            logger.info("LaTeX compile unavailable, falling back to text PDF: %s", exc)
    return generate_text_pdf_bytes(resume_text, candidate_name=candidate_name)


def generate_docx_bytes(resume: Dict[str, Any], candidate_name: str) -> bytes:
    resume_text = render_plain_text_resume(
        cast(ResumeData, resume),
        summary=str(resume.get("summary", "")),
    )
    return generate_text_docx_bytes(resume_text, candidate_name=candidate_name)


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------

class LLMMode(str, Enum):
    OPTIMIZE_WITH_JD = "optimize_with_jd"
    RESUME_ONLY = "resume_only"
    GENERATE = "generate"
    SCORE = "score"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class LLMAnalysisEngine:
    """Orchestrates rule-based ATS scoring and LLM-based resume generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[BaseLLMClient] = None,
    ) -> None:
        self.client: BaseLLMClient = (
            client if client is not None else ClaudeSonnetClient(api_key)
        )

    # ------------------------------------------------------------------
    # Public: standalone rule scoring
    # ------------------------------------------------------------------

    def compute_rule_ats_score(
        self,
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return full rule-based ATS breakdown without any LLM call."""
        rs = ATSRuleScorer.score(resume_data, jd_data)
        return {
            "rule_ats_score": rs.composite,
            "sub_scores": {
                "keyword_score": rs.keyword_score,
                "bullet_score": rs.bullet_score,
                "section_score": rs.section_score,
                "format_score": rs.format_score,
            },
            "keyword_coverage_pct": rs.keyword_coverage_pct,
            "matched_keywords": rs.matched_keywords,
            "missing_keywords": rs.missing_keywords,
            "weak_bullets": rs.weak_bullets,
            "unquantified_bullets": rs.unquantified_bullets,
            "format_issues": rs.format_issues,
            "missing_sections": rs.missing_sections,
            "recommendations": ATSRuleScorer.build_ats_recommendations(rs),
        }

    # ------------------------------------------------------------------
    # Public: blended scoring
    # ------------------------------------------------------------------

    def score_resume_quality(
        self,
        *,
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Blended score: 0.30 × rule_composite + 0.70 × llm_score.

        Rule diagnostics are injected into the LLM prompt so the model
        focuses on gaps already identified deterministically.
        """
        rs = ATSRuleScorer.score(resume_data, jd_data)

        enriched_ats: Dict[str, Any] = dict(ats_analysis or {})
        enriched_ats["rule_ats_score"] = rs.composite
        enriched_ats["rule_missing_keywords"] = rs.missing_keywords[:10]
        enriched_ats["rule_missing_sections"] = rs.missing_sections
        enriched_ats["rule_bullet_score"] = rs.bullet_score
        enriched_ats["rule_format_issues"] = rs.format_issues

        prompt = PromptBuilder.build_llm_scoring_prompt(
            resume_data=resume_data,
            jd_data=jd_data,
            ats_analysis=enriched_ats,
        )
        llm_raw = 60.0
        llm_reason = "Fallback applied — LLM scoring call failed."
        try:
            raw = self.client.analyze_resume(
                prompt,
                required_keys={"llm_score", "reason"},
                defaults={"llm_score": 60, "reason": llm_reason},
            )
            llm_raw = float(raw.get("llm_score", 60) or 60)
            llm_reason = str(raw.get("reason", llm_reason))
        except Exception as exc:
            logger.warning("LLM scoring failed, using fallback score: %s", exc)

        llm_norm = clamp01(llm_raw / 100.0)
        blended = clamp01(0.30 * rs.composite + 0.70 * llm_norm)

        return {
            "llm_score": round(blended, 3),
            "raw_llm_score": round(blended * 100, 2),
            "rule_ats_score": round(rs.composite, 3),
            "llm_component_score": round(llm_norm, 3),
            "blend_weights": {"rule": 0.30, "llm": 0.70},
            "rule_sub_scores": {
                "keyword_score": rs.keyword_score,
                "bullet_score": rs.bullet_score,
                "section_score": rs.section_score,
                "format_score": rs.format_score,
            },
            "keyword_coverage_pct": rs.keyword_coverage_pct,
            "missing_keywords": rs.missing_keywords[:15],
            "matched_keywords": rs.matched_keywords[:15],
            "missing_sections": rs.missing_sections,
            "format_issues": rs.format_issues,
            "reason": llm_reason,
            "ats_recommendations": ATSRuleScorer.build_ats_recommendations(rs),
        }

    # ------------------------------------------------------------------
    # Public: unified generation entrypoint
    # ------------------------------------------------------------------

    def generate(
        self,
        mode: str,
        resume_data: Optional[Dict[str, Any]] = None,
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        llm_mode = LLMMode(mode)

        if llm_mode == LLMMode.OPTIMIZE_WITH_JD:
            if resume_data is None or jd_data is None or ats_analysis is None:
                raise ValueError(
                    "resume_data, jd_data, and ats_analysis are required "
                    "for optimize_with_jd mode"
                )
            resume_data = BulletPreRewriter.rewrite_resume_bullets(resume_data)
            return self._generate_recommendations_split(
                resume_data=resume_data, jd_data=jd_data, ats_analysis=ats_analysis
            )

        if llm_mode == LLMMode.RESUME_ONLY:
            if resume_data is None:
                raise ValueError("resume_data is required for resume_only mode")
            resume_data = BulletPreRewriter.rewrite_resume_bullets(resume_data)
            return self._generate_recommendations_split(
                resume_data=resume_data, jd_data=None, ats_analysis=None
            )

        if llm_mode == LLMMode.GENERATE:
            if user_input is None:
                raise ValueError("user_input is required for generate mode")
            generated = self.generate_resume(user_input)
            rj = generated["resume_json"]
            return {
                "resume_text": generated["resume_text"],
                "latex_source": generated["latex_source"],
                "pdf_base64": generated["pdf_base64"],
                "docx_base64": generated["docx_base64"],
                "resume_json": rj,
                "summary": generated["summary"],
                "experience": rj.get("experience", []),
                "projects": rj.get("projects", []),
                "education": rj.get("education", ""),
                "skills": rj.get("skills", {}),
                "certifications": rj.get("certifications", []),
            }

        raise ValueError(f"Unsupported mode: {mode}")

    # ------------------------------------------------------------------
    # Internal: reduce payload
    # ------------------------------------------------------------------

    @staticmethod
    def _reduce_resume_payload(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        reduced: Dict[str, Any] = dict(resume_data)
        entities = reduced.get("entities")
        if isinstance(entities, dict):
            em = dict(cast(Dict[str, Any], entities))
            em["experience"] = em.get("experience", [])[:2]
            em["projects"] = em.get("projects", [])[:2]
            reduced["entities"] = em
            return reduced
        reduced["experience"] = reduced.get("experience", [])[:2]
        reduced["projects"] = reduced.get("projects", [])[:2]
        return reduced

    # ------------------------------------------------------------------
    # Internal: 3-call recommendation split
    # ------------------------------------------------------------------

    def _generate_recommendations_split(
        self,
        *,
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]],
        ats_analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        reduced = self._reduce_resume_payload(resume_data)
        rs = ATSRuleScorer.score(reduced, jd_data)

        enriched: Dict[str, Any] = dict(ats_analysis or {})
        enriched.update({
            "rule_ats_score": rs.composite,
            "missing_keywords": rs.missing_keywords[:10],
            "weak_bullets": rs.weak_bullets[:5],
            "unquantified_bullets": rs.unquantified_bullets[:5],
            "missing_sections": rs.missing_sections,
            "format_issues": rs.format_issues,
        })

        bullet_result = self.client.analyze_resume(
            PromptBuilder.build_bullet_improvements_prompt(
                resume_data=reduced, jd_data=jd_data, ats_analysis=enriched
            ),
            required_keys={"bullet_improvements"},
            defaults={"bullet_improvements": []},
            key_types={"bullet_improvements": list},
        )
        skill_result = self.client.analyze_resume(
            PromptBuilder.build_skill_suggestions_prompt(
                resume_data=reduced, jd_data=jd_data, ats_analysis=enriched
            ),
            required_keys={"skill_suggestions"},
            defaults={"skill_suggestions": []},
            key_types={"skill_suggestions": list},
        )
        gap_result = self.client.analyze_resume(
            PromptBuilder.build_gap_explanations_prompt(
                resume_data=reduced, jd_data=jd_data, ats_analysis=enriched
            ),
            required_keys={"gap_explanations"},
            defaults={"gap_explanations": []},
            key_types={"gap_explanations": list},
        )

        return {
            "bullet_improvements": cast(
                List[Any], bullet_result.get("bullet_improvements", [])
            ),
            "skill_suggestions": cast(
                List[Any], skill_result.get("skill_suggestions", [])
            ),
            "gap_explanations": cast(
                List[Any], gap_result.get("gap_explanations", [])
            ),
            "rule_ats_diagnostics": {
                "composite": rs.composite,
                "missing_keywords": rs.missing_keywords,
                "weak_bullets": rs.weak_bullets,
                "unquantified_bullets": rs.unquantified_bullets,
                "recommendations": ATSRuleScorer.build_ats_recommendations(rs),
            },
        }

    # ------------------------------------------------------------------
    # Sanitisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_metric_placeholders(text: str) -> str:
        cleaned = str(text or "")
        cleaned = re.sub(r"\bby\s*\[\s*[xX]\s*\]\s*%", "", cleaned)
        cleaned = re.sub(r"\[\s*[xX]\s*\]\s*%", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
        return cleaned

    def _sanitize_resume_placeholders(
        self, resume_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        output = dict(resume_json)

        def _fix_tail(text: str) -> str:
            raw = str(text or "").strip()
            if not raw:
                return raw
            end_punct = ""
            while raw and raw[-1] in ".!?":
                end_punct = raw[-1] + end_punct
                raw = raw[:-1].rstrip()
            parts = [p for p in raw.split() if p]
            if len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
                while len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
                    parts.pop()
            if len(parts) >= 4:
                if [parts[-2].lower(), parts[-1].lower()] == [
                    parts[-4].lower(), parts[-3].lower()
                ]:
                    parts = parts[:-2]
            cleaned = " ".join(parts).strip()
            return (cleaned + end_punct).strip() if cleaned else cleaned

        for section_key in ("experience", "projects"):
            rows_any = output.get(section_key, [])
            if not isinstance(rows_any, list):
                continue
            sanitized: List[Dict[str, Any]] = []
            for row in cast(List[Any], rows_any):
                if not isinstance(row, dict):
                    continue
                rc = dict(cast(Dict[str, Any], row))
                bullets = rc.get("bullets", [])
                if isinstance(bullets, list):
                    rc["bullets"] = [
                        _fix_tail(self._sanitize_metric_placeholders(str(b)))
                        for b in cast(List[Any], bullets)
                        if str(b).strip()
                    ]
                sanitized.append(rc)
            output[section_key] = sanitized
        return output

    # ------------------------------------------------------------------
    # Public wrappers kept for backward-compatibility
    # ------------------------------------------------------------------

    def generate_recommendations(
        self,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
        ats_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("Generating LLM recommendations for resume analysis")
        return self.generate(
            mode=LLMMode.OPTIMIZE_WITH_JD.value,
            resume_data=resume_data,
            jd_data=jd_data,
            ats_analysis=ats_analysis,
        )

    def generate_resume_only_improvements(
        self, resume_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("Generating resume-only improvements")
        return self.generate(mode=LLMMode.RESUME_ONLY.value, resume_data=resume_data)

    def generate_resume_text(self, user_input: Dict[str, Any]) -> str:
        resume_data = normalize_resume_data(user_input)
        suppress = self._is_recent_undergraduate_low_experience(resume_data)
        if suppress:
            resume_data = cast(ResumeData, {**resume_data, "summary": ""})
        sections = self._default_sections_from_resume_data(
            resume_data, suppress_summary=suppress
        )
        if suppress:
            sections["summary"] = ""
        return self._compose_resume_text(sections, resume_data)

    # ------------------------------------------------------------------
    # Deterministic section builder
    # ------------------------------------------------------------------

    @staticmethod
    def _default_sections_from_resume_data(
        resume_data: ResumeData,
        *,
        suppress_summary: bool = False,
    ) -> Dict[str, str]:
        summary = (
            "" if suppress_summary else str(resume_data.get("summary", "")).strip()
        )

        exp_lines: List[str] = []
        for exp in resume_data.get("experience", []):
            header = " | ".join(
                p for p in [
                    str(exp.get("title", "")).strip(),
                    str(exp.get("company", "")).strip(),
                    str(exp.get("duration", "")).strip(),
                ]
                if p
            )
            if header:
                exp_lines.append(header)
            exp_lines.extend(
                f"- {str(b).strip()}"
                for b in exp.get("bullets", [])
                if str(b).strip()
            )

        proj_lines: List[str] = []
        for proj in resume_data.get("projects", []):
            name = str(proj.get("name", "")).strip()
            techs = ", ".join(
                str(t).strip()
                for t in proj.get("technologies", [])
                if str(t).strip()
            )
            if name:
                proj_lines.append(f"{name} | {techs}" if techs else name)
            proj_lines.extend(
                f"- {str(b).strip()}"
                for b in proj.get("bullets", [])
                if str(b).strip()
            )

        skill_lines: List[str] = []
        for category, values in cast(
            Dict[str, Any], resume_data.get("skills", {})
        ).items():
            if not isinstance(values, list):
                continue
            cleaned = [str(v).strip() for v in cast(List[Any], values) if str(v).strip()]
            if cleaned:
                skill_lines.append(
                    f"{category.replace('_', ' ').title()}: {', '.join(cleaned)}"
                )

        certs = [
            str(c).strip()
            for c in resume_data.get("certifications", [])
            if str(c).strip()
        ]
        other_lines: List[str] = []
        if certs:
            other_lines.append(f"Certifications: {', '.join(certs)}")
        for section in resume_data.get("additional_sections", []):
            title = str(section.get("title", "Additional Information")).strip().upper()
            body = str(section.get("body", "")).strip()
            bullets = [
                str(i).strip()
                for i in section.get("bullets", [])
                if str(i).strip()
            ]
            other_lines.append(title)
            if body:
                other_lines.append(body)
            other_lines.extend(f"- {i}" for i in bullets)

        fallback: Dict[str, str] = {
            "summary": summary,
            "experience_block": "\n".join(exp_lines).strip(),
            "projects_block": "\n".join(proj_lines).strip(),
            "education_block": str(resume_data.get("education", "")).strip(),
            "skills_block": "\n".join(skill_lines).strip(),
            "other_block": "\n".join(other_lines).strip(),
        }
        fallback["experience_block"] = LLMAnalysisEngine._dedupe_block_bullets(
            fallback["experience_block"]
        )
        fallback["projects_block"] = LLMAnalysisEngine._dedupe_block_bullets(
            fallback["projects_block"]
        )
        return fallback

    @staticmethod
    def _sanitize_section_text(section_text: str) -> str:
        cleaned = str(section_text or "")
        cleaned = re.sub(r"\bby\s*\[\s*[xX]\s*\]\s*%", "", cleaned)
        cleaned = re.sub(r"\[\s*[xX]\s*\]\s*%", "", cleaned)
        cleaned = re.sub(r"\[\s*[xX]\s*\]", "", cleaned)
        _SKIP: Set[str] = {
            "no projects currently listed.",
            "no projects currently listed",
            "education details available",
            "additional achievements available upon request",
            "core skills: problem solving, collaboration",
        }
        filtered: List[str] = [
            ln.strip()
            for ln in cleaned.splitlines()
            if ln.strip() and ln.strip().lower() not in _SKIP
        ]
        return "\n".join(filtered).strip()

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    @classmethod
    def _is_recent_undergraduate_low_experience(
        cls, resume_data: ResumeData
    ) -> bool:
        edu = str(resume_data.get("education", "") or "").strip().lower()
        if not edu:
            return False
        ug = ("b.tech", "btech", "b.e", "be ", "be,", "be)", "be-",
              "bachelor", "undergraduate", "b.sc", "bca")
        pg = ("m.tech", "mtech", "master", "mba", "phd", "doctorate")
        if not any(m in edu for m in ug):
            return False
        if any(m in edu for m in pg):
            return False
        current_year = datetime.now().year
        edu_years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", edu)]
        if not (
            "present" in edu
            or "current" in edu
            or any(y >= current_year - 2 for y in edu_years)
        ):
            return False
        exp_rows = [
            r for r in resume_data.get("experience", [])
            if str(r.get("title", "") or "").strip()
            or str(r.get("company", "") or "").strip()
        ]
        if len(exp_rows) <= 2:
            return True
        total = 0.0
        for row in exp_rows:
            dur = str(row.get("duration", "") or "").lower()
            years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", dur)]
            if not years:
                continue
            end = current_year if "present" in dur else max(years)
            start = min(years)
            if end >= start:
                total += float(end - start + 1)
        return total <= 2.5

    @classmethod
    def _extract_bullets_from_block(cls, block_text: str) -> List[str]:
        return [
            re.sub(r"^[-•*]\s*", "", ln.strip()).strip()
            for ln in str(block_text or "").splitlines()
            if ln.strip().startswith(("-", "•", "*"))
            and re.sub(r"^[-•*]\s*", "", ln.strip()).strip()
        ]

    @classmethod
    def _has_repeated_bullets(cls, block_text: str) -> bool:
        bullets = cls._extract_bullets_from_block(block_text)
        if not bullets:
            return False
        normalized = [cls._normalize_for_match(b) for b in bullets]
        return len(normalized) != len(set(normalized))

    @staticmethod
    def _stable_seed(text: str) -> int:
        return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)

    @classmethod
    def _context_anchor(cls, context_line: str, section: str) -> str:
        raw = str(context_line or "").strip()
        if not raw:
            return (
                "business objectives" if section == "experience" else "product outcomes"
            )
        # Strip "Technologies: ..." suffix from project/experience headers
        # to avoid appending full tech stacks to every bullet.
        cleaned = re.sub(
            r"\s*Technologies\s*:.*$", "", raw, flags=re.IGNORECASE
        ).strip(" |,-")
        if not cleaned:
            cleaned = raw
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        if section == "experience" and parts:
            company = parts[0]
            title = parts[1] if len(parts) >= 2 else ""
            return f"{title} at {company}" if (title and company) else (title or company)
        return parts[0] if (section == "projects" and parts) else cleaned

    @classmethod
    def _metric_clause_for_text(cls, text: str, *, section: str, seed: int) -> str:
        lower = text.lower()
        if re.search(
            r"latency|response|turnaround|cycle|processing|delivery|resolution|time",
            lower,
        ):
            return f"reducing turnaround time by {10 + (seed % 21)}%"
        if re.search(r"cost|budget|spend|expense|resource", lower):
            return f"reducing operating cost by {8 + (seed % 18)}%"
        if re.search(r"accuracy|quality|error|defect|compliance|reliability", lower):
            return f"improving quality metrics by {9 + (seed % 20)}%"
        if re.search(
            r"user|customer|client|adoption|engagement|retention|satisfaction", lower
        ):
            return f"increasing adoption by {12 + (seed % 24)}%"
        if section == "projects" and re.search(
            r"platform|system|application|dashboard|portal|pipeline|automation", lower
        ):
            return f"accelerating feature delivery by {11 + (seed % 19)}%"
        return f"improving core KPI attainment by {10 + (seed % 23)}%"

    @classmethod
    def _enhance_bullets_deterministically(
        cls,
        bullets: List[str],
        *,
        context_line: str = "",
        section: str = "generic",
        start_index: int = 0,
    ) -> List[str]:
        output: List[str] = []
        seen: Set[str] = set()
        verbs = [
            "Engineered", "Optimized", "Implemented", "Orchestrated",
            "Spearheaded", "Delivered", "Scaled", "Streamlined",
        ]
        anchor = cls._context_anchor(context_line, section)

        _strip_sfx = re.compile(
            r"(?:,\s*strengthening measurable business outcomes\.?)"
            r"|(?:,\s*resulting in measurable improvement of \d+%\.?)"
            r"|(?:,\s*(?:reducing|improving|increasing|accelerating)[^,]*\d+%\.?)",
            re.IGNORECASE,
        )
        _strip_verb = re.compile(
            r"^(?:engineer(?:ed|ing)?|optimiz(?:e|ed|ing)|implement(?:ed|ing)?|"
            r"orchestrate(?:d|ing)?|spearhead(?:ed|ing)?|deliver(?:ed|ing)?|"
            r"scale(?:d|ing)?|streamline(?:d|ing)?|develop(?:ed|ing)?|"
            r"build(?:t|ing)?|create(?:d|ing)?|design(?:ed|ing)?|manage(?:d|ing)?|"
            r"lead(?:s|ing)?|analy(?:ze|zed|sing)|improv(?:e|ed|ing)|"
            r"coordinate(?:d|ing)?|execute(?:d|ing)?|architect(?:ed|ing)?|"
            r"establish(?:ed|ing)?|integrat(?:e|ed|ing)|direct(?:ed|ing)?|"
            r"facilitat(?:e|ed|ing)|support(?:ed|ing)?|launch(?:ed|ing)?|"
            r"automate(?:d|ing)?)\b\s*",
            re.IGNORECASE,
        )

        for index, raw in enumerate(bullets, start=start_index):
            text = str(raw).strip()
            if not text:
                continue
            text = _strip_sfx.sub("", text).strip(" .")
            normalized = cls._normalize_for_match(text)
            if normalized in seen:
                continue
            seen.add(normalized)

            seed = cls._stable_seed(f"{section}|{anchor}|{normalized}|{index}")
            verb = verbs[seed % len(verbs)]

            core = _strip_verb.sub("", text).strip(" .")
            core = re.sub(r"^(?:to\s+)?(?:a|an|the)\s+", "", core, flags=re.IGNORECASE)
            if core:
                core = core[0].lower() + core[1:] if len(core) > 1 else core.lower()
            else:
                core = "cross-functional initiatives"

            if verb.lower().startswith("scale") and core.lower().startswith("scal"):
                verb = "Implemented"
            elif verb.lower().startswith("deliver") and core.lower().startswith(
                ("author", "write")
            ):
                verb = "Produced"
            elif verb.lower().startswith("spearhead") and core.lower().startswith(
                ("build", "develop")
            ):
                verb = "Engineered"

            body = f"{verb} {core}"
            # Only append context anchor to the first bullet of each entry
            # to avoid repetitive suffixes on every line.
            if (
                anchor
                and index == start_index
                and cls._normalize_for_match(anchor) not in cls._normalize_for_match(body)
            ):
                body = f"{body} for {anchor}"

            text = (
                f"{body}."
                if _METRIC_RE.search(body)
                else f"{body}, {cls._metric_clause_for_text(body, section=section, seed=seed)}."
            )
            output.append(text)
        return output

    @classmethod
    def _normalize_block_quality(
        cls, block_text: str, *, section: str = "generic"
    ) -> str:
        lines = [ln.strip() for ln in str(block_text or "").splitlines() if ln.strip()]
        if not lines:
            return ""

        entries: List[Tuple[str, List[str]]] = []
        cur_hdr = ""
        cur_bul: List[str] = []
        for line in lines:
            if line.startswith(("-", "•", "*")):
                b = re.sub(r"^[-•*]\s*", "", line).strip()
                if b:
                    cur_bul.append(b)
            else:
                if cur_hdr or cur_bul:
                    entries.append((cur_hdr, cur_bul))
                cur_hdr, cur_bul = line, []
        if cur_hdr or cur_bul:
            entries.append((cur_hdr, cur_bul))

        out: List[str] = []
        seen_g: Set[str] = set()
        running = 0
        for header, bullets in entries:
            if header:
                out.append(header)
            if not bullets:
                continue
            enhanced = cls._enhance_bullets_deterministically(
                bullets, context_line=header, section=section, start_index=running
            )
            running += len(bullets)
            for idx, text in enumerate(enhanced, start=1):
                key = cls._normalize_for_match(text)
                if key in seen_g:
                    anchor = cls._context_anchor(header, section)
                    text = (
                        f"{text.rstrip('.')} driving "
                        f"{idx + len(seen_g)} tracked outcomes for {anchor}."
                    )
                    key = cls._normalize_for_match(text)
                seen_g.add(key)
                out.append(f"- {text}")
        return "\n".join(out).strip()

    @classmethod
    def _experience_block_complete(
        cls, block_text: str, resume_data: ResumeData
    ) -> bool:
        nb = cls._normalize_for_match(block_text)
        for row in resume_data.get("experience", []):
            company = cls._normalize_for_match(str(row.get("company", "")))
            title = cls._normalize_for_match(str(row.get("title", "")))
            if company and company not in nb:
                return False
            if not company and title and title not in nb:
                return False
        return True

    @classmethod
    def _projects_block_complete(
        cls, block_text: str, resume_data: ResumeData
    ) -> bool:
        nb = cls._normalize_for_match(block_text)
        for row in resume_data.get("projects", []):
            name = cls._normalize_for_match(str(row.get("name", "")))
            if name and name not in nb:
                return False
        return True

    @classmethod
    def _text_has_term(cls, corpus: str, term: str) -> bool:
        term_norm = re.sub(r"\s+", " ", str(term or "").strip().lower())
        if not term_norm:
            return False
        # Exact match first
        pattern = r"\b" + re.escape(term_norm).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, str(corpus or ""), flags=re.IGNORECASE):
            return True
        # Stemmed match: check each word in term against stemmed corpus words
        corpus_lower = str(corpus or "").lower()
        corpus_tokens = set(re.findall(r"\b[a-z][a-z0-9+#.]*\b", corpus_lower))
        corpus_stems = {ATSRuleScorer._stem(t) for t in corpus_tokens}
        term_words = [w for w in term_norm.split() if len(w) >= 3]
        if not term_words:
            return False
        matched = sum(1 for w in term_words if ATSRuleScorer._stem(w) in corpus_stems)
        return matched >= max(1, len(term_words) * 0.6)

    @classmethod
    def _jd_coverage_gaps(
        cls,
        sections: Dict[str, str],
        jd_context: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        def _collect_points(*keys: str) -> List[str]:
            items: List[str] = []
            seen: Set[str] = set()
            for key in keys:
                raw = jd_context.get(key, [])
                if isinstance(raw, (str, bytes, bytearray)):
                    candidates = [str(raw)]
                elif isinstance(raw, list):
                    candidates = [str(v) for v in cast(List[Any], raw)]
                else:
                    candidates = [str(raw)] if raw else []
                for candidate in candidates:
                    text = str(candidate).strip()
                    if not text:
                        continue
                    token = cls._normalize_for_match(text)
                    if token in seen:
                        continue
                    seen.add(token)
                    items.append(text)
            return items

        required_skills = [
            item
            for item in _collect_points(
                "skills_required",
                "required_skills",
                "must_have_skills",
            )
        ]
        if not required_skills:
            required_skills = _collect_points("skills")

        responsibilities = [
            item
            for item in _collect_points(
                "responsibilities",
                "job_responsibilities",
                "key_responsibilities",
                "requirements",
            )
        ]

        corpus = cls._normalize_for_match(
            "\n".join(
                [
                    sections.get("experience_block", ""),
                    sections.get("projects_block", ""),
                    sections.get("skills_block", ""),
                    sections.get("summary", ""),
                ]
            )
        )

        missing_required = [
            skill for skill in required_skills if not cls._text_has_term(corpus, skill)
        ]
        missing_responsibilities = [
            resp for resp in responsibilities if not cls._text_has_term(corpus, resp)
        ]

        return {
            "missing_required_skills": missing_required,
            "missing_responsibilities": missing_responsibilities,
        }

    @staticmethod
    def _is_date_only_metadata_line(text: str) -> bool:
        line = str(text or "").strip()
        if not line:
            return False

        date_range_pattern = re.compile(
            r"^(?:(?:[A-Za-z]{3,9}\s+)?(?:0?[1-9]|[12]\d|3[01])?\s*(?:,)?\s*)?"
            r"(?:(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})"
            r"\s*[-–]\s*"
            r"(?:present|current|(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})$",
            re.IGNORECASE,
        )
        if date_range_pattern.match(line):
            return True

        short_date_pattern = re.compile(
            r"^(?:present|current|(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})$",
            re.IGNORECASE,
        )
        return bool(short_date_pattern.match(line))

    @classmethod
    def _merge_entry_metadata_line(cls, header: str, line: str) -> str:
        base = str(header or "").strip()
        addon = str(line or "").strip()
        if not base:
            return addon
        if not addon:
            return base

        base_norm = cls._normalize_for_match(base)
        addon_norm = cls._normalize_for_match(addon)
        if addon_norm and addon_norm in base_norm:
            return base

        separator = " | " if cls._is_date_only_metadata_line(addon) else " - "
        return f"{base}{separator}{addon}"

    @staticmethod
    def _parse_entry_blocks(block_text: str) -> List[Tuple[str, List[str]]]:
        lines = [ln.strip() for ln in str(block_text or "").splitlines() if ln.strip()]
        entries: List[Tuple[str, List[str]]] = []
        cur_hdr = ""
        cur_bul: List[str] = []
        for line in lines:
            if line.startswith(("-", "•", "*")):
                b = re.sub(r"^[-•*]\s*", "", line).strip()
                if b:
                    cur_bul.append(b)
            else:
                if cur_hdr and not cur_bul:
                    cur_hdr = LLMAnalysisEngine._merge_entry_metadata_line(cur_hdr, line)
                    continue
                if cur_hdr or cur_bul:
                    entries.append((cur_hdr, cur_bul))
                cur_hdr, cur_bul = line, []
        if cur_hdr or cur_bul:
            entries.append((cur_hdr, cur_bul))
        return entries

    @classmethod
    def _dedupe_block_bullets(cls, block_text: str) -> str:
        entries = cls._parse_entry_blocks(block_text)
        if not entries:
            return str(block_text or "").strip()
        out: List[str] = []
        for header, bullets in entries:
            if header:
                out.append(header)
            seen_l: Set[str] = set()
            for bullet in bullets:
                cleaned = cls._sanitize_section_text(str(bullet or "")).strip()
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
                if not cleaned:
                    continue
                key = cls._normalize_for_match(cleaned)
                if not key or key in seen_l:
                    continue
                seen_l.add(key)
                out.append(f"- {cleaned}")
        return "\n".join(out).strip()

    @classmethod
    def _sync_structured_resume_with_sections(
        cls, resume_data: ResumeData, sections: Dict[str, str]
    ) -> ResumeData:
        synced: Dict[str, Any] = dict(resume_data)

        # Sync experience bullets; structural fields locked by enforce_structure_integrity.
        exp_entries = cls._parse_entry_blocks(sections.get("experience_block", ""))
        synced_exp: List[Dict[str, Any]] = [dict(e) for e in resume_data.get("experience", [])]
        for idx, entry in enumerate(synced_exp):
            if idx < len(exp_entries):
                parsed_bullets = exp_entries[idx][1]
                if parsed_bullets:
                    entry["bullets"] = parsed_bullets
        synced["experience"] = synced_exp

        proj_entries = cls._parse_entry_blocks(sections.get("projects_block", ""))
        synced_proj: List[Dict[str, Any]] = [dict(p) for p in resume_data.get("projects", [])]
        for idx, entry in enumerate(synced_proj):
            if idx < len(proj_entries):
                parsed_bullets = proj_entries[idx][1]
                if parsed_bullets:
                    entry["bullets"] = parsed_bullets
        synced["projects"] = synced_proj

        _ALIAS: Dict[str, str] = {
            "programming languages": "programming_languages",
            "languages": "programming_languages",
            "technical skills": "programming_languages",
            "tools": "tools", "frameworks": "tools", "platforms": "tools",
            "data science": "data_science", "machine learning": "data_science",
            "data visualization": "data_visualization",
            "visualization": "data_visualization",
            "databases": "databases", "database": "databases",
        }
        parsed_skills: Dict[str, List[str]] = {
            k: [] for k in (
                "programming_languages", "tools", "data_science",
                "data_visualization", "databases"
            )
        }
        for raw_line in str(sections.get("skills_block", "") or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ":" in line:
                label, raw_vals = line.split(":", 1)
                canonical = _ALIAS.get(label.strip().lower())
                vals = [v.strip() for v in raw_vals.split(",") if v.strip()]
                if canonical and vals:
                    parsed_skills[canonical].extend(vals)
                    continue
                if vals:
                    parsed_skills["tools"].extend(vals)
                    continue
            parsed_skills["tools"].extend(
                v.strip() for v in re.split(r",|\|", line) if v.strip()
            )

        existing = dict(cast(Dict[str, Any], resume_data.get("skills", {})))
        for key in parsed_skills:
            deduped: List[str] = []
            seen: Set[str] = set()
            for val in parsed_skills[key]:
                nv = cls._normalize_for_match(val)
                if nv and nv not in seen:
                    seen.add(nv)
                    deduped.append(val)
            parsed_skills[key] = deduped or [
                str(v).strip() for v in existing.get(key, []) if str(v).strip()
            ]
        synced["skills"] = parsed_skills

        edu = str(sections.get("education_block", "") or "").strip()
        if edu:
            synced["education"] = edu
        smry = str(sections.get("summary", "") or "").strip()
        if smry:
            synced["summary"] = smry

        cert_lines = [
            re.sub(r"^[-•*]\s*", "", line).strip()
            for line in str(sections.get("other_block", "") or "").splitlines()
            if re.sub(r"^[-•*]\s*", "", line).strip()
        ]
        parsed_certs: List[str] = []
        for line in cert_lines:
            low = cls._normalize_for_match(line)
            if low in {
                "certifications",
                "other",
                "additional information",
                "n/a",
                "none",
            }:
                continue
            parsed_certs.append(line)
        if parsed_certs:
            deduped_certs: List[str] = []
            seen_certs: Set[str] = set()
            for cert in parsed_certs:
                key = cls._normalize_for_match(cert)
                if key and key not in seen_certs:
                    seen_certs.add(key)
                    deduped_certs.append(cert)
            if deduped_certs:
                synced["certifications"] = deduped_certs[:5]

        return cast(ResumeData, synced)

    @staticmethod
    def _compose_resume_text(
        sections: Dict[str, str], resume_data: ResumeData
    ) -> str:
        lines: List[str] = [str(resume_data.get("name", "Candidate"))]
        contact = resume_data.get("contact", {})
        contact_parts = [
            str(contact.get("email", "")).strip(),
            str(contact.get("phone", "")).strip(),
            str(contact.get("linkedin", "")).strip(),
            str(contact.get("github", "")).strip(),
            str(contact.get("location", "")).strip(),
        ]
        rendered = " | ".join(p for p in contact_parts if p)
        if rendered:
            lines.extend([rendered, ""])

        # Keep section flow aligned with generation requirements.
        section_order: List[Tuple[str, str]] = [
            ("EXPERIENCE", "experience_block"),
            ("PROJECTS", "projects_block"),
            ("SKILLS", "skills_block"),
            ("EDUCATION", "education_block"),
            ("CERTIFICATIONS", "other_block"),
        ]
        for title, key in section_order:
            block = str(sections.get(key, "")).strip()
            if block:
                lines.extend([title, block, ""])

        summary_block = str(sections.get("summary", "")).strip()
        if summary_block:
            lines.extend(["PROFESSIONAL SUMMARY", summary_block, ""])
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # Main generation pipeline
    # ------------------------------------------------------------------

    def generate_resume(
        self,
        user_input: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fixed-template generation pipeline.

        1. Normalize → ResumeData
        2. Optional pre-rewrite weak bullets (safe_fix mode only)
        3. Build deterministic fallback sections
        4. LLM placeholder prompt (generate_text path)
        5. Validate retention (companies, project names)
        6. Optional correction pass if retention failed
        7. Hard guardrails (override if still broken)
        8. Sync structured data with finalized sections
        9. LaTeX → PDF + DOCX
        """
        logger.info("Generating resume with fixed-template placeholder pipeline")

        rewrite_mode = str(user_input.get("rewrite_mode", "ats_rewrite") or "").strip().lower()
        safe_fix_mode = rewrite_mode in {"safe_fix", "safe", "edit", "edit_mode"}

        structured_resume = normalize_resume_data(user_input)
        if safe_fix_mode:
            structured_resume = cast(
                ResumeData,
                BulletPreRewriter.rewrite_resume_bullets(dict(structured_resume)),
            )

        force_omit = bool(user_input.get("_omit_summary", False))
        suppress_summary = force_omit or self._is_recent_undergraduate_low_experience(
            structured_resume
        )
        if suppress_summary:
            structured_resume = cast(ResumeData, {**structured_resume, "summary": ""})

        fallback_sections = self._default_sections_from_resume_data(
            structured_resume, suppress_summary=suppress_summary
        )

        prompt_input: Dict[str, Any] = dict(user_input)
        if isinstance(jd_data, dict) and jd_data:
            jd_generation_context = dict(jd_data)
            jd_generation_context.update(enrich_jd_context(jd_data))
            prompt_input["jd_context"] = jd_generation_context
            if not str(prompt_input.get("target_role", "")).strip():
                target_hint = str(jd_data.get("job_title") or jd_data.get("target_role") or "").strip()
                if target_hint:
                    prompt_input["target_role"] = target_hint

        llm_output = ""
        prompt = PromptBuilder.build_placeholder_prompt(prompt_input)
        text_generator = getattr(self.client, "generate_text", None)
        if callable(text_generator):
            try:
                llm_output = str(text_generator(prompt) or "")
            except Exception as exc:
                logger.warning(
                    "Placeholder generation failed, using deterministic fallback: %s",
                    exc,
                )
        else:
            logger.info(
                "Client has no generate_text; attempting analyze_resume fallback"
            )

        if not llm_output.strip():
            analyze_fn = getattr(self.client, "analyze_resume", None)
            if callable(analyze_fn):
                try:
                    candidate = analyze_fn(prompt)
                    if isinstance(candidate, dict) and candidate:
                        merged: Dict[str, Any] = {
                            **prompt_input, **cast(Dict[str, Any], candidate)
                        }
                        structured_resume = normalize_resume_data(merged)
                        if suppress_summary:
                            structured_resume = cast(
                                ResumeData, {**structured_resume, "summary": ""}
                            )
                        fallback_sections = self._default_sections_from_resume_data(
                            structured_resume, suppress_summary=suppress_summary
                        )
                except Exception as exc:
                    logger.warning(
                        "Structured analyze_resume fallback failed: %s", exc
                    )

        sections = (
            parse_llm_sections(llm_output)
            if llm_output.strip()
            else {k: "" for k in PLACEHOLDER_SECTION_KEYS}
        )
        for key in PLACEHOLDER_SECTION_KEYS:
            sections[key] = self._sanitize_section_text(sections.get(key, ""))
            if not sections[key]:
                sections[key] = fallback_sections.get(key, "")

        has_source_experience = bool(structured_resume.get("experience", []))
        needs_exp_fix = has_source_experience and (
            not self._experience_block_complete(
                sections.get("experience_block", ""), structured_resume
            )
            or self._has_repeated_bullets(sections.get("experience_block", ""))
        )
        needs_proj_fix = (
            not self._projects_block_complete(
                sections.get("projects_block", ""), structured_resume
            )
            or self._has_repeated_bullets(sections.get("projects_block", ""))
        )
        jd_context_for_coverage = prompt_input.get("jd_context", {})
        jd_coverage_gaps: Dict[str, List[str]] = {
            "missing_required_skills": [],
            "missing_responsibilities": [],
        }
        if isinstance(jd_context_for_coverage, dict) and jd_context_for_coverage:
            jd_coverage_gaps = self._jd_coverage_gaps(
                sections=sections,
                jd_context=cast(Dict[str, Any], jd_context_for_coverage),
            )
        needs_jd_fix = bool(
            jd_coverage_gaps.get("missing_required_skills")
            or jd_coverage_gaps.get("missing_responsibilities")
        )

        if (needs_exp_fix or needs_proj_fix or needs_jd_fix) and callable(text_generator):
            issues: List[str] = []
            if needs_exp_fix:
                issues.append(
                    "EXPERIENCE_BLOCK missing entries/company names "
                    "OR repeated/non-quantified bullets"
                )
            if needs_proj_fix:
                issues.append(
                    "PROJECTS_BLOCK missing project names "
                    "OR repeated/non-quantified bullets"
                )
            if needs_jd_fix:
                missing_required = jd_coverage_gaps.get("missing_required_skills", [])
                missing_resp = jd_coverage_gaps.get("missing_responsibilities", [])
                if missing_required:
                    issues.append(
                        "Missing JD required skills coverage in generated resume: "
                        + ", ".join(missing_required)
                    )
                if missing_resp:
                    issues.append(
                        "Missing JD responsibilities coverage in generated bullets: "
                        + ", ".join(missing_resp)
                    )
            try:
                corrected = str(
                    text_generator(
                        PromptBuilder.build_placeholder_retry_prompt(
                            user_input=prompt_input,
                            previous_output=llm_output,
                            issues=issues,
                        )
                    )
                    or ""
                )
                corr = (
                    parse_llm_sections(corrected)
                    if corrected.strip()
                    else {k: "" for k in PLACEHOLDER_SECTION_KEYS}
                )
                for key in PLACEHOLDER_SECTION_KEYS:
                    corr[key] = self._sanitize_section_text(corr.get(key, ""))
                    if not corr[key]:
                        corr[key] = fallback_sections.get(key, "")
                # Do NOT apply _normalize_block_quality — it destroys JD-aligned bullets
                # by replacing action verbs and appending generic metrics.
                # Only deduplicate to preserve JD-specific wording from the LLM retry.
                corr["experience_block"] = self._dedupe_block_bullets(
                    corr.get("experience_block", "")
                )
                corr["projects_block"] = self._dedupe_block_bullets(
                    corr.get("projects_block", "")
                )
                if self._experience_block_complete(
                    corr.get("experience_block", ""), structured_resume
                ) and not self._has_repeated_bullets(corr.get("experience_block", "")):
                    sections["experience_block"] = self._dedupe_block_bullets(
                        corr["experience_block"]
                    )
                if self._projects_block_complete(
                    corr.get("projects_block", ""), structured_resume
                ) and not self._has_repeated_bullets(corr.get("projects_block", "")):
                    sections["projects_block"] = self._dedupe_block_bullets(
                        corr["projects_block"]
                    )
                for key in ("summary", "education_block", "skills_block", "other_block"):
                    if corr.get(key, "").strip():
                        sections[key] = corr[key]
            except Exception as exc:
                logger.warning("Placeholder correction pass failed: %s", exc)

        # Hard guardrails.
        if has_source_experience:
            if not self._experience_block_complete(
                sections.get("experience_block", ""), structured_resume
            ):
                logger.warning(
                    "LLM experience block dropped entries; using deterministic fallback"
                )
                sections["experience_block"] = fallback_sections["experience_block"]

            sections["experience_block"] = (
                self._dedupe_block_bullets(sections.get("experience_block", ""))
                or fallback_sections["experience_block"]
            )
        else:
            # Never fabricate experience content when source resume has no experience.
            sections["experience_block"] = ""

        if not self._projects_block_complete(
            sections.get("projects_block", ""), structured_resume
        ):
            logger.warning(
                "LLM projects block dropped entries; using deterministic fallback"
            )
            sections["projects_block"] = fallback_sections["projects_block"]

        if isinstance(jd_context_for_coverage, dict) and jd_context_for_coverage:
            final_jd_gaps = self._jd_coverage_gaps(
                sections=sections,
                jd_context=cast(Dict[str, Any], jd_context_for_coverage),
            )
            llm_missing_count = len(
                final_jd_gaps.get("missing_required_skills", [])
            ) + len(final_jd_gaps.get("missing_responsibilities", []))

            if llm_missing_count > 0:
                # Check if deterministic fallback actually has better JD coverage
                # before blindly replacing. If both miss skills, keep LLM output.
                fallback_jd_gaps = self._jd_coverage_gaps(
                    sections=fallback_sections,
                    jd_context=cast(Dict[str, Any], jd_context_for_coverage),
                )
                fallback_missing_count = len(
                    fallback_jd_gaps.get("missing_required_skills", [])
                ) + len(fallback_jd_gaps.get("missing_responsibilities", []))

                if fallback_missing_count < llm_missing_count and (llm_missing_count - fallback_missing_count) >= 2:
                    logger.warning(
                        "Generated blocks miss JD coverage (%d gaps vs %d in fallback); "
                        "using deterministic blocks with better coverage",
                        llm_missing_count,
                        fallback_missing_count,
                    )
                    sections["experience_block"] = fallback_sections["experience_block"]
                    sections["projects_block"] = fallback_sections["projects_block"]
                else:
                    logger.info(
                        "Generated blocks miss %d JD items but fallback misses %d; "
                        "keeping LLM output (equal or better coverage)",
                        llm_missing_count,
                        fallback_missing_count,
                    )

        sections["projects_block"] = (
            self._dedupe_block_bullets(sections.get("projects_block", ""))
            or fallback_sections["projects_block"]
        )

        if has_source_experience and not sections.get("experience_block", "").strip():
            sections["experience_block"] = fallback_sections["experience_block"]

        sections["summary"] = (
            ""
            if suppress_summary
            else sections.get("summary", "").strip() or fallback_sections["summary"]
        )
        sections["skills_block"] = (
            sections.get("skills_block", "").strip() or fallback_sections["skills_block"]
        )
        sections["education_block"] = (
            sections.get("education_block", "").strip()
            or fallback_sections["education_block"]
        )

        structured_resume = self._sync_structured_resume_with_sections(
            structured_resume, sections
        )
        resume_json: Dict[str, Any] = self._sanitize_resume_placeholders(
            dict(structured_resume)
        )
        structured_resume = cast(ResumeData, resume_json)

        # LaTeX render — uses typed renderers from latex_renderer.py.
        latex_sections = dict(sections)
        loc = str(structured_resume.get("contact", {}).get("location", ""))
        latex_sections["experience_block"] = render_experience(
            structured_resume.get("experience", []), location=loc
        )
        latex_sections["projects_block"] = render_projects(
            structured_resume.get("projects", []), location=loc
        )
        latex_sections["skills_block"] = render_skills(
            structured_resume.get("skills", {})
        )
        latex_sections["certifications_block"] = render_certifications(
            structured_resume.get("certifications", [])
        )
        latex_sections["other_block"] = render_other_block(structured_resume)
        if suppress_summary:
            latex_sections["summary"] = ""
            sections["summary"] = ""

        latex_source = fill_latex_template(
            LATEX_TEMPLATE,
            sections=latex_sections,
            resume_data=cast(Dict[str, Any], structured_resume),
        )

        resume_text = self._compose_resume_text(sections, structured_resume)
        resume_json["_latex_source"] = latex_source

        name = str(structured_resume.get("name", "Candidate"))
        pdf_bytes = generate_pdf_bytes(resume=resume_json, candidate_name=name)
        docx_bytes = generate_docx_bytes(resume=resume_json, candidate_name=name)
        resume_json.pop("_latex_source", None)

        return {
            "resume_text": resume_text,
            "latex_source": latex_source,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "docx_base64": base64.b64encode(docx_bytes).decode("utf-8"),
            "resume_json": resume_json,
            "resume_data": structured_resume,
            "summary": sections["summary"],
        }

    # ------------------------------------------------------------------
    # Refinement + quick tips
    # ------------------------------------------------------------------

    def refine_recommendation(
        self,
        original_recommendation: Dict[str, Any],
        feedback: str,
    ) -> Dict[str, Any]:
        logger.info("Refining recommendations based on feedback: %s", feedback)
        prompt = (
            "You are an expert ATS Resume Analyzer. A user has provided feedback on "
            "resume recommendations and you need to refine them.\n\n"
            f"ORIGINAL RECOMMENDATIONS:\n{dumps_pretty_json(original_recommendation)}\n\n"
            f"USER FEEDBACK:\n{feedback}\n\n"
            "Provide REFINED recommendations in the same JSON format. "
            "Respond ONLY with valid JSON."
        )
        return self.client.analyze_resume(prompt)

    def get_quick_tips(self, ats_analysis: Dict[str, Any]) -> List[str]:
        score = ats_analysis.get("ats_score", 0)
        components = ats_analysis.get("components", {})
        tips: List[str] = []

        if components.get("skill_score", 1) < 0.7:
            tips.append(
                "Add 3-5 missing keywords from the job description to the skills section"
            )
        if components.get("experience_score", 1) < 0.7:
            tips.append("Enhance 2-3 bullets with quantifiable outcomes and metrics")
        if components.get("impact_score", 1) < 0.7:
            tips.append(
                "Lead each bullet with strong action verbs "
                "(Developed, Increased, Reduced, etc.)"
            )
        if components.get("format_score", 1) < 0.7:
            tips.append("Ensure consistent formatting: one context + metric per bullet")
        if score < 0.6:
            tips.append(
                "Priority: Resume may not pass ATS screening. "
                "Focus on skill keywords first."
            )
        elif score < 0.75:
            tips.append(
                "Next step: Implement suggestions to push ATS score above 80%"
            )

        resume_snapshot = ats_analysis.get("resume_data")
        jd_snapshot = ats_analysis.get("jd_data")
        if isinstance(resume_snapshot, dict):
            for rt in self.compute_rule_ats_score(
                resume_snapshot, jd_snapshot
            ).get("recommendations", []):
                if rt not in tips:
                    tips.append(rt)

        return tips[:7] if tips else [
            "Resume is in good shape. Fine-tune with JD-specific keywords."
        ]