import time
import json
import urllib.request
from datetime import datetime

# =========================
# Raslen Crypto Bot
# PAPER TRADING ONLY
# =========================

SYMBOL = "BTCUSDT"
INTERVAL = "15m"

START_BALANCE = 10000.0
RISK_PER_TRADE = 0.01       # 1% من الرصيد
STOP_LOSS = 0.01            # 1%
TAKE_PROFIT = 0.02          # 2%

balance = START_BALANCE
position = None
entry_price = 0.0


def get_candles():
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={SYMBOL}&interval={INTERVAL}&limit=100"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RaslenCryptoBot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode())

    return [float(candle[4]) for candle in data]


def ema(prices, period):
    multiplier = 2 / (period + 1)
    value = prices[0]

    for price in prices[1:]:
        value = (price - value) * multiplier + value

    return value


def rsi(prices, period=14):
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
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def analyze(prices):
    fast_ema = ema(prices[-50:], 20)
    slow_ema = ema(prices, 50)
    current_rsi = rsi(prices)

    price = prices[-1]

    if fast_ema > slow_ema and 50 < current_rsi < 70:
        signal = "BUY"

    elif fast_ema < slow_ema and 30 < current_rsi < 50:
        signal = "SELL"

    else:
        signal = "WAIT"

    return signal, price, fast_ema, slow_ema, current_rsi


def open_paper_trade(price):
    global position, entry_price

    position = "BUY"
    entry_price = price

    print("\n🟢 PAPER BUY")
    print(f"Entry: ${price:,.2f}")
    print(f"Stop Loss: ${price * (1 - STOP_LOSS):,.2f}")
    print(f"Take Profit: ${price * (1 + TAKE_PROFIT):,.2f}")


def check_position(price):
    global position, entry_price, balance

    if position != "BUY":
        return

    stop = entry_price * (1 - STOP_LOSS)
    target = entry_price * (1 + TAKE_PROFIT)

    if price <= stop:
        loss = balance * RISK_PER_TRADE
        balance -= loss

        print("\n🔴 PAPER STOP LOSS")
        print(f"Exit: ${price:,.2f}")
        print(f"Result: -${loss:.2f}")
        print(f"Balance: ${balance:.2f}")

        position = None
        entry_price = 0

    elif price >= target:
        profit = balance * RISK_PER_TRADE * 2
        balance += profit

        print("\n🟢 PAPER TAKE PROFIT")
        print(f"Exit: ${price:,.2f}")
        print(f"Result: +${profit:.2f}")
        print(f"Balance: ${balance:.2f}")

        position = None
        entry_price = 0


def main():
    print("=" * 45)
    print("     RASLEN CRYPTO BOT")
    print("     PAPER TRADING MODE")
    print("=" * 45)

    while True:
        try:
            prices = get_candles()

            signal, price, fast, slow, current_rsi = analyze(prices)

            print("\n" + "-" * 45)
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"BTC Price : ${price:,.2f}")
            print(f"EMA 20    : ${fast:,.2f}")
            print(f"EMA 50    : ${slow:,.2f}")
            print(f"RSI       : {current_rsi:.2f}")
            print(f"Signal    : {signal}")
            print(f"Position  : {position}")
            print(f"Balance   : ${balance:.2f}")

            check_position(price)

            if position is None and signal == "BUY":
                open_paper_trade(price)

            time.sleep(60)

        except Exception as error:
            print("\n⚠️ Error:", error)
            print("Retrying in 60 seconds...")
            time.sleep(60)


if __name__ == "__main__":
    main()
