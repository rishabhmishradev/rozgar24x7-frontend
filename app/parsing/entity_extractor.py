"""Heuristic entity extraction for parsed resume sections."""

from __future__ import annotations

import importlib
import logging
import re
from collections import Counter
from typing import Any

from .experience_parser import ExperienceParser
from .pdf_extractor import Token, TokenLine
from .structured_utils import (
    clean_text_line,
    extract_validated_links,
    normalize_certification_entry,
    normalize_experience_entries,
    normalize_skill_key,
    parse_certification_lines,
    parse_project_section_lines,
    parse_skill_mentions,
    skill_display_label,
    summarize_total_experience,
)


logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3})?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    r"|(?:\+?\d{1,3}[\s-]?)?[6-9]\d{4}[\s.-]?\d{5}"
)
URL_RE = re.compile(r"https?://[^\s]+")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
DATE_RANGE_RE = re.compile(
    r"\b(?P<start>19\d{2}|20\d{2})\s*(?:-|to|–|—)\s*(?P<end>present|current|19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)
MONTH_RANGE_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|july?|aug|sep|sept|oct|nov|dec)[a-z]*\s*\d{2,4}\s*(?:-|to|–|—)\s*(?:present|current|(?:jan|feb|mar|apr|may|jun|july?|aug|sep|sept|oct|nov|dec)[a-z]*\s*\d{2,4})\b",
    re.IGNORECASE,
)

SKILL_GRAPH: dict[str, dict[str, list[str]]] = {
    "machine learning": {
        "related": ["feature engineering", "model tuning"],
        "tools": ["scikit-learn", "xgboost"],
    },
    "deep learning": {
        "related": ["cnn", "rnn", "transformer"],
        "tools": ["tensorflow", "pytorch"],
    },
    "nlp": {
        "related": ["tokenization", "named entity recognition", "sentiment analysis"],
        "tools": ["spacy", "nltk", "transformers"],
    },
    "backend engineering": {
        "related": ["api design", "microservices", "system design"],
        "tools": ["fastapi", "django", "flask", "node.js"],
    },
    "cloud": {
        "related": ["infra", "devops", "monitoring"],
        "tools": ["aws", "azure", "gcp", "docker", "kubernetes"],
    },
    "data engineering": {
        "related": ["etl", "data pipelines", "warehouse"],
        "tools": ["spark", "airflow", "postgresql", "mongodb"],
    },
}

SKILL_SYNONYMS = {
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "ai": "artificial intelligence",
    "tf": "tensorflow",
    "torch": "pytorch",
    "nodejs": "node.js",
    "nextjs": "next.js",
}

CORE_SKILLS = {
    "python",
    "r",
    "java",
    "c++",
    "c#",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "pandas",
    "numpy",
    "scikit-learn",
    "sql",
    "rest",
    "graphql",
    "linux",
    "pytest",
    "ci/cd",
    "tensorflow",
    "pytorch",
    "cnn",
    "rnn",
    "transformer",
    "php",
    "wordpress",
    "html",
    "css",
    "jquery",
}

OUTDATED_OR_LOW_RELEVANCE_SKILLS = {
    "wordpress",
    "jquery",
    "vb6",
    "flash",
    "dreamweaver",
}

ML_DOMAIN_SKILLS = {
    "machine learning",
    "deep learning",
    "cnn",
    "rnn",
    "transformer",
    "tensorflow",
    "pytorch",
    "scikit-learn",
    "xgboost",
}

WEB_ONLY_SKILLS = {
    "php",
    "wordpress",
    "html",
    "css",
    "jquery",
}

_skill_model: Any | None = None
_skill_catalog: set[str] | None = None
_skill_list: list[str] | None = None
_skill_embeddings: Any | None = None

STOPWORDS = {
    "and",
    "with",
    "from",
    "that",
    "this",
    "have",
    "will",
    "your",
    "for",
    "the",
    "you",
    "are",
    "was",
    "were",
    "has",
    "had",
    "using",
    "used",
    "into",
    "over",
    "more",
    "than",
    "year",
    "years",
    "resume",
    "professional",
}

DEGREE_TOKENS = ("bachelor", "master", "phd", "b.tech", "m.tech", "mba", "bsc", "msc", "post graduate", "postgraduate", "diploma", "associate", "secondary", "certificate", "program", "degree")


def _clean_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("-,:|"))


def normalize_skill(skill: str) -> str:
    normalized = normalize_skill_key(skill)
    return SKILL_SYNONYMS.get(normalized, normalized)


def _build_skill_catalog() -> set[str]:
    global _skill_catalog
    if _skill_catalog is not None:
        return _skill_catalog

    catalog: set[str] = set()
    for parent, data in SKILL_GRAPH.items():
        catalog.add(normalize_skill(parent))
        for item in data.get("related", []):
            catalog.add(normalize_skill(item))
        for item in data.get("tools", []):
            catalog.add(normalize_skill(item))

    for alias, canonical in SKILL_SYNONYMS.items():
        catalog.add(normalize_skill(alias))
        catalog.add(normalize_skill(canonical))

    for skill in CORE_SKILLS:
        catalog.add(normalize_skill(skill))

    _skill_catalog = catalog
    return catalog


