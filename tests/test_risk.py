"""Tests for shared risk accounting helpers."""

import math

import pytest

from kalshi_auto_trader import risk


def test_nonnegative_finite_predicate():
    assert risk.nonnegative_finite(0.0)
    assert risk.nonnegative_finite(1.25)
    assert not risk.nonnegative_finite(-0.01)
    assert not risk.nonnegative_finite(math.nan)
    assert not risk.nonnegative_finite(True)


def test_exceeds_run_budget_allows_exact_cap():
    assert not risk.exceeds_run_budget(7.25, 2.75, 10.0)


def test_run_budget_allows_exact_cap():
    assert risk.run_budget_allows(7.25, 2.75, 10.0)


def test_exceeds_run_budget_rejects_over_cap():
    assert risk.exceeds_run_budget(7.25, 2.76, 10.0)


def test_run_budget_allows_rejects_over_cap_and_nonfinite_inputs():
    assert not risk.run_budget_allows(7.25, 2.76, 10.0)
    assert not risk.run_budget_allows(math.nan, 1.0, 10.0)
    assert not risk.run_budget_allows(1.0, math.inf, 10.0)


def test_exceeds_run_budget_rejects_nonfinite_inputs():
    assert risk.exceeds_run_budget(math.nan, 1.0, 10.0)
    assert risk.exceeds_run_budget(1.0, math.inf, 10.0)
    assert risk.exceeds_run_budget(1.0, 2.0, math.nan)


def test_remaining_run_budget_never_negative():
    assert risk.remaining_run_budget(10.0, 7.25) == 2.75
    assert risk.remaining_run_budget(10.0, 12.0) == 0.0


def test_budget_usage_fraction_clamps_to_run_cap():
    assert risk.budget_usage_fraction(10.0, 2.5) == 0.25
    assert risk.budget_usage_fraction(10.0, 12.0) == 1.0
    assert risk.budget_usage_fraction(0.0, 1.0) == 0.0


def test_planned_total_cost_rounds_and_rejects_nonfinite_inputs():
    assert risk.planned_total_cost(1.234, 2.345) == 3.58
    assert risk.planned_total_cost(math.nan, 2.0) == math.inf


def test_run_budget_remaining_after_candidate_order():
    assert risk.run_budget_remaining_after(10.0, 4.25, 1.25) == 4.5
    assert risk.run_budget_remaining_after(10.0, 9.0, 2.0) == 0.0
    assert risk.run_budget_remaining_after(math.nan, 1.0, 2.0) == 0.0


def test_remaining_run_budget_rejects_nonfinite_inputs():
    assert risk.remaining_run_budget(math.inf, 1.0) == 0.0
    assert risk.remaining_run_budget(10.0, math.nan) == 0.0


def test_dollars_to_cents_rounds_to_integer_cents():
    assert risk.dollars_to_cents(12.345) == 1234


def test_dollars_to_cents_rejects_invalid_amounts():
    for value in (math.nan, math.inf, -1.0):
        with pytest.raises(ValueError):
            risk.dollars_to_cents(value)


def test_dollars_to_cents_rejects_boolean_amounts():
    with pytest.raises(ValueError):
        risk.dollars_to_cents(True)


def test_cents_to_dollars_converts_integer_cents():
    assert risk.cents_to_dollars(1234) == 12.34


def test_cents_to_dollars_rejects_invalid_amounts():
    for value in (-1, 1.5, True):
        with pytest.raises(ValueError):
            risk.cents_to_dollars(value)


def test_cost_to_cents_matches_dollar_conversion():
    assert risk.cost_to_cents(4.56) == 456


def test_balance_covers_cost_helper():
    assert risk.balance_covers_cost(456, 4.56)
    assert not risk.balance_covers_cost(455, 4.56)
    assert not risk.balance_covers_cost(True, 1.0)
    assert not risk.balance_covers_cost(100, math.nan)
