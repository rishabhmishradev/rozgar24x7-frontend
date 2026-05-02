"""LayoutLMv3 integration and Section Classification."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

try:
    import torch  # type: ignore
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification  # type: ignore
    from PIL import Image  # type: ignore
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

logger = logging.getLogger(__name__)

# Canonical labels — expanded with certifications, summary, contact
ID2LABEL = {
    0: "O",
    1: "B-HEADER",
    2: "I-HEADER",
    3: "B-EXPERIENCE",
    4: "I-EXPERIENCE",
    5: "B-EDUCATION",
    6: "I-EDUCATION",
    7: "B-SKILLS",
    8: "I-SKILLS",
    9: "B-PROJECTS",
    10: "I-PROJECTS",
    11: "B-CERTIFICATIONS",
    12: "I-CERTIFICATIONS",
    13: "B-SUMMARY",
    14: "I-SUMMARY",
    15: "B-CONTACT",
    16: "I-CONTACT",
}
LABEL2ID = {v: k for k, v in ID2LABEL.items()}


class ResumeLayoutModel:
    """Handles LayoutLMv3 processing for section classification.

    If no fine-tuned model checkpoint is available, uses heuristic mapping.
    """

    def __init__(self, model_checkpoint: Optional[str] = None):
        self.use_heuristics = False

        if not HAS_TRANSFORMERS:
            logger.warning(
                "transformers/torch not installed. "
                "Falling back to pure heuristic layout analysis."
            )
            self.use_heuristics = True
            return

        if model_checkpoint is None:
            self.use_heuristics = True
            logger.info(
                "No fine-tuned LayoutLMv3 model provided. "
                "Using heuristic rule mapping."
            )
        else:
            try:
                self.processor = LayoutLMv3Processor.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )
                self.model = LayoutLMv3ForTokenClassification.from_pretrained(
                    model_checkpoint
                )
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model.to(self.device)
            except Exception as e:
                logger.error(
                    "Failed to load LayoutLMv3 model from %s: %s",
                    model_checkpoint, e,
                )
                self.use_heuristics = True

    def predict(
        self,
        image_path: str,
        words: List[str],
        boxes: List[tuple[int, int, int, int]],
    ) -> List[str]:
        """Run LayoutLMv3 classification. Returns label names parallel to *words*.

        If heuristics mode is active, routes to a rule-based mapping engine.
        """
        if self.use_heuristics:
            return self._heuristic_prediction(words, boxes)

        try:
            image = Image.open(image_path).convert("RGB")
            encoding = self.processor(
                image, words, boxes=boxes, return_tensors="pt"
            )
            encoding = {k: v.to(self.device) for k, v in encoding.items()}

            with torch.no_grad():
                outputs = self.model(**encoding)

            logits = outputs.logits
            predictions = logits.argmax(-1).squeeze().tolist()
            word_ids = encoding.word_ids(batch_index=0)

            # Map word-piece predictions back to whole words
            final_labels: List[str] = []
            previous_word_idx = None
            for idx, word_idx in enumerate(word_ids):
                if word_idx is None:
                    continue
                if word_idx != previous_word_idx:
                    final_labels.append(
                        ID2LABEL.get(predictions[idx], "O")
                    )
                previous_word_idx = word_idx

            # Ensure lengths match
            if len(final_labels) < len(words):
                final_labels.extend(["O"] * (len(words) - len(final_labels)))
            return final_labels[: len(words)]

        except Exception as e:
            logger.error(
                "LayoutLMv3 prediction failed: %s. Falling back to heuristics.", e
            )
            return self._heuristic_prediction(words, boxes)

    # ── heuristic fallback ───────────────────────────────────────

    # Keyword → BIO start label (expanded)
    _SECTION_STARTS: Dict[str, str] = {
        # experience
        "experience": "B-EXPERIENCE",
        "employment": "B-EXPERIENCE",
        "work": "B-EXPERIENCE",
        "internship": "B-EXPERIENCE",
        "internships": "B-EXPERIENCE",
        "career": "B-EXPERIENCE",
        # education
        "education": "B-EDUCATION",
        "academic": "B-EDUCATION",
        "qualifications": "B-EDUCATION",
        "degrees": "B-EDUCATION",
        # skills
        "skills": "B-SKILLS",
        "technologies": "B-SKILLS",
        "competencies": "B-SKILLS",
        "proficiencies": "B-SKILLS",
        "tools": "B-SKILLS",
        # projects
        "projects": "B-PROJECTS",
        "portfolio": "B-PROJECTS",
        # certifications
        "certifications": "B-CERTIFICATIONS",
        "certificates": "B-CERTIFICATIONS",
        "licenses": "B-CERTIFICATIONS",
        "credentials": "B-CERTIFICATIONS",
        "training": "B-CERTIFICATIONS",
        # summary
        "summary": "B-SUMMARY",
        "profile": "B-SUMMARY",
        "objective": "B-SUMMARY",
        "overview": "B-SUMMARY",
        # achievements / awards
        "achievements": "B-CERTIFICATIONS",
        "awards": "B-CERTIFICATIONS",
        "honors": "B-CERTIFICATIONS",
        "publications": "B-CERTIFICATIONS",
    }

    def _heuristic_prediction(
        self,
        words: List[str],
        boxes: List[tuple[int, int, int, int]],
    ) -> List[str]:
        """Simulates model predictions using layout heuristics and text.

        Uses expanded keyword mapping and left-alignment detection.
        """
        labels: List[str] = []
        current_section = "O"

        for w, box in zip(words, boxes):
            wl = w.lower().strip().rstrip(":")
            # If word is left-aligned (x < 300 on 1000-scale) it may be a header
            if wl in self._SECTION_STARTS and box[0] < 300:
                begin_label = self._SECTION_STARTS[wl]
                continue_label = begin_label.replace("B-", "I-")
                labels.append(begin_label)
                current_section = continue_label
            else:
                labels.append(current_section)

        return labels