def _extract_noun_phrases(text: str) -> list[str]:
    try:
        spacy = importlib.import_module("spacy")  # pyright: ignore[reportMissingImports]
    except ImportError:
        return []

    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception as exc:
        logger.debug("spaCy model load failed for noun phrase extraction: %s", exc)
        return []

    doc = nlp(text)
    return [normalize_skill(chunk.text) for chunk in doc.noun_chunks if chunk.text.strip()]


def _get_embedding_model() -> Any | None:
    global _skill_model
    if _skill_model is not None:
        return _skill_model

    try:
        sentence_transformers = importlib.import_module(
            "sentence_transformers"
        )  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None

    model_cls = getattr(sentence_transformers, "SentenceTransformer")
    _skill_model = model_cls("all-MiniLM-L6-v2")
    return _skill_model


def _get_precomputed_skill_embeddings(catalog: set[str]) -> tuple[list[str], Any] | None:
    global _skill_list, _skill_embeddings

    model = _get_embedding_model()
    if model is None:
        return None

    if _skill_list is not None and _skill_embeddings is not None:
        return _skill_list, _skill_embeddings

    skill_list = sorted(catalog)
    if not skill_list:
        return None

    _skill_list = skill_list
    _skill_embeddings = model.encode(skill_list, convert_to_tensor=True)
    return _skill_list, _skill_embeddings


def _embedding_match_skills(
    candidates: list[str],
    catalog: set[str],
    threshold: float = 0.70,
) -> dict[str, float]:
    if not candidates:
        return {}

    model = _get_embedding_model()
    if model is None:
        return {}

    try:
        sentence_transformers = importlib.import_module("sentence_transformers")
        util = getattr(sentence_transformers, "util")

        precomputed = _get_precomputed_skill_embeddings(catalog)
        if precomputed is None:
            return {}

        skill_list, skill_emb = precomputed
        candidate_list = [normalize_skill(value) for value in candidates if value.strip()]
        if not candidate_list or not skill_list:
            return {}

        candidate_emb = model.encode(candidate_list, convert_to_tensor=True)
        similarity = util.cos_sim(candidate_emb, skill_emb)

        matches: dict[str, float] = {}
        for index, _candidate in enumerate(candidate_list):
            row = similarity[index]
            for skill_index, score in enumerate(row):
                score_value = float(score)
                if score_value >= threshold:
                    skill_name = skill_list[skill_index]
                    matches[skill_name] = max(matches.get(skill_name, 0.0), score_value)
        return matches
    except Exception as exc:
        logger.debug("Embedding skill matching failed: %s", exc)
        return {}


def _expand_skill_graph(skills: set[str]) -> set[str]:
    expanded = set(skills)
    for parent, data in SKILL_GRAPH.items():
        parent_norm = normalize_skill(parent)
        children = {normalize_skill(item) for item in data.get("related", []) + data.get("tools", [])}
        if parent_norm in expanded or (expanded & children):
            expanded.add(parent_norm)
    return expanded


def _direct_match_skills(text: str, catalog: set[str]) -> set[str]:
    lowered = text.lower()
    matched: set[str] = set()
    for skill in catalog:
        if re.search(rf"\b{re.escape(skill)}\b", lowered):
            matched.add(skill)
    for shorthand, canonical in SKILL_SYNONYMS.items():
        if re.search(rf"\b{re.escape(shorthand)}\b", lowered):
            matched.add(normalize_skill(canonical))
    return matched


def _skill_frequency(text: str, skill: str) -> int:
    return len(re.findall(rf"\b{re.escape(skill)}\b", text.lower()))


def _skill_sources(skill: str, sections: dict[str, str], full_text: str, embedding_hit: bool) -> list[str]:
    sources: set[str] = set()
    for section_name, section_text in sections.items():
        if re.search(rf"\b{re.escape(skill)}\b", section_text.lower()):
            if section_name == "skills":
                sources.add("skills_section")
            elif section_name == "experience":
                sources.add("experience")
            else:
                sources.add(section_name)

    if embedding_hit:
        sources.add("embedding")

    if not sources and re.search(rf"\b{re.escape(skill)}\b", full_text.lower()):
        sources.add("global_text")

    return sorted(sources)


def _skill_section_weight(sources: list[str]) -> float:
    weights = {
        "skills_section": 1.0,
        "experience": 0.85,
        "projects": 0.75,
        "summary": 0.65,
        "education": 0.45,
        "embedding": 0.5,
        "global_text": 0.4,
    }
    if not sources:
        return 0.0
    return max(weights.get(source, 0.35) for source in sources)


