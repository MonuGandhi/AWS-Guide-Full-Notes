# 📊 BankNifty Trading Bot

A comprehensive, modular algorithmic trading bot for the **BankNifty index** and **Indian banking sector stocks**, built in Python. It combines real-time market data from **Zerodha KiteConnect**, banking news from **NewsAPI**, technical analysis, and volatility metrics to generate **BUY / SELL signals with confidence levels**.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Real-time market data** | BankNifty index + 12 banking stocks via Zerodha KiteConnect API |
| **Technical indicators** | SMA, EMA, MACD, RSI, Bollinger Bands, ATR |
| **News sentiment** | Banking sector news fetched from NewsAPI, scored POSITIVE / NEGATIVE / NEUTRAL |
| **Volatility analysis** | Historical Volatility, ATR %, intraday range, volatility rank per stock |
| **Signal generation** | Weighted composite BUY / SELL / STRONG signals with confidence % |
| **Live dashboard** | Terminal dashboard with colour-coded signals, volatility heatmap, news tracker |
| **Trade logs** | JSON-lines trade signal log + rotating application log |
| **Demo mode** | Fully functional with synthetic data – no API keys required to try it |

---

## 🏗️ Project Structure

```
banknifty_bot/
├── config.py              # All settings: API keys, thresholds, weights
├── data_fetcher.py        # Zerodha KiteConnect + demo data generation
├── technical_analysis.py  # SMA / EMA / MACD / RSI / Bollinger Bands / ATR
├── news_sentiment.py      # NewsAPI integration + keyword sentiment scoring
├── volatility_analysis.py # Historical volatility, ATR %, heatmap data
├── signal_generator.py    # Composite BUY / SELL signal with confidence
├── logger_reporter.py     # Logging setup + trade reporter + summary prints
├── dashboard.py           # ANSI terminal dashboard
├── main.py                # Entry point – orchestrates the main loop
└── requirements.txt       # Python dependencies
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
cd banknifty_bot
pip install -r requirements.txt
```

### 2. Run in Demo Mode (no API keys needed)

```bash
python main.py
```

`DEMO_MODE = True` is set by default in `config.py`.  All market data and news are **simulated**.

### 3. Configure Live APIs

Edit `banknifty_bot/config.py`:

```python
DEMO_MODE = False

# Zerodha KiteConnect
ZERODHA_API_KEY      = "your_api_key"
ZERODHA_API_SECRET   = "your_api_secret"
ZERODHA_ACCESS_TOKEN = "your_access_token"   # obtained after login

# NewsAPI
NEWS_API_KEY = "your_newsapi_key"
```

