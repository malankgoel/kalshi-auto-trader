"""Tests for shared risk accounting helpers."""

import math

import pytest

from kalshi_auto_trader import risk


def test_exceeds_run_budget_allows_exact_cap():
    assert not risk.exceeds_run_budget(7.25, 2.75, 10.0)


def test_exceeds_run_budget_rejects_over_cap():
    assert risk.exceeds_run_budget(7.25, 2.76, 10.0)


def test_exceeds_run_budget_rejects_nonfinite_inputs():
    assert risk.exceeds_run_budget(math.nan, 1.0, 10.0)
    assert risk.exceeds_run_budget(1.0, math.inf, 10.0)
    assert risk.exceeds_run_budget(1.0, 2.0, math.nan)


def test_remaining_run_budget_never_negative():
    assert risk.remaining_run_budget(10.0, 7.25) == 2.75
    assert risk.remaining_run_budget(10.0, 12.0) == 0.0


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
