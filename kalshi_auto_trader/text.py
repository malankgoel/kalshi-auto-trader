"""Shared text normalization helpers."""

from __future__ import annotations


__all__ = ["has_text", "normalize_optional_text", "normalize_required_text"]


def has_text(value: str | None) -> bool:
    """Return True when a value has non-whitespace text after string coercion."""
    return value is not None and bool(str(value).strip())


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalize_required_text(value: str, label: str) -> str:
    normalized = normalize_optional_text(value)
    if normalized is None:
        raise ValueError(f"{label} is required")
    return normalized
