"""Tests for shared risk accounting helpers."""

from kalshi_auto_trader import risk


def test_exceeds_run_budget_allows_exact_cap():
    assert not risk.exceeds_run_budget(7.25, 2.75, 10.0)


def test_exceeds_run_budget_rejects_over_cap():
    assert risk.exceeds_run_budget(7.25, 2.76, 10.0)


def test_remaining_run_budget_never_negative():
    assert risk.remaining_run_budget(10.0, 7.25) == 2.75
    assert risk.remaining_run_budget(10.0, 12.0) == 0.0
