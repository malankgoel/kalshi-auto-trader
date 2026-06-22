"""Regression tests for malformed inputs at strategy boundaries."""

import math

import pytest

from kalshi_auto_trader.kalshi import KalshiClient
from kalshi_auto_trader.orders import build_order_params, size_order
from kalshi_auto_trader.world_cup import config, model
from kalshi_auto_trader.world_cup.trader import parse_args


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_size_order_rejects_nonfinite_values(value):
    assert size_order(value, 50) == 0
    assert size_order(10, value) == 0


def test_order_params_reject_out_of_range_price():
    with pytest.raises(ValueError, match="price_cents"):
        build_order_params("yes", 1, 101, "market")


def test_client_accepts_an_application_owned_session():
    session = object()
    client = KalshiClient(session=session)
    assert client.session is session


def test_invalid_live_price_is_ignored():
    game = {
        "model_over_2_5": 0.7,
        "model_btts": 0.5,
    }
    assert model.flag_bets(game, {"over_2_5_price": "not-a-price"}) == []


@pytest.mark.parametrize("argv", [["--home", "France"], ["--away", "Senegal"]])
def test_cli_requires_both_fixture_teams(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_market_series_configuration_is_immutable():
    assert all(isinstance(series, tuple) for series in config.KALSHI_SERIES.values())
