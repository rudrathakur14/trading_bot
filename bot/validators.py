"""
Input validators for the trading bot CLI.
Validates symbols, sides, order types, quantities, and prices
before any API call is made.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("trading_bot.validators")

# Supported symbols (common Binance Futures USDT-M pairs)
SUPPORTED_SYMBOLS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "SOLUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT",
}

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}
SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}USDT$")


class ValidationError(Exception):
    """Raised when user input fails validation."""
    pass


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalise trading symbol.

    Args:
        symbol: Trading pair symbol (e.g. 'btcusdt').

    Returns:
        Upper-cased symbol string.

    Raises:
        ValidationError: If symbol format is invalid.
    """
    symbol = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(symbol):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Must be a USDT-margined pair "
            f"like BTCUSDT, ETHUSDT, etc."
        )
    logger.debug("Symbol validated: %s", symbol)
    return symbol


def validate_side(side: str) -> str:
    """
    Validate order side.

    Args:
        side: BUY or SELL.

    Returns:
        Upper-cased side string.

    Raises:
        ValidationError: If side is not BUY or SELL.
    """
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}"
        )
    logger.debug("Side validated: %s", side)
    return side


def validate_order_type(order_type: str) -> str:
    """
    Validate order type.

    Args:
        order_type: MARKET, LIMIT, or STOP_MARKET.

    Returns:
        Upper-cased order type string.

    Raises:
        ValidationError: If order type is unsupported.
    """
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}"
        )
    logger.debug("Order type validated: %s", order_type)
    return order_type


def validate_quantity(quantity: float) -> float:
    """
    Validate order quantity.

    Args:
        quantity: Positive number representing trade quantity.

    Returns:
        Validated quantity as float.

    Raises:
        ValidationError: If quantity is not a positive number.
    """
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(f"Quantity must be a number, got '{quantity}'.")

    if quantity <= 0:
        raise ValidationError(f"Quantity must be positive, got {quantity}.")

    logger.debug("Quantity validated: %s", quantity)
    return quantity


def validate_price(price: Optional[float], order_type: str) -> Optional[float]:
    """
    Validate price — required for LIMIT and STOP_MARKET orders.

    Args:
        price: Price value (can be None for MARKET orders).
        order_type: The order type (used to decide if price is required).

    Returns:
        Validated price as float, or None for MARKET orders.

    Raises:
        ValidationError: If price is missing when required or not positive.
    """
    requires_price = order_type in ("LIMIT", "STOP_MARKET")

    if requires_price and price is None:
        raise ValidationError(
            f"Price is required for {order_type} orders."
        )

    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError):
            raise ValidationError(f"Price must be a number, got '{price}'.")
        if price <= 0:
            raise ValidationError(f"Price must be positive, got {price}.")

    logger.debug("Price validated: %s", price)
    return price


def validate_stop_price(stop_price: Optional[float], order_type: str) -> Optional[float]:
    """
    Validate stop price — required for STOP_MARKET orders.

    Args:
        stop_price: Stop trigger price.
        order_type: The order type.

    Returns:
        Validated stop price or None.

    Raises:
        ValidationError: If stop price is missing for STOP_MARKET orders.
    """
    if order_type == "STOP_MARKET" and stop_price is None:
        raise ValidationError("Stop price is required for STOP_MARKET orders.")

    if stop_price is not None:
        try:
            stop_price = float(stop_price)
        except (TypeError, ValueError):
            raise ValidationError(f"Stop price must be a number, got '{stop_price}'.")
        if stop_price <= 0:
            raise ValidationError(f"Stop price must be positive, got {stop_price}.")

    logger.debug("Stop price validated: %s", stop_price)
    return stop_price


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> dict:
    """
    Run all validations and return a clean parameter dict.

    Returns:
        Dict with validated parameters ready for the API layer.

    Raises:
        ValidationError: On any validation failure.
    """
    validated = {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, order_type.strip().upper()),
    }

    if order_type.strip().upper() == "STOP_MARKET":
        validated["stop_price"] = validate_stop_price(stop_price, order_type.strip().upper())

    logger.info("All inputs validated successfully: %s", validated)
    return validated
