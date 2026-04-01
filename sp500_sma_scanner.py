#!/usr/bin/env python3
"""
S&P 500 — Multi-SMA Scanner
Finds all S&P 500 stocks whose current price is within 1% of their 20, 150, or 200-day SMA.

Data sources (all free, no API keys):
  - Wikipedia: S&P 500 ticker list
  - Yahoo Finance (via yfinance):
      - 200-day & 50-day SMA: pre-calculated (from quote data)
      - 20-day & 150-day SMA: calculated from batch-downloaded history

Notification:
  - Telegram bot (via TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars)
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
SMA_WINDOWS = [20, 150, 200]


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


# ── 2. Fetch 200-day SMA from Yahoo quote data ───────────────────────────
def fetch_quote_data(symbol):
    """Get current price + pre-calculated 200-day SMA from Yahoo quote."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        sma_200 = info.get("twoHundredDayAverage")
        if price is None:
            return (symbol, None, None, "Missing price")
        return (symbol, float(price), float(sma_200) if sma_200 else None, None)
    except Exception as e:
        return (symbol, None, None, str(e))


# ── 3. Batch download history for 20-day & 150-day SMA ───────────────────
def compute_sma_from_history(tickers):
    """
    Download ~200 days of history for all tickers in one batch call,
    then compute 20-day and 150-day SMAs.
    Returns dict: {ticker: {20: sma_val, 150: sma_val}}
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=300)  # enough buffer for 150 trading days

    print("Batch downloading price history for 20 & 150-day SMA …")
    data = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    sma_dict = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                close = data["Close"].dropna()
            else:
                close = data[(ticker, "Close")].dropna()

            sma_dict[ticker] = {}
            for window in [20, 150]:
                if len(close) >= window:
                    sma_dict[ticker][window] = float(close.rolling(window=window).mean().iloc[-1])
                else:
                    sma_dict[ticker][window] = None
        except Exception:
            sma_dict[ticker] = {20: None, 150: None}

    return sma_dict


# ── 4. Main scan ──────────────────────────────────────────────────────────
def scan_all(tickers):
    # Step A: Get current prices + 200-day SMA from quote data (concurrent)
    print(f"Fetching quotes for {len(tickers)} tickers …\n")
    quote_results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_quote_data, sym): sym for sym in tickers}
        done = 0
        total = len(futures)
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  Quotes: {done}/{total}")
            sym, price, sma_200, err = future.result()
            if err:
                errors.append((sym, err))
            else:
                quote_results[sym] = {"price": price, 200: sma_200}

    # Step B: Batch download history for 20 & 150-day SMA
    valid_tickers = list(quote_results.keys())
    sma_dict = compute_sma_from_history(valid_tickers)

    # Step C: Merge and find stocks near any SMA
    results = []
    for sym, quote in quote_results.items():
        price = quote["price"]
        if price is None:
            continue

        sma_values = {
            20: sma_dict.get(sym, {}).get(20),
            150: sma_dict.get(sym, {}).get(150),
            200: quote.get(200),
        }

        for window in SMA_WINDOWS:
            sma = sma_values.get(window)
            if sma is None or sma == 0:
                continue
            pct = ((price - sma) / sma) * 100
            if abs(pct) <= THRESHOLD_PCT:
                results.append({
                    "Ticker": sym,
                    "SMA": f"{window}d",
                    "Close": round(price, 2),
                    f"SMA Value": round(sma, 2),
                    "% from SMA": round(pct, 2),
                    "Direction": "Above" if pct >= 0 else "Below",
                })

    return results, errors


# ── 5. Telegram notification ──────────────────────────────────────────────
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


# ── 6. Format & run ──────────────────────────────────────────────────────
def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    et_offset = datetime.timezone(datetime.timedelta(hours=-4))
    now_et = now.astimezone(et_offset)
    date_str = now_et.strftime("%Y-%m-%d %H:%M ET")

    print("=" * 60)
    print("  S&P 500 — Stocks Within 1% of 20/150/200-Day SMA")
    print(f"  Run: {date_str}")
    print("=" * 60)
    print()

    tickers = get_sp500_tickers()
    print(f"Loaded {len(tickers)} S&P 500 tickers from Wikipedia.\n")

    results, errors = scan_all(tickers)

    # Sort by SMA window, then by absolute distance
    if results:
        df = pd.DataFrame(results)
        df["abs_pct"] = df["% from SMA"].abs()
        df = df.sort_values(["SMA", "abs_pct"]).drop(columns=["abs_pct"])

        print(f"\nFound {len(df)} hits across 20/150/200-day SMAs:\n")
        print(df.to_string(index=False))
    else:
        print("No stocks within 1% of any SMA today.")

    print(f"\n({len(errors)} tickers had data issues and were skipped)")

    # ── Build Telegram message ──
    lines = [
        f"<b>S&P 500 — Stocks Near Key SMAs</b>",
        f"📅 {date_str}",
        "",
    ]

    if not results:
        lines.append("No stocks within 1% of their 20/150/200-day SMA today.")
    else:
        df = pd.DataFrame(results)
        df["abs_pct"] = df["% from SMA"].abs()

        for window in SMA_WINDOWS:
            group = df[df["SMA"] == f"{window}d"].sort_values("abs_pct")
            if group.empty:
                continue
            lines.append(f"<b>━━ {window}-Day SMA ({len(group)} stocks) ━━</b>")
            lines.append("")
            for _, row in group.iterrows():
                arrow = "🟢" if row["Direction"] == "Above" else "🔴"
                lines.append(
                    f"{arrow} <b>{row['Ticker']}</b>  "
                    f"${row['Close']:.2f}  →  "
                    f"SMA ${row['SMA Value']:.2f}  "
                    f"({row['% from SMA']:+.2f}%)"
                )
            lines.append("")

    if errors:
        lines.append(f"({len(errors)} tickers skipped)")

    message = "\n".join(lines)
    send_telegram(message)

    return 0


if __name__ == "__main__":
    sys.exit(main())
