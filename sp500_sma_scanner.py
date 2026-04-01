#!/usr/bin/env python3
"""
S&P 500 — 200-Day SMA Scanner
Finds all S&P 500 stocks whose current price is within 1% of their 200-day SMA.

Data sources (all free, no API keys):
  - Wikipedia: S&P 500 ticker list
  - Yahoo Finance (via yfinance): pre-calculated 200-day SMA + current price
"""

import datetime
import requests
from io import StringIO
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

THRESHOLD_PCT = 1.0
MAX_WORKERS = 20  # concurrent threads for Yahoo Finance requests

# ── 1. Get S&P 500 tickers from Wikipedia ─────────────────────────────────
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research bot)"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    tickers = df["Symbol"].tolist()
    # Fix tickers: Wikipedia uses dots (BRK.B), Yahoo uses dashes (BRK-B)
    tickers = [t.replace(".", "-") for t in tickers]
    return sorted(tickers)


# ── 2. Fetch pre-calculated 200-day SMA from Yahoo Finance ───────────────
def fetch_sma_data(symbol):
    """
    Returns (symbol, current_price, sma_200, pct_from_sma, error).
    Yahoo Finance provides twoHundredDayAverage directly — no history needed.
    """
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
    """Fetch SMA data for all tickers concurrently."""
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


# ── 3. Format & output ────────────────────────────────────────────────────
def main():
    now = datetime.datetime.now()
    print("=" * 60)
    print("  S&P 500 — Stocks Within 1% of 200-Day SMA")
    print(f"  Run: {now.strftime('%Y-%m-%d %H:%M ET')}")
    print("=" * 60)
    print()

    tickers = get_sp500_tickers()
    print(f"Loaded {len(tickers)} S&P 500 tickers from Wikipedia.\n")
    print(f"Fetching pre-calculated 200-day SMA from Yahoo Finance …\n")

    results, errors = scan_all(tickers)

    # Filter to within threshold
    near_sma = [r for r in results if abs(r["% from SMA"]) <= THRESHOLD_PCT]

    if not near_sma:
        summary = "No S&P 500 stocks are currently within 1% of their 200-day SMA."
        print(summary)
    else:
        df = pd.DataFrame(near_sma)
        df = df.sort_values("% from SMA", key=abs)

        print(f"Found {len(df)} stocks within 1% of their 200-day SMA:\n")
        print(df.to_string(index=False))

        # Save CSV
        csv_path = "/home/user/workspace/sp500_sma_results.csv"
        df.to_csv(csv_path, index=False)
        print(f"\nResults saved to {csv_path}")

    # Write summary file
    summary_path = "/home/user/workspace/sp500_sma_summary.txt"
    with open(summary_path, "w") as f:
        f.write(f"S&P 500 — Stocks Within 1% of 200-Day SMA\n")
        f.write(f"Date: {now.strftime('%Y-%m-%d %H:%M ET')}\n\n")
        if near_sma:
            df = pd.DataFrame(near_sma).sort_values("% from SMA", key=abs)
            f.write(f"Found {len(df)} stocks:\n\n")
            for _, row in df.iterrows():
                f.write(
                    f"  {row['Ticker']:6s}  "
                    f"Close: ${row['Close']:>9.2f}  "
                    f"SMA: ${row['200-SMA']:>9.2f}  "
                    f"{row['% from SMA']:+.2f}% ({row['Direction']})\n"
                )
        else:
            f.write("No stocks within 1% of their 200-day SMA today.\n")

        if errors:
            f.write(f"\n({len(errors)} tickers skipped due to data issues)\n")

    print(f"\n({len(errors)} tickers had data issues and were skipped)")
    print(f"Summary written to {summary_path}")
    return summary_path


if __name__ == "__main__":
    main()
