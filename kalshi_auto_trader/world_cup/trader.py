"""Self-contained Kalshi auto-trader for the next World Cup game.

When run, it: picks the next upcoming fixture (from the bundled schedule +
pre-tournament model), pulls that game's CURRENT Kalshi odds, de-vigs them,
flags every >=10% mispricing exactly as the backtest does, sizes each with
half-Kelly, and places the orders. A CSV ledger records submitted orders and is
settled from Kalshi market results before each run so the next game sizes from
the updated bankroll.

Order type is one switch: --order-type market|limit (or KALSHI_ORDER_TYPE).

SAFETY: dry-run is the DEFAULT -- nothing is sent unless you pass --live. Even
live, per-order/per-run dollar caps and an account-balance check apply, and each
order carries a deterministic client_order_id so re-running before a game can
never double-place (Kalshi rejects the duplicate).

    python3 execute_trades.py                     # dry-run, next game, market
    python3 execute_trades.py --order-type limit  # dry-run, limit pricing
    python3 execute_trades.py --demo --live       # place on the demo exchange
    python3 execute_trades.py --live              # place for real
    python3 execute_trades.py --home France --away Senegal   # a specific game

Env for live/demo: KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY_PATH.
"""

from __future__ import annotations

import argparse
import math
import sys

from kalshi_auto_trader import ledger, risk, settings
from kalshi_auto_trader.kalshi import KalshiClient
from kalshi_auto_trader.orders import (
    build_order_params,
    size_order,
    stable_client_order_id,
)
from kalshi_auto_trader.world_cup import config, markets as mm, model


__all__ = [
    "actionable_plans",
    "build_parser",
    "client_order_id",
    "live_auth_error",
    "main",
    "normalize_optional_text",
    "parse_args",
    "place_orders",
    "plan_bets",
    "positive_float",
    "print_header",
    "print_plan",
    "resolve_bankroll",
    "resolve_environment",
    "select_game",
    "total_risk_cost",
]


def client_order_id(game: dict, selection: str) -> str:
    """One bet -> one order, stable across re-runs (so Kalshi dedups retries)."""
    key = f"{game['date']}:{game['home_team']} vs {game['away_team']}:{selection}"
    return stable_client_order_id("kalshi-auto-trader", key)


# --------------------------------------------------------------------------- #
# planning                                                                    #
# --------------------------------------------------------------------------- #
def plan_bets(game: dict, bets: list, idx: dict, bankroll: float,
              order_type: str) -> list[dict]:
    plans: list[dict] = []
    running = 0.0
    for b in sorted(bets, key=lambda x: x.line):
        plan = {"selection": b.selection, "side": b.side, "line": b.line,
                "selection_team": b.selection_team,
                "model_prob": b.model_prob, "fair_prob": b.fair_prob,
                "edge": b.edge, "market_price_cents": b.market_price * 100.0,
                "kelly_fraction": model.staked_fraction(b.kelly_full),
                "skip": None}
        frac = plan["kelly_fraction"]
        stake = round(bankroll * frac, 2)
        plan["stake"] = stake
        if stake <= 0:
            plan["skip"] = "no +EV Kelly stake"; plans.append(plan); continue

        market, buy_side = mm.resolve_order(idx, b.line, b.side, b.selection,
                                            b.selection_team)
        if not market:
            plan["skip"] = "no live market"; plans.append(plan); continue
        ask = mm.side_ask_cents(market, buy_side)
        if ask is None or ask <= 0:
            plan["skip"] = "no ask price"; plans.append(plan); continue

        count = size_order(stake, ask)
        if count < 1:
            plan["skip"] = "stake < 1 contract"; plans.append(plan); continue

        params = build_order_params(buy_side, count, ask, order_type)
        if risk.exceeds_run_budget(running, params["risk_cost"], settings.MAX_TOTAL_COST):
            plan["skip"] = f"run cap ${settings.MAX_TOTAL_COST:.0f}"; plans.append(plan)
            continue
        running += params["risk_cost"]
        plan.update(ticker=market.get("ticker", ""), buy_side=buy_side,
                    ask=round(ask, 1), count=count,
                    client_order_id=client_order_id(game, b.selection), **params)
        plans.append(plan)
    return plans


