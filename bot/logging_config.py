"""
Logging configuration for the trading bot.
Sets up structured logging to both console and rotating log files.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_dir: str = "logs", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        log_dir: Directory to store log files.
        log_level: Logging level (default: INFO).

    Returns:
        Configured logger instance.
    """
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("trading_bot")
    logger.setLevel(log_level)

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # --- Log format ---
    detailed_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # --- Rotating file handler (general log) ---
    general_log = os.path.join(log_dir, "trading_bot.log")
    file_handler = RotatingFileHandler(
        general_log, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_fmt)

    # --- Rotating file handler (orders only) ---
    orders_log = os.path.join(log_dir, "orders.log")
    orders_handler = RotatingFileHandler(
        orders_log, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    orders_handler.setLevel(log_level)
    orders_handler.setFormatter(detailed_fmt)
    orders_handler.addFilter(logging.Filter("trading_bot.orders"))

    # --- Console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_fmt)

    logger.addHandler(file_handler)
    logger.addHandler(orders_handler)
    logger.addHandler(console_handler)

    logger.info("Logging initialised — log dir: %s", os.path.abspath(log_dir))
    return logger
