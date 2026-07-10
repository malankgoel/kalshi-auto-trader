"""Offline tests: no network, no API keys. Covers the model math (de-vig, edge
flagging, Kelly), order sizing/params, price extraction, bet->market mapping,
and an end-to-end plan with an injected fake client. Run: python -m pytest -q
"""

import os
import sys

from pytest import approx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_auto_trader import ledger as trade_log
from kalshi_auto_trader import settings
from kalshi_auto_trader.orders import (
    clamp_limit_price,
    market_max_price,
    validate_order_action,
    validate_order_count,
    validate_order_side,
    validate_order_type,
)
from kalshi_auto_trader.world_cup import markets as mm
from kalshi_auto_trader.world_cup import model
from kalshi_auto_trader.world_cup import trader as ex


# ----------------------------- model: de-vig ------------------------------ #
def test_devig_three_way_sums_to_one():
    h, d, a = model.devig_three_way(0.55, 0.30, 0.25)  # overround 1.10
    assert h + d + a == approx(1.0)
    assert h == approx(0.5)


def test_devig_binary_complement():
    assert model.devig_binary(0.55, 0.50) == approx(55 / 105)
    assert model.devig_binary(0.40, None) == approx(0.40)  # no complement known


def test_kelly_zero_without_edge():
    assert model.kelly_fraction(0.40, 0.50) == 0.0          # price >= model
    assert model.kelly_fraction(0.60, 0.50) == approx(0.2)  # (.6-.5)/(1-.5)


def test_parse_kickoff_utc_handles_valid_and_invalid_values():
    assert model.parse_kickoff_utc("2026-06-16T20:00:00Z") is not None
    assert model.parse_kickoff_utc("not-a-time") is None


# ----------------------------- model: flagging ---------------------------- #
def _game():
    return {"home_team": "Argentina", "away_team": "Algeria", "date": "2026-06-16",
            "kickoff_utc": "2099-01-01T00:00:00Z",
            "model_home_win": 0.70, "model_draw": 0.20, "model_away_win": 0.10,
            "model_over_2_5": 0.40, "model_btts": 0.35}


def test_flag_fades_overpriced_favourite():
    # market (de-vigged) has Argentina ~57%, model 70% -> back YES Argentina.
    odds = {"winner_home_price": 60, "winner_draw_price": 25, "winner_away_price": 20}
    bets = model.flag_bets(_game(), odds)
    arg = [b for b in bets if "Argentina" in b.selection]
    assert arg and arg[0].side == "YES" and arg[0].edge >= settings.EDGE_THRESHOLD


def test_no_flag_when_market_agrees():
    odds = {"winner_home_price": 70, "winner_draw_price": 20, "winner_away_price": 10}
    # under-2.5: model 40% vs market 40% -> no edge either way
    odds.update(over_2_5_price=60, btts_yes_price=35)
    bets = model.flag_bets(_game(), odds)
    assert all(b.line != "btts" for b in bets)  # 35 vs 35 -> no btts bet


def test_under_is_no_side_on_over_market():
    odds = {"over_2_5_price": 60}   # market over 60%, model 40% -> bet UNDER (NO)
    bets = model.flag_bets(_game(), odds)
    ou = [b for b in bets if b.line == "over_under"][0]
    assert ou.side == "NO" and ou.selection == "UNDER 2.5"


# ----------------------------- sizing / params ---------------------------- #
def test_size_floor_and_caps(monkeypatch):
    assert ex.size_order(4.33, 45.0) == 9
    assert ex.size_order(0.30, 45.0) == 0
    monkeypatch.setattr(settings, "MAX_ORDER_COST", 2.0)
    assert ex.size_order(100.0, 50.0) == 4


