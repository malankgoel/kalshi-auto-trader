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


@pytest.mark.parametrize("timeout", [0, 1.5, True])
def test_client_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="positive integer"):
        KalshiClient(timeout=timeout)


def test_list_markets_rejects_nonpositive_limit():
    client = KalshiClient()
    with pytest.raises(ValueError, match="limit"):
        client.list_markets(limit=0)


@pytest.mark.parametrize("limit", [1.5, True])
def test_list_markets_rejects_noninteger_limits(limit):
    client = KalshiClient()
    with pytest.raises(ValueError, match="positive integer"):
        client.list_markets(limit=limit)


@pytest.mark.parametrize("method", ["get", "post"])
def test_client_rejects_api_paths_without_leading_slash(method):
    client = KalshiClient()
    call = getattr(client, method)
    with pytest.raises(ValueError, match="API path"):
        call("markets", {} if method == "post" else None)


def test_get_market_requires_ticker():
    client = KalshiClient()
    with pytest.raises(ValueError, match="ticker"):
        client.get_market(" ")


def test_get_market_strips_ticker_before_request():
    client = KalshiClient()
    client.get = Mock(return_value={"market": {"ticker": "TEST-TICKER"}})

    assert client.get_market(" TEST-TICKER ") == {"ticker": "TEST-TICKER"}
    client.get.assert_called_once_with("/markets/TEST-TICKER")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"action": "hold"}, "action"),
        ({"side": "maybe"}, "side"),
        ({"order_type": "stop"}, "order_type"),
        ({"count": 0}, "count"),
        ({"ticker": " "}, "ticker"),
        ({"client_order_id": " "}, "client_order_id"),
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


@pytest.mark.parametrize("count", [1.5, True])
def test_create_order_rejects_noninteger_count_before_auth(count):
    client = KalshiClient()
    with pytest.raises(ValueError, match="positive integer"):
        client.create_order(
            ticker="TEST-TICKER",
            action="buy",
            side="yes",
            count=count,
            order_type="market",
            client_order_id="test-order",
        )


def test_create_order_strips_identifiers_before_posting():
    client = KalshiClient()
    client.post = Mock(return_value={"order": {"id": "created"}})

    assert client.create_order(
        ticker=" TEST-TICKER ",
        action="buy",
        side="yes",
        count=1,
        order_type="market",
        client_order_id=" order-1 ",
    ) == {"id": "created"}
    _, body = client.post.call_args.args
    assert body["ticker"] == "TEST-TICKER"
    assert body["client_order_id"] == "order-1"


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
