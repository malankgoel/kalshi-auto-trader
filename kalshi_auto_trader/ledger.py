"""Persistent CSV ledger for placed Kalshi auto-trader orders.

The log is intentionally simple: one row per successfully submitted order. Each
run first asks Kalshi whether pending markets have settled, updates those rows,
and derives the next sizing bankroll from the latest settled bankroll.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
import os
import tempfile
from typing import Optional

from kalshi_auto_trader import settings


COLUMNS = [
    "created_at",
    "updated_at",
    "environment",
    "status",
    "match_id",
    "date",
    "kickoff_utc",
    "home_team",
    "away_team",
    "line",
    "selection",
    "selection_team",
    "side",
    "buy_side",
    "ticker",
    "client_order_id",
    "order_id",
    "order_status",
    "model_prob",
    "fair_prob",
    "edge",
    "market_price_cents",
    "quoted_ask_cents",
    "recommended_stake",
    "kelly_fraction",
    "bankroll_before",
    "count",
    "order_type",
    "limit_price_cents",
    "buy_max_cost_cents",
    "estimated_cost",
    "placed_price_cents",
    "placed_price_source",
    "settled_at",
    "result",
    "profit",
    "bankroll_after",
]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_path(path: str | os.PathLike | None = None) -> str:
    resolved = os.fspath(path) if path else settings.TRADE_LOG_FILE
    if not resolved:
        raise ValueError("A trade log path is required.")
    return resolved


def ensure_log(path: str | os.PathLike | None = None) -> None:
    path = _resolve_path(path)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=COLUMNS).writeheader()


def read_rows(path: str | os.PathLike | None = None) -> list[dict]:
    path = _resolve_path(path)
    ensure_log(path)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(rows: list[dict], path: str | os.PathLike | None = None) -> None:
    path = _resolve_path(path)
    ensure_log(path)
    directory = os.path.dirname(os.path.abspath(path))
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=directory, delete=False
        ) as fh:
            temp_path = fh.name
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in COLUMNS})
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def current_bankroll(path: str | os.PathLike | None = None) -> float:
    """Latest settled bankroll, or the configured fallback for a fresh ledger."""
    rows = read_rows(path)
    bankroll = settings.BANKROLL
    found_settled = False
    for row in sorted(rows, key=lambda r: (r.get("settled_at", ""),
                                           r.get("created_at", ""))):
        val = row.get("bankroll_after")
        if val not in ("", None):
            parsed = _finite_float(val)
            if parsed is None:
                continue
            bankroll = parsed
            found_settled = True
    if not found_settled:
        for row in rows:
            val = row.get("bankroll_before")
            if val not in ("", None):
                parsed = _finite_float(val)
                if parsed is None:
                    continue
                bankroll = parsed
    return round(bankroll, 2)


def _field_cents(order: dict, *keys: str) -> Optional[float]:
    for key in keys:
        val = order.get(key)
        if val in ("", None):
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        return val * 100.0 if key.endswith("_dollars") else val
    return None


def placed_price(plan: dict, order: dict) -> tuple[float, str]:
    """Best available cents/contract actually attached to the submitted order.

    Kalshi market orders may not expose an immediate average fill in the create
    response, so we prefer fill/average fields when present and otherwise fall
    back to the submitted limit price or the ask used for sizing.
    """
    side = plan.get("buy_side", "")
    side_keys = ("yes_price", "yes_price_dollars") if side == "yes" else (
        "no_price", "no_price_dollars")
    for label, keys in (
        ("average_fill", ("average_fill_price", "average_fill_price_dollars",
                          "avg_fill_price", "avg_fill_price_dollars")),
        ("submitted_price", side_keys),
    ):
        cents = _field_cents(order, *keys)
        if cents is not None:
            return round(cents, 2), label
    if plan.get("limit_price") is not None:
        return float(plan["limit_price"]), "limit_price"
    return float(plan.get("ask", 0.0)), "quoted_ask"


def append_order(game: dict, plan: dict, order: dict, *, bankroll: float,
                 environment: str,
                 path: str | os.PathLike | None = None) -> None:
    rows = read_rows(path)
    coid = plan["client_order_id"]
    if any(r.get("client_order_id") == coid for r in rows):
        return
    now = _now()
    price, price_source = placed_price(plan, order)
    row = {
        "created_at": now,
        "updated_at": now,
        "environment": environment,
        "status": "pending",
        "match_id": game.get("match_id", ""),
        "date": game.get("date", ""),
        "kickoff_utc": game.get("kickoff_utc", ""),
        "home_team": game.get("home_team", ""),
        "away_team": game.get("away_team", ""),
        "line": plan.get("line", ""),
        "selection": plan.get("selection", ""),
        "selection_team": plan.get("selection_team", ""),
        "side": plan.get("side", ""),
        "buy_side": plan.get("buy_side", ""),
        "ticker": plan.get("ticker", ""),
        "client_order_id": coid,
        "order_id": order.get("order_id", order.get("id", "")),
        "order_status": order.get("status", "submitted"),
        "model_prob": _round(plan.get("model_prob")),
        "fair_prob": _round(plan.get("fair_prob")),
        "edge": _round(plan.get("edge")),
        "market_price_cents": _round(plan.get("market_price_cents")),
        "quoted_ask_cents": _round(plan.get("ask")),
        "recommended_stake": _money(plan.get("stake")),
        "kelly_fraction": _round(plan.get("kelly_fraction")),
        "bankroll_before": _money(bankroll),
        "count": plan.get("count", ""),
        "order_type": plan.get("order_type", ""),
        "limit_price_cents": plan.get("limit_price") or "",
        "buy_max_cost_cents": plan.get("buy_max_cost") or "",
        "estimated_cost": _money(plan.get("est_cost")),
        "placed_price_cents": _round(price),
        "placed_price_source": price_source,
    }
    rows.append(row)
    write_rows(rows, path)


def settle_pending(client, path: str | os.PathLike | None = None) -> int:
    """Update pending rows from Kalshi market settlement data.

    Returns the number of rows newly settled. Rows remain pending when Kalshi
    does not yet report a usable YES/NO result.
    """
    rows = read_rows(path)
    changed = 0
    for row in rows:
        if row.get("status") not in ("pending", "submitted", ""):
            continue
        winner = _market_winner(_safe_market(client, row.get("ticker", "")))
        if winner is None:
            continue
        price = _float(row.get("placed_price_cents")) / 100.0
        count = int(_float(row.get("count")))
        won = row.get("buy_side") == winner
        profit = round(count * (1.0 - price), 2) if won else round(-count * price, 2)
        row["status"] = "won" if won else "lost"
        row["result"] = winner
        row["profit"] = _money(profit)
        row["settled_at"] = _now()
        row["updated_at"] = row["settled_at"]
        changed += 1
    if changed:
        _recompute_bankrolls(rows)
        write_rows(rows, path)
    return changed


def _recompute_bankrolls(rows: list[dict]) -> None:
    bankroll: Optional[float] = None
    for row in rows:
        if bankroll is None:
            bankroll = _float(row.get("bankroll_before")) or settings.BANKROLL
        if row.get("status") not in ("won", "lost"):
            row["bankroll_after"] = ""
            continue
        bankroll = round(bankroll + _float(row.get("profit")), 2)
        row["bankroll_after"] = _money(bankroll)


def _safe_market(client, ticker: str) -> dict:
    if not ticker:
        return {}
    try:
        return client.get_market(ticker)
    except Exception:  # noqa: BLE001
        return {}


def _market_winner(market: dict) -> Optional[str]:
    for key in ("result", "settlement_value", "settled_result", "winning_side",
                "winner", "outcome"):
        val = _norm(market.get(key, ""))
        if val in ("yes", "y", "1", "true"):
            return "yes"
        if val in ("no", "n", "0", "false"):
            return "no"
    status = _norm(market.get("status", ""))
    if status not in ("settled", "closed", "finalized"):
        return None
    price = _field_cents(
        market, "last_price_dollars", "last_price",
        "previous_price_dollars", "previous_price",
    )
    if price is None:
        return None
    if price >= 99:
        return "yes"
    if price <= 1:
        return "no"
    return None


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _finite_float(value) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _float(value) -> float:
    return _finite_float(value) or 0.0


def _round(value) -> str:
    if value in ("", None):
        return ""
    return f"{float(value):.4f}"


def _money(value) -> str:
    if value in ("", None):
        return ""
    return f"{float(value):.2f}"
