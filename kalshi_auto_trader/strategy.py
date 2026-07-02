"""Shared strategy metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Small identity record for a strategy package."""

    name: str
    package: str
    description: str

    def __post_init__(self) -> None:
        for field in ("name", "package", "description"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} is required")
