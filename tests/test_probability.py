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


def test_clamp_probability_bounds_values():
    assert probability.clamp_probability(-0.2) == 0.0
    assert probability.clamp_probability(0.4) == 0.4
    assert probability.clamp_probability(1.2) == 1.0
    assert probability.clamp_probability(math.nan) == 0.0


def test_cents_to_probability_converts_valid_quotes():
    assert probability.cents_to_probability("37.5") == 0.375
    assert probability.cents_to_probability(100) == 1.0


def test_cents_to_probability_rejects_invalid_quotes():
    for value in (None, "", "bad", -1, 101, math.nan):
        assert probability.cents_to_probability(value) is None


def test_probability_to_cents_converts_and_clamps_values():
    assert probability.probability_to_cents(0.375) == 37.5
    assert probability.probability_to_cents(-0.2) == 0.0
    assert probability.probability_to_cents(1.2) == 100.0


def test_probability_complement_handles_valid_and_invalid_values():
    assert probability.probability_complement(0.37) == 0.63
    assert probability.probability_complement(math.nan) == 0.0


def test_probability_edge_returns_model_minus_market():
    assert round(probability.probability_edge(0.62, 0.50), 2) == 0.12
    assert probability.probability_edge(math.nan, 0.50) == 0.0


def test_edge_clears_threshold_helper():
    assert probability.edge_clears_threshold(0.10, 0.10)
    assert not probability.edge_clears_threshold(0.099, 0.10)
    assert not probability.edge_clears_threshold(math.nan, 0.10)
