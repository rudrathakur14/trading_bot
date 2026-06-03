# 🤖 Binance Futures Testnet Trading Bot

A clean, modular Python CLI application for placing orders on **Binance Futures Testnet (USDT-M)**. Supports Market, Limit, and Stop-Market orders with structured logging, input validation, and comprehensive error handling.

---

## 📁 Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package initialisation
│   ├── client.py            # Binance API client (auth, signing, HTTP)
│   ├── orders.py            # Order placement logic & formatted output
│   ├── validators.py        # Input validation layer
│   └── logging_config.py    # Rotating file + console logging setup
├── logs/
│   ├── sample_market_order.log   # Sample log — MARKET order
│   └── sample_limit_order.log    # Sample log — LIMIT order
├── cli.py                   # CLI entry point (argparse)
├── .env.example             # Template for API credentials
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

### 1. Prerequisites

- **Python 3.8+** installed
- A **Binance Futures Testnet** account

### 2. Get Testnet API Credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with a GitHub account
3. Click **"API Key"** in the bottom section to generate your API Key and Secret
4. Copy both values — you'll need them next

### 3. Clone and Install

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/trading_bot.git
cd trading_bot

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure API Credentials

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and paste your testnet keys
# BINANCE_API_KEY=your_key_here
# BINANCE_API_SECRET=your_secret_here
```

> ⚠️ **Never commit your `.env` file.** It's already in `.gitignore`.

---

## 🚀 How to Run

### Place a Market Order

```bash
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Place a Limit Order

```bash
python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3200
```

### Place a Stop-Market Order (Bonus Feature)

```bash
python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.01 --stop-price 60000
```

### Check Account Balance

```bash
python cli.py account
```

### Get Current Price

```bash
python cli.py price --symbol BTCUSDT
```

### View Help

```bash
python cli.py --help
python cli.py order --help
```

---

## 📋 Example Output

### Market Order

```
───────────────────────────────────────────────────────
  📋  ORDER REQUEST SUMMARY
───────────────────────────────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.01
───────────────────────────────────────────────────────

═══════════════════════════════════════════════════════
  ✅  ORDER RESPONSE
═══════════════════════════════════════════════════════
  Order ID      : 12345678
  Symbol        : BTCUSDT
  Side          : BUY
  Type          : MARKET
  Status        : FILLED
  Quantity      : 0.01000000
  Executed Qty  : 0.01000000
  Avg Price     : 67543.20000000
═══════════════════════════════════════════════════════

  ✅  Order placed successfully!
```

### Validation Error

```
  ❌  Validation error: Price is required for LIMIT orders.
```

---

## 🔧 Architecture & Design Decisions

| Layer | File | Responsibility |
|-------|------|----------------|
| **API Client** | `bot/client.py` | HMAC-SHA256 signing, HTTP requests, error parsing |
| **Order Logic** | `bot/orders.py` | Order param assembly, formatted output, logging |
| **Validation** | `bot/validators.py` | Input sanitisation, type/range checks |
| **Logging** | `bot/logging_config.py` | Rotating file handlers (general + orders) |
| **CLI** | `cli.py` | Argparse sub-commands, user-facing entry point |

### Key Design Principles

- **Separation of concerns** — API transport, business logic, validation, and presentation are in separate modules
- **Fail-fast validation** — All inputs are validated before any API call is made
- **Structured logging** — Every API request, response, and error is logged with timestamps and context
- **Clean error messages** — Users see friendly messages; raw stack traces stay in log files

---

## 📝 Logging

Logs are written to the `logs/` directory:

| File | Contents |
|------|----------|
| `trading_bot.log` | All application logs (API calls, errors, lifecycle) |
| `orders.log` | Order-specific logs only |

Both use **rotating file handlers** (5 MB max, 3 backups) so logs don't grow unbounded.

Sample log files from test runs are included in `logs/`:
- `sample_market_order.log` — MARKET BUY order on BTCUSDT
- `sample_limit_order.log` — LIMIT SELL order on ETHUSDT

---

## 🎁 Bonus Feature: Stop-Market Orders

In addition to MARKET and LIMIT, this bot supports **STOP_MARKET** orders — a conditional order that triggers a market sell/buy when price hits a stop level:

```bash
python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.01 --stop-price 60000
```

---

## ⚠️ Assumptions

1. **Testnet only** — This bot targets `https://testnet.binancefuture.com`. Do NOT use with real funds.
2. **USDT-M Futures** — Only USDT-margined futures pairs are supported.
3. **No position management** — This bot places individual orders; it does not track or manage open positions.
4. **Symbol validation is format-based** — The bot checks that symbols match the `*USDT` pattern but does not query the exchange for the full symbol list at runtime.
5. **GTC default** — Limit orders default to Good-Till-Cancelled (GTC) time-in-force.

---

## 🧪 Testing Against Testnet

The testnet provides **fake USDT balances** so you can test freely. After setting up your `.env`:

```bash
# Verify connectivity
python cli.py price --symbol BTCUSDT

# Check your testnet balance
python cli.py account

# Place a test market order
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

# Place a test limit order (pick a price far from market)
python cli.py order --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.01 --price 10000
```

---

## 📜 License

MIT License — free to use, modify, and distribute.
