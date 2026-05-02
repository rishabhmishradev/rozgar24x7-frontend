"""Utilities for extracting normalized text from resume files."""

from __future__ import annotations

import importlib
import io
import logging
import re
from pathlib import Path
from typing import Any, Callable


class UnsupportedFileTypeError(ValueError):
    """Raised when a file extension is not supported by the extractor."""


class ExtractionError(RuntimeError):
    """Raised when text extraction succeeds technically but yields unusable text."""


logger = logging.getLogger(__name__)


_REPLACEMENTS = {
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\xa0": " ",
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
}

_PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")


def _clean_unicode_artifacts(text: str) -> str:
    cleaned = text
    for source, target in _REPLACEMENTS.items():
        cleaned = cleaned.replace(source, target)
    # Drop icon-font/private-use glyphs frequently found in stylized resumes.
    return _PRIVATE_USE_RE.sub("", cleaned)


def _extraction_quality_is_low(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if len(words) < 30:
        return True
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    total_chars = max(len(text), 1)
    return (alpha_chars / total_chars) < 0.18


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace while preserving paragraph boundaries."""
    sanitized = _clean_unicode_artifacts(text)
    lines = [" ".join(line.split()) for line in sanitized.replace("\r", "").split("\n")]

    normalized: list[str] = []
    blank_streak = 0
    for line in lines:
        if not line.strip():
            blank_streak += 1
            if blank_streak <= 1:
                normalized.append("")
            continue
        blank_streak = 0
        normalized.append(line.strip())

    return "\n".join(normalized).strip()


def _extract_text_from_plain_text(file_path: Path) -> str:
    # UTF-8 should be the default; latin-1 fallback helps with legacy resumes.
    for encoding in ("utf-8", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _extract_text_from_rtf(file_path: Path) -> str:
    raw = _extract_text_from_plain_text(file_path)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", "", raw)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    return text


def _extract_text_from_pdf(file_path: Path) -> str:
    try:
        fitz = importlib.import_module("fitz")  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise ImportError(
            "PDF support requires the 'PyMuPDF' package. Install it with: pip install PyMuPDF"
        ) from exc

    logger.info("Extracting PDF text with PyMuPDF: %s", file_path)
    document: Any = fitz.open(str(file_path))
    try:
        pages: list[str] = []
        for page in document:
            block_texts: list[str] = []
            blocks = page.get_text("blocks", sort=True) or []
            for block in blocks:
                if len(block) >= 5 and isinstance(block[4], str):
                    line = block[4].strip()
                    if line:
                        block_texts.append(line)

            text = "\n".join(block_texts).strip()
            if len(text) < 40:
                text = str(page.get_text("text", sort=True) or page.get_text() or "")

            # Append native PDF links to text so they can be captured by regex later.
            links = page.get_links()
            if links:
                uris = sorted({str(link.get("uri")) for link in links if link.get("uri")})
                if uris:
                    text = f"{text}\n" + "\n".join(uris)

            pages.append(text)

        merged = "\n".join(pages)
        if _extraction_quality_is_low(merged):
            ocr_text = _extract_text_from_pdf_ocr(document)
            if ocr_text and len(ocr_text) > len(merged):
                logger.info("Using OCR fallback for PDF %s due to low native text quality", file_path.name)
                merged = ocr_text
        return merged
    finally:
        document.close()


def _extract_text_from_pdf_ocr(document: Any) -> str:
    try:
        pytesseract = importlib.import_module("pytesseract")
        pil_image = importlib.import_module("PIL.Image")
    except ImportError:
        return ""

    image_open = getattr(pil_image, "open", None)
    image_to_string = getattr(pytesseract, "image_to_string", None)
    if image_open is None or image_to_string is None:
        return ""

    pages: list[str] = []
    for page in document:
        try:
            pix = page.get_pixmap(dpi=220, alpha=False)
            image = image_open(io.BytesIO(pix.tobytes("png")))
            text = str(image_to_string(image, lang="eng") or "").strip()
            if text:
                pages.append(text)
        except Exception:
            continue

    return "\n".join(pages)


def _extract_text_from_docx(file_path: Path) -> str:
    try:
        docx = importlib.import_module("docx")  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise ImportError(
            "DOCX support requires the 'python-docx' package. Install it with: pip install python-docx"
        ) from exc

    document_fn = getattr(docx, "Document")
    document: Any = document_fn(str(file_path))
    logger.info("Extracting DOCX text: %s", file_path)

    lines: list[str] = []

    def _append_text(value: str) -> None:
        cleaned = str(value or "").strip()
        if cleaned:
            lines.append(cleaned)

    def _extract_table_lines(table: Any, seen_cells: set[int]) -> None:
        for row in getattr(table, "rows", []):
            for cell in getattr(row, "cells", []):
                cell_id = id(getattr(cell, "_tc", cell))
                if cell_id in seen_cells:
                    continue
                seen_cells.add(cell_id)

                for paragraph in getattr(cell, "paragraphs", []):
                    _append_text(getattr(paragraph, "text", ""))

                for nested_table in getattr(cell, "tables", []):
                    _extract_table_lines(nested_table, seen_cells)

    for paragraph in getattr(document, "paragraphs", []):
        _append_text(getattr(paragraph, "text", ""))

    seen_cells: set[int] = set()
    for table in getattr(document, "tables", []):
        _extract_table_lines(table, seen_cells)

    # Headers and footers often contain contact info in modern templates.
    for section in getattr(document, "sections", []):
        header = getattr(section, "header", None)
        footer = getattr(section, "footer", None)

        if header is not None:
            for paragraph in getattr(header, "paragraphs", []):
                _append_text(getattr(paragraph, "text", ""))
            for table in getattr(header, "tables", []):
                _extract_table_lines(table, seen_cells)

        if footer is not None:
            for paragraph in getattr(footer, "paragraphs", []):
                _append_text(getattr(paragraph, "text", ""))
            for table in getattr(footer, "tables", []):
                _extract_table_lines(table, seen_cells)

    return "\n".join(lines)


class TextExtractor:
    """Extract text from common resume formats."""

    _extractors: dict[str, Callable[[Path], str]] = {
        ".txt": _extract_text_from_plain_text,
        ".md": _extract_text_from_plain_text,
        ".rtf": _extract_text_from_rtf,
        ".pdf": _extract_text_from_pdf,
        ".docx": _extract_text_from_docx,
    }

    def extract(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        extractor = self._extractors.get(suffix)
        if extractor is None:
            supported = ", ".join(sorted(self._extractors))
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{suffix}'. Supported extensions: {supported}"
            )

        extracted = extractor(path)
        normalized = normalize_whitespace(extracted)
        if len(normalized) < 20:
            raise ExtractionError(
                "Extracted text is too short to parse reliably. "
                "The file may be image-based or malformed."
            )
        logger.info("Text extraction completed for %s (%d chars)", path.name, len(normalized))
        return normalized


def extract_text(file_path: str | Path) -> str:
    """Convenience function for one-off extraction."""
    return TextExtractor().extract(file_path)
