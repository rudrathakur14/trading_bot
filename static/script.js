/**
 * Trading Bot Dashboard — Frontend Logic
 * Handles form interaction, API calls, and UI updates
 */

// ── State ─────────────────────────────────────────────
const state = {
    side: 'BUY',
    orderType: 'MARKET',
    orderHistory: [],
};

// ── DOM Refs ──────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const form = $('#orderForm');
const btnBuy = $('#btnBuy');
const btnSell = $('#btnSell');
const submitBtn = $('#submitBtn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoader = $('#btnLoader');
const priceGroup = $('#priceGroup');
const stopPriceGroup = $('#stopPriceGroup');
const responseCard = $('#responseCard');
const responseBody = $('#responseBody');
const responseStatus = $('#responseStatus');
const historyBody = $('#historyBody');
const toastContainer = $('#toastContainer');
const symbolSelect = $('#symbol');
const quantitySuffix = $('#quantitySuffix');

// ── Side Toggle ───────────────────────────────────────
btnBuy.addEventListener('click', () => setSide('BUY'));
btnSell.addEventListener('click', () => setSide('SELL'));

function setSide(side) {
    state.side = side;
    btnBuy.classList.toggle('active', side === 'BUY');
    btnSell.classList.toggle('active', side === 'SELL');
    updateSubmitButton();
}

function updateSubmitButton() {
    const isBuy = state.side === 'BUY';
    btnText.textContent = `Place ${state.side} Order`;
    submitBtn.classList.toggle('submit-buy', isBuy);
    submitBtn.classList.toggle('submit-sell', !isBuy);
}

// ── Order Type Tabs ───────────────────────────────────
$$('.type-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        $$('.type-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.orderType = tab.dataset.type;

        priceGroup.style.display = state.orderType === 'LIMIT' ? 'block' : 'none';
        stopPriceGroup.style.display = state.orderType === 'STOP_MARKET' ? 'block' : 'none';
    });
});

// ── Symbol Change ─────────────────────────────────────
symbolSelect.addEventListener('change', () => {
    const sym = symbolSelect.value.replace('USDT', '');
    quantitySuffix.textContent = sym;
    fetchPrice(symbolSelect.value);
});

// ── Quick Amount Buttons ──────────────────────────────
$$('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $('#quantity').value = btn.dataset.amount;
    });
});

// ── Clear History ─────────────────────────────────────
$('#clearHistory').addEventListener('click', () => {
    state.orderHistory = [];
    renderHistory();
});

// ── Fetch Prices ──────────────────────────────────────
async function fetchPrice(symbol) {
    try {
        const res = await fetch(`/api/price/${symbol}`);
        const data = await res.json();
        if (data.success) {
            const price = parseFloat(data.price).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });

            if (symbol === 'BTCUSDT') {
                $('#btcPrice').textContent = `$${price}`;
                $('#btcChange').textContent = 'LIVE';
                $('#btcChange').className = 'ticker-change up';
            } else if (symbol === 'ETHUSDT') {
                $('#ethPrice').textContent = `$${price}`;
            }

            // Update status
            $('#statusDot .dot').className = 'dot online';
            $('#statusDot .status-text').textContent = 'Connected';
        }
    } catch (err) {
        $('#statusDot .dot').className = 'dot offline';
        $('#statusDot .status-text').textContent = 'Offline';
    }
}

// ── Submit Order ──────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
        symbol: symbolSelect.value,
        side: state.side,
        order_type: state.orderType,
        quantity: parseFloat($('#quantity').value),
    };

    if (state.orderType === 'LIMIT') {
        const price = $('#price').value;
        if (!price) {
            showToast('Price is required for Limit orders', 'error');
            return;
        }
        payload.price = parseFloat(price);
    }

    if (state.orderType === 'STOP_MARKET') {
        const stopPrice = $('#stopPrice').value;
        if (!stopPrice) {
            showToast('Stop Price is required for Stop-Market orders', 'error');
            return;
        }
        payload.stop_price = parseFloat(stopPrice);
    }

    if (!payload.quantity || payload.quantity <= 0) {
        showToast('Please enter a valid quantity', 'error');
        return;
    }

    // Show loading
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline';
    submitBtn.disabled = true;

    try {
        const res = await fetch('/api/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (data.success) {
            renderOrderResponse(data.order, true);
            addToHistory(data.order, true);
            showToast(`✅ ${payload.side} order placed successfully!`, 'success');
            flashCard('success');
        } else {
            renderOrderError(data.error);
            addToHistory({ ...payload, status: 'FAILED', error: data.error }, false);
            showToast(`❌ ${data.error}`, 'error');
            flashCard('error');
        }
    } catch (err) {
        renderOrderError('Network error — check your connection');
        showToast('❌ Network error', 'error');
        flashCard('error');
    } finally {
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
        submitBtn.disabled = false;
    }
});

