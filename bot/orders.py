"""
Order placement logic.
Bridges validated user input → Binance API calls → formatted output.
"""

import logging
from typing import Any, Dict, Optional

from bot.client import BinanceClient, BinanceClientError

logger = logging.getLogger("trading_bot.orders")


# ── Pretty output helpers ────────────────────────────────────────────

def _print_divider(char: str = "─", width: int = 55):
    print(char * width)


def print_order_summary(params: Dict[str, Any]):
    """Print a human-readable order request summary before submission."""
    _print_divider()
    print("  📋  ORDER REQUEST SUMMARY")
    _print_divider()
    print(f"  Symbol     : {params.get('symbol')}")
    print(f"  Side       : {params.get('side')}")
    print(f"  Type       : {params.get('order_type')}")
    print(f"  Quantity   : {params.get('quantity')}")
    if params.get("price") is not None:
        print(f"  Price      : {params.get('price')}")
    if params.get("stop_price") is not None:
        print(f"  Stop Price : {params.get('stop_price')}")
    _print_divider()


def print_order_response(response: Dict[str, Any], success: bool = True):
    """Print the API response in a clean tabular format."""
    _print_divider("═")
    status_icon = "✅" if success else "❌"
    print(f"  {status_icon}  ORDER RESPONSE")
    _print_divider("═")
    fields = [
        ("Order ID", "orderId"),
        ("Symbol", "symbol"),
        ("Side", "side"),
        ("Type", "type"),
        ("Status", "status"),
        ("Quantity", "origQty"),
        ("Executed Qty", "executedQty"),
        ("Price", "price"),
        ("Avg Price", "avgPrice"),
        ("Stop Price", "stopPrice"),
        ("Time In Force", "timeInForce"),
        ("Working Type", "workingType"),
        ("Update Time", "updateTime"),
    ]
    for label, key in fields:
        value = response.get(key)
        if value is not None and str(value) != "0" and str(value) != "0.00000000":
            print(f"  {label:<14}: {value}")
    _print_divider("═")


# ── Order placement ──────────────────────────────────────────────────

def place_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Place an order on Binance Futures Testnet.

    Args:
        client: Authenticated BinanceClient instance.
        symbol: Trading pair (e.g. BTCUSDT).
        side: BUY or SELL.
        order_type: MARKET, LIMIT, or STOP_MARKET.
        quantity: Order size.
        price: Limit price (required for LIMIT).
        stop_price: Trigger price (required for STOP_MARKET).
        time_in_force: Time-in-force policy (default GTC).

    Returns:
        API response dict on success.

    Raises:
        BinanceClientError: On API errors.
    """
    # Build request params
    params: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": str(quantity),
    }

    if order_type == "LIMIT":
        params["price"] = str(price)
        params["timeInForce"] = time_in_force

    if order_type == "STOP_MARKET":
        params["stopPrice"] = str(stop_price)
        params["closePosition"] = "false"
        if price is not None:
            params["price"] = str(price)

    # Log the request
    order_summary = {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price,
        "stop_price": stop_price,
    }
    print_order_summary(order_summary)
    logger.info("Placing order: %s", order_summary)

    try:
        response = client.place_order(**params)
        logger.info(
            "Order placed successfully — orderId=%s status=%s",
            response.get("orderId"),
            response.get("status"),
        )
        print_order_response(response, success=True)
        print("\n  ✅  Order placed successfully!\n")
        return response

    except BinanceClientError as exc:
        logger.error("Order failed — %s", exc)
        print_order_response(
            {"orderId": "N/A", "status": "FAILED", "error": exc.message},
            success=False,
        )
        print(f"\n  ❌  Order failed: {exc.message}\n")
        raise
