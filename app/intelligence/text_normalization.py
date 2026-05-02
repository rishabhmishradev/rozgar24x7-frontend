from __future__ import annotations

import re
from collections.abc import Iterable


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9+#./\s-]")
_TERM_NORMALIZATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bapps?\b"), "application"),
    (re.compile(r"\bapis?\b"), "api"),
    (re.compile(r"\bdatasets?\b"), "data"),
    (re.compile(r"\bcharts?\b"), "dashboard"),
    (re.compile(r"\bdashboards?\b"), "dashboard"),
    (re.compile(r"\breports?\b"), "report"),
    (re.compile(r"\binsights?\b"), "insight"),
    (re.compile(r"\bmetrics?\b"), "metric"),
    (re.compile(r"\bstakeholders?\b"), "stakeholder"),
    (re.compile(r"\bvisualizations?\b"), "visualization"),
)

_VERB_GROUPS: dict[str, tuple[str, ...]] = {
    "build": ("build", "building", "built", "develop", "developing", "developed", "create", "creating", "created", "prepare", "preparing", "prepared"),
    "analyze": ("analyze", "analyzing", "analyzed", "analyse", "analysing", "analysed", "evaluate", "evaluating", "evaluated", "assess", "assessing", "assessed"),
    "deploy": ("deploy", "deploying", "deployed", "launch", "launching", "launched"),
    "manage": ("manage", "managing", "managed", "coordinate", "coordinating", "coordinated", "lead", "leading", "led"),
    "optimize": ("optimize", "optimizing", "optimized", "optimise", "optimising", "optimised", "improve", "improving", "improved", "enhance", "enhancing", "enhanced"),
    "communicate": ("communicate", "communicating", "communicated", "present", "presenting", "presented", "report", "reporting", "reported", "document", "documenting", "documented", "deliver", "delivering", "delivered"),
}

VERB_NORMALIZATION_MAP: dict[str, str] = {
    variant: root
    for root, variants in _VERB_GROUPS.items()
    for variant in variants
}

_STOPWORDS = {
    "a", "an", "and", "for", "in", "of", "on", "the", "to", "with",
    "by", "from", "using", "into", "across", "through", "or",
}


def normalize_text_basic(text: str) -> str:
    value = str(text or "").lower()
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)
    value = _PUNCT_RE.sub(" ", value)
    for pattern, replacement in _TERM_NORMALIZATION_PATTERNS:
        value = pattern.sub(replacement, value)
    value = _WHITESPACE_RE.sub(" ", value).strip()
    return value


def normalize_action_verbs(text: str) -> str:
    tokens = normalize_text_basic(text).split()
    normalized = [VERB_NORMALIZATION_MAP.get(token, token) for token in tokens]
    return " ".join(normalized).strip()


def token_set(text: str) -> set[str]:
    tokens = normalize_action_verbs(text).split()
    return {token for token in tokens if token and token not in _STOPWORDS}


def _ngrams(tokens: Iterable[str], size: int) -> set[str]:
    values = [token for token in tokens if token]
    if len(values) < size:
        return set()
    return {" ".join(values[idx: idx + size]) for idx in range(len(values) - size + 1)}


def soft_phrase_overlap(target: str, bullet: str) -> float:
    target_norm = normalize_action_verbs(target)
    bullet_norm = normalize_action_verbs(bullet)
    if not target_norm or not bullet_norm:
        return 0.0
    if target_norm == bullet_norm or target_norm in bullet_norm:
        return 1.0

    target_tokens = [token for token in target_norm.split() if token not in _STOPWORDS]
    bullet_tokens = [token for token in bullet_norm.split() if token not in _STOPWORDS]
    if not target_tokens or not bullet_tokens:
        return 0.0

    token_overlap = len(set(target_tokens) & set(bullet_tokens)) / max(1, len(set(target_tokens)))
    target_bigrams = _ngrams(target_tokens, 2)
    bullet_bigrams = _ngrams(bullet_tokens, 2)
    bigram_overlap = (
        len(target_bigrams & bullet_bigrams) / max(1, len(target_bigrams))
        if target_bigrams else 0.0
    )
    return min(1.0, (0.7 * token_overlap) + (0.3 * bigram_overlap))