def _build_skill_scores(
    skills: set[str],
    embedding_scores: dict[str, float],
    sections: dict[str, str],
    full_text: str,
    jd_context: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    years = _estimate_total_experience_years(full_text)
    emb_weight, freq_weight, section_weight_factor = _adaptive_skill_weights(years)

    jd_required = {
        normalize_skill(value) for value in (jd_context or {}).get("skills_required", [])
    }
    jd_optional = {
        normalize_skill(value) for value in (jd_context or {}).get("skills_optional", [])
    }
    jd_all = jd_required | jd_optional

    scored: dict[str, dict[str, Any]] = {}
    for skill in sorted(skills):
        frequency = _skill_frequency(full_text, skill)
        freq_score = min(frequency / 5.0, 1.0)
        emb_score = min(max(embedding_scores.get(skill, 0.0), 0.0), 1.0)
        sources = _skill_sources(skill, sections, full_text, skill in embedding_scores)
        section_weight = _skill_section_weight(sources)

        weighted_confidence = (
            emb_weight * emb_score
            + freq_weight * freq_score
            + section_weight_factor * section_weight
        )
        base_confidence = max(
            emb_score,
            0.7 * emb_score + 0.3 * section_weight,
            weighted_confidence,
        )
        penalty, penalty_reasons = _negative_skill_penalty(skill, jd_required, jd_all)
        confidence = max(0.0, base_confidence - penalty)

        scored[skill] = {
            "score": round(min(confidence, 1.0), 2),
            "source": sources,
            "frequency": frequency,
            "confidence": round(min(confidence, 1.0), 2),
            "embedding_score": round(emb_score, 3),
            "section_weight": round(section_weight, 3),
            "penalty": round(penalty, 3),
            "penalty_reasons": penalty_reasons,
            "weights": {
                "embedding": emb_weight,
                "frequency": freq_weight,
                "section": section_weight_factor,
            },
        }
    return scored


def _adaptive_skill_weights(total_years: int) -> tuple[float, float, float]:
    # Freshers rely more on semantic evidence because explicit repetition is low.
    if total_years <= 2:
        return 0.65, 0.15, 0.20
    # Experienced resumes have denser repetition and richer section evidence.
    if total_years >= 7:
        return 0.35, 0.40, 0.25
    return 0.50, 0.30, 0.20


def _negative_skill_penalty(
    skill: str,
    jd_required: set[str],
    jd_all: set[str],
) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons: list[str] = []

    if skill in OUTDATED_OR_LOW_RELEVANCE_SKILLS:
        penalty += 0.12
        reasons.append("outdated_or_low_relevance")

    if jd_all and skill not in jd_all and skill not in SKILL_GRAPH:
        penalty += 0.08
        reasons.append("not_in_jd")

    jd_ml_focused = bool(jd_required & ML_DOMAIN_SKILLS)
    if jd_ml_focused and skill in WEB_ONLY_SKILLS:
        penalty += 0.18
        reasons.append("domain_mismatch_with_jd")

    return min(penalty, 0.6), reasons


def extract_name(text: str) -> str | None:
    lines = text.splitlines()[:5]
    for line in lines:
        candidate = _clean_token(line)
        if not candidate:
            continue
        if re.search(r"@|http|\d", candidate, re.IGNORECASE):
            continue
        if len(candidate.split()) <= 4:
            return candidate
    return None


def _extract_contact(text: str) -> dict[str, str | None]:
    emails = EMAIL_RE.findall(text)
    phones = [
        match.group(0).strip()
        for match in PHONE_RE.finditer(text)
        if len(re.sub(r"\D", "", match.group(0))) >= 10
    ]
    links = extract_validated_links(text)

    return {
        "name": extract_name(text),
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "linkedin": links["linkedin"],
        "github": links["github"],
        "portfolio": links["portfolio"],
    }


def _extract_skills(
    sections: dict[str, str],
    full_text: str,
    jd_context: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    catalog = _build_skill_catalog()
    skill_candidates: set[str] = set()
    explicit_skill_map = parse_skill_mentions(sections.get("skills", ""))

    for skill in explicit_skill_map:
        if 0 < len(skill) < 40:
            skill_candidates.add(skill)

    skill_candidates |= _direct_match_skills(full_text, catalog)
    embedding_scores: dict[str, float] = {}

    deduped = {normalize_skill(skill) for skill in skill_candidates if skill and normalize_skill(skill) in catalog}

    # High-precision parent inference: only elevate to "deep learning" when explicit DL evidence exists.
    deep_learning_evidence = {"cnn", "rnn", "transformer", "tensorflow", "pytorch"}
    if "deep learning" in catalog and "deep learning" not in deduped and (deduped & deep_learning_evidence):
        deduped.add("deep learning")

    # Fallback keyword injection is restricted to explicit skills-section hits.
    fallback_keywords = [
        "machine learning",
        "deep learning",
        "natural language processing",
        "nlp",
        "python",
        "tensorflow",
        "pytorch",
        "kubernetes",
        "docker",
        "data pipelines",
        "algorithms",
    ]
    lowered_text = full_text.lower()
    skills_section_lower = sections.get("skills", "").lower()

    def _exact_keyword_hit(haystack: str, keyword: str) -> bool:
        if not haystack.strip():
            return False
        return bool(re.search(rf"\b{re.escape(keyword.lower())}\b", haystack))

    for keyword in fallback_keywords:
        canonical = normalize_skill(keyword)
        if (
            canonical in catalog
            and _exact_keyword_hit(skills_section_lower, keyword)
            and _exact_keyword_hit(lowered_text, keyword)
        ):
            deduped.add(canonical)

    # Explicitly parse comma/newline separated skills section content with high confidence intent.
    skills_section = sections.get("skills", "")
    if skills_section:
        for raw_skill in explicit_skill_map:
            cleaned = normalize_skill(raw_skill)
            if cleaned and cleaned in catalog:
                deduped.add(cleaned)

    scored = _build_skill_scores(deduped, embedding_scores, sections, full_text, jd_context)

    # Ensure strict fallback skills are retained only when they are explicit in skills section.
    for keyword in fallback_keywords:
        canonical = normalize_skill(keyword)
        if (
            canonical in catalog
            and canonical not in scored
            and _exact_keyword_hit(skills_section_lower, keyword)
            and _exact_keyword_hit(lowered_text, keyword)
        ):
            scored[canonical] = {
                "score": 0.6,
                "source": ["fallback_keyword"],
                "frequency": _skill_frequency(full_text, canonical),
                "confidence": 0.6,
                "embedding_score": 0.0,
                "section_weight": 0.4,
                "penalty": 0.0,
                "penalty_reasons": [],
                "weights": {
                    "embedding": 0.0,
                    "frequency": 0.0,
                    "section": 1.0,
                },
            }

    for skill_name, payload in scored.items():
        explicit_meta = explicit_skill_map.get(skill_name, {})
        payload["canonical_key"] = skill_name
        payload["display_label"] = skill_display_label(skill_name)
        payload["aliases"] = list(explicit_meta.get("aliases", []))
        payload["child_skills"] = list(explicit_meta.get("child_skills", []))

    logger.info("Extracted %d unique skills", len(scored))
    return scored, sorted(scored.keys())


def _extract_education(sections: dict[str, str]) -> list[dict[str, Any]]:
    """Extract education entries from education section.
    
    Handles formats like:
    - "Institution Name"
      "Degree Name"
      "Location"
      "Year - Year"
    - "Institution Name (Degree Name)"
      "Location"
      "Year - Year"
    """
    education_text = sections.get("education", "")
    entries: list[dict[str, Any]] = []

    lines = [line.strip() for line in education_text.splitlines() if line.strip()]
    if not lines:
        return entries

    # Group lines into education blocks
    blocks = _group_education_lines(lines)

    # Parse each block
    for block in blocks:
        if not block:
            continue

        entry = _parse_education_block(block)
        if entry.get("degree") or entry.get("institution") or entry.get("year"):
            entries.append(entry)

    return entries


def _group_education_lines(lines: list[str]) -> list[list[str]]:
    """Group education lines into logical entry blocks.
    
    Each block represents one education entry (institution + degree + location + dates).
    """
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for i, line in enumerate(lines):
        # Check if this line starts a new education entry
        # New entries are typically institution names (capitalized, 2-5 words, not a date/year)
        if (
            current_block
            and i > 0
            and _looks_like_institution_start(line)
            and not _looks_like_institution_start(lines[i - 1])
        ):
            # We've likely hit the start of a new entry
            blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    return blocks


def _looks_like_institution_start(line: str) -> bool:
    """Check if a line looks like the start of a NEW education entry (institution name).
    
    Only returns True for strong institution indicators to avoid false positives
    on program/degree names that follow the institution.
    
    Examples of institutions: "University of X", "X Institute", "X School"
    Counter-examples: "Women Leadership Program", "Bachelor of Science"
    """
    if not line:
        return False

    lower = line.lower()

    # Strong, specific institution keywords - these MUST be present
    # (not just any capitalized phrase)
    institution_keywords = {
        "university",
        "institute",
        "school",
        "college",
        "academy",
        "polytechnic",
        "iit",
        "iim",
        "isb",  # Specific institutions
    }

    # Only return True if we find a strong keyword
    return any(kw in lower for kw in institution_keywords)


def _parse_education_block(lines: list[str]) -> dict[str, Any]:
    """Parse a single education block (usually 2-4 lines).
    
    Typical format:
    - Line 0: Institution (maybe with degree in parens)
    - Line 1: Dates
    - Line 2: Location
    - Line 3: Program/Degree (if not in parens)
    """
    institution = ""
    degree = ""
    location = ""
    year = ""

    full_text = " ".join(lines)

    # Extract year/date info first
    month_ranges = MONTH_RANGE_RE.findall(full_text)
    if month_ranges:
        year = month_ranges[0]
    else:
        date_ranges = DATE_RANGE_RE.findall(full_text)
        if date_ranges:
            start, end = date_ranges[0]
            year = f"{start}-{end}"
        else:
            year_matches = YEAR_RE.findall(full_text)
            if year_matches:
                year = year_matches[0]

    # Process lines in order to identify institution, location, and degree
    # The institution is the line containing institution keywords
    # Degrees/programs are everything else that's not a date or location
    
    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        # Strip dates from the line so we don't throw away the whole line if the date is embedded
        clean_text = clean
        if MONTH_RANGE_RE.search(clean_text):
            clean_text = re.sub(MONTH_RANGE_RE, "", clean_text).strip(" ,|-")
        if DATE_RANGE_RE.search(clean_text):
            clean_text = re.sub(DATE_RANGE_RE, "", clean_text).strip(" ,|-")
        
        # safely remove standalone years
        clean_text = re.sub(r"\b(19\d{2}|20\d{2})\b", "", clean_text).strip(" ,|-")
        # cleanup extra whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip(" ,|-")

        if not clean_text:
            continue

        lower = clean_text.lower()

        # Check if contains institution keywords - highest priority for institution
        institution_keywords = {"university", "institute", "school", "college"}
        if any(kw in lower for kw in institution_keywords):
            # This is the institution line
            if "(" in clean_text and ")" in clean_text:
                inst_match = re.match(r"([^(]+)\(([^)]+)\)", clean_text)
                if inst_match:
                    institution = inst_match.group(1).strip()
                    # Could be degree in parens
                    if any(dt in inst_match.group(2).lower() for dt in DEGREE_TOKENS):
                        degree_candidate = inst_match.group(2).strip()
                        if not degree:
                            degree = degree_candidate
            else:
                institution = clean_text
            continue

        # Check if location
        if _looks_like_location(clean_text) and not location:
            location = clean_text
            continue

        # Check if degree
        if any(dt in lower for dt in DEGREE_TOKENS):
            if not degree:
                degree = clean_text
            continue

        # Default: if we don't have an institution yet, this is it
        # Otherwise, it's a degree/program line
        if not institution and not _looks_like_location(clean_text):
            institution = clean_text
        elif not degree and not _looks_like_location(clean_text):
            degree = clean_text

    # Build text representation
    text_parts = []
    if institution:
        text_parts.append(institution)
    if degree:
        text_parts.append(degree)
    if location:
        text_parts.append(location)
    if year:
        text_parts.append(year)

    return {
        "text": " | ".join(text_parts) if text_parts else " ".join(lines),
        "degree": degree if degree else None,
        "institution": institution if institution else None,
        "year": year if year else None,
    }


def extract_experience_structured(text: str) -> list[dict[str, Any]]:
    """Extract experience entries from resume text, handling compact multi-role layouts."""
    entries: list[dict[str, Any]] = []

    raw_lines = [_normalize_resume_line(line) for line in text.splitlines()]
    lines = [line for line in raw_lines if line and not re.fullmatch(r"[_-]{5,}", line)]
    if not lines:
        return entries

    current_header: list[str] = []
    current_body: list[str] = []

    for line in lines:
        if _is_experience_header_candidate(line):
            # New job header encountered: flush previous entry first.
            if current_header and current_body:
                entry = _build_experience_entry(current_header, current_body)
                if entry:
                    entries.append(entry)
                current_header = []
                current_body = []

            if not current_header:
                current_header = [line]
            else:
                current_header.append(line)
            continue

        if _is_supporting_header_line(line) and current_header and not current_body:
            current_header.append(line)
            continue

        if _is_bullet_line(line):
            current_body.append(line)
            continue

        if current_body:
            current_body.append(line)
            continue

        if current_header and not current_body:
            current_header.append(line)

    if current_header:
        entry = _build_experience_entry(current_header, current_body)
        if entry:
            entries.append(entry)

    return entries


def _normalize_resume_line(value: str) -> str:
    """Normalize extracted text lines by removing invisible separators and extra spaces."""
    cleaned = str(value or "")
    cleaned = cleaned.replace("\u200b", "")  # zero-width space from PDF extraction
    cleaned = cleaned.replace("\u200c", "")
    cleaned = cleaned.replace("\u200d", "")
    cleaned = cleaned.replace("\ufeff", "")
    # Normalize common PDF bullet glyphs so downstream bullet detection is consistent.
    cleaned = cleaned.replace("\uf0b7", "•")
    cleaned = cleaned.replace("\uf0a7", "•")
    cleaned = cleaned.replace("\u2023", "•")
    cleaned = cleaned.replace("\u25e6", "•")
    cleaned = cleaned.replace("\u2043", "•")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_bullet_line(line: str) -> bool:
    clean = _normalize_resume_line(line)
    if not clean:
        return False
    return bool(re.match(r"^[•●▪◦‣\-*]\s*", clean))


def _is_experience_header_candidate(line: str) -> bool:
    clean = _normalize_resume_line(line)
    if not clean:
        return False
    if _is_bullet_line(clean):
        return False

    has_date = bool(MONTH_RANGE_RE.search(clean) or DATE_RANGE_RE.search(clean))
    # Standalone date lines are supporting header lines, not primary headers.
    if has_date and not (_looks_like_role(clean) or "|" in clean or "," in clean):
        return False

    # Typical role headers are in "Company, Location | Role" or "Role | Company" format.
    if "|" in clean and _looks_like_role(clean):
        return True

    # Fallback: short role-like headers can start new entries even without pipe.
    return len(clean.split()) <= 10 and _looks_like_role(clean)


def _is_supporting_header_line(line: str) -> bool:
    clean = _normalize_resume_line(line)
    if not clean:
        return False
    return bool(DATE_RANGE_RE.search(clean) or MONTH_RANGE_RE.search(clean) or _looks_like_location(clean))


def _build_experience_entry(header_lines: list[str], body_lines: list[str]) -> dict[str, Any] | None:
    catalog = _build_skill_catalog()
    cleaned_header = [_normalize_resume_line(line) for line in header_lines if _normalize_resume_line(line)]
    if not cleaned_header:
        return None

    cleaned_body = [_normalize_resume_line(line) for line in body_lines if _normalize_resume_line(line)]
    bullets = _extract_bullets_from_lines(cleaned_body)

    combined_text = " ".join(cleaned_header + cleaned_body)
    years = YEAR_RE.findall(combined_text)
    ranges = DATE_RANGE_RE.findall(combined_text)
    role, company, duration = _parse_role_company_duration_improved(cleaned_header, ranges)

    header = " ".join(cleaned_header)
    inferred_skills = sorted(_direct_match_skills(" ".join([header] + bullets), catalog))
    inferred_skills = sorted(set(inferred_skills))

    urls = URL_RE.findall(combined_text)
    link = urls[0] if urls else None

    return {
        "header": header,
        "role": role,
        "company": company,
        "duration": duration,
        "bullets": bullets,
        "years": years,
        "date_ranges": ranges,
        "skills_inferred": inferred_skills,
        "link": link,
    }


def _separate_header_and_bullets(lines: list[str]) -> tuple[list[str], list[str]]:
    """Separate header lines from bullet points.
    
    Headers are the first 1-3 non-empty lines before any bullet markers.
    Once we hit a bullet marker or substantive bullet line, everything after is bullets.
    """
    header_lines: list[str] = []
    bullet_lines: list[str] = []
    in_bullets = False

    for line in lines:
        if not line.strip():
            continue

        # Check if this is a bullet marker or bullet point line
        if (
            line.startswith(("• ", "● ", "- "))
            or line in {"•", "●", "-"}
            or (line.startswith("-") and len(line) > 1 and line[1] != "-")
        ):
            in_bullets = True

        if in_bullets:
            bullet_lines.append(line)
        else:
            # Only add to header if we haven't exceeded max header line count
            # and the line doesn't look like it's starting bullets
            if len(header_lines) < 5 and not _looks_like_job_boundary_line(line):
                header_lines.append(line)
            elif len(header_lines) < 3:
                # Allow a bit more flexibility for company/duration lines
                header_lines.append(line)
            else:
                # Once we have 3 header lines and encounter another line,
                # it's likely a bullet or detail line
                in_bullets = True
                bullet_lines.append(line)

    return header_lines, bullet_lines


def _parse_role_company_duration_improved(
    header_lines: list[str], ranges: list[tuple[str, str]]
) -> tuple[str, str, str]:
    """Parse role, company, and duration from header lines.
    
    Handles formats like:
    - "Location | Job Title" + "Company"
    - "Job Title" + "Company"
    - "Company | Location" + "Job Title May 2023 - Present"
    """
    duration = ""
    if ranges:
        start, end = ranges[0]
        duration = f"{start}-{end}"

    if not header_lines:
        return "", "", duration

    role = ""
    company = ""
    location = ""

    # Process each header line
    for line_idx, line in enumerate(header_lines):
        clean_line = _clean_token(line)
        # Remove date ranges from the line
        clean_line = re.sub(DATE_RANGE_RE, "", clean_line).strip(" ,|-")

        if not clean_line:
            continue

        # First try to split by pipe (|) separator which typically separates location from role
        if "|" in clean_line:
            parts = re.split(r"\s*\|\s*", clean_line, maxsplit=1)
            first_part = parts[0].strip()
            second_part = parts[1].strip() if len(parts) > 1 else ""

            # Determine which part is what
            first_is_location = _looks_like_location(first_part)
            second_is_role = _looks_like_role(second_part)

            if first_is_location and second_is_role:
                location = first_part
                role = second_part
                if "," in first_part:
                    company_candidate = first_part.split(",", 1)[0].strip()
                    if company_candidate:
                        company = company_candidate
            elif second_is_role:
                # Common format: "Company, Location | Role"
                role = second_part
                if "," in first_part:
                    company_candidate = first_part.split(",", 1)[0].strip()
                    company = company_candidate or first_part
                else:
                    company = first_part
            elif _looks_like_role(first_part):
                role = first_part
                if _looks_like_location(second_part):
                    location = second_part
                elif _looks_like_company(second_part):
                    company = second_part
            else:
                role = clean_line
        else:
            # No pipe separator - determine based on content
            if DATE_RANGE_RE.search(clean_line) or MONTH_RANGE_RE.search(clean_line):
                if not duration:
                    duration = clean_line
                continue
                
            # Try splitting by comma, often the last element is the company 
            if "," in clean_line and not company:
                parts = [p.strip() for p in clean_line.split(",")]
                if len(parts) > 1:
                    last_part = parts[-1]
                    if _looks_like_company(last_part) or last_part.isupper() or len(last_part.split()) <= 2:
                        company = last_part
                        role = ", ".join(parts[:-1])
                        continue

            if _looks_like_role(clean_line):
                if not role:
                    role = clean_line
            elif _looks_like_company(clean_line):
                if not company:
                    company = clean_line
            elif _looks_like_location(clean_line):
                if not location:
                    location = clean_line
            else:
                # Default: earlier lines are role, later lines are company
                if line_idx == 0 or not role:
                    role = clean_line
                else:
                    company = clean_line

    return role, company, duration


def _looks_like_location(text: str) -> bool:
    """Check if text looks like a location."""
    if not text:
        return False

    lower = text.lower()
    location_keywords = {
        "london",
        "new york",
        "usa",
        "singapore",
        "mumbai",
        "bangalore",
        "delhi",
        "remote",
        "hybrid",
        "los angeles",
        "san francisco",
        "tokyo",
        "paris",
        "berlin",
        "toronto",
        "sydney",
        "bangalore",
        "hyderabad",
        "pune",
        "india",
        "united states",
        "canada",
        "australia",
        "france",
        "germany",
        "japan",
    }
    if any(re.search(rf"\b{re.escape(loc)}\b", lower) for loc in location_keywords):
        return True

    # Country/state short codes must be exact words to avoid matching inside words.
    if re.search(r"\b(?:us|uk|ny|ca|tx)\b", lower):
        return True

    return False


def _looks_like_role(text: str) -> bool:
    """Check if text looks like a job title/role."""
    if not text:
        return False

    lower = text.lower()
    role_keywords = {
        "engineer",
        "developer",
        "scientist",
        "manager",
        "analyst",
        "consultant",
        "architect",
        "lead",
        "director",
        "coordinator",
        "specialist",
        "officer",
        "associate",
        "junior",
        "senior",
        "principal",
        "staff",
        "intern",
        "apprentice",
        "assistant",
        "executive",
        "president",
        "vp",
        "vice",
        "designer",
        "marketer",
        "administrator",
        "administrator",
        "intern",
    }

    # Check for exact role keywords
    return any(word in lower for word in role_keywords)


def _looks_like_company(text: str) -> bool:
    """Check if text looks like a company name."""
    if not text:
        return False

    lower = text.lower()

    # Company name indicators
    company_indicators = {
        "inc",
        "ltd",
        "llc",
        "corp",
        "company",
        "bank",
        "solutions",
        "technologies",
        "consulting",
        "group",
        "gmbh",
    }
    if any(ind in lower for ind in company_indicators):
        return True

    # Proper nouns/capitalized (rough heuristic)
    if len(text) > 0 and text[0].isupper() and len(text.split()) <= 6:
        # Exclude locations
        if not _looks_like_location(text):
            return True

    return False


def _extract_bullets_from_lines(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    current_parts: list[str] = []
    pending_marker = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if re.fullmatch(r"[_-]{5,}", line):
            continue

        if line in {"●", "•", "-", "*"}:
            if current_parts:
                bullet = " ".join(current_parts).strip()
                if _is_substantive_bullet_line(bullet):
                    bullets.append(bullet)
                current_parts = []
            pending_marker = True
            continue

        if _is_bullet_line(line):
            if current_parts:
                bullet = " ".join(current_parts).strip()
                if _is_substantive_bullet_line(bullet):
                    bullets.append(bullet)
            clean_bullet = re.sub(r"^[•●\-*]\s*", "", line).strip()
            current_parts = [clean_bullet]
            pending_marker = False
            continue

        if pending_marker:
            current_parts = [line]
            pending_marker = False
            continue

        if current_parts and _looks_like_job_boundary_line(line):
            bullet = " ".join(current_parts).strip()
            if _is_substantive_bullet_line(bullet):
                bullets.append(bullet)
            current_parts = []
            continue

        if current_parts:
            current_parts.append(line)

    if current_parts:
        bullet = " ".join(current_parts).strip()
        if _is_substantive_bullet_line(bullet):
            bullets.append(bullet)

    return bullets


def _fallback_bullets_from_lines(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        clean = line.strip()
        if _is_substantive_bullet_line(clean):
            bullets.append(re.sub(r"^[•●\-*]\s*", "", clean).strip())
    return bullets


def _find_role_line(lines: list[str]) -> str:
    role_tokens = {
        "engineer",
        "developer",
        "scientist",
        "manager",
        "analyst",
        "consultant",
        "architect",
        "lead",
    }
    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in role_tokens):
            return line
    return ""


def _is_substantive_bullet_line(text: str) -> bool:
    if not text:
        return False
    if re.fullmatch(r"[_-]{5,}", text):
        return False
    if DATE_RANGE_RE.search(text):
        return False
    if YEAR_RE.search(text) and len(text.split()) <= 4:
        return False
    if "," in text and len(text.split()) <= 6 and any(loc in text for loc in [" NY", " CA", " UK", " United Kingdom", " New York"]):
        return False
    return len(text.split()) >= 6


def _looks_like_job_boundary_line(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return False
    if DATE_RANGE_RE.search(clean):
        return True

    # Company + location style lines
    if "," in clean and any(
        token in clean
        for token in ["United Kingdom", "New York", "London", " NY", " CA", " TX"]
    ):
        return True

    # Short role headers often indicate a transition between positions.
    role_tokens = ["engineer", "developer", "manager", "analyst", "consultant", "architect", "scientist"]
    lowered = clean.lower()
    if len(clean.split()) <= 6 and any(token in lowered for token in role_tokens):
        return True

    return False


def _parse_role_company_duration(header: str, ranges: list[tuple[str, str]]) -> tuple[str, str, str]:
    clean_header = _clean_token(header)
    duration = ""
    if ranges:
        start, end = ranges[0]
        duration = f"{start}-{end}"
        clean_header = re.sub(DATE_RANGE_RE, "", clean_header).strip(" ,|-")

    role = clean_header
    company = ""

    split_match = re.split(r"\s*(?:,|\||\bat\b)\s*", clean_header, maxsplit=1, flags=re.IGNORECASE)
    if len(split_match) == 2:
        role, company = split_match[0].strip(), split_match[1].strip()

    return role, company, duration


def _extract_experience(sections: dict[str, str]) -> list[dict[str, Any]]:
    exp_text = sections.get("experience", "")
    if not exp_text.strip():
        return []

    lines = [clean_text_line(line) for line in exp_text.splitlines() if clean_text_line(line)]
    token_lines: list[TokenLine] = []
    for idx, line in enumerate(lines):
        token = Token(
            text=line,
            bbox=(0.0, float(idx * 12), 500.0, float(idx * 12 + 10)),
            font_size=11.0,
            page=0,
        )
        token_lines.append(TokenLine(tokens=[token], page=0))

    raw_entries = ExperienceParser().parse(token_lines)
    return normalize_experience_entries(
        [
            {
                "role": entry.get("job_title"),
                "company": entry.get("company"),
                "location": entry.get("location"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "duration": entry.get("date_string"),
                "bullets": entry.get("description", []),
            }
            for entry in raw_entries
        ]
    )




def _extract_keywords(text: str, max_items: int = 25) -> list[str]:
    try:
        sklearn_text = importlib.import_module("sklearn.feature_extraction.text")
        vectorizer_cls = getattr(sklearn_text, "TfidfVectorizer")
        vectorizer = vectorizer_cls(stop_words="english", ngram_range=(1, 2), max_features=256)
        matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = matrix.toarray()[0]
        ranked = sorted(zip(feature_names, scores), key=lambda item: item[1], reverse=True)
        keywords = [term for term, score in ranked if score > 0][:max_items]
        return keywords
    except Exception as exc:
        logger.debug("sklearn TF-IDF unavailable, using Counter fallback: %s", exc)
        tokens = re.findall(r"[A-Za-z][A-Za-z+.#-]{2,}", text.lower())
        filtered = [token for token in tokens if token not in STOPWORDS]
        counts = Counter(filtered)
        return [word for word, _ in counts.most_common(max_items)]


def _extract_projects(sections: dict[str, str]) -> list[dict[str, Any]]:
    projects_text = sections.get("projects", "")
    if not projects_text.strip():
        return []
    return parse_project_section_lines(projects_text.splitlines())


def _extract_certifications_structured(sections: dict[str, str]) -> list[dict[str, Any]]:
    cert_text = sections.get("certifications", "")
    if not cert_text.strip():
        return []
    normalized: list[dict[str, Any]] = []
    for entry in parse_certification_lines(cert_text.splitlines()):
        item = normalize_certification_entry(entry)
        if item:
            normalized.append(item)
    return normalized


def _estimate_total_experience_years(text: str) -> float:
    lines = [clean_text_line(line) for line in text.splitlines() if clean_text_line(line)]
    if not lines:
        return 0.0

    token_lines: list[TokenLine] = []
    for idx, line in enumerate(lines):
        token = Token(
            text=line,
            bbox=(0.0, float(idx * 12), 500.0, float(idx * 12 + 10)),
            font_size=11.0,
            page=0,
        )
        token_lines.append(TokenLine(tokens=[token], page=0))

    experience_rows = normalize_experience_entries(
        [
            {
                "role": entry.get("job_title"),
                "company": entry.get("company"),
                "location": entry.get("location"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "duration": entry.get("date_string"),
                "bullets": entry.get("description", []),
            }
            for entry in ExperienceParser().parse(token_lines)
        ]
    )
    return float(summarize_total_experience(experience_rows).get("total_experience_years_float", 0.0))


def extract_entities(
    text: str,
    sections: dict[str, str],
    jd_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract structured entities from a resume text and its sections."""
    skills_scored, skill_names = _extract_skills(sections, text, jd_context)
    experience = _extract_experience(sections)
    experience_summary = summarize_total_experience(experience)
    entities: dict[str, Any] = {
        "contact": _extract_contact(text),
        "skills": skills_scored,
        "skill_names": skill_names,
        "education": _extract_education(sections),
        "experience": experience,
        "projects": _extract_projects(sections),
        "certifications": _extract_certifications_structured(sections),
        "keywords": _extract_keywords(text),
        **experience_summary,
    }
    logger.info(
        "Entity extraction complete: skills=%d, experience_entries=%d",
        len(entities["skills"]),
        len(entities["experience"]),
    )
    return entities
