# S&P 500 — 200-Day SMA Scanner

Daily scanner that identifies S&P 500 stocks trading within 1% of their 200-day simple moving average. Runs automatically via GitHub Actions and sends results to Telegram.

## How It Works

1. **Ticker list** — Pulled live from [Wikipedia's S&P 500 list](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies)
2. **Price + SMA data** — Fetched from Yahoo Finance via `yfinance`. Uses the pre-calculated `twoHundredDayAverage` field — no historical data download needed
3. **Filter** — Returns all stocks where `|current_price - 200_SMA| / 200_SMA <= 1%`
4. **Notify** — Sends formatted results to Telegram

## No Paid APIs

- **Wikipedia** — S&P 500 constituent list (free)
- **Yahoo Finance** via `yfinance` — Current price + 200-day SMA (free, no API key)
- **Telegram Bot API** — Push notifications (free)
- **GitHub Actions** — Scheduler (free for public repos)

## Automated Schedule

Runs every weekday at **4:00 AM ET** (premarket open) via GitHub Actions.

You can also trigger it manually from the Actions tab.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** you receive

### 2. Get Your Chat ID

1. Message your new bot (send it anything)
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id": 123456789}` — that number is your chat ID

### 3. Add GitHub Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret:

- `TELEGRAM_BOT_TOKEN` — your bot token
- `TELEGRAM_CHAT_ID` — your chat ID

### 4. Done

The workflow runs automatically on weekday premarket opens. To test immediately, go to Actions → "Daily SMA Scan" → "Run workflow".

## Local Usage

```bash
pip install -r requirements.txt

# Without Telegram:
python sp500_sma_scanner.py

# With Telegram:
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python sp500_sma_scanner.py
```

## Example Telegram Message

```
S&P 500 — Stocks Near 200-Day SMA
📅 2026-04-01 04:00 ET

18 stocks within 1%:

🟢 CINF  $158.13  →  SMA $158.03  (+0.06%)
🔴 WST   $252.94  →  SMA $253.27  (-0.13%)
🔴 MCD   $307.73  →  SMA $308.59  (-0.28%)
🟢 ROK   $370.58  →  SMA $369.00  (+0.43%)
...
```
