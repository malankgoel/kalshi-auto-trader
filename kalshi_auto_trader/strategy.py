"""Shared strategy metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Small identity record for a strategy package."""

    name: str
    package: str
    description: str
