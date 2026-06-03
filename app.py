"""
Flask web application for the Binance Futures Testnet Trading Bot.
Provides a premium dark-themed trading dashboard UI.
"""

import json
import logging
from flask import Flask, render_template, request, jsonify

from bot.logging_config import setup_logging
from bot.client import BinanceClient, BinanceClientError
from bot.validators import validate_all, ValidationError
from bot.orders import place_order

# Initialise logging and client
logger = setup_logging()
app = Flask(__name__, template_folder="templates", static_folder="static")


def get_client():
    """Create a fresh BinanceClient instance."""
    return BinanceClient()


@app.route("/")
def index():
    """Serve the main trading dashboard."""
    return render_template("index.html")


@app.route("/api/price/<symbol>")
def api_price(symbol):
    """Fetch current price for a symbol."""
    try:
        client = get_client()
        data = client.get_ticker_price(symbol.upper())
        return jsonify({"success": True, "symbol": symbol.upper(), "price": data.get("price", "N/A")})
    except BinanceClientError as exc:
        return jsonify({"success": False, "error": exc.message}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/order", methods=["POST"])
def api_order():
    """Place an order via the API."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No JSON data provided"}), 400

    # Extract fields
    symbol = data.get("symbol", "")
    side = data.get("side", "")
    order_type = data.get("order_type", "")
    quantity = data.get("quantity")
    price = data.get("price")
    stop_price = data.get("stop_price")

    # Validate
    try:
        validated = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    # Place order
    try:
        client = get_client()
        response = place_order(
            client=client,
            symbol=validated["symbol"],
            side=validated["side"],
            order_type=validated["order_type"],
            quantity=validated["quantity"],
            price=validated.get("price"),
            stop_price=validated.get("stop_price"),
        )
        return jsonify({
            "success": True,
            "order": {
                "orderId": response.get("orderId"),
                "symbol": response.get("symbol"),
                "side": response.get("side"),
                "type": response.get("type"),
                "status": response.get("status"),
                "origQty": response.get("origQty"),
                "executedQty": response.get("executedQty"),
                "price": response.get("price"),
                "avgPrice": response.get("avgPrice"),
                "stopPrice": response.get("stopPrice"),
                "timeInForce": response.get("timeInForce"),
                "updateTime": response.get("updateTime"),
            }
        })
    except BinanceClientError as exc:
        return jsonify({"success": False, "error": exc.message}), 400
    except Exception as exc:
        logger.error("Unexpected error placing order: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/account")
def api_account():
    """Fetch account balances."""
    try:
        client = get_client()
        info = client.get_account_info()
        assets = info.get("assets", [])
        balances = []
        for asset in assets:
            wallet = float(asset.get("walletBalance", 0))
            if wallet > 0:
                balances.append({
                    "asset": asset["asset"],
                    "walletBalance": wallet,
                    "unrealizedProfit": float(asset.get("unrealizedProfit", 0)),
                })
        return jsonify({"success": True, "balances": balances})
    except BinanceClientError as exc:
        return jsonify({"success": False, "error": exc.message}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    print("\n  🚀  Trading Bot Web UI running at: http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
