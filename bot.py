import time
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone


# ============================================================
# Raslen Crypto Bot
# PAPER TRADING ONLY
# ============================================================

PAIR = "XBTUSD"
INTERVAL = 15

START_BALANCE = 10000.0

RISK_PER_TRADE = 0.01
STOP_LOSS = 0.01
TAKE_PROFIT = 0.02

CHECK_INTERVAL = 60

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing from Railway Variables")


# ============================================================
# PAPER TRADING STATE
# ============================================================

balance = START_BALANCE
position = None
entry_price = 0.0
last_signal = "WAIT"
last_price = 0.0
last_update = None


# ============================================================
# HTTP HELPER
# ============================================================

def http_get(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RaslenCryptoBot/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def http_post(url, data, timeout=15):
    encoded = urllib.parse.urlencode(data).encode()

    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "User-Agent": "RaslenCryptoBot/1.0",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


# ============================================================
# KRAKEN MARKET DATA
# ============================================================

def get_candles():
    """
    Get BTC/USD 15-minute candles from Kraken.

    Kraken OHLC response format:
    [time, open, high, low, close, vwap, volume, count]
    """

    url = (
        "https://api.kraken.com/0/public/OHLC"
        f"?pair={PAIR}&interval={INTERVAL}"
    )

    data = http_get(url)

    if data.get("error"):
        raise RuntimeError(
            "Kraken API error: " + str(data["error"])
        )

    result = data.get("result", {})

    candles = result.get("XXBTZUSD")

    if candles is None:
        # Kraken can sometimes use a different key.
        possible = [
            value for key, value in result.items()
            if key != "last" and isinstance(value, list)
        ]

        if not possible:
            raise RuntimeError("No candle data received from Kraken")

        candles = possible[0]

    prices = []

    for candle in candles:
        try:
            close_price = float(candle[4])
            prices.append(close_price)
        except (ValueError, TypeError, IndexError):
            continue

    if len(prices) < 50:
        raise RuntimeError(
            f"Not enough candle data: {len(prices)} candles"
        )

    return prices


# ============================================================
# INDICATORS
# ============================================================

def ema(prices, period):
    if len(prices) < period:
        raise ValueError("Not enough prices for EMA")

    multiplier = 2 / (period + 1)

    value = sum(prices[:period]) / period

    for price in prices[period:]:
        value = (price - value) * multiplier + value

    return value


def rsi(prices, period=14):
    if len(prices) < period + 1:
        raise ValueError("Not enough prices for RSI")

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# MARKET ANALYSIS
# ============================================================

def analyze(prices):
    fast_ema = ema(prices, 20)
    slow_ema = ema(prices, 50)
    current_rsi = rsi(prices)

    price = prices[-1]

    if fast_ema > slow_ema and 50 < current_rsi < 70:
        signal = "BUY"

    elif fast_ema < slow_ema and 30 < current_rsi < 50:
        signal = "SELL"

    else:
        signal = "WAIT"

    return (
        signal,
        price,
        fast_ema,
        slow_ema,
        current_rsi
    )


# ============================================================
# PAPER TRADING
# ============================================================

def open_paper_trade(price):
    global position
    global entry_price

    if position is not None:
        return

    position = "BUY"
    entry_price = price

    print("\n🟢 PAPER BUY")
    print(f"Entry: ${price:,.2f}")
    print(
        f"Stop Loss: "
        f"${price * (1 - STOP_LOSS):,.2f}"
    )
    print(
        f"Take Profit: "
        f"${price * (1 + TAKE_PROFIT):,.2f}"
    )


def check_position(price):
    global position
    global entry_price
    global balance

    if position != "BUY":
        return None

    stop = entry_price * (1 - STOP_LOSS)
    target = entry_price * (1 + TAKE_PROFIT)

    if price <= stop:

        loss = balance * RISK_PER_TRADE
        balance -= loss

        message = (
            "🔴 PAPER STOP LOSS\n\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Exit: ${price:,.2f}\n"
            f"Result: -${loss:.2f}\n"
            f"Balance: ${balance:.2f}"
        )

        print("\n" + message)

        position = None
        entry_price = 0.0

        return message

    if price >= target:

        profit = balance * RISK_PER_TRADE * 2
        balance += profit

        message = (
            "🟢 PAPER TAKE PROFIT\n\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Exit: ${price:,.2f}\n"
            f"Result: +${profit:.2f}\n"
            f"Balance: ${balance:.2f}"
        )

        print("\n" + message)

        position = None
        entry_price = 0.0

        return message

    return None


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
)


