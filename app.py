"""
Flask web application for the Binance Futures Testnet Trading Bot & Local Stock Market Simulator.
Provides a premium dark-themed trading dashboard UI connected to a secure SQLite database.
"""

import json
import logging
import os
import sqlite3
import sys
import time
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from bot.logging_config import setup_logging
from bot.client import BinanceClient, BinanceClientError
from bot.validators import validate_all, ValidationError
from bot.orders import place_order

# Initialise logging
logger = setup_logging()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "super_secret_tradingbot_key_12345"

DATABASE = 'trading_bot.db'

# ------------------------------------------------------------------
# Database Initialization & Helpers
# ------------------------------------------------------------------

def now():
    """Get current formatted timestamp."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def get_db():
    """Create a fresh SQLite database connection."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database tables."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Wallets Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance REAL NOT NULL DEFAULT 1000000.0,
                investments REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Transactions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Holdings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL, -- 'stock', 'crypto', 'mf'
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, symbol)
            )
        ''')
        
        # Orders Table (Local Bookkeeping)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL,
                type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                currency TEXT NOT NULL DEFAULT '₹',
                asset_type TEXT NOT NULL DEFAULT 'stock',
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # SIPs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                fund_name TEXT NOT NULL,
                monthly_amount REAL NOT NULL,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
    logger.info("SQLite database tables initialized successfully.")

# Run database init
init_db()


def get_client():
    """Create a fresh BinanceClient instance."""
    return BinanceClient()


# ------------------------------------------------------------------
# Page Routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main premium trading dashboard."""
    return render_template("index.html")


# ------------------------------------------------------------------
# Authentication APIs
# ------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Register a new user account."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"success": False, "error": "Name, email, and password are required."}), 400

    db = get_db()
    try:
        # Check if user already exists
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            return jsonify({"success": False, "error": "An account with this email already exists."}), 400

        # Create user
        pwd_hash = generate_password_hash(password)
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, phone, password_hash) VALUES (?, ?, ?, ?)",
            (name, email, phone, pwd_hash)
        )
        user_id = cursor.lastrowid
        
        # Create wallet
        cursor.execute("INSERT INTO wallets (user_id, balance, investments) VALUES (?, 1000000.0, 0.0)", (user_id,))
        
        db.commit()
        
        # Set session
        session["user_id"] = user_id
        session["user_email"] = email
        session["user_name"] = name
        
        return jsonify({
            "success": True,
            "session": {"email": email, "name": name, "user_id": user_id}
        })
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/auth/check_email", methods=["POST"])
def auth_check_email():
    """Check if an email is already registered."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400

    db = get_db()
    try:
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            return jsonify({"success": True, "exists": True})
        return jsonify({"success": True, "exists": False})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Login to an existing account."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    verify_only = data.get("verify_only", False)

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    db = get_db()
    try:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"success": False, "error": "Incorrect email or password."}), 400

        if verify_only:
            # Only checking credentials, do not set session
            return jsonify({
                "success": True,
                "session": {"email": user["email"], "name": user["name"]}
            })

        # Set session
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_name"] = user["name"]

        return jsonify({
            "success": True,
            "session": {"email": user["email"], "name": user["name"], "user_id": user["id"]}
        })
    except Exception as exc:
        logger.error("Login error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Logout the current user session."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


@app.route("/api/auth/session", methods=["GET"])
def auth_session():
    """Get active session details."""
    if "user_id" in session:
        return jsonify({
            "success": True,
            "session": {
                "email": session["user_email"],
                "name": session["user_name"],
                "user_id": session["user_id"]
            }
        })
    return jsonify({"success": False, "error": "No active session."}), 401


# ------------------------------------------------------------------
# Wallet & Transaction APIs
# ------------------------------------------------------------------

@app.route("/api/wallet", methods=["GET"])
def wallet_get():
    """Retrieve the current user's wallet details."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    db = get_db()
    try:
        wallet = db.execute("SELECT balance, investments FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        txns = db.execute(
            "SELECT type, title, amount, timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 50",
            (user_id,)
        ).fetchall()
        
        txn_list = []
        for t in txns:
            txn_list.append({
                "type": t["type"],
                "title": t["title"],
                "amount": t["amount"],
                "time": t["timestamp"]
            })
            
        return jsonify({
            "success": True,
            "balance": wallet["balance"] if wallet else 1000000.0,
            "investments": wallet["investments"] if wallet else 0.0,
            "transactions": txn_list
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/wallet/deposit", methods=["POST"])
def wallet_deposit():
    """Deposit simulated money to the wallet."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return jsonify({"success": False, "error": "Amount must be positive."}), 400

    db = get_db()
    try:
        db.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        db.execute(
            "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'deposit', 'Money Added', ?)",
            (user_id, amount)
        )
        db.commit()
        return jsonify({"success": True, "message": "Deposited successfully."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/wallet/withdraw", methods=["POST"])
def wallet_withdraw():
    """Withdraw money from the wallet."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    method = data.get("method", "UPI")
    if amount <= 0:
        return jsonify({"success": False, "error": "Amount must be positive."}), 400

    db = get_db()
    try:
        wallet = db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if not wallet or wallet["balance"] < amount:
            return jsonify({"success": False, "error": "Insufficient balance."}), 400

        db.execute("UPDATE wallets SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        db.execute(
            "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'withdraw', ?, ?)",
            (user_id, f"Withdrawal ({method})", -amount)
        )
        db.commit()
        return jsonify({"success": True, "message": "Withdrawn successfully."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


# ------------------------------------------------------------------
# Portfolio & Trade APIs
# ------------------------------------------------------------------

@app.route("/api/portfolio", methods=["GET"])
def portfolio_get():
    """Retrieve user portfolio details (holdings and orders)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    db = get_db()
    try:
        # Holdings
        holdings = db.execute("SELECT symbol, name, asset_type, quantity, avg_price FROM holdings WHERE user_id = ?", (user_id,)).fetchall()
        holdings_list = []
        for h in holdings:
            holdings_list.append({
                "symbol": h["symbol"],
                "name": h["name"],
                "asset_type": h["asset_type"],
                "quantity": h["quantity"],
                "avg_price": h["avg_price"]
            })

        # Orders
        orders = db.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user_id,)).fetchall()
        orders_list = []
        for o in orders:
            orders_list.append({
                "orderId": o["id"],
                "symbol": o["symbol"],
                "name": o["name"],
                "side": o["side"],
                "type": o["type"],
                "qty": o["quantity"],
                "price": o["price"],
                "status": o["status"],
                "time": o["timestamp"],
                "currency": o["currency"],
                "assetType": o["asset_type"]
            })

        return jsonify({
            "success": True,
            "holdings": holdings_list,
            "orders": orders_list
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/trade", methods=["POST"])
def trade_place():
    """Execute a local buy or sell order, recording in database."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    name = data.get("name", "")
    side = data.get("side", "BUY") # BUY / SELL
    order_type = data.get("type", "MARKET")
    qty = float(data.get("quantity", 0))
    price = float(data.get("price", 0))
    currency = data.get("currency", "₹")
    asset_type = data.get("assetType", "stock") # stock / crypto

    if qty <= 0 or price <= 0:
        return jsonify({"success": False, "error": "Invalid quantity or price."}), 400

    cost = qty * price
    cost_inr = cost * 83.5 if asset_type == "crypto" else cost

    db = get_db()
    try:
        wallet = db.execute("SELECT balance, investments FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not found."}), 400
            
        cursor = db.cursor()
        
        if side == "BUY":
            if wallet["balance"] < cost_inr:
                return jsonify({"success": False, "error": "Insufficient balance."}), 400
            
            # Deduct balance, add to investments
            cursor.execute("UPDATE wallets SET balance = balance - ?, investments = investments + ? WHERE user_id = ?", (cost_inr, cost_inr, user_id))
            
            # Update holdings
            curr = db.execute("SELECT quantity, avg_price FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, symbol)).fetchone()
            if curr:
                new_qty = curr["quantity"] + qty
                new_avg = ((curr["quantity"] * curr["avg_price"]) + cost) / new_qty
                cursor.execute(
                    "UPDATE holdings SET quantity = ?, avg_price = ? WHERE user_id = ? AND symbol = ?",
                    (new_qty, new_avg, user_id, symbol)
                )
            else:
                cursor.execute(
                    "INSERT INTO holdings (user_id, symbol, name, asset_type, quantity, avg_price) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, symbol, name, asset_type, qty, price)
                )
            # Add transaction log
            cursor.execute(
                "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'trade', ?, ?)",
                (user_id, f"BUY {qty} {symbol}", -cost_inr)
            )
        else: # SELL
            curr = db.execute("SELECT quantity, avg_price FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, symbol)).fetchone()
            if not curr or curr["quantity"] < qty:
                return jsonify({"success": False, "error": f"You don't hold enough quantity of {symbol} to sell."}), 400
            
            # Add balance, reduce investments
            cursor.execute("UPDATE wallets SET balance = balance + ?, investments = CASE WHEN investments >= ? THEN investments - ? ELSE 0 END WHERE user_id = ?", (cost_inr, cost_inr, cost_inr, user_id))
            
            # Update holdings
            new_qty = curr["quantity"] - qty
            if new_qty <= 0:
                cursor.execute("DELETE FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, symbol))
            else:
                cursor.execute("UPDATE holdings SET quantity = ? WHERE user_id = ? AND symbol = ?", (new_qty, user_id, symbol))
                
            # Add transaction log
            cursor.execute(
                "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'trade', ?, ?)",
                (user_id, f"SELL {qty} {symbol}", cost_inr)
            )

        # Log order
        status = "FILLED" if order_type == "MARKET" else "NEW"
        cursor.execute(
            "INSERT INTO orders (user_id, symbol, name, side, type, quantity, price, status, currency, asset_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, symbol, name, side, order_type, qty, price, status, currency, asset_type)
        )
        order_id = cursor.lastrowid
        db.commit()

        return jsonify({
            "success": True,
            "order": {
                "orderId": order_id,
                "symbol": symbol,
                "name": name,
                "side": side,
                "type": order_type,
                "qty": qty,
                "price": price,
                "status": status,
                "time": now(),
                "currency": currency,
                "assetType": asset_type
            }
        })
    except Exception as exc:
        logger.error("Trade error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/mutualfunds/invest", methods=["POST"])
def mf_invest():
    """Invest lump sum in a Mutual Fund."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    fund_name = data.get("name", "")
    amt = float(data.get("amount", 0))

    if amt < 500:
        return jsonify({"success": False, "error": "Minimum investment is ₹500"}), 400

    db = get_db()
    try:
        wallet = db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if not wallet or wallet["balance"] < amt:
            return jsonify({"success": False, "error": "Insufficient balance."}), 400

        cursor = db.cursor()
        cursor.execute("UPDATE wallets SET balance = balance - ?, investments = investments + ? WHERE user_id = ?", (amt, amt, user_id))
        
        # Add to holdings
        curr = db.execute("SELECT quantity, avg_price FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, fund_name)).fetchone()
        if curr:
            new_qty = curr["quantity"] + (amt / curr["avg_price"])
            cursor.execute("UPDATE holdings SET quantity = ? WHERE user_id = ? AND symbol = ?", (new_qty, user_id, fund_name))
        else:
            cursor.execute(
                "INSERT INTO holdings (user_id, symbol, name, asset_type, quantity, avg_price) VALUES (?, ?, ?, 'mf', ?, 1.0)",
                (user_id, fund_name, fund_name, amt)
            )

        cursor.execute(
            "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'invest', ?, ?)",
            (user_id, f"MF: {fund_name}", -amt)
        )
        db.commit()
        return jsonify({"success": True, "message": f"Successfully invested {amt} in {fund_name}"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/mutualfunds/sip", methods=["POST"])
def mf_sip():
    """Start an SIP for a Mutual Fund."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json() or {}
    fund_name = data.get("name", "")
    amt = float(data.get("amount", 0))

    if amt <= 0:
        return jsonify({"success": False, "error": "Invalid SIP amount."}), 400

    db = get_db()
    try:
        wallet = db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        if not wallet or wallet["balance"] < amt:
            return jsonify({"success": False, "error": "Insufficient balance for first monthly installment."}), 400

        cursor = db.cursor()
        cursor.execute("UPDATE wallets SET balance = balance - ?, investments = investments + ? WHERE user_id = ?", (amt, amt, user_id))
        
        # Add to holdings
        curr = db.execute("SELECT quantity, avg_price FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, fund_name)).fetchone()
        if curr:
            new_qty = curr["quantity"] + (amt / curr["avg_price"])
            cursor.execute("UPDATE holdings SET quantity = ? WHERE user_id = ? AND symbol = ?", (new_qty, user_id, fund_name))
        else:
            cursor.execute(
                "INSERT INTO holdings (user_id, symbol, name, asset_type, quantity, avg_price) VALUES (?, ?, ?, 'mf', ?, 1.0)",
                (user_id, fund_name, fund_name, amt)
            )

        cursor.execute(
            "INSERT INTO sips (user_id, fund_name, monthly_amount) VALUES (?, ?, ?)",
            (user_id, fund_name, amt)
        )
        cursor.execute(
            "INSERT INTO transactions (user_id, type, title, amount) VALUES (?, 'sip', ?, ?)",
            (user_id, f"SIP: {fund_name} (₹{amt}/mo)", -amt)
        )
        db.commit()
        return jsonify({"success": True, "message": f"SIP of {amt}/mo started for {fund_name}"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/orders/clear", methods=["POST"])
def orders_clear():
    """Clear order history from the database."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    db = get_db()
    try:
        db.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        db.commit()
        return jsonify({"success": True, "message": "Order history cleared."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        db.close()


# ------------------------------------------------------------------
# Original Binance API Routes (for keeping backwards compatibility)
# ------------------------------------------------------------------

@app.route("/api/price/<symbol>")
def api_price(symbol):
    """Fetch current price for a symbol from Binance."""
    try:
        client = get_client()
        data = client.get_ticker_price(symbol.upper())
        return jsonify({"success": True, "symbol": symbol.upper(), "price": data.get("price", "N/A")})
    except BinanceClientError as exc:
        return jsonify({"success": False, "error": exc.message}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/binance/order", methods=["POST"])
def api_binance_order():
    """Place a real order on Binance Futures Testnet."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    side = data.get("side", "")
    order_type = data.get("order_type", "")
    quantity = data.get("quantity")
    price = data.get("price")
    stop_price = data.get("stop_price")

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
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    print("\n  🚀  Trading Bot Web UI running at: http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
