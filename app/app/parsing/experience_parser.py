"""Parses the EXPERIENCE section into distinct structural blocks."""

from __future__ import annotations

import logging
import re
from typing import Any

from .pdf_extractor import TokenLine
from .structured_utils import (
    DATE_RANGE_RE,
    YEAR_RE,
    clean_text_line,
    extract_date_range,
    looks_like_company,
    looks_like_location,
    looks_like_role,
    maybe_swap_role_company,
    normalize_dash_text,
    strip_bullet_prefix,
)

logger = logging.getLogger(__name__)

BULLET_PREFIX_RE = re.compile(r"^\s*[\u2022\u25cf\u25aa\u25b8\uf0b7\uf0a7\-\*]+(?:\s|\u200b|\u200c|\u200d)*")
RESPONSIBILITY_LABEL_RE = re.compile(r"^(?:key\s+responsibilities?|responsibilities?|highlights?)\s*:?", re.I)


def _clean_job_field(text: str) -> str:
    return re.sub(r"^[-|\u2022\uf0b7\uf0a7,\\_]+|[-|\u2022\uf0b7\uf0a7,\\_]+$", "", clean_text_line(text)).strip()


def _normalize_line_text(text: str) -> str:
    return clean_text_line(text).replace("\uf0b7", "\u2022").replace("\uf0a7", "\u2022")


def _contains_date_token(text: str) -> bool:
    line = normalize_dash_text(text)
    start, end = extract_date_range(line)
    return bool((start and end) or YEAR_RE.search(line))


def _is_date_only_line(text: str) -> bool:
    stripped = _normalize_line_text(text)
    if not stripped or not _contains_date_token(stripped):
        return False
    return not _strip_dates(stripped)


def _strip_dates(text: str) -> str:
    line = normalize_dash_text(text)
    return DATE_RANGE_RE.sub("", line).strip(" |,-")


def _normalize_bullet_text(text: str) -> str:
    return strip_bullet_prefix(text)


def _is_responsibility_label(text: str) -> bool:
    return bool(RESPONSIBILITY_LABEL_RE.match(_normalize_line_text(text)))


def _looks_like_standalone_company(text: str, next_text: str = "") -> bool:
    line = _clean_job_field(text)
    if not line or line.endswith(".") or BULLET_PREFIX_RE.match(line):
        return False
    if looks_like_location(line) or looks_like_role(line):
        return False
    if len(line.split()) > 5:
        return False
    if not _looks_like_companyish_text(line):
        return False
    next_clean = _clean_job_field(next_text)
    return not next_clean or _is_date_only_line(next_clean) or _looks_like_new_role_header(next_clean)


def _looks_like_companyish_text(text: str) -> bool:
    line = _clean_job_field(text)
    if not line or looks_like_role(line):
        return False
    lowered = line.lower()
    if re.search(r"\b(club|trust|bank|school|college|foundation|association|organization|institute)\b", lowered):
        return True
    if "," in line:
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) >= 2 and len(parts[-1]) <= 3:
            return False
    return looks_like_company(line)


def split_title_company(text: str) -> tuple[str, str | None]:
    clean = _clean_job_field(text)

    if "|" in clean:
        parts = [part.strip() for part in re.split(r"\|+", clean) if part.strip()]
        if len(parts) >= 2:
            left = parts[0]
            right = parts[1]
            if looks_like_role(right) and (looks_like_company(left) or "," in left):
                return right, left
            if looks_like_company(left) and looks_like_role(right):
                return right, left
            return left, right
        return parts[0], None

    lowered = clean.lower()
    if " at " in lowered:
        left, right = re.split(r"\bat\b", clean, maxsplit=1, flags=re.I)
        return left.strip(), right.strip() or None

    parts = [part.strip() for part in clean.split(",") if part.strip()]
    if len(parts) >= 2:
        left = ", ".join(parts[:-1]).strip()
        right = parts[-1].strip()
        if looks_like_role(left) and not looks_like_role(right):
            return left, right or None
        if looks_like_role(parts[0]) and looks_like_company(right):
            return parts[0], right

    return clean, None


