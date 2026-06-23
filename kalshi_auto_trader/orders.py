"""Reusable order sizing and parameter helpers."""

from __future__ import annotations

import math
import uuid
from typing import Literal

from kalshi_auto_trader import settings


def clamp_limit_price(price_cents: float) -> int:
    """Clamp a requested limit price into Kalshi's valid 1-99 cent range."""
    return max(
        settings.MIN_PRICE_CENTS,
        min(settings.MAX_PRICE_CENTS, int(round(price_cents))),
    )


def market_max_price(price_cents: float) -> float:
    """Maximum market-order cents per contract after slippage headroom."""
    return min(100.0, price_cents + settings.MARKET_SLIPPAGE_CENTS)


def size_order(stake_dollars: float, price_cents: float) -> int:
    """Whole contracts bought by ``stake_dollars`` at ``price_cents``."""
    if not (math.isfinite(stake_dollars) and math.isfinite(price_cents)):
        return 0
    if stake_dollars <= 0 or price_cents <= 0 or price_cents > 100:
        return 0
    count = int((stake_dollars * 100.0) // price_cents)
    count = min(count, settings.MAX_CONTRACTS_PER_ORDER)
    count = min(count, int((settings.MAX_ORDER_COST * 100.0) // price_cents))
    return max(count, 0)


def build_order_params(
    side: Literal["yes", "no"],
    count: int,
    price_cents: float,
    order_type: Literal["market", "limit"],
) -> dict:
    """Convert a side/count/ask into Kalshi order fields."""
    if side not in ("yes", "no"):
        raise ValueError("side must be 'yes' or 'no'")
    if order_type not in settings.ORDER_TYPES:
        raise ValueError("order_type must be 'market' or 'limit'")
    if count <= 0:
        raise ValueError("count must be positive")
    if not math.isfinite(price_cents) or not 0 < price_cents <= 100:
        raise ValueError("price_cents must be between 0 and 100")
    params = {
        "order_type": order_type,
        "yes_price": None,
        "no_price": None,
        "buy_max_cost": None,
        "risk_cost": None,
    }
    if order_type == "limit":
        limit_price = clamp_limit_price(price_cents + settings.LIMIT_BUFFER_CENTS)
        params["yes_price" if side == "yes" else "no_price"] = limit_price
        params["limit_price"] = limit_price
        params["est_cost"] = round(count * limit_price / 100.0, 2)
        params["risk_cost"] = params["est_cost"]
    else:
        max_price = market_max_price(price_cents)
        params["buy_max_cost"] = int(math.ceil(count * max_price))
        params["limit_price"] = None
        params["est_cost"] = round(count * price_cents / 100.0, 2)
        params["risk_cost"] = round(params["buy_max_cost"] / 100.0, 2)
    return params


def stable_client_order_id(namespace: str, key: str) -> str:
    """Deterministic UUID for idempotent Kalshi order submission."""
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, key))
