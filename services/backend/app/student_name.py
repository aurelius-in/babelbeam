"""Sanitize temporary classroom display names. Pure helpers, no I/O."""

from __future__ import annotations

import re

_MAX_LEN = 40
_WHITESPACE = re.compile(r"\s+")


def sanitize_display_name(raw: object) -> str:
    """Return a short display name, or empty if none is usable."""
    if not isinstance(raw, str):
        return ""
    cleaned = _WHITESPACE.sub(" ", raw.strip())
    if not cleaned:
        return ""
    return cleaned[:_MAX_LEN]
