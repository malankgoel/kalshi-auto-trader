"""Offline tests for World Cup command-line parsing."""

import pytest

from kalshi_auto_trader import settings
from kalshi_auto_trader.world_cup.trader import (
    build_parser,
    resolve_environment,
    select_game,
)


def test_cli_accepts_positive_risk_overrides():
    args = build_parser().parse_args(["--bankroll", "75", "--max-total", "15"])
    assert args.bankroll == 75.0
    assert args.max_total == 15.0


def test_environment_resolver_maps_demo_flag():
    parser = build_parser()
    assert resolve_environment(parser.parse_args([])) == ("prod", None)
    assert resolve_environment(parser.parse_args(["--demo"])) == (
        "demo", settings.DEMO_BASE_URL,
    )


def test_game_selector_uses_match_id():
    args = build_parser().parse_args(["--match-id", "1"])
    game = select_game(args)
    assert game is not None
    assert game["match_id"] == "1"


@pytest.mark.parametrize("flag", ["--bankroll", "--max-total"])
def test_cli_rejects_nonpositive_risk_overrides(flag):
    with pytest.raises(SystemExit):
        build_parser().parse_args([flag, "0"])


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_cli_rejects_nonfinite_risk_overrides(value):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--bankroll", value])