> **Zerodha access token**: You need to complete the OAuth login flow each day.  
> See [KiteConnect documentation](https://kite.trade/docs/connect/v3/) for details.

---

## 📈 Signal Logic

### Signal Classification

| Signal | Combined Score | Meaning |
|---|---|---|
| 🟢🟢 **STRONG_BUY** | ≥ 0.70 | Strong uptrend – high confidence BUY |
| 🟢 **BUY** | 0.55 – 0.70 | Uptrend detected |
| ⚪ **NEUTRAL** | 0.35 – 0.55 | No clear direction |
| 🔴 **SELL** | 0.20 – 0.35 | Downtrend detected |
| 🔴🔴 **STRONG_SELL** | ≤ 0.20 | Strong downtrend – high confidence SELL |

### Composite Score Formula

```
combined_score = (technical_score  × 0.50)
               + (sentiment_score  × 0.30)
               + (neutral_base     × 0.20)

confidence = |combined_score − 0.5| × 2.0 × volatility_modifier
```

### Technical Indicators Used

| Indicator | Signal |
|---|---|
| SMA (9/21) cross | Bullish/Bearish cross |
| EMA (12/26) cross | Trend confirmation |
| RSI (14) | < 30 oversold → BUY, > 70 overbought → SELL |
| MACD (12/26/9) | Histogram direction + signal cross |
| Bollinger Bands | Price near lower band → BUY, near upper → SELL |

---

## 📰 News Sentiment

- Queries NewsAPI for `BankNifty`, `India banking sector`, `RBI monetary policy`, and related terms
- Filters only banking-relevant articles
- Scores each headline using positive/negative keyword lists
- Aggregates into a composite sentiment score (−1.0 to +1.0)
- Results are cached for `NEWS_FETCH_INTERVAL_MINUTES` (default 15 min)

---

## 🌡️ Volatility Heatmap

Each banking stock is assigned a volatility label:

| Label | Daily HV | Signal Impact |
|---|---|---|
| **HIGH** | > 3 % | Confidence multiplier 0.70 |
| **NORMAL** | 1 % – 3 % | Confidence multiplier 1.00 |
| **LOW** | < 1 % | Confidence multiplier 0.90 |

---

## 🖥️ Dashboard Preview

```
════════════════════════════════════════════════════════════════════════════════════
  📊  BankNifty Trading Bot  [DEMO MODE]                         Refresh #3
  2025-03-22  10:45:32
════════════════════════════════════════════════════════════════════════════════════

  🏦  NIFTY BANK   47,832.15   ▲ 0.83 %   O:47,650  H:47,960  L:47,590

  Trading Signals
  ────────────────────────────────────────────────────────────────────────────────
  Symbol          Price     Chg%   Signal          Conf   Trend     News       Vol
  ─────────────   ─────────  ─────  ──────────────  ─────  ────────  ──────     ──────
  HDFCBANK        1,667.30  +1.05%  STRONG_BUY       78%   UP        POSITIVE   NORMAL
  ICICIBANK         995.80  +0.61%  BUY              62%   UP        POSITIVE   NORMAL
  SBIN              762.40  +0.26%  NEUTRAL          41%   SIDEWAYS  NEUTRAL    HIGH
  AXISBANK        1,043.20  -0.72%  SELL             55%   DOWN      NEGATIVE   NORMAL
  ...

  Volatility Heatmap
  ────────────────────────────────────────────────────────────────────────────────
  Symbol         HV (ann)   ATR%    Rank   Bar
  SBIN           28.4%      1.82%   82%    ████████████████░░░░  [HIGH]
  BANDHANBNK     26.1%      1.74%   71%    ██████████████░░░░░░  [HIGH]
  HDFCBANK       18.2%      1.15%   45%    █████████░░░░░░░░░░░  [NORMAL]
  ...

  News Sentiment Tracker
  ────────────────────────────────────────────────────────────────────────────────
  📰✅  Overall: POSITIVE   Score: +0.342   Articles: 6   ✅ 4  ❌ 1  ⚪ 1
    • HDFC Bank Q3 profit surges 18% YoY, beats estimates
    • BankNifty rallies 2% as banking stocks witness strong buying
    ...
════════════════════════════════════════════════════════════════════════════════════
```

---

## ⚙️ Configuration Reference

Key settings in `config.py`:

| Variable | Default | Description |
|---|---|---|
| `DEMO_MODE` | `True` | Use simulated data (no API keys needed) |
| `DASHBOARD_REFRESH_SECONDS` | `30` | How often to redraw the dashboard |
| `TECHNICAL_WEIGHT` | `0.50` | Weight of technical analysis in composite score |
| `NEWS_SENTIMENT_WEIGHT` | `0.30` | Weight of news sentiment |
| `VOLATILITY_WEIGHT` | `0.20` | Weight of volatility component |
| `RSI_OVERBOUGHT` | `70` | RSI level considered overbought |
| `RSI_OVERSOLD` | `30` | RSI level considered oversold |
| `SHORT_MA_PERIOD` | `9` | Short-term MA period |
| `LONG_MA_PERIOD` | `21` | Long-term MA period |
| `HISTORICAL_DATA_DAYS` | `60` | Days of OHLCV history to fetch |
| `NEWS_FETCH_INTERVAL_MINUTES` | `15` | News cache duration |

---

## 📝 Logs

- `logs/banknifty_bot.log` – Application log (rotating, up to 10 MB × 5 files)
- `logs/trade_signals.log` – JSON-lines trade signal log

Example trade signal record:
```json
{
  "timestamp": "2025-03-22T10:45:32",
  "symbol": "HDFCBANK",
  "signal": "STRONG_BUY",
  "confidence": 0.78,
  "combined_score": 0.74,
  "technical_score": 0.81,
  "sentiment_score": 0.64,
  "vol_modifier": 1.0,
  "trend_direction": "UP",
  "trend_strength": 0.62,
  "technical_signal": "STRONG_BUY",
  "news_sentiment": "POSITIVE",
  "volatility_label": "NORMAL",
  "reasons": ["Technical: STRONG_BUY ...", "Sentiment: POSITIVE ...", "Volatility: NORMAL ..."]
}
```

---

## ⚠️ Disclaimer

This bot is for **educational purposes only**.  
It does **not** execute real trades automatically.  
Always consult a licensed financial advisor before making investment decisions.  
Past performance of indicators is not indicative of future results.

---

## 🛠️ Requirements

- Python 3.8+
- Zerodha Kite account + KiteConnect subscription (for live mode)
- NewsAPI free or paid plan (for live news)
