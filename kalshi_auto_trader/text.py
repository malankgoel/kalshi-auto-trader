"""Shared text normalization helpers."""

from __future__ import annotations


__all__ = ["normalize_optional_text", "normalize_required_text"]


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
