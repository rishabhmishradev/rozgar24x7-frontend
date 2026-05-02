"""Lossless layout-aware PDF text extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import fitz  # type: ignore

logger = logging.getLogger(__name__)

_INVISIBLE_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

@dataclass
class Token:
    """A segment of text with layout information."""
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    font_size: float
    page: int
    flags: int = 0  # To identify bold/italic from PyMuPDF
    is_link: bool = False
    link_target: Optional[str] = None

    @property
    def is_bold(self) -> bool:
        """PyMuPDF flags: bit 4 (value 16) = bold."""
        return bool(self.flags & (1 << 4))

@dataclass
class TokenLine:
    """A logical line containing tokens."""
    tokens: List[Token]
    page: int
    bbox: tuple[float, float, float, float] = field(init=False)

    def __post_init__(self):
        if not self.tokens:
            self.bbox = (0.0, 0.0, 0.0, 0.0)
        else:
            x0 = min(t.bbox[0] for t in self.tokens)
            y0 = min(t.bbox[1] for t in self.tokens)
            x1 = max(t.bbox[2] for t in self.tokens)
            y1 = max(t.bbox[3] for t in self.tokens)
            self.bbox = (x0, y0, x1, y1)

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.tokens)
        
    @property
    def font_size(self) -> float:
        """Returns the most frequent or max font size in the line."""
        if not self.tokens:
            return 0.0
        return max(t.font_size for t in self.tokens)

    @property
    def is_bold(self) -> bool:
        """True if the majority of tokens in this line are bold."""
        if not self.tokens:
            return False
        bold_count = sum(1 for t in self.tokens if t.is_bold)
        return bold_count > len(self.tokens) / 2

def _point_in_rect(pt: tuple[float, float], rect: fitz.Rect) -> bool:
    return rect.x0 <= pt[0] <= rect.x1 and rect.y0 <= pt[1] <= rect.y1


def _clean_extracted_text(text: str) -> str:
    """Normalize extracted span text by removing invisible separators."""
    cleaned = _INVISIBLE_CHARS_RE.sub("", text)
    return cleaned.strip()

def extract_tokens(pdf_path: str | Path) -> List[TokenLine]:
    """
    Losslessly extracts text tokens grouped into logical lines from a PDF.
    Captures exact bounding boxes, font sizes, and hyperlinks.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    all_lines: List[TokenLine] = []

    for page_num, page in enumerate(doc):
        # Gather hyperlinks
        links = page.get_links()
        link_rects = []
        for l in links:
            if "uri" in l and "from" in l:
                # "from" is the rect, "uri" is the target
                link_rects.append((l["from"], l["uri"]))

        # Extract "dict" layout
        blocks = page.get_text("dict").get("blocks", [])
        
        for block in blocks:
            # Type 0 is text
            if block.get("type") != 0:
                continue
                
            for line in block.get("lines", []):
                line_tokens: List[Token] = []
                for span in line.get("spans", []):
                    span_text = _clean_extracted_text(span.get("text", ""))
                    if not span_text:
                        continue
                        
                    span_bbox = span.get("bbox")
                    if not span_bbox or len(span_bbox) < 4:
                        continue
                    span_size = span.get("size", 0.0)
                    span_flags = span.get("flags", 0)
                    
                    # Compute center of span to check link intersection
                    center_x = (span_bbox[0] + span_bbox[2]) / 2.0
                    center_y = (span_bbox[1] + span_bbox[3]) / 2.0
                    
                    is_link = False
                    link_target = None
                    for rect, uri in link_rects:
                        if _point_in_rect((center_x, center_y), rect):
                            is_link = True
                            link_target = uri
                            break
                            
                    line_tokens.append(Token(
                        text=span_text,
                        bbox=tuple(span_bbox),
                        font_size=span_size,
                        page=page_num,
                        flags=span_flags,
                        is_link=is_link,
                        link_target=link_target
                    ))
                
                if line_tokens:
                    all_lines.append(TokenLine(tokens=line_tokens, page=page_num))

    doc.close()
    return all_lines

def render_pages_as_images(pdf_path: str | Path, output_dir: str | Path, dpi: int = 150) -> List[Path]:
    """Renders PDF pages to images, useful for LayoutLMv3 processing."""
    path = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(str(path))
    image_paths = []
    
    for page_num, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = out_dir / f"{path.stem}_page_{page_num}.png"
        pix.save(str(img_path))
        image_paths.append(img_path)
        
    doc.close()
    return image_paths
