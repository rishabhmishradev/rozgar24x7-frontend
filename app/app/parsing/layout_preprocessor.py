"""Layout Preprocessing for normalising bounding boxes and detecting columns."""

from __future__ import annotations

import logging
from typing import List, cast

from .pdf_extractor import TokenLine

logger = logging.getLogger(__name__)

def normalize_bbox(bbox: tuple[float, float, float, float], page_width: float, page_height: float) -> tuple[int, int, int, int]:
    """
    Normalizes a bounding box to a 0-1000 integer scale based on page dimensions.
    This format is required for LayoutLMv3.
    """
    if page_width <= 0 or page_height <= 0:
        return (0, 0, 0, 0)
        
    x0, y0, x1, y1 = bbox
    # Clip to bounds and normalize
    norm_x0 = max(0, min(1000, int(1000 * (x0 / page_width))))
    norm_y0 = max(0, min(1000, int(1000 * (y0 / page_height))))
    norm_x1 = max(0, min(1000, int(1000 * (x1 / page_width))))
    norm_y1 = max(0, min(1000, int(1000 * (y1 / page_height))))
    
    # Ensure standard box invariant
    norm_x1 = max(norm_x0, norm_x1)
    norm_y1 = max(norm_y0, norm_y1)
    
    return (norm_x0, norm_y0, norm_x1, norm_y1)


def detect_layout_complexity(lines: List[TokenLine], page_width: float = 612.0) -> str:
    """
    Determines if the document layout is 'single-column' or 'complex' (multi-column).
    
    We determine this by inspecting the left X coordinates. If a substantial number
    of lines start significantly right of the primary left margin, it's multi-column.
    """
    if not lines:
        return "single-column"
        
    left_margins = [line.bbox[0] for line in lines]
    
    if len(left_margins) < 6:
        return "single-column"
        
    # Find the global minimum left margin as the primary document left edge
    primary_margin = min(left_margins)
    
    # Count how many lines start far from the primary margin.
    # Use a slightly lower threshold to detect narrow sidebars in modern templates.
    far_right_threshold = primary_margin + (page_width * 0.3)
    far_right_margins = [m for m in left_margins if m > far_right_threshold]
    far_right_lines = len(far_right_margins)

    # Adaptive minimum so one-page resumes with fewer lines can still be recognized.
    min_far_right_lines = max(3, int(len(lines) * 0.15))
    if far_right_lines < min_far_right_lines:
        return "single-column"

    ratio = far_right_lines / len(lines)

    # Distinct right cluster with reasonable density indicates multi-column layout.
    secondary_margin = min(far_right_margins) if far_right_margins else primary_margin
    margin_separation = secondary_margin - primary_margin

    if ratio >= 0.18 and margin_separation >= page_width * 0.28:
        logger.info(f"Complex layout detected. Side column ratio: {ratio:.2f}")
        return "complex"

    if ratio >= 0.26:
        logger.info(f"Complex layout detected. Side column ratio: {ratio:.2f}")
        return "complex"
        
    return "single-column"

def prep_lines_for_layout_model(lines: List[TokenLine], page_width: float, page_height: float) -> List[dict]:
    """
    Converts TokenLines into flat token lists with 1000-scaled bboxes for LayoutLMv3 ingestion.
    """
    prepped = []
    for line in lines:
        for t in line.tokens:
            norm_b = normalize_bbox(t.bbox, page_width, page_height)
            prepped.append({
                "text": t.text,
                "bbox": norm_b,
                "page": t.page
            })
    return prepped
