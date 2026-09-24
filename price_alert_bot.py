"""
Free multi-stock price-target alert -> Discord notifier.

How it works:
- Reads the list of stocks + target prices from stocks.json (edit that
  file to add/remove stocks -- no code changes needed).
- Reads DISCORD_WEBHOOK_URL from an environment variable (GitHub secret).
- For each stock, fetches the latest price using yfinance (free).
- If the price has crossed (gone at or above) the target price, sends a
  Discord message -- but only once per "crossing", using state.json to
  remember which symbols already alerted, so it won't spam you every
  5 minutes while the price stays above the target.
- If the price later drops back below the target, the alert resets, so
  you'll get notified again if it crosses up a second time.
"""

import json
import os
import sys
from pathlib import Path

import requests
import yfinance as yf

BASE_DIR = Path(__file__).parent
STOCKS_FILE = BASE_DIR / "stocks.json"
STATE_FILE = BASE_DIR / "state.json"


def load_stocks() -> list[dict]:
    return json.loads(STOCKS_FILE.read_text())


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_latest_price(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    price = ticker.fast_info.get("last_price")
    if price is None:
        hist = ticker.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"Could not fetch price for {symbol}")
        price = float(hist["Close"].iloc[-1])
    return float(price)


def send_discord_message(webhook_url: str, content: str) -> None:
    resp = requests.post(webhook_url, json={"content": content}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    stocks = load_stocks()
    state = load_state()

    for stock in stocks:
        symbol = stock["symbol"]
        target = float(stock["target"])

        try:
            price = get_latest_price(symbol)
        except Exception as exc:  # noqa: BLE001
            print(f"{symbol}: could not fetch price ({exc}), skipping")
            continue

        print(f"{symbol}: current price = {price}, target = {target}")

        was_above = state.get(symbol, False)
        is_above = price >= target

        if is_above and not was_above:
            message = (
                f"🔔 **{symbol}** crossed your target price!\n"
                f"Current price: **{price}**\n"
                f"Target: {target}"
            )
            send_discord_message(webhook_url, message)
            print(f"Alert sent for {symbol}.")

        state[symbol] = is_above

    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
