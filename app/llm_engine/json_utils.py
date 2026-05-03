"""JSON utility helpers isolated from LLM orchestration logic."""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, Optional, cast

logger = logging.getLogger(__name__)


def dumps_compact_json(data: Any) -> str:
    """Serialize to compact JSON for prompt payloads."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=True)


def dumps_pretty_json(data: Any) -> str:
    """Serialize to readable JSON for diagnostics/prompt context."""
    return json.dumps(data, indent=2, ensure_ascii=True)


def loads_json(text: str) -> Any:
    """Parse JSON text and return Python object."""
    return json.loads(text)


def parse_json_or_python_literal(text: str) -> Optional[Any]:
    """Parse text as JSON first, then as Python literal fallback."""
    candidate = str(text or "").strip()
    if not candidate:
        return None

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        return ast.literal_eval(candidate)
    except (ValueError, SyntaxError):
        return None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract a top-level JSON object from full or mixed model output."""
    candidate = str(text or "").strip()
    if not candidate:
        return None

    # Direct parse first.
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return cast(Dict[str, Any], parsed)
    except (json.JSONDecodeError, ValueError):
        pass

    # Substring extraction for fenced/chatty responses.
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return cast(Dict[str, Any], parsed)
        except (json.JSONDecodeError, ValueError):
            pass

    # Last resort: truncated JSON repair.
    repaired = repair_truncated_json_object(candidate)
    if repaired:
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return cast(Dict[str, Any], parsed)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def repair_truncated_json_object(text: str) -> Optional[str]:
    """Try minimal bracket balancing repair for truncated JSON object text."""
    candidate = str(text or "").strip()
    if not candidate:
        return None

    try:
        if candidate.count("{") > candidate.count("}"):
            candidate += "}" * (candidate.count("{") - candidate.count("}"))
        if candidate.count("[") > candidate.count("]"):
            candidate += "]" * (candidate.count("[") - candidate.count("]"))

        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return candidate
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("Bracket-balancing repair failed: %s", exc)
        pass

    if "}" in candidate:
        try:
            trimmed = candidate.rsplit("}", 1)[0] + "}"
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict):
                return trimmed
        except (json.JSONDecodeError, ValueError):
            return None

    return None
