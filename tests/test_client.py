"""Offline tests for reusable Kalshi client boundaries."""

from unittest.mock import Mock

import pytest

from kalshi_auto_trader.kalshi import KalshiClient


def test_client_context_manager_closes_session():
    client = KalshiClient()
    client.session.close = Mock()

    with client as active:
        assert active is client

    client.session.close.assert_called_once_with()


def test_list_markets_rejects_nonpositive_limit():
    client = KalshiClient()
    with pytest.raises(ValueError, match="limit"):
        client.list_markets(limit=0)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"action": "hold"}, "action"),
        ({"side": "maybe"}, "side"),
        ({"order_type": "stop"}, "order_type"),
        ({"count": 0}, "count"),
    ],
)
def test_create_order_rejects_invalid_fields_before_auth(override, message):
    client = KalshiClient()
    fields = {
        "ticker": "TEST-TICKER",
        "action": "buy",
        "side": "yes",
        "count": 1,
        "order_type": "market",
        "client_order_id": "test-order",
    }
    fields.update(override)

    with pytest.raises(ValueError, match=message):
        client.create_order(**fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"side": "yes", "yes_price": None},
        {"side": "yes", "yes_price": 100},
        {"side": "no", "no_price": 0},
    ],
)
def test_limit_order_requires_valid_selected_side_price(fields):
    client = KalshiClient()
    with pytest.raises(ValueError, match="limit .*_price"):
        client.create_order(
            ticker="TEST-TICKER",
            action="buy",
            count=1,
            order_type="limit",
            client_order_id="test-order",
            **fields,
        )
