"""Shared structured parsing helpers for resume entities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse


BULLET_PREFIX_RE = re.compile(r"^\s*[\u2022\u25cf\u25aa\u25b8\uf0b7\uf0a7\-*]+(?:\s|\u200b|\u200c|\u200d)*")
DATE_COMPONENT_RE = (
    r"(?:present|current|now|ongoing|"
    r"\d{1,2}[/-]\d{2,4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{2,4}|"
    r"(?:19|20)\d{2})"
)
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{DATE_COMPONENT_RE})\s*(?:-|–|—|to)\s*(?P<end>{DATE_COMPONENT_RE})",
    re.IGNORECASE,
)
LINKEDIN_TEXT_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s|]+", re.IGNORECASE)
GITHUB_TEXT_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s|]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s|]+|www\.[^\s|]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
MONTH_NAME_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{2,4}\b",
    re.IGNORECASE,
)
MM_YYYY_RE = re.compile(r"\b\d{1,2}[/-]\d{2,4}\b")
LOCATION_RE = re.compile(
    r"\b(?:remote|hybrid|onsite|on-site|work from home|wfh|india|singapore|usa|uk|"
    r"bangalore|bengaluru|mumbai|pune|hyderabad|delhi|new york|london|toronto|sydney|"
    r"berlin|paris|tokyo|dubai)\b",
    re.IGNORECASE,
)

MONTH_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

SKILL_ALIAS_MAP = {
    "adv excel": "excel",
    "advanced excel": "excel",
    "ai": "artificial intelligence",
    "ci cd": "ci/cd",
    "eda": "exploratory data analysis",
    "js": "javascript",
    "ml": "machine learning",
    "ms excel": "excel",
    "m s excel": "excel",
    "microsoft excel": "excel",
    "nextjs": "next.js",
    "nlp": "natural language processing",
    "nodejs": "node.js",
    "powerbi": "power bi",
    "py": "python",
    "tf": "tensorflow",
    "torch": "pytorch",
}

SKILL_DISPLAY_MAP = {
    "artificial intelligence": "Artificial Intelligence",
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "css": "CSS",
    "eda": "EDA",
    "excel": "Excel",
    "gcp": "GCP",
    "github": "GitHub",
    "html": "HTML",
    "javascript": "JavaScript",
    "ml": "ML",
    "natural language processing": "Natural Language Processing",
    "next.js": "Next.js",
    "node.js": "Node.js",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "power bi": "Power BI",
    "python": "Python",
    "pytorch": "PyTorch",
    "scikit-learn": "scikit-learn",
    "sql": "SQL",
    "tensorflow": "TensorFlow",
    "typescript": "TypeScript",
}

PLACEHOLDER_TOKENS = {
    "example",
    "example.com",
    "placeholder",
    "sample",
    "test",
    "username",
    "user-name",
    "your-name",
    "yourname",
    "yourprofile",
    "your-profile",
    "your-profile-url",
    "profile-url",
    "linkedin-profile",
    "github-profile",
    "portfolio-url",
}

SKILL_NOISE_TOKENS = {
    "business",
    "dashboard",
    "development",
    "management",
    "technical",
    "tools",
}

CHILD_ONLY_SKILLS = {
    "basic statistics",
    "chart",
    "charts",
    "pivot table",
    "pivot tables",
}

SKILL_JOIN_PREFIXES = {
    "dashboard",
    "data",
    "deep",
    "google",
    "machine",
    "marketing",
    "problem",
    "project",
    "strategic",
    "team",
    "time",
}

SKILL_JOIN_SUFFIXES = {
    "analysis",
    "analytics",
    "development",
    "learning",
    "management",
    "planning",
    "science",
    "strategy",
    "visualization",
}

ROLE_HINT_RE = re.compile(
    r"\b(?:engineer|developer|consultant|analyst|manager|intern|director|lead|architect|"
    r"president|officer|specialist|associate|scientist|head|chairperson|founder|owner|"
    r"executive|coordinator|designer|administrator|mentor|trainer)\b",
    re.IGNORECASE,
)
COMPANY_HINT_RE = re.compile(
    r"\b(?:inc\.?|ltd\.?|llc|corp\.?|company|technologies|systems|services|bank|"
    r"university|pvt\.?|group|trust|club|foundation|association|organization|school|"
    r"institute|academy|society|labs?|consulting|ventures|solutions)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedMonth:
    year: int
    month: int
    precision: str
    is_present: bool = False


def clean_text_line(value: str) -> str:
    cleaned = str(value or "")
    cleaned = cleaned.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    cleaned = cleaned.replace("\uf0b7", "\u2022").replace("\uf0a7", "\u2022")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def strip_bullet_prefix(value: str) -> str:
    return BULLET_PREFIX_RE.sub("", clean_text_line(value)).strip()


def normalize_dash_text(value: str) -> str:
    return clean_text_line(value).replace("–", "-").replace("—", "-").replace("−", "-")


def is_present_token(value: str) -> bool:
    return normalize_dash_text(value).lower() in {"present", "current", "now", "ongoing"}


def normalize_year_token(token: str) -> int | None:
    token = clean_text_line(token)
    if not token:
        return None
    if re.fullmatch(r"(?:19|20)\d{2}", token):
        return int(token)
    if re.fullmatch(r"\d{2}", token):
        year = int(token)
        return 2000 + year if year <= 49 else 1900 + year
    return None


def parse_month_token(value: str, *, is_end: bool = False, today: date | None = None) -> ParsedMonth | None:
    current = today or date.today()
    token = normalize_dash_text(value).strip(" ,|()[]")
    if not token:
        return None

    if is_present_token(token):
        return ParsedMonth(year=current.year, month=current.month, precision="month", is_present=True)

    mm_yyyy = re.fullmatch(r"(?P<month>\d{1,2})[/-](?P<year>\d{2,4})", token)
    if mm_yyyy:
        month = int(mm_yyyy.group("month"))
        year = normalize_year_token(mm_yyyy.group("year"))
        if year and 1 <= month <= 12:
            return ParsedMonth(year=year, month=month, precision="month")

    month_name = re.fullmatch(r"(?P<month>[A-Za-z]+)\.?\s+(?P<year>\d{2,4})", token)
    if month_name:
        month_key = month_name.group("month").lower().rstrip(".")
        month = MONTH_LOOKUP.get(month_key)
        year = normalize_year_token(month_name.group("year"))
        if year and month:
            return ParsedMonth(year=year, month=month, precision="month")

    year = normalize_year_token(token)
    if year:
        return ParsedMonth(year=year, month=12 if is_end else 1, precision="year")

    return None


def month_index(value: ParsedMonth) -> int:
    return value.year * 12 + (value.month - 1)


def extract_date_range(text: str) -> tuple[str | None, str | None]:
    match = DATE_RANGE_RE.search(normalize_dash_text(text))
    if not match:
        return None, None
    return clean_text_line(match.group("start")), clean_text_line(match.group("end"))


def canonical_date_display(value: str | None) -> str:
    if not value:
        return ""
    cleaned = clean_text_line(value)
    return "Present" if is_present_token(cleaned) else cleaned


def compute_duration_months(
    start_date: str | None,
    end_date: str | None,
    *,
    today: date | None = None,
) -> tuple[int, bool]:
    start = parse_month_token(start_date or "", is_end=False, today=today)
    end = parse_month_token(end_date or "", is_end=True, today=today)
    if start is None or end is None:
        return 0, False
    start_idx = month_index(start)
    end_idx = month_index(end)
    if end_idx < start_idx:
        return 0, end.is_present
    return (end_idx - start_idx) + 1, end.is_present


def merge_month_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted((start, end) for start, end in intervals if end >= start)
    if not ordered:
        return []

    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        current = merged[-1]
        if start <= current[1] + 1:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def format_months_display(total_months: int) -> str:
    years, months = divmod(max(0, total_months), 12)
    parts: list[str] = []
    if years:
        parts.append(f"{years} year" if years == 1 else f"{years} years")
    if months or not parts:
        parts.append(f"{months} month" if months == 1 else f"{months} months")
    return " ".join(parts)


def summarize_total_experience(
    experience_entries: Iterable[dict[str, Any]],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    intervals: list[tuple[int, int]] = []
    for entry in experience_entries:
        start_raw = entry.get("start_date") or ""
        end_raw = entry.get("end_date") or ""
        if (not start_raw or not end_raw) and entry.get("duration"):
            start_guess, end_guess = extract_date_range(str(entry.get("duration") or ""))
            start_raw = start_raw or start_guess or ""
            end_raw = end_raw or end_guess or ""

        start = parse_month_token(str(start_raw), is_end=False, today=today)
        end = parse_month_token(str(end_raw), is_end=True, today=today)
        if start is None or end is None:
            continue

        start_idx = month_index(start)
        end_idx = month_index(end)
        if end_idx >= start_idx:
            intervals.append((start_idx, end_idx))

    merged = merge_month_intervals(intervals)
    total_months = sum((end - start) + 1 for start, end in merged)
    total_years_float = round(total_months / 12.0, 2)
    return {
        "total_experience_months": total_months,
        "total_experience_years_float": total_years_float,
        "total_experience_years": total_years_float,
        "total_experience_display": format_months_display(total_months),
        "experience_intervals_merged": merged,
    }


def role_hint_score(value: str) -> int:
    return len(ROLE_HINT_RE.findall(clean_text_line(value)))


def looks_like_role(value: str) -> bool:
    return role_hint_score(value) > 0


def looks_like_location(value: str) -> bool:
    line = clean_text_line(value)
    if not line:
        return False
    if LOCATION_RE.search(line):
        return True
    if "," in line and len(line.split()) <= 6 and not looks_like_role(line):
        return True
    return False


def looks_like_company(value: str) -> bool:
    line = clean_text_line(value)
    if not line or looks_like_location(line):
        return False
    if COMPANY_HINT_RE.search(line):
        return True
    if len(line.split()) <= 4 and not line.endswith("."):
        if line.isupper() or all(token[:1].isupper() for token in line.split() if token[:1].isalpha()):
            return True
    return False


def maybe_swap_role_company(role: str, company: str) -> tuple[str, str]:
    role_clean = clean_text_line(role)
    company_clean = clean_text_line(company)
    if not role_clean and company_clean:
        return role_clean, company_clean
    if looks_like_role(role_clean) and not looks_like_role(company_clean):
        return role_clean, company_clean
    if looks_like_role(company_clean) and not looks_like_role(role_clean):
        return company_clean, role_clean
    if looks_like_company(role_clean) and not looks_like_company(company_clean):
        return company_clean, role_clean
    return role_clean, company_clean


def normalize_experience_entry(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any] | None:
    role = clean_text_line(
        str(entry.get("role") or entry.get("job_title") or entry.get("title") or "")
    )
    company = clean_text_line(
        str(
            entry.get("company")
            or entry.get("company_name")
            or entry.get("organization")
            or entry.get("employer")
            or ""
        )
    )
    location = clean_text_line(str(entry.get("location") or entry.get("place") or ""))
    start_date = canonical_date_display(str(entry.get("start_date") or ""))
    end_date = canonical_date_display(str(entry.get("end_date") or ""))

    if (not start_date or not end_date) and entry.get("duration"):
        inferred_start, inferred_end = extract_date_range(str(entry.get("duration") or ""))
        start_date = start_date or canonical_date_display(inferred_start)
        end_date = end_date or canonical_date_display(inferred_end)

    role, company = maybe_swap_role_company(role, company)

    bullets_raw = entry.get("bullets", entry.get("description", []))
    bullets: list[str] = []
    if isinstance(bullets_raw, list):
        bullets = [clean_text_line(value) for value in bullets_raw if clean_text_line(str(value))]
    elif isinstance(bullets_raw, str):
        bullets = [clean_text_line(value) for value in str(bullets_raw).splitlines() if clean_text_line(value)]

    duration_months, is_present = compute_duration_months(start_date, end_date, today=today)
    duration = " - ".join(part for part in [start_date, end_date] if part)
    header = " | ".join(part for part in [role, company] if part)
    years = YEAR_RE.findall(duration)
    date_ranges = []
    if start_date and end_date:
        date_ranges = [(start_date, end_date)]

    if not (role or company or location or start_date or end_date or bullets):
        return None

    return {
        "company": company,
        "role": role,
        "location": location,
        "start_date": start_date,
        "end_date": end_date,
        "is_present": is_present,
        "duration_months": duration_months,
        "bullets": bullets,
        "header": header,
        "job_title": role,
        "title": role,
        "duration": duration,
        "date_ranges": date_ranges,
        "years": years,
        "skills_inferred": list(entry.get("skills_inferred") or []),
        "link": entry.get("link"),
    }


def normalize_experience_entries(entries: Iterable[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        item = normalize_experience_entry(entry, today=today)
        if item:
            normalized.append(item)
    return normalized


def split_items_outside_parentheses(text: str, separators: set[str] | None = None) -> list[str]:
    separators = separators or {",", ";", "|"}
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for char in text:
        if char == "(":
            depth += 1
            current.append(char)
            continue
        if char == ")":
            depth = max(0, depth - 1)
            current.append(char)
            continue
        if char in separators and depth == 0:
            token = clean_text_line("".join(current))
            if token:
                parts.append(token)
            current = []
            continue
        current.append(char)

    token = clean_text_line("".join(current))
    if token:
        parts.append(token)
    return parts


def normalize_skill_key(value: str) -> str:
    cleaned = clean_text_line(value).lower()
    cleaned = cleaned.strip(":-")
    cleaned = cleaned.replace("&", " & ")
    cleaned = re.sub(r"[._]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return SKILL_ALIAS_MAP.get(cleaned, cleaned)


def skill_display_label(value: str) -> str:
    canonical = normalize_skill_key(value)
    if canonical in SKILL_DISPLAY_MAP:
        return SKILL_DISPLAY_MAP[canonical]
    return " ".join(part.capitalize() for part in canonical.split())


def _should_join_skill_lines(current: str, next_line: str) -> bool:
    current_clean = clean_text_line(current)
    next_clean = clean_text_line(next_line)
    if not current_clean or not next_clean:
        return False
    if any(marker in current_clean for marker in [":", "|", ",", "/", "(", ")"]):
        return False
    if any(marker in next_clean for marker in [":", "|", ",", "/", "(", ")"]):
        return False
    current_words = current_clean.split()
    next_words = next_clean.split()
    if len(current_words) > 3 or len(next_words) > 3:
        return False

    current_key = normalize_skill_key(current_clean)
    next_key = normalize_skill_key(next_clean)
    if current_key in SKILL_JOIN_PREFIXES or next_key in SKILL_JOIN_SUFFIXES:
        return True
    if len(current_words) == 1 and len(next_words) == 1:
        return current_key in SKILL_JOIN_PREFIXES or next_key in SKILL_JOIN_SUFFIXES
    return False


def _normalize_skill_lines(skill_section: str) -> list[str]:
    raw_lines = [clean_text_line(line) for line in str(skill_section or "").splitlines() if clean_text_line(line)]
    if not raw_lines:
        return []

    normalized: list[str] = []
    pending = ""
    pending_is_category = False

    for line in raw_lines:
        if ":" in line:
            if pending:
                normalized.append(pending)
            pending = line
            pending_is_category = True
            continue

        if pending and pending_is_category:
            pending = f"{pending} {line}".strip()
            continue

        if pending and _should_join_skill_lines(pending, line):
            pending = f"{pending} {line}".strip()
            continue

        if pending:
            normalized.append(pending)
        pending = line
        pending_is_category = False

    if pending:
        normalized.append(pending)

    return normalized


def _should_emit_child_as_top_level(child: str, parent: str) -> bool:
    child_key = normalize_skill_key(child)
    parent_key = normalize_skill_key(parent)
    if not child_key or child_key in CHILD_ONLY_SKILLS:
        return False
    if parent_key == "excel" and child_key in {"basic statistics", "chart", "charts", "pivot table", "pivot tables"}:
        return False
    return True


def _looks_like_tool_blob(value: str) -> bool:
    clean = clean_text_line(value)
    if not clean:
        return False
    lowered = clean.lower()
    for label in ("tools:", "technologies:", "tech stack:", "stack:"):
        if lowered.startswith(label):
            return True
    tool_items = normalize_tool_list(clean.split(":", 1)[1] if ":" in clean else clean)
    if len(tool_items) >= 2:
        short_items = sum(1 for item in tool_items if len(item.split()) <= 4)
        return short_items == len(tool_items)
    return False


def _looks_like_project_organization(value: str) -> bool:
    clean = clean_text_line(value)
    if not clean or looks_like_location(clean) or _looks_like_tool_blob(clean):
        return False
    if looks_like_company(clean):
        return True
    if "|" in clean:
        return False
    words = clean.split()
    if 1 <= len(words) <= 5 and clean[0].isupper() and not looks_like_role(clean):
        return True
    return False


def _parse_project_title_tools_line(value: str) -> tuple[str, list[str]]:
    clean = clean_text_line(value)
    if not clean:
        return "", []

    lowered = clean.lower()
    for label in ("tools:", "technologies:", "tech stack:", "stack:"):
        if lowered.startswith(label):
            return "", normalize_tool_list(clean.split(":", 1)[1])

    parts = split_items_outside_parentheses(clean, separators={"|"})
    if len(parts) >= 2:
        trailing = " | ".join(parts[1:])
        if _looks_like_tool_blob(trailing):
            return parts[0], normalize_tool_list(", ".join(parts[1:]))
    return clean, []


def _is_year_only_line(value: str) -> bool:
    clean = clean_text_line(value).strip("()[]")
    return bool(re.fullmatch(r"(?:19|20)\d{2}", clean))


def _extract_year_token(value: str) -> str:
    match = YEAR_RE.search(clean_text_line(value))
    return match.group(1) if match else ""


def _parse_certification_line(value: str) -> dict[str, Any]:
    line = clean_text_line(value)
    credential_match = re.search(
        r"\b(?:credential(?:\s+id)?|license(?:\s+number)?|id)\s*[:#-]?\s*([A-Za-z0-9-]+)\b",
        line,
        re.IGNORECASE,
    )
    credential_id = clean_text_line(credential_match.group(1)) if credential_match else ""
    content = re.sub(
        r"\b(?:credential(?:\s+id)?|license(?:\s+number)?|id)\s*[:#-]?\s*[A-Za-z0-9-]+\b",
        "",
        line,
        flags=re.IGNORECASE,
    )

    segments = [part for part in split_items_outside_parentheses(content, separators={"|"}) if part]
    if len(segments) == 1 and " - " in content:
        dash_parts = [clean_text_line(part) for part in content.split(" - ") if clean_text_line(part)]
        if len(dash_parts) == 2:
            segments = dash_parts

    year = ""
    cleaned_segments: list[str] = []
    for segment in segments:
        segment_year = _extract_year_token(segment)
        if segment_year and not year:
            year = segment_year
        stripped = re.sub(r"\b(19\d{2}|20\d{2})\b", "", segment).strip(" |-,")
        if stripped:
            cleaned_segments.append(stripped)

    name = cleaned_segments[0] if cleaned_segments else ""
    issuer = cleaned_segments[1] if len(cleaned_segments) >= 2 else ""

    if not issuer and name and " via " in name.lower():
        issuer = name.split(" via ", 1)[1].strip()

    return {
        "name": name,
        "issuer": issuer,
        "year": year,
        "credential_id": credential_id,
    }


def parse_skill_mentions(skill_section: str) -> dict[str, dict[str, Any]]:
    lines = _normalize_skill_lines(skill_section)
    parsed: dict[str, dict[str, Any]] = {}

    def upsert(skill_name: str, *, parent: str | None = None, alias: str | None = None) -> None:
        canonical = normalize_skill_key(skill_name)
        if not canonical or len(canonical) < 2:
            return
        if parent:
            parent_canonical = normalize_skill_key(parent)
            parent_record = parsed.setdefault(
                parent_canonical,
                {
                    "canonical_key": parent_canonical,
                    "display_label": skill_display_label(parent_canonical),
                    "aliases": [],
                    "child_skills": [],
                },
            )
            if canonical != parent_canonical and canonical not in parent_record["child_skills"]:
                parent_record["child_skills"].append(canonical)
            if not _should_emit_child_as_top_level(canonical, parent_canonical):
                if alias and alias not in parent_record["aliases"]:
                    parent_record["aliases"].append(alias)
                return

        if canonical in SKILL_NOISE_TOKENS:
            return

        record = parsed.setdefault(
            canonical,
            {
                "canonical_key": canonical,
                "display_label": skill_display_label(canonical),
                "aliases": [],
                "child_skills": [],
            },
        )
        if alias and alias not in record["aliases"]:
            record["aliases"].append(alias)

    for line in lines:
        payload = line.split(":", 1)[1] if ":" in line and len(line.split(":", 1)[0].split()) <= 4 else line
        for item in split_items_outside_parentheses(payload):
            if " & " in item and len(item.split()) <= 6 and "(" not in item:
                for part in item.split(" & "):
                    upsert(part, alias=item)
                continue

            match = re.fullmatch(r"(?P<base>.+?)\s*\((?P<children>.+)\)", item)
            if match:
                base = clean_text_line(match.group("base"))
                upsert(base, alias=item)
                for child in re.split(r",|/|&", match.group("children")):
                    child_clean = clean_text_line(child)
                    if child_clean:
                        upsert(child_clean, parent=base, alias=item)
                continue

            upsert(item)

    for record in parsed.values():
        record["aliases"].sort()
        record["child_skills"].sort()
    return parsed


def normalize_tool_list(value: Any) -> list[str]:
    raw_items: list[str] = []
    if isinstance(value, list):
        raw_items = [clean_text_line(str(item)) for item in value if clean_text_line(str(item))]
    elif isinstance(value, str):
        raw_items = split_items_outside_parentheses(value, separators={",", ";", "|", "/"})

    seen: set[str] = set()
    normalized: list[str] = []
    for item in raw_items:
        clean = clean_text_line(item)
        if clean and clean.lower() not in seen:
            normalized.append(clean)
            seen.add(clean.lower())
    return normalized


def normalize_project_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_text_line(str(entry.get("title") or entry.get("name") or entry.get("project_name") or ""))
    organization = clean_text_line(
        str(entry.get("organization") or entry.get("client") or entry.get("issuer") or "")
    )
    tools = normalize_tool_list(entry.get("tools", entry.get("technologies", [])))

    bullets_raw = entry.get("bullets", entry.get("description", []))
    bullets: list[str] = []
    if isinstance(bullets_raw, list):
        bullets = [clean_text_line(value) for value in bullets_raw if clean_text_line(str(value))]
    elif isinstance(bullets_raw, str):
        bullets = [
            strip_bullet_prefix(line)
            for line in str(bullets_raw).splitlines()
            if strip_bullet_prefix(line)
        ]

    if not title and entry.get("text"):
        title = clean_text_line(str(entry.get("text") or ""))

    if not (title or organization or tools or bullets):
        return None

    return {
        "title": title,
        "organization": organization,
        "tools": tools,
        "bullets": bullets,
        "name": title,
        "technologies": tools,
        "text": " | ".join(part for part in [title, organization] if part),
        "description": "\n".join(bullets),
        "link": entry.get("link"),
    }


def normalize_certification_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    name = clean_text_line(str(entry.get("name") or entry.get("title") or ""))
    issuer = clean_text_line(str(entry.get("issuer") or entry.get("organization") or ""))
    year = clean_text_line(str(entry.get("year") or ""))
    credential_id = clean_text_line(
        str(entry.get("credential_id") or entry.get("credential") or entry.get("credentialId") or "")
    )

    if not credential_id:
        text = " | ".join(part for part in [name, issuer, year] if part)
        match = re.search(r"\b(?:credential(?:\s+id)?|license(?:\s+number)?|id)\s*[:#-]?\s*([A-Za-z0-9-]+)\b", text, re.I)
        if match:
            credential_id = clean_text_line(match.group(1))

    if not (name or issuer or year or credential_id):
        return None

    return {
        "name": name,
        "issuer": issuer,
        "year": year,
        "credential_id": credential_id or None,
        "text": " | ".join(part for part in [name, issuer, year] if part),
    }


def parse_project_header(header_lines: list[str]) -> tuple[str, str, list[str]]:
    lines = [clean_text_line(line) for line in header_lines if clean_text_line(line)]
    if not lines:
        return "", "", []

    title = ""
    organization = ""
    tools: list[str] = []

    consumed = 0
    if len(lines) >= 2:
        first = lines[0]
        second = lines[1]
        second_title, second_tools = _parse_project_title_tools_line(second)
        first_title, first_tools = _parse_project_title_tools_line(first)

        if _looks_like_project_organization(first) and second_title:
            organization = first
            title = second_title
            tools.extend(second_tools)
            consumed = 2
        elif _looks_like_project_organization(second) and first_title:
            organization = second
            title = first_title
            tools.extend(first_tools)
            consumed = 2

    if not consumed:
        first = lines[0]
        parts = split_items_outside_parentheses(first, separators={"|"})
        if len(parts) >= 3 and _looks_like_tool_blob(" | ".join(parts[2:])):
            if _looks_like_project_organization(parts[0]) and not _looks_like_project_organization(parts[1]):
                organization = parts[0]
                title = parts[1]
            else:
                title = parts[0]
                organization = parts[1]
            tools = normalize_tool_list(", ".join(parts[2:]))
            consumed = 1
        elif len(parts) == 2:
            if _looks_like_tool_blob(parts[1]):
                title = parts[0]
                tools = normalize_tool_list(parts[1])
            elif _looks_like_project_organization(parts[0]) and not _looks_like_project_organization(parts[1]):
                organization = parts[0]
                title = parts[1]
            elif _looks_like_project_organization(parts[1]) and not _looks_like_project_organization(parts[0]):
                title = parts[0]
                organization = parts[1]
            else:
                title = parts[0]
                organization = parts[1]
            consumed = 1
        elif " at " in first.lower():
            left, right = re.split(r"\bat\b", first, maxsplit=1, flags=re.IGNORECASE)
            title = clean_text_line(left)
            organization = clean_text_line(right)
            consumed = 1
        else:
            parsed_title, parsed_tools = _parse_project_title_tools_line(first)
            title = parsed_title
            tools.extend(parsed_tools)
            consumed = 1

    for line in lines[consumed:]:
        lowered = line.lower()
        if lowered.startswith(("tools:", "technologies:", "tech stack:", "stack:")):
            tools.extend(normalize_tool_list(line.split(":", 1)[1]))
            continue
        if not organization and _looks_like_project_organization(line):
            organization = line
            continue
        if (not tools) and _looks_like_tool_blob(line):
            tools.extend(normalize_tool_list(line.split(":", 1)[1] if ":" in line else line))
            continue
        if not title:
            parsed_title, parsed_tools = _parse_project_title_tools_line(line)
            title = parsed_title
            tools.extend(parsed_tools)
            continue
        if not organization and not looks_like_location(line):
            organization = line
            continue
        title = " ".join(part for part in [title, line] if part).strip()

    deduped_tools = normalize_tool_list(tools)
    return title, organization, deduped_tools


def parse_project_section_lines(lines: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    header_lines: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        nonlocal header_lines, bullets
        title, organization, tools = parse_project_header(header_lines)
        entry = normalize_project_entry(
            {
                "title": title,
                "organization": organization,
                "tools": tools,
                "bullets": bullets,
            }
        )
        if entry:
            entries.append(entry)
        header_lines = []
        bullets = []

    for raw_line in lines:
        line = clean_text_line(str(raw_line))
        if not line:
            continue
        if BULLET_PREFIX_RE.match(line):
            bullets.append(strip_bullet_prefix(line))
            continue
        if bullets and line[:1].islower():
            bullets[-1] = f"{bullets[-1]} {line}".strip()
            continue
        if bullets:
            flush()
        header_lines.append(line)

    if header_lines or bullets:
        flush()

    return entries


def parse_certification_lines(lines: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    normalized_lines = [clean_text_line(str(raw_line)) for raw_line in lines if clean_text_line(str(raw_line))]
    idx = 0
    while idx < len(normalized_lines):
        line = normalized_lines[idx]
        if _is_year_only_line(line):
            if entries and not entries[-1].get("year"):
                entries[-1]["year"] = _extract_year_token(line)
                entries[-1]["text"] = " | ".join(
                    part for part in [entries[-1].get("name"), entries[-1].get("issuer"), entries[-1].get("year")] if part
                )
            idx += 1
            continue

        parsed_entry = _parse_certification_line(line)
        if idx + 1 < len(normalized_lines) and _is_year_only_line(normalized_lines[idx + 1]) and not parsed_entry.get("year"):
            parsed_entry["year"] = _extract_year_token(normalized_lines[idx + 1])
            idx += 1

        entry = normalize_certification_entry(parsed_entry)
        if entry:
            entries.append(entry)
        idx += 1
    return entries


def normalize_url_candidate(url: str) -> str | None:
    candidate = clean_text_line(unquote(url)).strip(".,);]")
    if not candidate:
        return None
    if re.match(r"^(?:linkedin\.com|github\.com|www\.)", candidate, re.IGNORECASE):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def is_placeholder_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower().strip("/")
    query = parse_qs(parsed.query)
    decoded_query = " ".join(unquote(value) for values in query.values() for value in values).lower()

    if host in {"example.com", "www.example.com"}:
        return True
    if host.endswith("google.com") and parsed.path.startswith("/search"):
        return True

    candidate_text = " ".join(part for part in [host, path, decoded_query] if part)
    return any(token in candidate_text for token in PLACEHOLDER_TOKENS)


def validated_profile_url(url: str | None, *, platform: str | None = None) -> str | None:
    if not url:
        return None
    normalized = normalize_url_candidate(url)
    if not normalized or is_placeholder_url(normalized):
        return None

    parsed = urlparse(normalized)
    host = parsed.netloc.lower()
    path = parsed.path.lower().strip("/")
    if platform == "linkedin":
        if "linkedin.com" not in host or not path.startswith("in/"):
            return None
        if path in {"in", "in/", "pub"}:
            return None
    if platform == "github":
        if "github.com" not in host:
            return None
        if not path or "/" in path.strip("/"):
            return normalized if path and not is_placeholder_url(normalized) else None
    return normalized


def extract_validated_links(text: str, hyperlink_urls: Iterable[str] | None = None) -> dict[str, str | None]:
    candidates: list[str] = []
    for url in hyperlink_urls or []:
        if url:
            candidates.append(str(url))
    candidates.extend(LINKEDIN_TEXT_RE.findall(text))
    candidates.extend(GITHUB_TEXT_RE.findall(text))
    candidates.extend(URL_RE.findall(text))

    linkedin = None
    github = None
    portfolio = None

    for candidate in candidates:
        normalized = normalize_url_candidate(candidate)
        if not normalized:
            continue

        host = urlparse(normalized).netloc.lower()
        if "linkedin.com" in host:
            linkedin = linkedin or validated_profile_url(normalized, platform="linkedin")
            continue
        if "github.com" in host:
            github = github or validated_profile_url(normalized, platform="github")
            continue
        if portfolio is None and not is_placeholder_url(normalized):
            portfolio = normalized

    return {
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
    }