// ── Render Order Response ─────────────────────────────
function renderOrderResponse(order, success) {
    responseStatus.textContent = order.status || 'UNKNOWN';
    responseStatus.className = `response-status ${success ? 'success' : 'error'}`;

    const sideClass = order.side === 'BUY' ? 'buy' : 'sell';
    const statusClass = order.status === 'FILLED' ? 'filled' : 'new-order';

    let html = '<div class="order-details fade-in">';

    const fields = [
        { label: 'Order ID', value: order.orderId, cls: '' },
        { label: 'Status', value: order.status, cls: statusClass },
        { label: 'Symbol', value: order.symbol, cls: '' },
        { label: 'Side', value: order.side, cls: sideClass },
        { label: 'Type', value: order.type, cls: '' },
        { label: 'Quantity', value: order.origQty, cls: '' },
    ];

    if (order.executedQty && order.executedQty !== '0') {
        fields.push({ label: 'Executed Qty', value: order.executedQty, cls: '' });
    }
    if (order.price && order.price !== '0') {
        fields.push({ label: 'Price', value: order.price, cls: '' });
    }
    if (order.avgPrice && order.avgPrice !== '0') {
        fields.push({ label: 'Avg Price', value: order.avgPrice, cls: '' });
    }
    if (order.stopPrice && order.stopPrice !== '0') {
        fields.push({ label: 'Stop Price', value: order.stopPrice, cls: '' });
    }
    if (order.timeInForce) {
        fields.push({ label: 'Time In Force', value: order.timeInForce, cls: '' });
    }

    fields.forEach(f => {
        if (f.value !== undefined && f.value !== null) {
            html += `
                <div class="detail-item">
                    <div class="detail-label">${f.label}</div>
                    <div class="detail-value ${f.cls}">${f.value}</div>
                </div>`;
        }
    });

    html += '</div>';
    responseBody.innerHTML = html;
}

function renderOrderError(error) {
    responseStatus.textContent = 'FAILED';
    responseStatus.className = 'response-status error';

    responseBody.innerHTML = `
        <div class="order-details fade-in">
            <div class="detail-item full-width">
                <div class="detail-label">Error</div>
                <div class="detail-value sell">${error}</div>
            </div>
        </div>`;
}

// ── Order History ─────────────────────────────────────
function addToHistory(order, success) {
    state.orderHistory.unshift({
        symbol: order.symbol,
        side: order.side,
        type: order.type || order.order_type,
        qty: order.origQty || order.quantity,
        status: order.status || 'FAILED',
        success,
        time: new Date().toLocaleTimeString(),
    });

    if (state.orderHistory.length > 20) state.orderHistory.pop();
    renderHistory();
}

function renderHistory() {
    if (state.orderHistory.length === 0) {
        historyBody.innerHTML = '<div class="empty-state small"><p class="empty-text">No orders yet</p></div>';
        return;
    }

    let html = '';
    state.orderHistory.forEach(o => {
        const sideClass = o.side === 'BUY' ? 'buy' : 'sell';
        const statusClass = o.status === 'FILLED' ? 'filled' : o.status === 'NEW' ? 'new-order' : 'failed';
        html += `
            <div class="history-item slide-up">
                <div class="history-left">
                    <span class="history-side ${sideClass}">${o.side}</span>
                    <div class="history-info">
                        <span class="history-symbol">${o.symbol}</span>
                        <span class="history-type">${o.type} · ${o.time}</span>
                    </div>
                </div>
                <div class="history-right">
                    <span class="history-qty">${o.qty}</span>
                    <span class="history-status ${statusClass}">${o.status}</span>
                </div>
            </div>`;
    });

    historyBody.innerHTML = html;
}

// ── Flash Card Effect ─────────────────────────────────
function flashCard(type) {
    responseCard.classList.add(`flash-${type}`);
    setTimeout(() => responseCard.classList.remove(`flash-${type}`), 1500);
}

// ── Toast Notifications ───────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('exit');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ── Initialise ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    fetchPrice('BTCUSDT');
    fetchPrice('ETHUSDT');
    updateSubmitButton();

    // Refresh prices every 15 seconds
    setInterval(() => {
        fetchPrice('BTCUSDT');
        fetchPrice('ETHUSDT');
    }, 15000);
});
