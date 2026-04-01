#!/usr/bin/env python3
"""
S&P 500 — 200-Day SMA Scanner
Finds all S&P 500 stocks whose current price is within 1% of their 200-day SMA.

Data sources (all free, no API keys):
  - Wikipedia: S&P 500 ticker list
  - Yahoo Finance (via yfinance): pre-calculated 200-day SMA + current price

Notification:
  - Telegram bot (optional, via TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars)
"""

import os
import sys
import datetime
import requests
from io import StringIO
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

THRESHOLD_PCT = 1.0
MAX_WORKERS = 20


# ── 1. Get S&P 500 tickers from Wikipedia ─────────────────────────────────
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research bot)"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    tickers = df["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]
    return sorted(tickers)


# ── 2. Fetch pre-calculated 200-day SMA from Yahoo Finance ───────────────
def fetch_sma_data(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        sma_200 = info.get("twoHundredDayAverage")
        if price is None or sma_200 is None or sma_200 == 0:
            return (symbol, None, None, None, "Missing price or SMA data")
        pct = ((price - sma_200) / sma_200) * 100
        return (symbol, float(price), float(sma_200), float(pct), None)
    except Exception as e:
        return (symbol, None, None, None, str(e))


def scan_all(tickers):
    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_sma_data, sym): sym for sym in tickers}
        done = 0
        total = len(futures)
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  Progress: {done}/{total}")
            sym, price, sma, pct, err = future.result()
            if err:
                errors.append((sym, err))
            else:
                results.append({
                    "Ticker": sym,
                    "Close": round(price, 2),
                    "200-SMA": round(sma, 2),
                    "% from SMA": round(pct, 2),
                    "Direction": "Above" if pct >= 0 else "Below",
                })
    return results, errors


# ── 3. Telegram notification ──────────────────────────────────────────────
def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram env vars not set — skipping notification.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    })
    if resp.ok:
        print("Telegram notification sent.")
        return True
    else:
        print(f"Telegram error: {resp.status_code} {resp.text}")
        return False


# ── 4. Format & run ──────────────────────────────────────────────────────
def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    et_offset = datetime.timezone(datetime.timedelta(hours=-4))
    now_et = now.astimezone(et_offset)
    date_str = now_et.strftime("%Y-%m-%d %H:%M ET")

    print("=" * 60)
    print("  S&P 500 — Stocks Within 1% of 200-Day SMA")
    print(f"  Run: {date_str}")
    print("=" * 60)
    print()

    tickers = get_sp500_tickers()
    print(f"Loaded {len(tickers)} S&P 500 tickers from Wikipedia.\n")
    print("Fetching pre-calculated 200-day SMA from Yahoo Finance …\n")

    results, errors = scan_all(tickers)
    near_sma = [r for r in results if abs(r["% from SMA"]) <= THRESHOLD_PCT]

    # ── Console output ──
    if not near_sma:
        print("No S&P 500 stocks are currently within 1% of their 200-day SMA.")
    else:
        df = pd.DataFrame(near_sma).sort_values("% from SMA", key=abs)
        print(f"Found {len(df)} stocks within 1% of their 200-day SMA:\n")
        print(df.to_string(index=False))

    print(f"\n({len(errors)} tickers had data issues and were skipped)")

    # ── Build Telegram message ──
    lines = [f"<b>S&P 500 — Stocks Near 200-Day SMA</b>", f"📅 {date_str}", ""]

    if not near_sma:
        lines.append("No stocks within 1% of their 200-day SMA today.")
    else:
        df = pd.DataFrame(near_sma).sort_values("% from SMA", key=abs)
        lines.append(f"<b>{len(df)} stocks within 1%:</b>")
        lines.append("")
        for _, row in df.iterrows():
            arrow = "🟢" if row["Direction"] == "Above" else "🔴"
            lines.append(
                f"{arrow} <b>{row['Ticker']}</b>  "
                f"${row['Close']:.2f}  →  "
                f"SMA ${row['200-SMA']:.2f}  "
                f"({row['% from SMA']:+.2f}%)"
            )

    if errors:
        lines.append(f"\n({len(errors)} tickers skipped)")

    message = "\n".join(lines)
    send_telegram(message)

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
