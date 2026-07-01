"""Shared risk accounting helpers for Kalshi-backed strategies."""

from __future__ import annotations

import math


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
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a non-negative finite number")
    return int(round(amount * 100))