def telegram_get_updates(offset=None):
    params = {
        "timeout": 5
    }

    if offset is not None:
        params["offset"] = offset

    query = urllib.parse.urlencode(params)

    url = (
        f"{TELEGRAM_API}/getUpdates?{query}"
    )

    return http_get(url, timeout=15)


def telegram_send(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"

    return http_post(
        url,
        {
            "chat_id": str(chat_id),
            "text": text
        },
        timeout=15
    )


def telegram_commands():
    """
    Configure Telegram command menu.
    """

    url = f"{TELEGRAM_API}/setMyCommands"

    commands = json.dumps([
        {
            "command": "start",
            "description": "Start the bot"
        },
        {
            "command": "status",
            "description": "Show paper trading status"
        },
        {
            "command": "signal",
            "description": "Show current market signal"
        }
    ])

    try:
        http_post(
            url,
            {
                "commands": commands
            }
        )

        print("Telegram commands configured.")

    except Exception as error:
        print(
            "Could not configure Telegram commands:",
            error
        )


# ============================================================
# TELEGRAM MESSAGES
# ============================================================

def get_status_message():

    if last_update:
        update_text = last_update
    else:
        update_text = "Not available"

    if position:
        position_text = (
            f"BUY @ ${entry_price:,.2f}"
        )
    else:
        position_text = "None"

    return (
        "📊 RASLEN CRYPTO BOT\n\n"
        "🧪 PAPER TRADING ONLY\n\n"
        f"💰 Balance: ${balance:,.2f}\n"
        f"📌 Position: {position_text}\n"
        f"📈 Last Signal: {last_signal}\n"
        f"💵 BTC Price: ${last_price:,.2f}\n"
        f"🕐 Last Update: {update_text}\n\n"
        "Commands:\n"
        "/start\n"
        "/status\n"
        "/signal"
    )


def get_signal_message():

    try:
        prices = get_candles()

        signal, price, fast, slow, current_rsi = (
            analyze(prices)
        )

        return (
            "📈 CURRENT BTC ANALYSIS\n\n"
            "🧪 PAPER TRADING\n\n"
            f"💵 BTC/USD: ${price:,.2f}\n"
            f"EMA 20: ${fast:,.2f}\n"
            f"EMA 50: ${slow:,.2f}\n"
            f"RSI: {current_rsi:.2f}\n\n"
            f"📌 Signal: {signal}"
        )

    except Exception as error:

        return (
            "⚠️ Could not get market data.\n\n"
            f"Error: {error}"
        )


def handle_telegram_message(message):

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat_id is None:
        return

    text = message.get("text", "").strip()

    if not text:
        return

    command = text.split()[0].lower()

    if command.startswith("/start"):

        telegram_send(
            chat_id,
            "🤖 Raslen Crypto Bot\n\n"
            "Welcome!\n\n"
            "🧪 This bot is PAPER TRADING ONLY.\n"
            "No real trades are executed.\n\n"
            "Commands:\n"
            "/status - account status\n"
            "/signal - current BTC analysis"
        )

    elif command.startswith("/status"):

        telegram_send(
            chat_id,
            get_status_message()
        )

    elif command.startswith("/signal"):

        telegram_send(
            chat_id,
