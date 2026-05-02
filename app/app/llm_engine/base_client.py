"""Base abstraction for pluggable LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseLLMClient(ABC):
    """Provider-neutral client contract used by LLMAnalysisEngine."""

    @abstractmethod
    def analyze_resume(
        self,
        prompt: str,
        max_retries: int = 3,
        required_keys: Optional[set[str]] = None,
        defaults: Optional[Dict[str, Any]] = None,
        key_types: Optional[Dict[str, type]] = None,
    ) -> Dict[str, Any]:
        """Run prompt against model and return normalized JSON dict."""
        raise NotImplementedError
