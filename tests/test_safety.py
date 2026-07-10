"""Regression tests for malformed inputs at strategy boundaries."""

import math

import pytest

from kalshi_auto_trader import settings
from kalshi_auto_trader.kalshi import KalshiClient
from kalshi_auto_trader.orders import (
    build_order_params,
    clamp_limit_price,
    market_max_price,
    size_order,
    stable_client_order_id,
    validate_buy_max_cost,
    validate_limit_price,
)
from kalshi_auto_trader.strategy import StrategyMetadata
from kalshi_auto_trader.world_cup import STRATEGY, STRATEGY_NAME, config, model
from kalshi_auto_trader.world_cup.trader import parse_args


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_size_order_rejects_nonfinite_values(value):
    assert size_order(value, 50) == 0
    assert size_order(10, value) == 0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_market_max_price_rejects_nonfinite_values(value):
    assert market_max_price(value) == 0.0


def test_market_max_price_floors_negative_prices():
    assert market_max_price(-10.0) == 0.0


def test_positive_int_env_parser_rejects_zero(monkeypatch):
    monkeypatch.setenv("KALSHI_TEST_POSITIVE_INT", "0")
    assert settings._env_positive_int("KALSHI_TEST_POSITIVE_INT", 4) == 4


def test_order_params_reject_out_of_range_price():
    with pytest.raises(ValueError, match="price_cents"):
        build_order_params("yes", 1, 101, "market")


@pytest.mark.parametrize("price", [None, 0, 100])
def test_limit_price_validator_rejects_out_of_range_values(price):
    with pytest.raises(ValueError, match="limit yes_price"):
        validate_limit_price(price, "yes")


@pytest.mark.parametrize("price", [1.5, True])
def test_limit_price_validator_rejects_noninteger_values(price):
    with pytest.raises(ValueError, match="limit no_price"):
        validate_limit_price(price, "no")


@pytest.mark.parametrize("buy_max_cost", [0, -1, 1.5, True])
def test_buy_max_cost_validator_rejects_invalid_values(buy_max_cost):
    with pytest.raises(ValueError, match="buy_max_cost"):
        validate_buy_max_cost(buy_max_cost)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_limit_price_clamp_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="finite"):
        clamp_limit_price(value)


@pytest.mark.parametrize(
    ("namespace", "key", "message"),
    [("", "x", "namespace"), ("ns", " ", "key")],
)
def test_stable_order_id_rejects_blank_inputs(namespace, key, message):
    with pytest.raises(ValueError, match=message):
        stable_client_order_id(namespace, key)


def test_stable_order_id_strips_inputs_before_hashing():
    assert stable_client_order_id(" world-cup ", " match-21 ") == stable_client_order_id(
        "world-cup",
        "match-21",
    )


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


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_kelly_rejects_nonfinite_values(value):
    assert model.kelly_fraction(value, 0.5) == 0.0
    assert model.kelly_fraction(0.6, value) == 0.0


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_kelly_rejects_out_of_range_model_probabilities(value):
    assert model.kelly_fraction(value, 0.5) == 0.0


@pytest.mark.parametrize("entry_price", [0.0, 1.0])
def test_kelly_rejects_endpoint_entry_prices(entry_price):
    assert model.kelly_fraction(0.6, entry_price) == 0.0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_staked_fraction_rejects_nonfinite_values(value):
    assert model.staked_fraction(value) == 0.0


def test_staked_fraction_floors_negative_values():
    assert model.staked_fraction(-0.1) == 0.0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_devig_three_way_rejects_nonfinite_values(value):
    assert model.devig_three_way(value, 0.3, 0.2) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_devig_three_way_rejects_out_of_range_values(value):
    assert model.devig_three_way(value, 0.3, 0.2) == (0.0, 0.0, 0.0)


def test_devig_binary_handles_nonfinite_values():
    assert model.devig_binary(math.nan, 0.4) == 0.0
    assert model.devig_binary(0.6, math.inf) == 0.6


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_devig_binary_rejects_out_of_range_yes_values(value):
    assert model.devig_binary(value, 0.4) == 0.0


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_devig_binary_ignores_out_of_range_no_values(value):
    assert model.devig_binary(0.6, value) == 0.6


@pytest.mark.parametrize("argv", [["--home", "France"], ["--away", "Senegal"]])
def test_cli_requires_both_fixture_teams(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_cli_strips_fixture_selectors():
    team_args = parse_args([
        "--home", " France ", "--away", " Senegal ",
    ])
    match_args = parse_args([
        "--match-id", " 21 ",
    ])
    assert team_args.home == "France"
    assert team_args.away == "Senegal"
    assert match_args.match_id == "21"


def test_cli_rejects_conflicting_fixture_selectors():
    with pytest.raises(SystemExit):
        parse_args(["--match-id", "21", "--home", "France", "--away", "Senegal"])


def test_market_series_configuration_is_immutable():
    assert all(isinstance(series, tuple) for series in config.KALSHI_SERIES.values())


def test_world_cup_strategy_metadata_matches_name():
    assert STRATEGY.name == STRATEGY_NAME
    assert STRATEGY.package == "kalshi_auto_trader.world_cup"


def test_strategy_metadata_requires_nonblank_fields():
    with pytest.raises(ValueError, match="name"):
        StrategyMetadata(name=" ", package="pkg", description="desc")


def test_strategy_metadata_strips_text_fields():
    metadata = StrategyMetadata(
        name=" World Cup ",
        package=" kalshi_auto_trader.world_cup ",
        description=" Match prediction strategy ",
    )
    assert metadata.name == "World Cup"
    assert metadata.package == "kalshi_auto_trader.world_cup"
    assert metadata.description == "Match prediction strategy"
