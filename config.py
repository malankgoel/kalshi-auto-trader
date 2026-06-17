"""Configuration for the self-contained Kalshi auto-trader.

This repo carries everything it needs: the pre-tournament model snapshot and the
schedule live in ``data/``. At run time it picks the next game, pulls that game's
current Kalshi odds, flags >=10% mispricings exactly as the backtest does, sizes
them with half-Kelly, and places the orders. No external files; the only local
state is the trade log used for settlement and bankroll tracking.

Every knob has an environment-variable override so you don't edit code to go
live, switch order type, or change risk caps.
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Bundled model data (this repo is self-contained)                            #
# --------------------------------------------------------------------------- #
DATA_DIR = os.path.join(HERE, "data")
# The pre-tournament forecast: trained on data through 2026-06-10, before any
# 2026 World Cup match was played. This is the model the edges are measured
# against -- a later, hindsight-refit snapshot would inflate the "edge".
PREDICTIONS_FILE = os.path.join(DATA_DIR, "match_predictions.csv")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule_2026.csv")

# --------------------------------------------------------------------------- #
# Betting rules (must mirror the model's backtest)                            #
# --------------------------------------------------------------------------- #
EDGE_THRESHOLD = _env_float("EDGE_THRESHOLD", 0.10)   # flag a line at >=10% edge
OVER_UNDER_LINE = 2.5
KELLY_FRACTION = _env_float("KELLY_FRACTION", 0.50)   # half-Kelly
MAX_STAKE_FRACTION = _env_float("MAX_STAKE_FRACTION", 0.25)  # cap per bet

# Bankroll for Kelly sizing. When trading live with a key, the trader uses your
# logged bankroll after settled trades instead; this is the starting/fallback
# bankroll for dry-runs and a new empty ledger. Override with --bankroll or
# BANKROLL.
BANKROLL = _env_float("BANKROLL", 50.0)
TRADE_LOG_FILE = os.environ.get(
    "KALSHI_TRADE_LOG_FILE", os.path.join(DATA_DIR, "trade_log.csv")
)

# --------------------------------------------------------------------------- #
# Kalshi API                                                                  #
# --------------------------------------------------------------------------- #
PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
KALSHI_BASE_URL = os.environ.get("KALSHI_BASE_URL")  # full override if set

KALSHI_API_KEY_ID = os.environ.get("KALSHI_API_KEY_ID")
KALSHI_PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH")

# 2026 World Cup per-match series. MUST match the wording the markets use.
KALSHI_SERIES = {
    "winner": ["KXWCGAME"],
    "over_under": ["KXWCTOTAL"],
    "btts": ["KXWCBTTS"],
}

# --------------------------------------------------------------------------- #
# Order behaviour  (market <-> limit is one switch)                           #
# --------------------------------------------------------------------------- #
# "market" or "limit". Override per run with --order-type, or globally with
# KALSHI_ORDER_TYPE. Sizing is identical; only the price field sent differs.
ORDER_TYPE = os.environ.get("KALSHI_ORDER_TYPE", "market").lower()
LIMIT_BUFFER_CENTS = _env_int("KALSHI_LIMIT_BUFFER_CENTS", 2)     # limit = ask + this
MARKET_SLIPPAGE_CENTS = _env_int("KALSHI_MARKET_SLIPPAGE_CENTS", 3)  # market buy_max_cost headroom

# --------------------------------------------------------------------------- #
# Risk caps  (hard stops, enforced regardless of model stake)                 #
# --------------------------------------------------------------------------- #
MAX_CONTRACTS_PER_ORDER = _env_int("MAX_CONTRACTS_PER_ORDER", 500)
MAX_ORDER_COST = _env_float("MAX_ORDER_COST", 25.0)    # dollars, single order
MAX_TOTAL_COST = _env_float("MAX_TOTAL_COST", 100.0)   # dollars, one run total
MIN_PRICE_CENTS = 1
MAX_PRICE_CENTS = 99
