"""Shared probability conversion and validation helpers."""

from __future__ import annotations

import math
from typing import Optional


__all__ = [
    "cents_to_probability",
    "clamp_probability",
    "is_probability",
    "probability_edge",
    "probability_to_cents",
]


def is_probability(value: float) -> bool:
    return math.isfinite(value) and 0.0 <= value <= 1.0


def clamp_probability(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def cents_to_probability(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        cents = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(cents) or not 0 <= cents <= 100:
        return None
    return cents / 100.0


def probability_to_cents(value: float) -> float:
    return round(clamp_probability(value) * 100.0, 4)


def probability_edge(model_prob: float, fair_prob: float) -> float:
    """Model probability minus fair market probability."""
    if not (is_probability(model_prob) and is_probability(fair_prob)):
        return 0.0
    return model_prob - fair_prob