# --------------------------------------------------------------------------- #
# rendering + execution                                                       #
# --------------------------------------------------------------------------- #
def actionable_plans(plans: list[dict]) -> list[dict]:
    return [p for p in plans if not p.get("skip")]


def total_risk_cost(plans: list[dict]) -> float:
    return round(sum(p["risk_cost"] for p in actionable_plans(plans)), 2)


def print_header(game: dict, odds: dict, bankroll: float, order_type: str,
                 live: bool) -> None:
    mode = "LIVE" if live else "DRY-RUN"
    print(f"\n=== {mode} · {order_type.upper()} · {game['home_team']} vs "
          f"{game['away_team']} ({game['date']}, kickoff {game['kickoff_utc']}) ===")
    print(f"Bankroll for sizing: ${bankroll:.2f}  ·  "
          f"edge >= {settings.EDGE_THRESHOLD:.0%}  ·  half-Kelly (cap "
          f"{settings.MAX_STAKE_FRACTION:.0%}/bet)")
    if not odds:
        print("No live Kalshi markets matched this game yet (may not be open). "
              "Try again closer to kickoff.")


def print_plan(plans: list[dict], live: bool) -> float:
    actionable = actionable_plans(plans)
    total = total_risk_cost(plans)
    print(f"\n{len(actionable)} order(s) to place / {len(plans)} flagged\n")
    hdr = (f"{'Selection':16} {'Mdl':>4} {'Fair':>4} {'Edge':>5} {'Ask':>5} "
           f"{'Cnt':>4} {'Price':>6} {'Max':>7}")
    print(hdr); print("-" * len(hdr))
    for p in plans:
        if p.get("skip"):
            print(f"{p['selection'][:16]:16} {p['model_prob']*100:>3.0f}% "
                  f"{p['fair_prob']*100:>3.0f}% {p['edge']*100:>+4.0f}% "
                  f"{'':>5} {'':>4} {'-- ' + p['skip']:>14}")
            continue
        price = p.get("limit_price")
        price_s = f"{price}c" if price is not None else "mkt"
        print(f"{p['selection'][:16]:16} {p['model_prob']*100:>3.0f}% "
              f"{p['fair_prob']*100:>3.0f}% {p['edge']*100:>+4.0f}% {p['ask']:>4.0f}c "
              f"{p['count']:>4} {price_s:>6} ${p['risk_cost']:>6.2f}")
    print("-" * len(hdr))
    print(f"{'TOTAL max cost':>54}  ${total:.2f}  (run cap ${settings.MAX_TOTAL_COST:.0f})")
    return total


def place_orders(client, game: dict, plans: list[dict], order_type: str,
                 bankroll: float, environment: str) -> None:
    for p in actionable_plans(plans):
        try:
            order = client.create_order(
                ticker=p["ticker"], action="buy", side=p["buy_side"],
                count=p["count"], order_type=order_type,
                client_order_id=p["client_order_id"],
                yes_price=p.get("yes_price"), no_price=p.get("no_price"),
                buy_max_cost=p.get("buy_max_cost"))
            ledger.append_order(game, p, order, bankroll=bankroll,
                                environment=environment,
                                path=config.TRADE_LOG_FILE)
            print(f"  placed {p['selection']:16} {p['count']:>4} @ {p['ticker']} "
                  f"-> {order.get('status', 'submitted')} ({order.get('order_id','')})")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "409" in msg or "duplicate" in msg.lower():
                print(f"  skip   {p['selection']:16} already placed earlier (dedup)")
            else:
                print(f"  FAILED {p['selection']:16} {p['ticker']}: {msg[:160]}")


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def resolve_bankroll(args, ledger_bankroll: float) -> float:
    if args.bankroll is not None:
        return args.bankroll
    return ledger_bankroll


