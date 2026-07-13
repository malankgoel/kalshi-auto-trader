"""Shared risk accounting helpers for Kalshi-backed strategies."""

from __future__ import annotations

import math


__all__ = [
    "cents_to_dollars",
    "cost_to_cents",
    "dollars_to_cents",
    "exceeds_run_budget",
    "remaining_run_budget",
]


def remaining_run_budget(max_total_cost: float, spent_cost: float) -> float:
    """Dollars left before a run-level spend cap is exhausted."""
    if not (math.isfinite(max_total_cost) and math.isfinite(spent_cost)):
        return 0.0
    return max(round(max_total_cost - spent_cost, 2), 0.0)


def exceeds_run_budget(spent_cost: float, next_cost: float, max_total_cost: float) -> bool:
    """Return True when adding ``next_cost`` would breach the run cap."""
    if not all(math.isfinite(v) for v in (spent_cost, next_cost, max_total_cost)):
        return True
    return round(spent_cost + next_cost, 2) > max_total_cost


def dollars_to_cents(amount: float) -> int:
    """Convert a non-negative dollar amount to integer cents."""
    if isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a non-negative finite number")
    return int(round(amount * 100))


def cents_to_dollars(amount_cents: int) -> float:
    """Convert a non-negative integer cent amount to dollars."""
    if (
        isinstance(amount_cents, bool)
        or not isinstance(amount_cents, int)
        or amount_cents < 0
    ):
        raise ValueError("amount_cents must be a non-negative integer")
    return round(amount_cents / 100.0, 2)


def cost_to_cents(cost_dollars: float) -> int:
    """Convert a planned dollar cost to cents for balance comparisons."""
    return dollars_to_cents(cost_dollars)
