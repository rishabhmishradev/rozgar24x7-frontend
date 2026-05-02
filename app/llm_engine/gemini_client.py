"""Gemini API client for resume analysis."""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Dict, Any, Optional, cast
import logging

from dotenv import load_dotenv
from app.llm_engine.base_client import BaseLLMClient
from app.llm_engine.json_utils import extract_json_object, repair_truncated_json_object

# Import the new Google GenAI library
try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)
MAX_RECOMMENDATION_ITEMS = 7
DEFAULT_REQUEST_TIMEOUT_SECONDS = 90
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

# Load environment variables from project root .env and override stale process values.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)


class GeminiAPIClient(BaseLLMClient):
    """Client for interacting with Gemini API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key. If None, reads from GOOGLE_API_KEY env var.
        """
        if genai is None:
            raise ImportError(
                "google-genai is not installed. "
                "Install with: pip install google-genai"
            )

        self.api_key = self._resolve_api_key(api_key)
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY not provided and not found in environment"
            )

        # Keep a single canonical model identifier to avoid invalid name formats from env overrides.
        self.model_name = DEFAULT_GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key)
        self.generation_config: Dict[str, Any] = {
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 3000,
            "candidate_count": 1,
        }
        timeout_env = os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "").strip()
        self.request_timeout_seconds = (
            int(timeout_env)
            if timeout_env.isdigit() and int(timeout_env) > 0
            else DEFAULT_REQUEST_TIMEOUT_SECONDS
        )

    @staticmethod
    def _resolve_api_key(explicit_key: Optional[str]) -> str:
        """Resolve API key from explicit arg or environment and normalize common copy/paste issues."""
        raw = explicit_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        key = str(raw).strip().strip('"').strip("'")

        # Guard against a common accidental prefix typo seen in copied keys.
        if key.startswith("AIAIza"):
            key = "AIza" + key[len("AIAIza"):]

        return key

    def _generate_content_with_timeout(self, prompt: str) -> Any:
        """Run model generation with explicit timeout guard."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=cast(Any, {**self.generation_config}),
            )
            try:
                return future.result(timeout=self.request_timeout_seconds)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise TimeoutError(
                    f"Gemini request timed out after {self.request_timeout_seconds} seconds"
                ) from exc

    def generate_text(self, prompt: str) -> str:
        """Simple text generation path without JSON extraction/validation."""
        response = self._generate_content_with_timeout(prompt)
        return self._extract_response_text(response).strip()

    def analyze_resume(
        self,
        prompt: str,
        max_retries: int = 3,
        required_keys: Optional[set[str]] = None,
        defaults: Optional[Dict[str, Any]] = None,
        key_types: Optional[Dict[str, type]] = None,
    ) -> Dict[str, Any]:
        """Analyze resume using Gemini API.
        
        Args:
            prompt: Full analysis prompt from PromptBuilder
            max_retries: Number of retries for API calls
            
        Returns:
            Dict containing parsed JSON response from Gemini
        """
        # Do not force full recommendation schema when callers provide partial keys.
        if required_keys is None:
            required_keys = set()

        if defaults is None:
            defaults = {}

        if key_types is None:
            key_types = {}

        generation_required_keys = {
            "summary",
            "experience",
            "projects",
            "education",
            "skills",
            "certifications",
        }
        is_generation_request = required_keys == generation_required_keys

        for attempt in range(max_retries):
            try:
                prompt_for_attempt = prompt
                if attempt > 0:
                    if is_generation_request:
                        prompt_for_attempt += (
                            "\n\nIMPORTANT: Previous response was truncated. "
                            "Return COMPLETE valid JSON and preserve required content length."
                        )
                    else:
                        prompt_for_attempt += (
                            "\n\nIMPORTANT: Previous response was truncated. "
                            "Return COMPLETE valid JSON with the SAME schema and SAME required keys. "
                            "Do NOT remove or rename keys."
                        )

                response = self._generate_content_with_timeout(prompt_for_attempt)
                logger.debug("LLM response received")

                # Extract JSON from response
                response_text = self._extract_response_text(response)
                if not response_text.strip():
                    raise ValueError("Empty LLM response")

                response_text = self._sanitize_response_text(response_text)
                logger.debug("LLM response sanitized; length=%s", len(response_text))

                # Check for obviously truncated responses (too short to be valid JSON)
                if len(response_text) < 30:
                    raise ValueError(f"Response too short to be valid JSON: {len(response_text)} chars")

                # Fail fast on obvious truncation to trigger retry.
                if not response_text.strip().endswith("}"):
                    repaired = self._attempt_json_repair(response_text)
                    if repaired:
                        response_text = repaired
                        logger.info("JSON repair succeeded; attempting extraction")
                    else:
                        raise ValueError("Truncated LLM response; could not repair")

                json_data = self._extract_json(response_text)

                if not json_data:
                    logger.warning(
                        f"Attempt {attempt + 1}: Could not extract JSON from response"
                    )
                    if attempt < max_retries - 1:
                        continue
                    raise ValueError("Failed to extract JSON from response")

                # Graceful key fallback: missing keys use defaults instead of hard-failing
                # This prevents retry loops when LLM returns partial JSON
                for key in required_keys:
                    if key not in json_data:
                        if defaults and key in defaults:
                            json_data[key] = defaults[key]
                            logger.warning(f"Missing key '{key}'; using default value")
                        else:
                            logger.warning(f"Missing key '{key}' with no default; skipping")

                # Coerce model output into expected top-level shapes where safe.
                if key_types:
                    json_data = self._coerce_key_types(json_data, key_types)

                # Guardrail: trim oversized recommendation arrays to schema max.
                for key in ("bullet_improvements", "skill_suggestions", "gap_explanations"):
                    value = json_data.get(key)
                    if isinstance(value, list):
                        value_list = cast(list[Any], value)
                        if len(value_list) > MAX_RECOMMENDATION_ITEMS:
                            json_data[key] = value_list[:MAX_RECOMMENDATION_ITEMS]

                # Validate schema
                self._validate_schema(json_data, required_keys, key_types)
                return json_data

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning("Attempt %s failed: %s", attempt + 1, str(e))
                else:
                    logger.error("Attempt %s failed: %s", attempt + 1, str(e))
                error_text = str(e).lower()
                is_invalid_key = (
                    "api_key_invalid" in error_text
                    or "api key expired" in error_text
                    or "invalid api key" in error_text
                    or "api key not valid" in error_text
                )
                if is_invalid_key:
                    raise ValueError(
                        "Gemini API key was rejected by the API. Verify the exact GOOGLE_API_KEY value loaded by the app process and restart Streamlit after updating .env."
                    ) from e
                is_overloaded = (
                    "503" in error_text
                    or "unavailable" in error_text
                    or "overloaded" in error_text
                )
                if is_overloaded and attempt < max_retries - 1:
                    backoff_seconds = 2 ** attempt
                    logger.warning(
                        "Gemini overloaded (attempt %s/%s). Backing off for %ss.",
                        attempt + 1,
                        max_retries,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    continue
                if attempt == max_retries - 1:
                    raise

        raise RuntimeError(f"Failed after {max_retries} attempts")

    @staticmethod
    def _coerce_key_types(data: Dict[str, Any], key_types: Dict[str, type]) -> Dict[str, Any]:
        """Coerce top-level fields to expected schema types when feasible."""
        normalized: Dict[str, Any] = dict(data)

        for key, expected_type in key_types.items():
            if key not in normalized:
                continue
            value = normalized.get(key)
            if isinstance(value, expected_type):
                continue

            if expected_type is str:
                if isinstance(value, list):
                    value_list = cast(list[Any], value)
                    normalized[key] = " | ".join(
                        str(item).strip() for item in value_list if str(item).strip()
                    )
                elif isinstance(value, dict):
                    value_dict = cast(Dict[Any, Any], value)
                    normalized[key] = " ".join(
                        str(v).strip() for v in value_dict.values() if str(v).strip()
                    )
                else:
                    normalized[key] = str(value or "")

            elif expected_type is list:
                if isinstance(value, tuple):
                    value_tuple = cast(tuple[Any, ...], value)
                    normalized[key] = list(value_tuple)
                elif isinstance(value, set):
                    value_set = cast(set[Any], value)
                    normalized[key] = list(value_set)
                elif isinstance(value, dict):
                    value_dict = cast(Dict[Any, Any], value)
                    normalized[key] = list(value_dict.values())
                elif isinstance(value, str):
                    normalized[key] = [value] if value.strip() else []

            elif expected_type is dict:
                if isinstance(value, list):
                    value_list = cast(list[Any], value)
                    # Common generation fallback for skills if model returns flat list.
                    normalized[key] = {
                        "programming_languages": [
                            str(item).strip() for item in value_list if str(item).strip()
                        ],
                        "data_science": [],
                        "data_visualization": [],
                        "databases": [],
                        "tools": [],
                    }
                elif isinstance(value, str):
                    normalized[key] = {}

        return normalized

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Collect full response text from candidates/content/parts when available."""
        text_chunks: list[str] = []

        candidates = getattr(response, "candidates", None)
        if not candidates:
            return ""

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue

            parts = getattr(content, "parts", None)
            if not parts:
                continue

            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_chunks.append(str(part_text))
                else:
                    try:
                        text_chunks.append(str(part))
                    except Exception:
                        pass

        return "\n".join(text_chunks)

    @staticmethod
    def _sanitize_response_text(response_text: str) -> str:
        """Normalize model output by trimming and removing markdown fences."""
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"^```", "", cleaned)
            cleaned = re.sub(r"```$", "", cleaned)

        return cleaned.strip()

    @staticmethod
    def _attempt_json_repair(text: str) -> Optional[str]:
        """Try minimal bracket balancing repair for partially truncated JSON."""
        return repair_truncated_json_object(text)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from text response.
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Parsed JSON dict or None if not found
        """
        extracted = extract_json_object(text)
        if extracted is None:
            return None
        return extracted

    @staticmethod
    def _validate_schema(
        data: Dict[str, Any],
        required_keys: Optional[set[str]] = None,
        key_types: Optional[Dict[str, type]] = None,
    ) -> bool:
        """Validate response matches expected schema.

        Args:
            data: Response data to validate
            required_keys: Required top-level keys
            key_types: Optional expected Python types for top-level keys

        Returns:
            True if valid

        Raises:
            ValueError if invalid
        """

        if required_keys is None:
            required_keys = {
                "bullet_improvements",
                "skill_suggestions",
                "gap_explanations",
            }

        if key_types is None and required_keys == {
            "bullet_improvements",
            "skill_suggestions",
            "gap_explanations",
        }:
            key_types = {
                "bullet_improvements": list,
                "skill_suggestions": list,
                "gap_explanations": list,
            }

        missing = required_keys - set(data.keys())
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        if key_types:
            for key, expected_type in key_types.items():
                if key in data and not isinstance(data.get(key), expected_type):
                    if expected_type is list:
                        raise ValueError(f"{key} must be a list")
                    raise ValueError(
                        f"{key} must be of type {expected_type.__name__}"
                    )

        return True

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "model": self.model_name,
            "temperature": 0.3,
            "max_output_tokens": 3000,
            "candidate_count": 1,
        }
