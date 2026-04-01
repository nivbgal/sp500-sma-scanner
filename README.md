# S&P 500 — 200-Day SMA Scanner

Daily scanner that identifies S&P 500 stocks trading within 1% of their 200-day simple moving average.

## How It Works

1. **Ticker list** — Pulled live from [Wikipedia's S&P 500 list](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies)
2. **Price + SMA data** — Fetched from Yahoo Finance via `yfinance`. Uses the pre-calculated `twoHundredDayAverage` field (no need to download historical data and compute it ourselves)
3. **Filter** — Returns all stocks where `|current_price - 200_SMA| / 200_SMA <= 1%`

## No Paid APIs

- **Wikipedia** — S&P 500 constituent list (free, always up to date)
- **Yahoo Finance** via `yfinance` — Current price + pre-calculated 200-day SMA (free, no API key)

## Setup

```bash
pip install yfinance pandas requests lxml html5lib
python sp500_sma_scanner.py
```

## Output

- Console table of matching stocks
- `sp500_sma_results.csv` — Full results as CSV
- `sp500_sma_summary.txt` — Human-readable summary

## Example Output

```
Ticker  Close  200-SMA  % from SMA Direction
   ROK 368.95   369.00       -0.01     Below
  CINF 158.34   158.03        0.20     Above
   MCD 307.28   308.59       -0.42     Below
   GE  294.48   293.15        0.45     Above
  ABBV 214.75   215.96       -0.56     Below
```

## Requirements

- Python 3.9+
- See `requirements.txt`
