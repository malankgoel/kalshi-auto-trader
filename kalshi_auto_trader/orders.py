"""Reusable order sizing and parameter helpers."""

from __future__ import annotations

import math
import uuid
from typing import Literal

from kalshi_auto_trader import settings
from kalshi_auto_trader.text import normalize_required_text


ORDER_SIDES = frozenset({"yes", "no"})
ORDER_ACTIONS = frozenset({"buy", "sell"})

__all__ = [
    "ORDER_ACTIONS",
    "ORDER_SIDES",
    "build_order_params",
    "clamp_limit_price",
    "market_max_price",
    "normalize_order_action",
    "normalize_order_side",
    "normalize_order_type",
    "size_order",
    "stable_client_order_id",
    "validate_buy_max_cost",
    "validate_limit_price",
    "validate_order_action",
    "validate_order_count",
    "validate_order_side",
    "validate_order_type",
]


def normalize_order_action(action: str) -> str:
    return normalize_required_text(action, "action").lower()


def normalize_order_side(side: str) -> str:
    return normalize_required_text(side, "side").lower()


def normalize_order_type(order_type: str) -> str:
    return normalize_required_text(order_type, "order_type").lower()


def validate_order_action(action: str) -> None:
    action = normalize_order_action(action)
    if action not in ORDER_ACTIONS:
        raise ValueError("action must be 'buy' or 'sell'")


def validate_order_side(side: str) -> None:
    side = normalize_order_side(side)
    if side not in ORDER_SIDES:
        raise ValueError("side must be 'yes' or 'no'")


def validate_order_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")


def validate_order_type(order_type: str) -> None:
    order_type = normalize_order_type(order_type)
    if order_type not in settings.ORDER_TYPES:
        raise ValueError("order_type must be 'market' or 'limit'")


def validate_limit_price(price_cents: int, side: str) -> None:
    if (
        isinstance(price_cents, bool)
        or not isinstance(price_cents, int)
        or not 1 <= price_cents <= 99
    ):
        raise ValueError(f"limit {side}_price must be between 1 and 99")


def validate_buy_max_cost(buy_max_cost: int) -> None:
    if (
        isinstance(buy_max_cost, bool)
        or not isinstance(buy_max_cost, int)
        or buy_max_cost <= 0
    ):
        raise ValueError("buy_max_cost must be a positive integer")


def clamp_limit_price(price_cents: float) -> int:
    """Clamp a requested limit price into Kalshi's valid 1-99 cent range."""
    if not math.isfinite(price_cents):
        raise ValueError("price_cents must be finite")
    return max(
        settings.MIN_PRICE_CENTS,
        min(settings.MAX_PRICE_CENTS, int(round(price_cents))),
    )


def market_max_price(price_cents: float) -> float:
    """Maximum market-order cents per contract after slippage headroom."""
    if not math.isfinite(price_cents):
        return 0.0
    return max(0.0, min(100.0, price_cents + settings.MARKET_SLIPPAGE_CENTS))


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
    side = normalize_order_side(side)
    order_type = normalize_order_type(order_type)
    validate_order_side(side)
    validate_order_type(order_type)
    validate_order_count(count)
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
    namespace = normalize_required_text(namespace, "namespace")
    key = normalize_required_text(key, "key")
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, key))