def resolve_environment(args) -> tuple[str, str | None]:
    if args.demo:
        return "demo", settings.DEMO_BASE_URL
    return "prod", None


def select_game(args) -> dict | None:
    if args.match_id or (args.home and args.away):
        return model.find_game(args.match_id or "", args.home or "", args.away or "")
    return model.next_game()


def live_auth_error(live: bool, authenticated: bool) -> str | None:
    if live and not authenticated:
        return (
            "Live trading needs an API key. Set KALSHI_API_KEY_ID and "
            "KALSHI_PRIVATE_KEY_PATH (see README)."
        )
    return None


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be a finite number greater than zero"
        ) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError(
            "value must be a finite number greater than zero"
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--order-type", choices=sorted(settings.ORDER_TYPES),
                    default=settings.ORDER_TYPE)
    ap.add_argument("--live", action="store_true",
                    help="actually submit orders (default: dry-run)")
    ap.add_argument("--demo", action="store_true",
                    help="use Kalshi's demo exchange")
    ap.add_argument("--match-id", help="trade a specific fixture by schedule id")
    ap.add_argument("--home", help="home team (with --away) to trade a specific game")
    ap.add_argument("--away", help="away team")
    ap.add_argument("--bankroll", type=positive_float, default=None,
                    help="override Kelly bankroll (default: logged bankroll)")
    ap.add_argument("--max-total", type=positive_float, default=None,
                    help="override per-run total spend cap (dollars)")
    return ap


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.match_id = normalize_optional_text(args.match_id)
    args.home = normalize_optional_text(args.home)
    args.away = normalize_optional_text(args.away)
    if bool(args.home) != bool(args.away):
        parser.error("--home and --away must be provided together")
    if args.match_id and (args.home or args.away):
        parser.error("--match-id cannot be combined with --home/--away")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.max_total is not None:
        settings.MAX_TOTAL_COST = args.max_total

    environment, base_url = resolve_environment(args)
    client = KalshiClient(base_url=base_url)
    settled = ledger.settle_pending(client, path=config.TRADE_LOG_FILE)
    ledger_bankroll = ledger.current_bankroll(path=config.TRADE_LOG_FILE)
    if settled:
        print(f"Settled {settled} logged order(s). Ledger bankroll: "
              f"${ledger_bankroll:.2f}")
    auth_error = live_auth_error(args.live, client.authenticated)
    if auth_error:
        sys.exit(auth_error)

    game = select_game(args)
    if not game:
        sys.exit("No upcoming fixture with a model prediction was found.")

    idx = mm.build_market_index(client, game["home_team"], game["away_team"],
                                game["date"])
    odds = mm.build_odds_row(idx, game["home_team"], game["away_team"])
    bets = model.flag_bets(game, odds)

    bankroll = resolve_bankroll(args, ledger_bankroll)
    print_header(game, odds, bankroll, args.order_type, args.live)
    if not bets:
        print("\nNo line clears the threshold; nothing to bet.")
        return

    plans = plan_bets(game, bets, idx, bankroll, args.order_type)
    total = print_plan(plans, args.live)

    if not args.live:
        print("\nDRY-RUN: no orders sent. Add --live to place (or --demo --live "
              "to rehearse on the demo exchange).")
        return

    try:
        bal = client.get_balance().get("balance", 0)
        print(f"\nAccount balance: ${bal/100:.2f}")
        if risk.dollars_to_cents(total) > bal:
            sys.exit(f"Planned spend ${total:.2f} exceeds balance ${bal/100:.2f}. "
                     f"Aborting -- no orders sent.")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Could not read balance ({exc}). Aborting before placing.")

    place_orders(client, game, plans, args.order_type, bankroll, environment)
    print("\nDone.")


if __name__ == "__main__":
    main()
