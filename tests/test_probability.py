"""Tests for shared probability helpers."""

import math

from kalshi_auto_trader import probability


def test_is_probability_accepts_closed_unit_interval():
    assert probability.is_probability(0.0)
    assert probability.is_probability(0.5)
    assert probability.is_probability(1.0)


def test_is_probability_rejects_invalid_values():
    for value in (-0.1, 1.1, math.nan, math.inf):
        assert not probability.is_probability(value)


def test_cents_to_probability_converts_valid_quotes():
    assert probability.cents_to_probability("37.5") == 0.375
    assert probability.cents_to_probability(100) == 1.0


def test_cents_to_probability_rejects_invalid_quotes():
    for value in (None, "", "bad", -1, 101, math.nan):
        assert probability.cents_to_probability(value) is None
