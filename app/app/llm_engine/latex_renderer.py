"""LaTeX rendering pipeline for structured resume data."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, cast

from app.llm_engine.structured_resume_pipeline import AdditionalSectionEntry, ExperienceEntry, ProjectEntry, ResumeData, SkillsData


LATEX_TEMPLATE = r"""
\documentclass[a4paper,10pt]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=0.5in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=black,
}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\pagestyle{empty}
\raggedright
\sloppy

	itleformat{\section}{\large\bfseries\uppercase}{}{0pt}{}[\titlerule]
	itlespacing{\section}{0pt}{8pt}{6pt}

\begin{document}

\begin{center}
    {\huge \textbf{{{name}}}} \\
    \vspace{4pt}
    {contact_block}
\end{center}

{education_section_start}
{education_block}
{education_section_end}

{experience_section_start}
{experience_block}
{experience_section_end}

{projects_section_start}
{projects_block}
{projects_section_end}

{skills_section_start}
{skills_block}
{skills_section_end}

{certifications_section_start}
{certifications_block}
{certifications_section_end}

\end{document}
""".strip()


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def render_contact(resume_data: ResumeData) -> str:
    c = resume_data.get("contact", {})
    parts: List[str] = []

    location = str(c.get("location", "")).strip()
    if location:
        parts.append(latex_escape(location))

    email = str(c.get("email", "")).strip()
    if email:
        display = latex_escape(email)
        parts.append(rf"\href{{mailto:{email}}}{{{display}}}")

    phone = str(c.get("phone", "")).strip()
    if phone:
        tel_href = re.sub(r"[^+\d]", "", phone)
        display = latex_escape(phone)
        parts.append(rf"\href{{tel:{tel_href}}}{{{display}}}" if tel_href else display)

    linkedin = str(c.get("linkedin", "")).strip()
    if linkedin:
        href = linkedin if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", linkedin) else f"https://{linkedin}"
        parts.append(rf"\href{{{href}}}{{LinkedIn}}")

    github = str(c.get("github", "")).strip()
    if github:
        href = github if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", github) else f"https://{github}"
        parts.append(rf"\href{{{href}}}{{GitHub}}")

    return " | ".join(parts)


def _render_hanging_bullets(items: List[str]) -> str:
    rows: List[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        rows.append(f"\\item {latex_escape(text)}")
    if not rows:
        return ""
    return "\n".join([
        r"\begin{itemize}[noitemsep, topsep=0pt]",
        *rows,
        r"\end{itemize}",
    ])


def render_experience(exp_list: List[ExperienceEntry], location: str = "") -> str:
    output: List[str] = []

    def _normalize_duration(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r"\s*[-–]\s*", " - ", text)
        text = re.sub(r"\b(0?[1-9]|1[0-2])\s*/\s*((?:19|20)\d{2})\b", r"\1/\2", text)
        # Fix OCR-like month splits such as "Oc - ber".
        text = re.sub(r"\b([A-Za-z]{2,})\s+-\s+([A-Za-z]{2,})\b", r"\1\2", text)
        month_repairs = {
            "ocber": "October",
            "septber": "September",
            "novber": "November",
            "decber": "December",
        }
        for broken, repaired in month_repairs.items():
            text = re.sub(rf"\b{broken}\b", repaired, text, flags=re.IGNORECASE)
        text = re.sub(
            r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\s+(Present)\b",
            r"\1 - \2",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    for exp in exp_list:
        title = latex_escape(str(exp.get("title", "")))
        company = latex_escape(str(exp.get("company", "")))
        duration = latex_escape(_normalize_duration(str(exp.get("duration", ""))))
        row_location = str(exp.get("location", "")).strip()
        location_text = latex_escape(row_location or location)
        bullet_lines = _render_hanging_bullets([str(b) for b in exp.get("bullets", [])])
        left_label = company if company else title
        role_label = title if company else ""
        role_segment = f" | \\textit{{{role_label}}}" if role_label else ""
        if duration:
            heading = (
                f"\\noindent\\makebox[\\textwidth][s]"
                f"{{\\textbf{{{left_label}}}{role_segment}\\hfill\\textbf{{{duration}}}}}"
            )
        else:
            heading = f"\\textbf{{{left_label}}}{role_segment}"

        block_lines: List[str] = [heading]
        if location_text:
            block_lines.append(f"{location_text}\\")
        if bullet_lines:
            block_lines.append(bullet_lines)

        block = "\n".join(line for line in block_lines if line).strip()
        output.append(block)
    return "\n\n".join(output)


def _split_project_name_and_duration(name: str, explicit_duration: str = "") -> tuple[str, str]:
    raw_name = str(name or "").strip()
    raw_duration = str(explicit_duration or "").strip()
    if raw_duration:
        return raw_name, raw_duration

    if not raw_name:
        return "", ""

    month_token = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
    point_token = rf"(?:(?:{month_token}\s+)?(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}})"
    date_pattern = re.compile(
        rf"{point_token}\s*[-–]\s*(?:present|{point_token})",
        re.IGNORECASE,
    )
    match = date_pattern.search(raw_name)
    if not match:
        return raw_name, ""

    duration = re.sub(r"\s*[-–]\s*", " - ", match.group(0).strip())
    duration = re.sub(r"\b(0?[1-9]|1[0-2])\s*/\s*((?:19|20)\d{2})\b", r"\1/\2", duration)
    remainder = (raw_name[: match.start()] + " " + raw_name[match.end() :]).strip(" |-\t")
    cleaned_name = re.sub(r"\s{2,}", " ", remainder).strip()
    return (cleaned_name or raw_name), duration


def render_projects(project_list: List[ProjectEntry], location: str = "") -> str:
    output: List[str] = []

    def _extract_project_fields(proj: ProjectEntry) -> tuple[str, str, List[str]]:
        raw_name = str(proj.get("name", "") or "").strip()
        raw_duration = str(proj.get("duration", "") or proj.get("date", "") or proj.get("dates", "")).strip()
        technologies = [str(t).strip() for t in proj.get("technologies", []) if str(t).strip()]

        if "|" in raw_name:
            head, tail = raw_name.split("|", 1)
            raw_name = head.strip()
            if tail.strip() and not technologies:
                technologies = [p.strip() for p in re.split(r",|/", tail) if p.strip()]

        if re.search(r"technologies\s*:", raw_name, re.IGNORECASE):
            head, tail = re.split(r"technologies\s*:", raw_name, maxsplit=1, flags=re.IGNORECASE)
            raw_name = head.strip(" -|:")
            if tail.strip() and not technologies:
                technologies = [p.strip() for p in re.split(r",|/", tail) if p.strip()]

        name, duration = _split_project_name_and_duration(raw_name, raw_duration)
        duration = re.sub(r"\s*[-–]\s*", " - ", duration).strip()
        duration = re.sub(r"\b(0?[1-9]|1[0-2])\s*/\s*((?:19|20)\d{2})\b", r"\1/\2", duration)
        return name, duration, technologies

    for proj in project_list:
        split_name, split_duration, technologies = _extract_project_fields(proj)
        name = latex_escape(split_name)
        duration = latex_escape(split_duration)
        bullet_lines = _render_hanging_bullets([str(b) for b in proj.get("bullets", [])])

        heading = f"\\textbf{{{name}}}"
        if duration:
            heading = (
                f"\\noindent\\makebox[\\textwidth][s]"
                f"{{\\textbf{{{name}}}\\hfill\\textbf{{{duration}}}}}"
            )

        block_lines: List[str] = [heading]
        if technologies:
            tech_text = latex_escape(", ".join(technologies))
            block_lines.append(f"\\textit{{Technologies: {tech_text}}}\\\\")
        if location:
            block_lines.append(f"{latex_escape(location)}\\\\")
        if bullet_lines:
            block_lines.append(bullet_lines)

        block = "\n".join(line for line in block_lines if line).strip()
        output.append(block)
    return "\n\n".join(output)


def render_skills(skills: SkillsData) -> str:
    def _normalize_skill_items(values: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        skip_labels = {
            "programming languages",
            "data science",
            "data visualization",
            "databases",
            "tools",
            "skills",
        }
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            if ":" in text:
                left, right = text.split(":", 1)
                if len(left.split()) <= 4 and right.strip():
                    text = right.strip()
            canonical = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            if not canonical or canonical in skip_labels or canonical in seen:
                continue
            seen.add(canonical)
            cleaned.append(text)
        return cleaned

    lines: List[str] = []
    ordered = [
        ("programming_languages", "Programming Languages"),
        ("data_science", "Data Science"),
        ("data_visualization", "Data Visualization"),
        ("databases", "Databases"),
        ("tools", "Tools"),
    ]

    values_by_category: Dict[str, List[str]] = {}
    occupied: set[str] = set()
    for key, _label in ordered:
        normalized_values = _normalize_skill_items(cast(List[str], skills.get(key, [])))
        if key == "tools":
            filtered_tools: List[str] = []
            for item in normalized_values:
                marker = re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
                if marker in occupied:
                    continue
                filtered_tools.append(item)
            normalized_values = filtered_tools
        values_by_category[key] = normalized_values
        for item in normalized_values:
            occupied.add(re.sub(r"[^a-z0-9]+", " ", item.lower()).strip())

    for key, label in ordered:
        values = values_by_category.get(key, [])
        if not values:
            continue
        value_text = latex_escape(", ".join(values))
        lines.append(f"\\noindent \\textbf{{{label}:}} {value_text}\\\\")
    return "\n".join(lines)


def render_additional_sections(additional_sections: List[AdditionalSectionEntry]) -> str:
    blocks: List[str] = []
    for section in additional_sections:
        title = latex_escape(str(section.get("title", "Additional Information")))
        bullets = [str(item).strip() for item in section.get("bullets", []) if str(item).strip()]
        body = latex_escape(str(section.get("body", "")).strip())

        section_lines: List[str] = [f"\\sectionline{{{title}}}"]
        if bullets:
            bullet_lines = "\n".join([f"\\item {latex_escape(str(item))}" for item in bullets])
            section_lines.extend([
                r"\begin{itemize}[label=\resumebullet]",
                bullet_lines,
                r"\end{itemize}",
            ])
        elif body:
            section_lines.append(body)

        if len(section_lines) > 1:
            blocks.append("\n".join(section_lines))

    return "\n\n".join(blocks)


def render_other_block(resume_data: ResumeData) -> str:
    pieces: List[str] = []

    certifications = []
    for item in resume_data.get("certifications", []):
        if isinstance(item, dict):
            text = " | ".join(
                str(item.get(key) or "").strip()
                for key in ("name", "issuer", "year")
                if str(item.get(key) or "").strip()
            )
        else:
            text = str(item).strip()
        if text:
            certifications.append(text)
    if certifications:
        pieces.append(r"\textbf{Certifications}\\")
        pieces.extend([f"\\item {latex_escape(cert)}" for cert in certifications])

    if not pieces:
        return ""

    return "\n".join([
        pieces[0],
        r"\begin{itemize}[label=\resumebullet]",
        *pieces[1:],
        r"\end{itemize}",
    ])


def render_certifications(certifications: list[Any]) -> str:
    if not certifications:
        return ""

    def _clean_cert_text(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = text.replace(r"\{\}", " ")
        text = text.replace("{}", " ")
        text = re.sub(r"\\textbackslash\{\}", " ", text)
        text = re.sub(r"\\[{}]", " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip(" -|,")

    rows = []
    for certification in certifications:
        if isinstance(certification, dict):
            certification = " | ".join(
                str(certification.get(key) or "").strip()
                for key in ("name", "issuer", "year")
                if str(certification.get(key) or "").strip()
            )
        cleaned = _clean_cert_text(str(certification))
        if cleaned:
            rows.append(f"\\item {latex_escape(cleaned)}")
    if not rows:
        return ""
    return "\n".join([
        r"\begin{itemize}[noitemsep, topsep=0pt]",
        *rows,
        r"\end{itemize}",
    ])


def _non_empty_lines(text: str) -> List[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _plain_lines_to_latex(text: str) -> str:
    lines = _non_empty_lines(text)
    return "\\\\\n".join([latex_escape(line) for line in lines])


def _bullet_ready_block_to_latex(text: str) -> str:
    lines = _non_empty_lines(text)
    if not lines:
        return ""

    chunks: List[str] = []
    bullets: List[str] = []

    def flush_bullets() -> None:
        if not bullets:
            return
        chunks.extend([
            r"\begin{itemize}[noitemsep, topsep=0pt]",
            *bullets,
            r"\end{itemize}",
        ])
        bullets.clear()

    for line in lines:
        if re.match(r"^[-*•]\s+", line):
            cleaned = re.sub(r"^[-*•]\s+", "", line).strip()
            if cleaned:
                bullets.append(f"\\item {latex_escape(cleaned)}")
            continue

        flush_bullets()
        chunks.append(f"\\textbf{{{latex_escape(line)}}}\\\\")

    flush_bullets()
    return "\n".join(chunks)


def _education_block_to_latex(text: str) -> str:
    lines = _non_empty_lines(text)
    if not lines:
        return ""

    month_token = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
    year_or_month_year = rf"(?:(?:{month_token}\s+)?(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}})"
    date_pattern = re.compile(
        rf"{year_or_month_year}\s*[-–]\s*(?:present|{year_or_month_year})",
        re.IGNORECASE,
    )

    def _looks_like_date(value: str) -> bool:
        return bool(date_pattern.search(value))

    def _is_date_only_line(value: str) -> bool:
        return bool(
            re.fullmatch(
                rf"{year_or_month_year}\s*[-–]\s*(?:present|{year_or_month_year})",
                str(value or "").strip(),
                re.IGNORECASE,
            )
        )

    def _expand_multientry_lines(raw_lines: List[str]) -> List[str]:
        expanded: List[str] = []
        for line in raw_lines:
            matches = list(date_pattern.finditer(line))
            if len(matches) <= 1:
                expanded.append(line)
                continue
            cursor = 0
            for match in matches:
                end = match.end()
                chunk = line[cursor:end].strip(" ,;|")
                if chunk:
                    expanded.append(chunk)
                cursor = end
        return expanded

    lines = _expand_multientry_lines(lines)

    def _looks_like_location(value: str) -> bool:
        return bool(re.search(r",|\bonline\b|\bremote\b|\bhybrid\b", value, re.IGNORECASE))

    def _split_institution_location(value: str) -> tuple[str, str]:
        raw = str(value or "").strip()
        if not raw or "," not in raw:
            return raw, ""
        institution, location = raw.split(",", 1)
        return institution.strip(), location.strip()

    out: List[str] = []

    if any("|" in line for line in lines):
        i = 0
        while i < len(lines):
            line = lines[i]

            # Handle 2-line education tuples: "Institute, Location" + "Degree | Date"
            if "|" not in line and i + 1 < len(lines) and "|" in lines[i + 1]:
                next_parts = [part.strip() for part in lines[i + 1].split("|") if part.strip()]
                if len(next_parts) == 2 and _looks_like_date(next_parts[1]):
                    institution_raw, location_raw = _split_institution_location(line)
                    degree_raw, date_raw = next_parts
                    institution = latex_escape(institution_raw)
                    location = latex_escape(location_raw)
                    degree = latex_escape(degree_raw)
                    duration = latex_escape(date_raw)

                    out.append(f"\\noindent\\textbf{{{institution}}}\\hfill\\textbf{{{duration}}}\\\\")
                    if location:
                        out.append(f"\\noindent {degree}\\hfill {location}\\\\")
                    else:
                        out.append(f"\\noindent {degree}\\\\")
                    i += 2
                    continue

            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) >= 4:
                institution = latex_escape(parts[0])
                location = latex_escape(parts[1])
                description = latex_escape(" | ".join(parts[2:-1]))
                duration = latex_escape(parts[-1])
                out.append(f"\\noindent\\textbf{{{institution}}}\\hfill\\textbf{{{duration}}}\\\\")
                out.append(f"\\noindent {description}\\hfill {location}\\\\")
                i += 1
                continue
            if len(parts) == 3:
                institution = latex_escape(parts[0])
                description = latex_escape(parts[1])
                duration = latex_escape(parts[2])
                out.append(f"\\noindent\\textbf{{{institution}}}\\hfill\\textbf{{{duration}}}\\\\")
                out.append(f"\\noindent {description}\\\\")
                i += 1
                continue
            if len(parts) == 2:
                left = latex_escape(parts[0])
                right = latex_escape(parts[1])
                out.append(f"\\noindent\\textbf{{{left}}}\\hfill\\textbf{{{right}}}\\\\")
                i += 1
                continue
            out.append(f"\\noindent {latex_escape(line)}\\\\")
            i += 1
        return "\n".join(out)

    buffer: List[str] = []
    entries: List[tuple[str, str, str, str]] = []
    for line in lines:
        inline_match = date_pattern.search(line)
        if inline_match and not _is_date_only_line(line):
            before = line[: inline_match.start()].strip(" ,;|")
            after = line[inline_match.end() :].strip(" ,;|")
            duration = line[inline_match.start() : inline_match.end()].strip()
            institution = before
            description = after
            entries.append((institution, description, duration, ""))
            buffer = []
            continue

        if _is_date_only_line(line):
            date_text = line
            info = [value for value in buffer if value.strip()]
            institution = info[0] if info else ""
            location = ""
            description = ""
            if len(info) >= 3:
                location = info[1]
                description = " ".join(info[2:])
            elif len(info) == 2:
                if _looks_like_location(info[1]):
                    location = info[1]
                else:
                    description = info[1]
            entries.append((institution, description, date_text, location))
            buffer = []
        else:
            buffer.append(line)

    if buffer:
        institution = buffer[0]
        description = " ".join(buffer[1:]) if len(buffer) > 1 else ""
        entries.append((institution, description, "", ""))

    for institution, description, duration, location in entries:
        if institution:
            if duration:
                out.append(
                    f"\\noindent\\textbf{{{latex_escape(institution)}}}\\hfill\\textbf{{{latex_escape(duration)}}}\\\\"
                )
            else:
                out.append(f"\\noindent\\textbf{{{latex_escape(institution)}}}\\\\")
        if description or location:
            left = latex_escape(description) if description else ""
            right = latex_escape(location) if location else ""
            if left and right:
                out.append(f"\\noindent {left}\\hfill {right}\\\\")
            elif left:
                out.append(f"\\noindent {left}\\\\")
            elif right:
                # Keep education descriptor text (for example, degree lines) left-aligned.
                out.append(f"\\noindent {right}\\\\")

    return "\n".join(out)


def _skills_block_to_latex(text: str) -> str:
    lines = _non_empty_lines(text)
    if not lines:
        return ""

    if len(lines) == 1:
        raw = lines[0]
        label_pattern = re.compile(
            r"(Programming Languages|Data Science|Data Visualization|Databases|Tools)\s*:",
            re.IGNORECASE,
        )
        matches = list(label_pattern.finditer(raw))
        if len(matches) > 1:
            rebuilt: List[str] = []
            for idx, match in enumerate(matches):
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
                segment = raw[match.start() : end].strip(" ,;|")
                if segment:
                    rebuilt.append(segment)
            lines = rebuilt

    rendered_lines: List[str] = []
    for line in lines:
        rendered_lines.append(f"\\noindent {latex_escape(line)}\\\\")
    return "\n".join(rendered_lines)


def _certifications_block_to_latex(text: str) -> str:
    lines = _non_empty_lines(text)
    if not lines:
        return ""
    rows: List[str] = []
    for line in lines:
        cleaned = re.sub(r"^[-*•]\s+", "", line).strip()
        cleaned = cleaned.replace(r"\{\}", " ").replace("{}", " ")
        cleaned = re.sub(r"\\textbackslash\{\}", " ", cleaned)
        cleaned = re.sub(r"\\[{}]", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned:
            rows.append(f"\\item {latex_escape(cleaned)}")
    if not rows:
        return ""
    return "\n".join([
        r"\begin{itemize}[noitemsep, topsep=0pt]",
        *rows,
        r"\end{itemize}",
    ])


def fill_latex_template(template: str, sections: Dict[str, str], resume_data: Dict[str, Any]) -> str:
    """Fill fixed LaTeX template with escaped LLM-generated placeholder content blocks."""
    safe_sections = {
        "experience_block": str(sections.get("experience_block", "") or "").strip(),
        "projects_block": str(sections.get("projects_block", "") or "").strip(),
        "education_block": str(sections.get("education_block", "") or "").strip(),
        "skills_block": str(sections.get("skills_block", "") or "").strip(),
        "certifications_block": str(sections.get("certifications_block", "") or "").strip(),
        "other_block": str(sections.get("other_block", "") or "").strip(),
    }

    def _is_latex_block(text: str) -> bool:
        return bool(re.search(r"\\(begin|end|item|textbf|textit|section|hfill)", text))

    experience_block = safe_sections["experience_block"] if _is_latex_block(safe_sections["experience_block"]) else _bullet_ready_block_to_latex(safe_sections["experience_block"])
    projects_block = safe_sections["projects_block"] if _is_latex_block(safe_sections["projects_block"]) else _bullet_ready_block_to_latex(safe_sections["projects_block"])
    education_block = safe_sections["education_block"] if _is_latex_block(safe_sections["education_block"]) else _education_block_to_latex(safe_sections["education_block"])
    skills_block = safe_sections["skills_block"] if _is_latex_block(safe_sections["skills_block"]) else _skills_block_to_latex(safe_sections["skills_block"])
    certifications_source = safe_sections["certifications_block"] or safe_sections["other_block"]
    certifications_block = (
        certifications_source
        if _is_latex_block(certifications_source)
        else _certifications_block_to_latex(certifications_source)
    )

    latex = template
    latex = latex.replace("{name}", latex_escape(str(resume_data.get("name", "Candidate"))))
    latex = latex.replace("{contact_block}", render_contact(cast(ResumeData, resume_data)))

    latex = latex.replace("{education_section_start}", "\\section{Education}" if education_block else "")
    latex = latex.replace("{education_block}", education_block)
    latex = latex.replace("{education_section_end}", "" if education_block else "")

    latex = latex.replace("{experience_section_start}", "\\section{Experience}" if experience_block else "")
    latex = latex.replace("{experience_block}", experience_block)
    latex = latex.replace("{experience_section_end}", "" if experience_block else "")
    latex = latex.replace("{projects_section_start}", "\\section{Projects}" if projects_block else "")
    latex = latex.replace("{projects_block}", projects_block)
    latex = latex.replace("{projects_section_end}", "" if projects_block else "")

    latex = latex.replace("{skills_section_start}", "\\section{Skills}" if skills_block else "")
    latex = latex.replace("{skills_block}", skills_block)
    latex = latex.replace("{skills_section_end}", "" if skills_block else "")

    latex = latex.replace("{certifications_section_start}", "\\section{Certifications}" if certifications_block else "")
    latex = latex.replace("{certifications_block}", certifications_block)
    latex = latex.replace("{certifications_section_end}", "" if certifications_block else "")

    # Guard against accidental tab-escaped LaTeX commands in templates.
    latex = latex.replace("\titleformat", "\\titleformat")
    latex = latex.replace("\titlespacing", "\\titlespacing")
    latex = latex.replace("\titlerule", "\\titlerule")
    return latex


def build_latex_resume(resume_data: ResumeData, summary: str = "") -> str:
    sections = {
        "experience_block": render_experience(
            resume_data.get("experience", []),
            location=str(resume_data.get("contact", {}).get("location", "")),
        ),
        "projects_block": render_projects(
            resume_data.get("projects", []),
            location=str(resume_data.get("contact", {}).get("location", "")),
        ),
        "education_block": str(resume_data.get("education", "")),
        "skills_block": render_skills(resume_data.get("skills", {})),
        "certifications_block": render_certifications(resume_data.get("certifications", [])),
        "other_block": render_other_block(resume_data),
    }
    latex = fill_latex_template(LATEX_TEMPLATE, sections=sections, resume_data=cast(Dict[str, Any], resume_data))
    return latex


def _count_pdf_pages(pdf_bytes: bytes) -> int | None:
    try:
        import fitz  # type: ignore[import-not-found]

        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            page_count = getattr(document, "page_count", None)
            if isinstance(page_count, int):
                return page_count
            if page_count is not None:
                return int(page_count)
    except Exception:
        return None
    return None


def _apply_layout_profile(latex_source: str, profile: int) -> str:
    if profile <= 0:
        return latex_source

    profile_settings: Dict[int, Dict[str, Any]] = {
        1: {
            "doc_pt": "12pt",
            "margin": "0.48in",
            "list": r"leftmargin=13pt,labelindent=0pt,labelwidth=7.5pt,labelsep=5.5pt,itemindent=0pt,itemsep=0pt,topsep=0pt,parsep=0pt,partopsep=0pt",
            "name": ("21", "22"),
            "contact": ("13", "14"),
            "section": ("0.60", "0.26", "0.80"),
        },
        2: {
            "doc_pt": "11pt",
            "margin": "0.45in",
            "list": r"leftmargin=12pt,labelindent=0pt,labelwidth=7pt,labelsep=5pt,itemindent=0pt,itemsep=0pt,topsep=0pt,parsep=0pt,partopsep=0pt",
            "name": ("20", "21"),
            "contact": ("12", "13"),
            "section": ("0.50", "0.22", "0.65"),
        },
        3: {
            "doc_pt": "10pt",
            "margin": "0.42in",
            "list": r"leftmargin=11pt,labelindent=0pt,labelwidth=6.5pt,labelsep=4.5pt,itemindent=0pt,itemsep=0pt,topsep=0pt,parsep=0pt,partopsep=0pt",
            "name": ("19", "20"),
            "contact": ("11", "12"),
            "section": ("0.40", "0.18", "0.50"),
        },
        4: {
            "doc_pt": "9pt",
            "margin": "0.40in",
            "list": r"leftmargin=10.5pt,labelindent=0pt,labelwidth=6pt,labelsep=4pt,itemindent=0pt,itemsep=0pt,topsep=0pt,parsep=0pt,partopsep=0pt",
            "name": ("18", "19"),
            "contact": ("10", "11"),
            "section": ("0.30", "0.14", "0.35"),
        },
    }

    if profile not in profile_settings:
        return latex_source
    settings = profile_settings[profile]

    tuned = latex_source
    tuned = re.sub(
        r"\\documentclass\[[^\]]+\]\{article\}",
        rf"\\documentclass[{settings['doc_pt']},a4paper]{{article}}",
        tuned,
        count=1,
    )
    tuned = re.sub(
        r"\\usepackage\[margin=[^\]]+\]\{geometry\}",
        rf"\\usepackage[margin={settings['margin']}]{{geometry}}",
        tuned,
        count=1,
    )
    tuned = re.sub(
        r"\\setlist\[itemize\]\{[^\n]*\}",
        rf"\\setlist[itemize]{{{settings['list']}}}",
        tuned,
        count=1,
    )
    tuned = re.sub(
        r"\\newcommand\{\\resumename\}\[1\]\{[^\n]*\}",
        rf"\\newcommand{{\\resumename}}[1]{{{{\\fontsize{{{settings['name'][0]}}}{{{settings['name'][1]}}}\\selectfont\\textbf{{#1}}}}}}",
        tuned,
        count=1,
    )
    tuned = re.sub(
        r"\\newcommand\{\\contactline\}\[1\]\{[^\n]*\}",
        rf"\\newcommand{{\\contactline}}[1]{{{{\\fontsize{{{settings['contact'][0]}}}{{{settings['contact'][1]}}}\\selectfont #1}}}}",
        tuned,
        count=1,
    )
    section_macro = (
        rf"\\newcommand{{\\sectionline}}[1]{{\\vspace{{{settings['section'][0]}em}}"
        rf"\\noindent{{\\fontsize{{12}}{{14}}\\selectfont\\textbf{{\\MakeUppercase{{#1}}}}}}"
        rf"\\par\\vspace{{{settings['section'][1]}em}}\\hrule\\vspace{{{settings['section'][2]}em}}}}"
    )
    tuned = re.sub(
        r"\\newcommand\{\\sectionline\}\[1\]\{[^\n]*\}",
        section_macro,
        tuned,
        count=1,
    )
    return tuned


def _compile_latex_once(latex_source: str, latex_engine_path: str, env: Dict[str, str], engine_name: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="resume_latex_") as tmp_dir:
        workdir = Path(tmp_dir)
        tex_path = workdir / "resume.tex"
        tex_path.write_text(latex_source, encoding="utf-8")

        cmd = [latex_engine_path, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"]
        try:
            process = subprocess.run(
                cmd,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{engine_name} timed out") from exc

        if process.returncode != 0:
            stderr = process.stderr[-2000:] if process.stderr else ""
            stdout = process.stdout[-2000:] if process.stdout else ""
            raise RuntimeError(f"{engine_name} failed. stdout={stdout} stderr={stderr}")

        pdf_path = workdir / "resume.pdf"
        if not pdf_path.exists():
            raise RuntimeError(f"{engine_name} finished without producing resume.pdf")
        return pdf_path.read_bytes()


def _resolve_latex_engines(env: Dict[str, str]) -> List[tuple[str, str]]:
    def _is_available(executable: str) -> bool:
        return bool(executable and (Path(executable).exists() or shutil.which(executable)))

    xelatex_path = (
        env.get("XELATEX_PATH", "").strip()
        or shutil.which("xelatex")
        or str(Path.home() / "AppData" / "Local" / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64" / "xelatex.exe")
    )
    pdflatex_path = (
        env.get("PDFLATEX_PATH", "").strip()
        or shutil.which("pdflatex")
        or str(Path.home() / "AppData" / "Local" / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64" / "pdflatex.exe")
    )

    engines: List[tuple[str, str]] = []
    if _is_available(xelatex_path):
        engines.append(("xelatex", xelatex_path))
    if _is_available(pdflatex_path):
        engines.append(("pdflatex", pdflatex_path))
    return engines


def compile_latex_to_pdf(latex_source: str) -> bytes:
    """Compile LaTeX source to PDF bytes with single-page auto-fit profiles."""
    env = os.environ.copy()
    engines = _resolve_latex_engines(env)
    if not engines:
        raise RuntimeError("No LaTeX engine found. Install xelatex or pdflatex, or set XELATEX_PATH/PDFLATEX_PATH.")

    last_compiled_pdf: bytes | None = None
    last_compile_error: Exception | None = None

    # Keep content unchanged; only tighten layout progressively when page count is > 1.
    for profile in (0, 1, 2, 3, 4):
        candidate_source = _apply_layout_profile(latex_source, profile)
        compiled_pdf: bytes | None = None
        compiled_this_profile = False
        for engine_name, engine_path in engines:
            try:
                compiled_pdf = _compile_latex_once(candidate_source, engine_path, env, engine_name)
                compiled_this_profile = True
                break
            except Exception as exc:
                last_compile_error = exc
                continue

        if not compiled_this_profile:
            if profile == 0 and last_compile_error is not None:
                raise last_compile_error
            continue

        if compiled_pdf is None:
            continue

        last_compiled_pdf = compiled_pdf
        page_count = _count_pdf_pages(compiled_pdf)
        if page_count is None or page_count <= 1:
            return compiled_pdf

    if last_compiled_pdf is not None:
        return last_compiled_pdf
    if last_compile_error is not None:
        raise RuntimeError(f"LaTeX compile failed for all profiles: {last_compile_error}") from last_compile_error
    raise RuntimeError("LaTeX compile failed for all profiles")

