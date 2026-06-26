"""Shared runtime settings for Kalshi-backed trading apps.

Keep use-case specifics, such as model data paths and market series tickers, in
the app package. This module should stay reusable for future strategies.
"""

from __future__ import annotations

import math
import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value >= 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def _env_choice(name: str, default: str, choices: frozenset[str]) -> str:
    value = os.environ.get(name, default).strip().lower()
    return value if value in choices else default


# --------------------------------------------------------------------------- #
# Generic betting rules                                                        #
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
TRADE_LOG_FILE = os.environ.get("KALSHI_TRADE_LOG_FILE", "")

# --------------------------------------------------------------------------- #
# Kalshi API                                                                  #
# --------------------------------------------------------------------------- #
PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
KALSHI_BASE_URL = os.environ.get("KALSHI_BASE_URL")  # full override if set

KALSHI_API_KEY_ID = os.environ.get("KALSHI_API_KEY_ID")
KALSHI_PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
KALSHI_HTTP_TIMEOUT = _env_int("KALSHI_HTTP_TIMEOUT", 20)
KALSHI_HTTP_RETRIES = max(1, _env_int("KALSHI_HTTP_RETRIES", 4))
KALSHI_MARKET_PAGE_LIMIT = _env_int("KALSHI_MARKET_PAGE_LIMIT", 200)

# --------------------------------------------------------------------------- #
# Order behaviour  (market <-> limit is one switch)                           #
# --------------------------------------------------------------------------- #
# "market" or "limit". Override per run with --order-type, or globally with
# KALSHI_ORDER_TYPE. Sizing is identical; only the price field sent differs.
ORDER_TYPES = frozenset({"market", "limit"})
ORDER_TYPE = _env_choice("KALSHI_ORDER_TYPE", "market", ORDER_TYPES)
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
