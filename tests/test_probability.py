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
