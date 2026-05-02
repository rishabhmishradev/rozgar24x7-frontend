"""Converts input documents to a normalized PDF format."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class NormalizationError(RuntimeError):
    """Raised when document normalization fails."""


def _get_libreoffice_path() -> Optional[str]:
    """Tries to find the LibreOffice executable."""
    if os.name == "nt":
        # Windows standard paths
        paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return None
    else:
        from shutil import which
        return which("soffice") or which("libreoffice")


def normalize_to_pdf(input_path: str | Path, output_dir: Optional[str | Path] = None) -> Path:
    """Converts a document to PDF. Returns path to the generated PDF.
    
    If input is already a PDF, it returns the input path.
    If input is DOCX, uses LibreOffice headless or docx2pdf to convert to PDF.
    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    ext = input_path.suffix.lower()
    if ext == ".pdf":
        return input_path
        
    if ext != ".docx":
        raise ValueError(f"Unsupported file format for normalization: {ext}. Only .pdf and .docx are supported.")
        
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())
    else:
        output_dir = Path(output_dir).resolve()
        
    out_path = output_dir / f"{input_path.stem}.pdf"
    
    # Try LibreOffice first securely
    lo_path = _get_libreoffice_path()
    if lo_path:
        logger.info(f"Converting {input_path} to PDF using LibreOffice")
        try:
            subprocess.run(
                [lo_path, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(input_path)],
                check=True,
                capture_output=True
            )
            if out_path.exists():
                return out_path
        except subprocess.CalledProcessError as e:
            logger.warning(f"LibreOffice conversion failed: {e.stderr.decode('utf-8', errors='ignore')}")
    
    # Fallback to docx2pdf
    logger.info(f"Converting {input_path} to PDF using docx2pdf")
    try:
        from docx2pdf import convert
        convert(str(input_path), str(out_path))
        if out_path.exists():
            return out_path
    except ImportError:
        raise NormalizationError("docx2pdf is not installed.")
    except Exception as e:
        raise NormalizationError(f"docx2pdf conversion failed: {e}")
        
    raise NormalizationError("Failed to convert DOCX to PDF.")

