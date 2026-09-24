"""
Free stock price range alert -> Discord notifier.

How it works:
- Reads STOCK_SYMBOL, LOW_PRICE, HIGH_PRICE, DISCORD_WEBHOOK_URL from
  environment variables (set as GitHub Actions secrets/variables).
- Fetches the latest price using yfinance (free, no API key needed).
- If the price is inside [LOW_PRICE, HIGH_PRICE], sends a message to the
  Discord webhook -- but only once per "entry" into the range, using
  state.json to remember whether it already alerted, so it doesn't spam
  you every few minutes while the price stays inside the range.
"""

import json
import os
import sys
from pathlib import Path

import requests
import yfinance as yf

STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_latest_price(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    # fast_info is quick and works for most NSE/BSE/US symbols
    price = ticker.fast_info.get("last_price")
    if price is None:
        # fallback: last close from recent history
        hist = ticker.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"Could not fetch price for {symbol}")
        price = float(hist["Close"].iloc[-1])
    return float(price)


def send_discord_message(webhook_url: str, content: str) -> None:
    resp = requests.post(webhook_url, json={"content": content}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    symbol = os.environ["STOCK_SYMBOL"]
    low = float(os.environ["LOW_PRICE"])
    high = float(os.environ["HIGH_PRICE"])
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]

    price = get_latest_price(symbol)
    print(f"{symbol}: current price = {price}")

    state = load_state()
    was_in_range = state.get(symbol, False)
    is_in_range = low <= price <= high

    if is_in_range and not was_in_range:
        message = (
            f"🔔 **{symbol}** touched your price range!\n"
            f"Current price: **{price}**\n"
            f"Watched range: {low} - {high}"
        )
        send_discord_message(webhook_url, message)
        print("Alert sent to Discord.")
    else:
        print("No new alert needed (either out of range, or already alerted).")

    state[symbol] = is_in_range
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
