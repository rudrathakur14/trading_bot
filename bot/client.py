"""
Binance Futures Testnet API client.
Handles authentication, request signing, and low-level HTTP communication.
"""

import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("trading_bot.client")

# Binance Futures Testnet base URL
BASE_URL = "https://testnet.binancefuture.com"


class BinanceClientError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, status_code: int, code: int, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error [{status_code}] code={code}: {message}")


class BinanceClient:
    """
    Low-level wrapper around the Binance Futures Testnet REST API.

    Responsibilities:
        - HMAC-SHA256 request signing
        - Timestamp and recvWindow management
        - Structured error handling and logging
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = BASE_URL,
        recv_window: int = 5000,
    ):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window

        if not self.api_key or not self.api_secret:
            logger.warning(
                "API credentials not set. Provide them via constructor args "
                "or BINANCE_API_KEY / BINANCE_API_SECRET env vars."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

        logger.info("BinanceClient initialised — base_url=%s", self.base_url)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp, recvWindow, and HMAC-SHA256 signature to params."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window

        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        params["signature"] = signature
        return params

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Send an HTTP request to the Binance API.

        Args:
            method: HTTP method (GET, POST, DELETE, …).
            endpoint: API path (e.g. '/fapi/v1/order').
            params: Query / body parameters.
            signed: Whether to sign the request.

        Returns:
            Parsed JSON response dict.

        Raises:
            BinanceClientError: On API-level errors.
            requests.RequestException: On network-level failures.
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}

        if signed:
            params = self._sign(params)

        logger.info("API %s %s | params=%s", method, endpoint, {
            k: v for k, v in params.items() if k != "signature"
        })

        try:
            response = self.session.request(method, url, params=params, timeout=10)
        except requests.ConnectionError as exc:
            logger.error("Network error: %s", exc)
            raise
        except requests.Timeout:
            logger.error("Request timed out: %s %s", method, url)
            raise

        # Log raw response
        logger.debug("Response [%s]: %s", response.status_code, response.text[:500])

        # Handle errors
        if response.status_code >= 400:
            try:
                body = response.json()
                code = body.get("code", -1)
                msg = body.get("msg", response.text)
            except ValueError:
                code = -1
                msg = response.text
            logger.error(
                "API error — status=%s code=%s msg=%s",
                response.status_code, code, msg,
            )
            raise BinanceClientError(response.status_code, code, msg)

        return response.json()

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> Dict[str, Any]:
        """Fetch Binance server time (useful to check connectivity)."""
        return self._request("GET", "/fapi/v1/time")

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange trading rules and symbol info."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_ticker_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch the latest price for a symbol."""
        return self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})

    def get_account_info(self) -> Dict[str, Any]:
        """Fetch futures account information (signed)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    # ------------------------------------------------------------------
    # Order endpoints
    # ------------------------------------------------------------------

    def place_order(self, **params) -> Dict[str, Any]:
        """
        Place a new order (signed POST).

        Required params at minimum: symbol, side, type, quantity.
        """
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query a specific order by orderId."""
        return self._request(
            "GET", "/fapi/v1/order",
            {"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an active order."""
        return self._request(
            "DELETE", "/fapi/v1/order",
            {"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """List all open orders, optionally filtered by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params, signed=True)
