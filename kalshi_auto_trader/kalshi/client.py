"""Self-contained Kalshi REST client (reads + authenticated writes).

Public market data (``/markets``, ``/events``, ``/series``, candlesticks) is
readable without auth. Placing orders, reading balance, and reading positions
are write/account endpoints and require an RSA API key: set KALSHI_API_KEY_ID
and KALSHI_PRIVATE_KEY_PATH (a .pem downloaded from your Kalshi account).
Requests are signed RSA-PSS over ``timestamp + METHOD + path`` per Kalshi docs.

Docs: https://docs.kalshi.com/api-reference
"""

from __future__ import annotations

import base64
import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from kalshi_auto_trader import settings
from kalshi_auto_trader.orders import (
    validate_limit_price,
    validate_order_action,
    validate_order_count,
    validate_order_side,
    validate_order_type,
)

try:  # signing only needed when an API key is configured
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - optional dependency
    _HAVE_CRYPTO = False


class KalshiClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        key_id: Optional[str] = settings.KALSHI_API_KEY_ID,
        private_key_path: Optional[str] = settings.KALSHI_PRIVATE_KEY_PATH,
        timeout: int = settings.KALSHI_HTTP_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        base_url = base_url or settings.KALSHI_BASE_URL or settings.PROD_BASE_URL
        if not base_url.strip():
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.key_id = key_id
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self._private_key = None
        if key_id and private_key_path:
            if not _HAVE_CRYPTO:
                raise RuntimeError(
                    "cryptography is required for API-key auth: pip install cryptography"
                )
            with open(private_key_path, "rb") as fh:
                self._private_key = serialization.load_pem_private_key(
                    fh.read(), password=None
                )

    @property
    def authenticated(self) -> bool:
        return self._private_key is not None

    def close(self) -> None:
        """Release pooled HTTP connections held by the client session."""
        self.session.close()

    def __enter__(self) -> "KalshiClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # signing                                                            #
    # ------------------------------------------------------------------ #
    def _headers(self, method: str, path: str) -> dict[str, str]:
        if not self._private_key:
            return {}
        ts = str(int(time.time() * 1000))
        # Kalshi signs: timestamp + METHOD + path (path includes the API prefix,
        # excludes the query string and host).
        msg = (ts + method.upper() + path).encode("utf-8")
        sig = self._private_key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    # ------------------------------------------------------------------ #
    # low-level GET / POST                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _api_path(path: str) -> str:
        if not path.startswith("/"):
            raise ValueError("API path must start with '/'")
        return path

    def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        path = self._api_path(path)
        url = self.base_url + path
        sign_path = urlparse(url).path
        for attempt in range(settings.KALSHI_HTTP_RETRIES):
            headers = self._headers("GET", sign_path)
            resp = self.session.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
            if resp.status_code == 429:  # rate limited -> back off
                time.sleep(1.0 + attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}

    def post(self, path: str, body: dict) -> dict[str, Any]:
        """Authenticated POST. Raises on non-2xx with the server's error text
        attached so failures are debuggable."""
        path = self._api_path(path)
        if not self._private_key:
            raise RuntimeError(
                "A Kalshi API key is required for this action. Set "
                "KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH."
            )
        url = self.base_url + path
        sign_path = urlparse(url).path
        for attempt in range(settings.KALSHI_HTTP_RETRIES):
            headers = self._headers("POST", sign_path)  # fresh timestamp per try
            headers["Content-Type"] = "application/json"
            resp = self.session.post(
                url, json=body, headers=headers, timeout=self.timeout
            )
            if resp.status_code == 429:
                time.sleep(1.0 + attempt)
                continue
            if resp.status_code >= 400:
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.reason}: {resp.text}", response=resp
                )
            return resp.json() if resp.text else {}
        resp.raise_for_status()
        return {}

    # ------------------------------------------------------------------ #
    # market discovery (public)                                          #
    # ------------------------------------------------------------------ #
    def list_markets(self, *, series_ticker: Optional[str] = None,
                     event_ticker: Optional[str] = None,
                     status: Optional[str] = None,
                     limit: int = settings.KALSHI_MARKET_PAGE_LIMIT) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        out, cursor = [], None
        while True:
            params: dict[str, Any] = {"limit": limit}
            if series_ticker:
                params["series_ticker"] = series_ticker
            if event_ticker:
                params["event_ticker"] = event_ticker
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            data = self.get("/markets", params)
            out.extend(data.get("markets", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        return out

    def get_market(self, ticker: str) -> dict:
        ticker = ticker.strip()
        if not ticker:
            raise ValueError("ticker is required")
        return self.get(f"/markets/{ticker}").get("market", {})

    # ------------------------------------------------------------------ #
    # portfolio (auth required)                                          #
    # ------------------------------------------------------------------ #
    def get_balance(self) -> dict[str, Any]:
        """Account balance; ``balance`` is available cash in CENTS."""
        return self.get("/portfolio/balance")

    def get_positions(self) -> dict[str, Any]:
        return self.get("/portfolio/positions")

    def create_order(self, *, ticker: str, action: str, side: str, count: int,
                     order_type: str = "market", client_order_id: str,
                     yes_price: Optional[int] = None,
                     no_price: Optional[int] = None,
                     buy_max_cost: Optional[int] = None) -> dict[str, Any]:
        """Submit an order to POST /portfolio/orders.

        action "buy"|"sell"; side "yes"|"no"; count = contracts.
        order_type "market" or "limit". For a market BUY, ``buy_max_cost`` (in
        CENTS) caps total spend, bounding slippage. For a limit order, pass
        ``yes_price`` or ``no_price`` (1-99 cents). ``client_order_id`` dedupes:
        re-sending the same id is rejected (409), so a retry can't double-place.
        Returns the created order object.
        """
        ticker = ticker.strip()
        client_order_id = client_order_id.strip()
        if not ticker:
            raise ValueError("ticker is required")
        if not client_order_id:
            raise ValueError("client_order_id is required")
        validate_order_action(action)
        validate_order_side(side)
        validate_order_type(order_type)
        validate_order_count(count)
        if order_type == "limit":
            selected_price = yes_price if side == "yes" else no_price
            validate_limit_price(selected_price, side)
        body: dict[str, Any] = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "count": int(count),
            "type": order_type,
            "client_order_id": client_order_id,
        }
        if order_type == "limit":
            if yes_price is not None:
                body["yes_price"] = int(yes_price)
            if no_price is not None:
                body["no_price"] = int(no_price)
        if buy_max_cost is not None:
            body["buy_max_cost"] = int(buy_max_cost)
        return self.post("/portfolio/orders", body).get("order", {})
