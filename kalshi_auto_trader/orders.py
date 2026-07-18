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
    "estimated_order_cost",
    "finite_price_cents",
    "limit_order_price",
    "market_buy_max_cost",
    "market_max_price",
    "normalize_order_action",
    "normalize_order_side",
    "normalize_order_type",
    "order_action_is_valid",
    "order_count_is_valid",
    "order_side_is_valid",
    "order_type_is_valid",
    "size_order",
    "stable_client_order_id",
    "tradable_price_cents",
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


def order_action_is_valid(action: str) -> bool:
    try:
        return normalize_order_action(action) in ORDER_ACTIONS
    except ValueError:
        return False


def order_count_is_valid(count: int) -> bool:
    return not isinstance(count, bool) and isinstance(count, int) and count > 0


def order_side_is_valid(side: str) -> bool:
    try:
        return normalize_order_side(side) in ORDER_SIDES
    except ValueError:
        return False


def order_type_is_valid(order_type: str) -> bool:
    try:
        return normalize_order_type(order_type) in settings.ORDER_TYPES
    except ValueError:
        return False


def validate_order_action(action: str) -> None:
    action = normalize_order_action(action)
    if action not in ORDER_ACTIONS:
        raise ValueError("action must be 'buy' or 'sell'")


def validate_order_side(side: str) -> None:
    if not order_side_is_valid(side):
        raise ValueError("side must be 'yes' or 'no'")


def validate_order_count(count: int) -> None:
    if not order_count_is_valid(count):
        raise ValueError("count must be a positive integer")


def validate_order_type(order_type: str) -> None:
    if not order_type_is_valid(order_type):
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


def finite_price_cents(price_cents: float) -> bool:
    """Return True when a cents quote is a finite non-boolean number."""
    try:
        return not isinstance(price_cents, bool) and math.isfinite(price_cents)
    except TypeError:
        return False


def tradable_price_cents(price_cents: float) -> bool:
    """Return True when a quote can be used to size a buy order."""
    return finite_price_cents(price_cents) and 0 < price_cents <= 100


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
    if not finite_price_cents(price_cents):
        return 0.0
    return max(0.0, min(100.0, price_cents + settings.MARKET_SLIPPAGE_CENTS))


def estimated_order_cost(count: int, price_cents: float) -> float:
    validate_order_count(count)
    if not finite_price_cents(price_cents) or price_cents < 0:
        raise ValueError("price_cents must be a non-negative finite number")
    return round(count * price_cents / 100.0, 2)


def limit_order_price(price_cents: float) -> int:
    return clamp_limit_price(price_cents + settings.LIMIT_BUFFER_CENTS)


def market_buy_max_cost(count: int, price_cents: float) -> int:
    validate_order_count(count)
    return int(math.ceil(count * market_max_price(price_cents)))


def size_order(stake_dollars: float, price_cents: float) -> int:
    """Whole contracts bought by ``stake_dollars`` at ``price_cents``."""
    if not math.isfinite(stake_dollars) or not tradable_price_cents(price_cents):
        return 0
    if stake_dollars <= 0:
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
    if not tradable_price_cents(price_cents):
        raise ValueError("price_cents must be between 0 and 100")
    params = {
        "order_type": order_type,
        "yes_price": None,
        "no_price": None,
        "buy_max_cost": None,
        "risk_cost": None,
    }
    if order_type == "limit":
        limit_price = limit_order_price(price_cents)
        params["yes_price" if side == "yes" else "no_price"] = limit_price
        params["limit_price"] = limit_price
        params["est_cost"] = estimated_order_cost(count, limit_price)
        params["risk_cost"] = params["est_cost"]
    else:
        params["buy_max_cost"] = market_buy_max_cost(count, price_cents)
        params["limit_price"] = None
        params["est_cost"] = estimated_order_cost(count, price_cents)
        params["risk_cost"] = round(params["buy_max_cost"] / 100.0, 2)
    return params


def stable_client_order_id(namespace: str, key: str) -> str:
    """Deterministic UUID for idempotent Kalshi order submission."""
    namespace = normalize_required_text(namespace, "namespace")
    key = normalize_required_text(key, "key")
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, key))