def test_market_params_buy_max_cost(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_SLIPPAGE_CENTS", 3)
    p = ex.build_order_params("yes", 10, 44.0, "market")
    assert p["yes_price"] is None and p["buy_max_cost"] == 10 * 47
    assert p["est_cost"] == approx(4.40)
    assert p["risk_cost"] == approx(4.70)


def test_limit_params_side_and_clamp(monkeypatch):
    monkeypatch.setattr(settings, "LIMIT_BUFFER_CENTS", 2)
    p = ex.build_order_params("no", 8, 20.0, "limit")
    assert p["no_price"] == 22 and p["yes_price"] is None and p["buy_max_cost"] is None
    monkeypatch.setattr(settings, "LIMIT_BUFFER_CENTS", 10)
    assert ex.build_order_params("yes", 1, 95.0, "limit")["yes_price"] == 99


def test_order_params_normalize_side_text():
    params = ex.build_order_params(" NO ", 1, 20.0, "limit")
    assert params["no_price"] is not None


def test_order_params_normalize_order_type_text():
    params = ex.build_order_params("yes", 1, 20.0, " LIMIT ")
    assert params["limit_price"] is not None


def test_limit_price_clamp_bounds():
    assert clamp_limit_price(-4) == settings.MIN_PRICE_CENTS
    assert clamp_limit_price(101) == settings.MAX_PRICE_CENTS


def test_market_max_cost_never_exceeds_contract_payout(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_SLIPPAGE_CENTS", 10)
    p = ex.build_order_params("yes", 3, 95.0, "market")
    assert p["buy_max_cost"] == 300
    assert p["risk_cost"] == 3.0


def test_market_max_price_respects_contract_payout(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_SLIPPAGE_CENTS", 10)
    assert market_max_price(95.0) == 100.0
    assert market_max_price(44.0) == 54.0


def test_order_params_reject_invalid_inputs():
    with pytest.raises(ValueError, match="side"):
        ex.build_order_params("maybe", 1, 50.0, "market")
    with pytest.raises(ValueError, match="order_type"):
        ex.build_order_params("yes", 1, 50.0, "stop")
    with pytest.raises(ValueError, match="count"):
        ex.build_order_params("yes", 0, 50.0, "market")


def test_validate_order_side_rejects_invalid_side():
    validate_order_side("yes")
    with pytest.raises(ValueError, match="side"):
        validate_order_side("maybe")


def test_validate_order_count_rejects_invalid_count():
    validate_order_count(1)
    with pytest.raises(ValueError, match="positive integer"):
        validate_order_count(True)


def test_validate_order_type_rejects_invalid_type():
    validate_order_type("market")
    with pytest.raises(ValueError, match="order_type"):
        validate_order_type("stop")


def test_validate_order_action_rejects_invalid_action():
    validate_order_action("buy")
    with pytest.raises(ValueError, match="action"):
        validate_order_action("hold")


@pytest.mark.parametrize("count", [1.5, True])
def test_order_params_reject_noninteger_counts(count):
    with pytest.raises(ValueError, match="positive integer"):
        ex.build_order_params("yes", count, 50.0, "market")


# ----------------------------- price extraction --------------------------- #
def test_yes_price_mid_then_last():
    assert mm.yes_price_cents({"yes_bid": 40, "yes_ask": 44}) == approx(42.0)
    assert mm.yes_price_cents({"last_price_dollars": "0.37"}) == approx(37.0)


def test_yes_price_ignores_nonfinite_quotes():
    assert mm.yes_price_cents({"yes_bid": "nan", "last_price": 39}) == approx(39.0)


def test_yes_price_ignores_out_of_range_quotes():
    assert mm.yes_price_cents({"last_price": 101}) is None


def test_side_ask_complement():
    assert mm.side_ask_cents({"yes_bid": 40}, "no") == approx(60.0)
    assert mm.side_ask_cents({"yes_ask_dollars": "0.47"}, "yes") == approx(47.0)
    with pytest.raises(ValueError, match="side"):
        mm.side_ask_cents({}, "maybe")


def test_side_ask_normalizes_side_text():
    assert mm.side_ask_cents({"yes_ask": 44}, " YES ") == approx(44.0)


# ----------------------------- mapping ------------------------------------ #
def _index():
    return {"winner": {"argentina": {"ticker": "KXWCGAME-26JUN16ARGALG-ARG",
                                      "yes_bid": 58, "yes_ask": 62},
                       "algeria": {"ticker": "KXWCGAME-26JUN16ARGALG-ALG"}},
            "draw": {"ticker": "KXWCGAME-26JUN16ARGALG-TIE"},
            "over": {"ticker": "KXWCTOTAL-26JUN16ARGALG-T2.5"},
            "btts": {"ticker": "KXWCBTTS-26JUN16ARGALG-BTTS"}}


def test_resolve_winner_and_under():
    m, side = mm.resolve_order(_index(), "winner", "YES", "YES Argentina", "Argentina")
    assert m["ticker"].endswith("-ARG") and side == "yes"
    m2, s2 = mm.resolve_order(_index(), "over_under", "NO", "UNDER 2.5", "")
    assert m2["ticker"].startswith("KXWCTOTAL") and s2 == "no"


def test_build_odds_row_from_index():
    row = mm.build_odds_row(_index(), "Argentina", "Algeria")
    assert row["winner_home_price"] == approx(60.0)  # mid of 58/62


def test_fixture_matching_ignores_nonstring_dates():
    market = {
        "event_ticker": "KXWCGAME-26JUN16ARGALG",
        "yes_sub_title": "Argentina",
    }
    assert not mm._match_teams(market, "Argentina", "Algeria", True)


def test_client_order_id_stable():
    g = _game()
    assert ex.client_order_id(g, "YES Argentina") == ex.client_order_id(g, "YES Argentina")
    assert ex.client_order_id(g, "YES Argentina") != ex.client_order_id(g, "UNDER 2.5")


# ----------------------------- integration -------------------------------- #
class _FakeClient:
    authenticated = False
    def list_markets(self, *, series_ticker=None, status=None, **_):
        if series_ticker == "KXWCGAME" and status == "open":
            return [
                {"ticker": "KXWCGAME-26JUN16ARGALG-ARG", "yes_sub_title": "Argentina",
                 "event_ticker": "KXWCGAME-26JUN16ARGALG", "yes_bid": 58, "yes_ask": 62,
                 "no_ask": 42},
                {"ticker": "KXWCGAME-26JUN16ARGALG-ALG", "yes_sub_title": "Algeria",
                 "event_ticker": "KXWCGAME-26JUN16ARGALG", "yes_bid": 18, "yes_ask": 22,
                 "no_ask": 82},
                {"ticker": "KXWCGAME-26JUN16ARGALG-TIE", "yes_sub_title": "Tie",
                 "event_ticker": "KXWCGAME-26JUN16ARGALG", "yes_bid": 22, "yes_ask": 26,
                 "no_ask": 78},
            ]
        return []


def test_plan_bets_end_to_end():
    idx = mm.build_market_index(_FakeClient(), "Argentina", "Algeria", "2026-06-16")
    odds = mm.build_odds_row(idx, "Argentina", "Algeria")
    bets = model.flag_bets(_game(), odds)               # model home 70% >> market 60%
    plans = ex.plan_bets(_game(), bets, idx, bankroll=50.0, order_type="market")
    placed = [p for p in plans if not p.get("skip")]
    assert placed, "expected at least one actionable order"
    arg = [p for p in placed if "Argentina" in p["selection"]][0]
    assert arg["buy_side"] == "yes" and arg["count"] >= 1 and arg["buy_max_cost"]
    assert arg["risk_cost"] >= arg["est_cost"]


def test_actionable_plans_filters_skips():
    plans = [
        {"selection": "A", "skip": None},
        {"selection": "B", "skip": "no ask"},
    ]
    assert ex.actionable_plans(plans) == [plans[0]]


def test_total_risk_cost_ignores_skipped_plans():
    plans = [
        {"risk_cost": 1.235, "skip": None},
        {"risk_cost": 99.0, "skip": "cap"},
    ]
    assert ex.total_risk_cost(plans) == 1.24


# ----------------------------- trade log ---------------------------------- #
def test_trade_log_appends_and_settles(tmp_path):
    path = tmp_path / "trade_log.csv"
    game = _game()
    plan = {
        "client_order_id": ex.client_order_id(game, "YES Argentina"),
        "line": "winner", "selection": "YES Argentina",
        "selection_team": "Argentina", "side": "YES", "buy_side": "yes",
        "ticker": "KXWCGAME-26JUN16ARGALG-ARG",
        "model_prob": 0.70, "fair_prob": 0.60, "edge": 0.10,
        "market_price_cents": 60, "ask": 40, "stake": 10.0,
        "kelly_fraction": 0.20, "count": 10, "order_type": "limit",
        "limit_price": 40, "buy_max_cost": None, "est_cost": 4.0,
    }
    trade_log.append_order(game, plan, {"order_id": "abc", "status": "open"},
                           bankroll=50.0, environment="demo", path=str(path))
    rows = trade_log.read_rows(str(path))
    assert rows[0]["status"] == "pending"
    assert rows[0]["placed_price_cents"] == "40.0000"
    assert trade_log.current_bankroll(str(path)) == 50.0

    class _MarketClient:
        def get_market(self, ticker):
            assert ticker == plan["ticker"]
            return {"status": "settled", "result": "yes"}

    assert trade_log.settle_pending(_MarketClient(), str(path)) == 1
    settled = trade_log.read_rows(str(path))[0]
    assert settled["status"] == "won"
    assert settled["profit"] == "6.00"
    assert settled["bankroll_after"] == "56.00"
    assert trade_log.current_bankroll(str(path)) == 56.0


def test_placed_price_ignores_nonfinite_order_prices():
    plan = {"buy_side": "yes", "limit_price": 44, "ask": 40}
    order = {"average_fill_price": "nan", "yes_price": "inf"}
    assert trade_log.placed_price(plan, order) == (44.0, "limit_price")


def test_trade_log_strips_ticker_before_settlement_lookup(tmp_path):
    path = tmp_path / "trade_log.csv"
    trade_log.write_rows([
        {
            "status": "pending",
            "ticker": " TEST-TICKER ",
            "placed_price_cents": "40",
            "count": "1",
            "buy_side": "yes",
            "bankroll_before": "50.00",
        }
    ], path)

    class _MarketClient:
        def get_market(self, ticker):
            assert ticker == "TEST-TICKER"
            return {"status": "settled", "result": "yes"}

    assert trade_log.settle_pending(_MarketClient(), path) == 1


def test_trade_log_skips_invalid_settlement_rows(tmp_path):
    path = tmp_path / "trade_log.csv"
    trade_log.write_rows([
        {
            "status": "pending",
            "ticker": "TEST-TICKER",
            "placed_price_cents": "0",
            "count": "1",
            "buy_side": "yes",
            "bankroll_before": "50.00",
        }
    ], path)

    class _MarketClient:
        def get_market(self, _ticker):
            return {"status": "settled", "result": "yes"}

    assert trade_log.settle_pending(_MarketClient(), path) == 0
    assert trade_log.read_rows(path)[0]["status"] == "pending"


def test_trade_log_blanks_nonfinite_numeric_fields(tmp_path):
    path = tmp_path / "trade_log.csv"
    game = _game()
    plan = {
        "client_order_id": "nonfinite-row",
        "buy_side": "yes",
        "model_prob": float("nan"),
        "stake": float("inf"),
        "limit_price": 40,
        "ask": 40,
    }
    trade_log.append_order(
        game, plan, {}, bankroll=float("nan"), environment="demo", path=path
    )
    row = trade_log.read_rows(path)[0]
    assert row["model_prob"] == ""
    assert row["recommended_stake"] == ""
    assert row["bankroll_before"] == ""


def test_trade_log_repairs_empty_file(tmp_path):
    path = tmp_path / "trade_log.csv"
    path.touch()
    trade_log.ensure_log(path)
    assert path.read_text(encoding="utf-8").startswith("created_at,updated_at,")


def test_trade_log_rejects_blank_path():
    with pytest.raises(ValueError, match="trade log path"):
        trade_log.ensure_log(" ")


def test_trade_log_ignores_nonfinite_bankroll_values(tmp_path):
    path = tmp_path / "trade_log.csv"
    trade_log.write_rows([
        {"created_at": "1", "bankroll_before": "nan"},
        {"created_at": "2", "bankroll_before": "65.25"},
        {"created_at": "3", "settled_at": "3", "bankroll_after": "inf"},
    ], path)
    assert trade_log.current_bankroll(path) == 65.25