def extract_dates(text: str) -> tuple[str | None, str | None]:
    return extract_date_range(text)


def is_job_header(line: TokenLine, avg_font_size: float, next_text: str = "") -> bool:
    text = _normalize_line_text(line.text)
    if not text or BULLET_PREFIX_RE.match(text):
        return False
    return (
        "|" in text
        or _contains_date_token(text)
        or _looks_like_standalone_company(text, next_text)
        or _looks_like_new_role_header(text)
        or (avg_font_size > 0 and line.font_size > avg_font_size * 1.1)
    )


def _looks_like_new_role_header(text: str) -> bool:
    line = _clean_job_field(text)
    if not line or BULLET_PREFIX_RE.match(line) or line.endswith(".") or _is_date_only_line(line):
        return False
    if len(line.split()) > 12:
        return False
    if looks_like_role(line):
        return True
    if "|" in line or " at " in line.lower():
        return True
    return bool("," in line and looks_like_company(line) and looks_like_role(line))


def _new_job() -> dict[str, Any]:
    return {
        "job_title": "",
        "company": "",
        "location": "",
        "start_date": "",
        "end_date": "",
        "date_string": "",
        "description": [],
    }


def _has_job_content(job: dict[str, Any]) -> bool:
    return bool(
        job.get("job_title")
        or job.get("company")
        or job.get("location")
        or job.get("start_date")
        or job.get("end_date")
        or job.get("description")
    )


def _is_experience_section_heading(text: str) -> bool:
    normalized = _normalize_line_text(text).lower().strip(" :")
    return normalized in {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "career history",
        "internship experience",
    }


def _is_strong_job_boundary(text: str, next_text: str, current_job: dict[str, Any]) -> bool:
    line = _clean_job_field(text)
    if not line:
        return False
    if _looks_like_standalone_company(line, next_text):
        return True
    if _contains_date_token(line) and (looks_like_role(_strip_dates(line)) or looks_like_company(_strip_dates(line))):
        return True
    if _looks_like_new_role_header(line) and (
        _is_date_only_line(next_text) or _looks_like_standalone_company(next_text) or current_job.get("description")
    ):
        return True
    return False


