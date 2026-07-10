"""Shared strategy metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass

from kalshi_auto_trader.text import normalize_required_text


__all__ = ["StrategyMetadata"]


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Small identity record for a strategy package."""

    name: str
    package: str
    description: str

    def __post_init__(self) -> None:
        for field in ("name", "package", "description"):
            value = normalize_required_text(getattr(self, field), field)
            object.__setattr__(self, field, value)
