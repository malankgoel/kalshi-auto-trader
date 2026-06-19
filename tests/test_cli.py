"""Offline tests for World Cup command-line parsing."""

import pytest

from kalshi_auto_trader.world_cup.trader import build_parser


def test_cli_accepts_positive_risk_overrides():
    args = build_parser().parse_args(["--bankroll", "75", "--max-total", "15"])
    assert args.bankroll == 75.0
    assert args.max_total == 15.0


@pytest.mark.parametrize("flag", ["--bankroll", "--max-total"])
def test_cli_rejects_nonpositive_risk_overrides(flag):
    with pytest.raises(SystemExit):
        build_parser().parse_args([flag, "0"])