class ExperienceParser:
    """Split experience lines into job dictionaries."""

    def parse(self, experience_lines: list[TokenLine]) -> list[dict[str, Any]]:
        if not experience_lines:
            return []

        jobs: list[dict[str, Any]] = []
        current_job = _new_job()
        pending_bullet_marker = False
        freeform_bullet_mode = False

        y_gaps: list[float] = []
        font_sizes = [line.font_size for line in experience_lines if line.text.strip()]
        for idx in range(1, len(experience_lines)):
            prev_line = experience_lines[idx - 1]
            curr_line = experience_lines[idx]
            if prev_line.page == curr_line.page:
                gap = curr_line.bbox[1] - prev_line.bbox[3]
                if gap > 0:
                    y_gaps.append(gap)

        avg_gap = sum(y_gaps) / len(y_gaps) if y_gaps else 12.0
        block_gap_threshold = avg_gap * 1.8
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0.0

        for idx, line in enumerate(experience_lines):
            text = _normalize_line_text(line.text)
            next_text = _normalize_line_text(experience_lines[idx + 1].text) if idx + 1 < len(experience_lines) else ""
            if not text or _is_experience_section_heading(text):
                continue

            if BULLET_PREFIX_RE.match(text):
                bullet = _normalize_bullet_text(text)
                if bullet:
                    current_job["description"].append(bullet)
                    pending_bullet_marker = False
                else:
                    pending_bullet_marker = True
                continue

            if pending_bullet_marker:
                if _is_strong_job_boundary(text, next_text, current_job):
                    pending_bullet_marker = False
                else:
                    current_job["description"].append(text)
                    pending_bullet_marker = False
                    continue

            if _is_responsibility_label(text):
                freeform_bullet_mode = True
                continue

            header_detected = is_job_header(line, avg_font_size, next_text)
            date_only_line = _is_date_only_line(text)

            if (
                current_job.get("company")
                and (current_job.get("start_date") or current_job.get("end_date"))
                and not current_job.get("job_title")
                and _looks_like_new_role_header(text)
                and not current_job.get("description")
            ):
                _, company = split_title_company(text)
                current_job["job_title"] = _clean_job_field(text)
                if company and not current_job.get("company"):
                    current_job["company"] = _clean_job_field(company)
                continue

            if (
                current_job.get("job_title")
                and (current_job.get("start_date") or current_job.get("end_date"))
                and not current_job.get("company")
                and not current_job.get("description")
                and _looks_like_new_role_header(text)
                and not looks_like_role(current_job.get("job_title") or "")
            ):
                current_job["company"] = _clean_job_field(current_job.get("job_title") or "")
                current_job["job_title"] = _clean_job_field(text)
                continue

            if (
                current_job.get("job_title")
                and (current_job.get("start_date") or current_job.get("end_date"))
                and not current_job.get("company")
                and not current_job.get("description")
                and not date_only_line
                and not _looks_like_new_role_header(text)
                and not BULLET_PREFIX_RE.match(text)
            ):
                if _looks_like_companyish_text(text):
                    current_job["company"] = _clean_job_field(text)
                elif looks_like_location(text):
                    current_job["location"] = _clean_job_field(text)
                else:
                    current_job["company"] = _clean_job_field(text)
                continue

            if (
                (current_job.get("company") or current_job.get("job_title"))
                and (current_job.get("start_date") or current_job.get("end_date"))
                and looks_like_location(text)
                and not current_job.get("description")
            ):
                current_job["location"] = _clean_job_field(text)
                continue

            if freeform_bullet_mode:
                if _is_strong_job_boundary(text, next_text, current_job):
                    freeform_bullet_mode = False
                else:
                    current_job["description"].append(text)
                    continue

            if (
                current_job["description"]
                and not date_only_line
                and not BULLET_PREFIX_RE.match(text)
                and not _is_strong_job_boundary(text, next_text, current_job)
            ):
                current_job["description"][-1] = f"{current_job['description'][-1]} {text}".strip()
                continue

            if date_only_line and _has_job_content(current_job) and not current_job["description"]:
                start_date, end_date = extract_dates(text)
                if start_date and not current_job.get("start_date"):
                    current_job["start_date"] = start_date
                if end_date and not current_job.get("end_date"):
                    current_job["end_date"] = end_date
                if current_job.get("start_date"):
                    current_job["date_string"] = (
                        f"{current_job['start_date']} - {current_job['end_date']}"
                        if current_job.get("end_date")
                        else current_job["start_date"]
                    )
                continue

            if _is_strong_job_boundary(text, next_text, current_job) and _has_job_content(current_job):
                if current_job.get("description") or current_job.get("job_title") or current_job.get("company"):
                    jobs.append(self._finalize_job(current_job))
                    current_job = _new_job()
                    freeform_bullet_mode = False

            start_date, end_date = extract_dates(text)
            header_text = _strip_dates(text)

            if _looks_like_standalone_company(text, next_text) and not current_job.get("company"):
                current_job["company"] = _clean_job_field(text)
            elif header_text:
                title, company = split_title_company(header_text)
                title_clean = _clean_job_field(title)
                company_clean = _clean_job_field(company or "")

                if start_date and not company_clean and title_clean and not looks_like_role(title_clean):
                    if not current_job.get("company"):
                        current_job["company"] = title_clean
                    elif not current_job.get("job_title"):
                        current_job["job_title"] = title_clean
                else:
                    if title_clean and not current_job.get("job_title") and not _looks_like_standalone_company(title_clean, next_text):
                        current_job["job_title"] = title_clean
                if company_clean and not current_job.get("company"):
                    current_job["company"] = company_clean

            if (
                not current_job.get("job_title")
                and _looks_like_new_role_header(text)
                and not _looks_like_standalone_company(text, next_text)
                and (looks_like_role(text) or looks_like_role(header_text))
            ):
                title, company = split_title_company(text)
                current_job["job_title"] = _clean_job_field(title)
                if company and not current_job.get("company"):
                    current_job["company"] = _clean_job_field(company)

            if looks_like_location(text) and not current_job.get("location") and not current_job.get("description"):
                current_job["location"] = _clean_job_field(text)

            if start_date:
                current_job["start_date"] = current_job.get("start_date") or start_date
            if end_date:
                current_job["end_date"] = current_job.get("end_date") or end_date

            if current_job.get("start_date"):
                current_job["date_string"] = (
                    f"{current_job['start_date']} - {current_job['end_date']}"
                    if current_job.get("end_date")
                    else current_job["start_date"]
                )

            if idx > 0:
                prev_line = experience_lines[idx - 1]
                if prev_line.page == line.page:
                    gap = line.bbox[1] - prev_line.bbox[3]
                    if gap > block_gap_threshold and _has_job_content(current_job) and current_job["description"]:
                        jobs.append(self._finalize_job(current_job))
                        current_job = _new_job()
                        freeform_bullet_mode = False

            if header_detected and not current_job.get("job_title") and not current_job.get("company"):
                current_job["job_title"] = _clean_job_field(header_text or text)

        if _has_job_content(current_job):
            jobs.append(self._finalize_job(current_job))

        merged_jobs = self._merge_fragmented_jobs(jobs)
        logger.debug(
            "Experience parser debug: parsed_entries=%s entries=%s",
            len(merged_jobs),
            [
                {
                    "job_title": job.get("job_title"),
                    "company": job.get("company"),
                    "date_string": job.get("date_string"),
                    "description_count": len(job.get("description", [])),
                }
                for job in merged_jobs
            ],
        )
        return merged_jobs

    def _merge_fragmented_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(jobs) < 2:
            return jobs

        merged: list[dict[str, Any]] = []
        idx = 0
        while idx < len(jobs):
            current = dict(jobs[idx])

            if idx + 1 < len(jobs):
                nxt = jobs[idx + 1]
                current_has_dates = bool(current.get("start_date"))
                current_has_desc = bool(current.get("description"))
                next_has_dates = bool(nxt.get("start_date"))
                next_has_desc = bool(nxt.get("description"))
                next_role = _clean_job_field(nxt.get("job_title") or "")

                if current_has_dates and not current_has_desc and next_role and not next_has_dates and next_has_desc:
                    role = _clean_job_field(current.get("job_title") or "")
                    if role and next_role.lower() not in role.lower():
                        current["job_title"] = f"{role} - {next_role}".strip(" -")
                    elif not role:
                        current["job_title"] = next_role
                    current["description"] = list(nxt.get("description") or [])
                    if not current.get("company") and nxt.get("company"):
                        current["company"] = nxt.get("company")
                    if not current.get("location") and nxt.get("location"):
                        current["location"] = nxt.get("location")
                    merged.append(self._finalize_job(current))
                    idx += 2
                    continue

            merged.append(self._finalize_job(current))
            idx += 1

        return merged

    def _finalize_job(self, job: dict[str, Any]) -> dict[str, Any]:
        role, company = maybe_swap_role_company(
            _clean_job_field(job.get("job_title") or ""),
            _clean_job_field(job.get("company") or ""),
        )
        return {
            "job_title": role,
            "company": company,
            "location": _clean_job_field(job.get("location") or ""),
            "start_date": _clean_job_field(job.get("start_date") or ""),
            "end_date": _clean_job_field(job.get("end_date") or ""),
            "date_string": _clean_job_field(job.get("date_string") or ""),
            "description": [clean_text_line(line) for line in job.get("description", []) if clean_text_line(str(line))],
        }
