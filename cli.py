"""
CLI entry point for the Binance Futures Testnet Trading Bot.
Uses argparse with sub-commands for a clean, intuitive interface.
"""

import argparse
import sys
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from bot.logging_config import setup_logging
from bot.client import BinanceClient, BinanceClientError
from bot.validators import validate_all, ValidationError
from bot.orders import place_order


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser with sub-commands."""
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="🤖 Binance Futures Testnet Trading Bot — place orders from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Market buy 0.01 BTC
  python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

  # Limit sell 0.5 ETH at $3,200
  python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3200

  # Stop-market sell (bonus feature)
  python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.01 --stop-price 60000

  # Check account balance
  python cli.py account

  # Get current price
  python cli.py price --symbol BTCUSDT
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── order sub-command ────────────────────────────────────────────
    order_parser = subparsers.add_parser(
        "order", help="Place a new order on Binance Futures Testnet."
    )
    order_parser.add_argument(
        "--symbol", "-s", required=True,
        help="Trading pair symbol (e.g. BTCUSDT)",
    )
    order_parser.add_argument(
        "--side", required=True, choices=["BUY", "SELL", "buy", "sell"],
        help="Order side: BUY or SELL",
    )
    order_parser.add_argument(
        "--type", "-t", dest="order_type", required=True,
        choices=["MARKET", "LIMIT", "STOP_MARKET", "market", "limit", "stop_market"],
        help="Order type: MARKET, LIMIT, or STOP_MARKET",
    )
    order_parser.add_argument(
        "--quantity", "-q", type=float, required=True,
        help="Order quantity (e.g. 0.01)",
    )
    order_parser.add_argument(
        "--price", "-p", type=float, default=None,
        help="Limit price (required for LIMIT orders)",
    )
    order_parser.add_argument(
        "--stop-price", type=float, default=None,
        help="Stop trigger price (required for STOP_MARKET orders)",
    )

    # ── account sub-command ──────────────────────────────────────────
    subparsers.add_parser("account", help="Show testnet account information.")

    # ── price sub-command ────────────────────────────────────────────
    price_parser = subparsers.add_parser("price", help="Get current price for a symbol.")
    price_parser.add_argument(
        "--symbol", "-s", required=True,
        help="Trading pair symbol (e.g. BTCUSDT)",
    )

    return parser


def cmd_order(args, client: BinanceClient, logger: logging.Logger):
    """Handle the 'order' sub-command."""
    try:
        validated = validate_all(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValidationError as exc:
        logger.error("Validation failed: %s", exc)
        print(f"\n  ❌  Validation error: {exc}\n")
        sys.exit(1)

    try:
        place_order(
            client=client,
            symbol=validated["symbol"],
            side=validated["side"],
            order_type=validated["order_type"],
            quantity=validated["quantity"],
            price=validated.get("price"),
            stop_price=validated.get("stop_price"),
        )
    except BinanceClientError:
        sys.exit(1)


def cmd_account(client: BinanceClient, logger: logging.Logger):
    """Handle the 'account' sub-command."""
    try:
        info = client.get_account_info()
        print("\n" + "═" * 55)
        print("  💰  ACCOUNT INFORMATION")
        print("═" * 55)
        # Show non-zero balances
        assets = info.get("assets", [])
        has_balance = False
        for asset in assets:
            wallet = float(asset.get("walletBalance", 0))
            if wallet > 0:
                has_balance = True
                print(f"  {asset['asset']:<8}  Balance: {wallet:>14.4f}  "
                      f"Unrealised PnL: {float(asset.get('unrealizedProfit', 0)):>10.4f}")
        if not has_balance:
            print("  No balances found.")
        print("═" * 55 + "\n")
    except BinanceClientError as exc:
        logger.error("Failed to fetch account info: %s", exc)
        print(f"\n  ❌  Error: {exc.message}\n")
        sys.exit(1)


def cmd_price(args, client: BinanceClient, logger: logging.Logger):
    """Handle the 'price' sub-command."""
    symbol = args.symbol.strip().upper()
    try:
        data = client.get_ticker_price(symbol)
        print(f"\n  💲  {symbol} current price: {data.get('price', 'N/A')}\n")
    except BinanceClientError as exc:
        logger.error("Failed to fetch price: %s", exc)
        print(f"\n  ❌  Error: {exc.message}\n")
        sys.exit(1)


def main():
    """Main entry point."""
    logger = setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialise the Binance client
    client = BinanceClient()

    logger.info("Command received: %s", args.command)

    if args.command == "order":
        cmd_order(args, client, logger)
    elif args.command == "account":
        cmd_account(client, logger)
    elif args.command == "price":
        cmd_price(args, client, logger)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
