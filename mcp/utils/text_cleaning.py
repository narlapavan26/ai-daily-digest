"""
Text normalization helpers for MCP endpoints (HTML, LaTeX, markdown excerpts).
"""

from __future__ import annotations

import html
import re

_SENTENCE_END_CHARS = (". ", ".\n", "! ", "? ")


def clean_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_latex(text: str) -> str:
    """Remove LaTeX math markers while keeping readable text content."""
    if not text:
        return ""
    text = re.sub(r"\$\\[a-zA-Z]+\{([^}]*)\}\$", r"\1", text)
    text = re.sub(r"\$\\[a-zA-Z]+\$$", "", text)
    text = re.sub(r"\$([^$]{1,30})\$", r"\1", text)
    text = re.sub(r"\$[^$]*\$", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def truncate_at_sentence(text: str, limit: int = 1500) -> str:
    """Truncate text at a sentence boundary to avoid mid-word cuts."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_end = -1
    for sep in _SENTENCE_END_CHARS:
        last_end = max(last_end, truncated.rfind(sep))
    if last_end > limit // 2:
        return truncated[: last_end + 1].strip()
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return (truncated[:last_space] + "...").strip()
    return truncated + "..."


def clean_markdown_excerpt(text: str, max_chars: int = 2000) -> str:
    """Basic markdown cleanup for compact README/release excerpts."""
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = clean_html(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."
