"""Shared risk accounting helpers for Kalshi-backed strategies."""

from __future__ import annotations


def remaining_run_budget(max_total_cost: float, spent_cost: float) -> float:
    """Dollars left before a run-level spend cap is exhausted."""
    return max(round(max_total_cost - spent_cost, 2), 0.0)


def exceeds_run_budget(spent_cost: float, next_cost: float, max_total_cost: float) -> bool:
    """Return True when adding ``next_cost`` would breach the run cap."""
    return round(spent_cost + next_cost, 2) > max_total_cost
