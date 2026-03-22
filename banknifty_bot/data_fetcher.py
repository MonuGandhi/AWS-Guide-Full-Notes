"""
Data Fetcher Module
===================
Fetches real-time and historical market data from Zerodha KiteConnect API.

Responsibilities:
    - Authenticate with Zerodha KiteConnect
    - Fetch BankNifty index data (LTP, OHLCV)
    - Fetch individual banking stock data
    - Retrieve historical OHLCV candles for technical analysis
    - Generate simulated data when DEMO_MODE is True
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from config import (
    BANKING_STOCKS,
    BANKNIFTY_EXCHANGE,
    BANKNIFTY_INSTRUMENT_TOKEN,
    BANKNIFTY_SYMBOL,
    CANDLE_INTERVAL,
    DEMO_MODE,
    HISTORICAL_DATA_DAYS,
    ZERODHA_ACCESS_TOKEN,
    ZERODHA_API_KEY,
    ZERODHA_API_SECRET,
)

logger = logging.getLogger(__name__)


# ─── Instrument token cache ──────────────────────────────────────────────────
_DEMO_TOKENS: Dict[str, int] = {
    stock["symbol"]: 1000 + idx for idx, stock in enumerate(BANKING_STOCKS)
}


class DataFetcher:
    """Fetches market data from Zerodha KiteConnect API or demo simulation."""

    def __init__(self) -> None:
        self.kite = None
        self._instrument_tokens: Dict[str, int] = {}
        self._demo_base_prices: Dict[str, float] = self._build_demo_base_prices()
        self._initialize_kite()

    # ─── Initialization ──────────────────────────────────────────────────────

    def _build_demo_base_prices(self) -> Dict[str, float]:
        """Seed realistic base prices for demo simulation."""
        base = {
            "HDFCBANK":   1650.0,
            "ICICIBANK":   990.0,
            "KOTAKBANK":  1750.0,
            "AXISBANK":   1050.0,
            "SBIN":        760.0,
            "BANKBARODA":  220.0,
            "PNB":         100.0,
            "INDUSINDBK": 1400.0,
            "FEDERALBNK":  175.0,
            "IDFCFIRSTB":   80.0,
            "BANDHANBNK":  200.0,
            "AUBANK":      600.0,
            "NIFTY BANK": 48000.0,
        }
        return base

    def _initialize_kite(self) -> None:
        """Connect to Zerodha KiteConnect API."""
        if DEMO_MODE:
            logger.info("DEMO_MODE enabled – using simulated market data.")
            return

        try:
            from kiteconnect import KiteConnect  # type: ignore

            self.kite = KiteConnect(api_key=ZERODHA_API_KEY)
            self.kite.set_access_token(ZERODHA_ACCESS_TOKEN)
            logger.info("Zerodha KiteConnect initialised successfully.")
            self._load_instrument_tokens()
        except ImportError:
            logger.error(
                "kiteconnect package not installed. "
                "Run: pip install kiteconnect  — falling back to DEMO_MODE."
            )
            self._demo_fallback()
        except Exception as exc:
            logger.error("KiteConnect init failed: %s – falling back to DEMO_MODE.", exc)
            self._demo_fallback()

    def _demo_fallback(self) -> None:
        """Silently switch to demo mode on any API error."""
        import config as _cfg
        _cfg.DEMO_MODE = True
        logger.warning("Switched to DEMO_MODE due to API error.")

    def _load_instrument_tokens(self) -> None:
        """Cache NSE instrument tokens for configured banking stocks."""
        if not self.kite:
            return
        try:
            instruments = self.kite.instruments("NSE")
            for instrument in instruments:
                symbol = instrument["tradingsymbol"]
                if symbol in {s["symbol"] for s in BANKING_STOCKS}:
                    self._instrument_tokens[symbol] = instrument["instrument_token"]
            self._instrument_tokens[BANKNIFTY_SYMBOL] = BANKNIFTY_INSTRUMENT_TOKEN
            logger.info("Loaded %d instrument tokens.", len(self._instrument_tokens))
        except Exception as exc:
            logger.error("Failed to load instrument tokens: %s", exc)

    # ─── BankNifty Index ─────────────────────────────────────────────────────

    def fetch_banknifty_quote(self) -> Optional[Dict]:
        """Return the latest BankNifty index quote."""
        if DEMO_MODE:
            return self._demo_index_quote()

        try:
            key = f"{BANKNIFTY_EXCHANGE}:{BANKNIFTY_SYMBOL}"
            data = self.kite.quote([key])[key]
            quote = {
                "symbol":        BANKNIFTY_SYMBOL,
                "last_price":    data["last_price"],
                "open":          data["ohlc"]["open"],
                "high":          data["ohlc"]["high"],
                "low":           data["ohlc"]["low"],
                "close":         data["ohlc"]["close"],
                "volume":        data.get("volume", 0),
                "change":        data.get("net_change", 0.0),
                "change_pct":    data.get("net_change", 0.0) / data["ohlc"]["close"] * 100
                                 if data["ohlc"]["close"] else 0.0,
                "timestamp":     datetime.now(),
            }
            logger.debug("BankNifty quote: %s", quote["last_price"])
            return quote
        except Exception as exc:
            logger.error("Error fetching BankNifty quote: %s", exc)
            return None

    def _demo_index_quote(self) -> Dict:
        base = self._demo_base_prices["NIFTY BANK"]
        price = base + random.uniform(-300, 300)
        change = price - base
        return {
            "symbol":     BANKNIFTY_SYMBOL,
            "last_price": round(price, 2),
            "open":       round(base - random.uniform(0, 200), 2),
            "high":       round(price + random.uniform(0, 150), 2),
            "low":        round(price - random.uniform(0, 150), 2),
            "close":      round(base, 2),
            "volume":     random.randint(500_000, 2_000_000),
            "change":     round(change, 2),
            "change_pct": round(change / base * 100, 2),
            "timestamp":  datetime.now(),
        }

    # ─── Banking Stocks ───────────────────────────────────────────────────────

    def fetch_all_stock_quotes(self) -> Dict[str, Dict]:
        """Return latest quotes for all configured banking stocks."""
        if DEMO_MODE:
            return {s["symbol"]: self._demo_stock_quote(s) for s in BANKING_STOCKS}

        symbols = [f"{s['exchange']}:{s['symbol']}" for s in BANKING_STOCKS]
        try:
            raw = self.kite.quote(symbols)
        except Exception as exc:
            logger.error("Error fetching stock quotes: %s", exc)
            return {}

        quotes: Dict[str, Dict] = {}
        for stock in BANKING_STOCKS:
            key = f"{stock['exchange']}:{stock['symbol']}"
            if key not in raw:
                continue
            data = raw[key]
            prev_close = data["ohlc"]["close"]
            price = data["last_price"]
            quotes[stock["symbol"]] = {
                "symbol":     stock["symbol"],
                "name":       stock["name"],
                "last_price": price,
                "open":       data["ohlc"]["open"],
                "high":       data["ohlc"]["high"],
                "low":        data["ohlc"]["low"],
                "close":      prev_close,
                "volume":     data.get("volume", 0),
                "change":     round(price - prev_close, 2),
                "change_pct": round((price - prev_close) / prev_close * 100, 2)
                              if prev_close else 0.0,
                "timestamp":  datetime.now(),
            }
        return quotes

    def _demo_stock_quote(self, stock: Dict) -> Dict:
        sym = stock["symbol"]
        base = self._demo_base_prices.get(sym, 500.0)
        price = base * (1 + random.uniform(-0.03, 0.03))
        change = price - base
        return {
            "symbol":     sym,
            "name":       stock["name"],
            "last_price": round(price, 2),
            "open":       round(base * (1 + random.uniform(-0.01, 0.01)), 2),
            "high":       round(price * 1.01, 2),
            "low":        round(price * 0.99, 2),
            "close":      round(base, 2),
            "volume":     random.randint(100_000, 5_000_000),
            "change":     round(change, 2),
            "change_pct": round(change / base * 100, 2),
            "timestamp":  datetime.now(),
        }

    # ─── Historical OHLCV ────────────────────────────────────────────────────

    def fetch_historical_data(
        self,
        symbol: str,
        exchange: str = "NSE",
        interval: str = CANDLE_INTERVAL,
        days: int = HISTORICAL_DATA_DAYS,
    ) -> Optional[pd.DataFrame]:
        """
        Return a DataFrame with columns [date, open, high, low, close, volume].
        Falls back to synthetic data in DEMO_MODE.
        """
        if DEMO_MODE:
            return self._demo_historical_data(symbol, days)

        token = self._instrument_tokens.get(symbol)
        if token is None:
            logger.warning("No instrument token for %s", symbol)
            return None

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        try:
            candles = self.kite.historical_data(
                token, from_date, to_date, interval
            )
            if not candles:
                logger.warning("No historical data returned for %s", symbol)
                return None
            df = pd.DataFrame(candles)
            df.rename(
                columns={
                    "date":   "date",
                    "open":   "open",
                    "high":   "high",
                    "low":    "low",
                    "close":  "close",
                    "volume": "volume",
                },
                inplace=True,
            )
            df["date"] = pd.to_datetime(df["date"])
            df.sort_values("date", inplace=True)
            df.reset_index(drop=True, inplace=True)
            logger.debug("Fetched %d candles for %s", len(df), symbol)
            return df
        except Exception as exc:
            logger.error("Error fetching historical data for %s: %s", symbol, exc)
            return None

    def _demo_historical_data(self, symbol: str, days: int) -> pd.DataFrame:
        """Generate synthetic OHLCV data using a random walk."""
        base = self._demo_base_prices.get(symbol, 1000.0)
        dates = [datetime.now() - timedelta(days=days - i) for i in range(days)]
        rows = []
        price = base
        for dt in dates:
            change_pct = random.uniform(-0.025, 0.025)
            open_p = round(price, 2)
            close_p = round(price * (1 + change_pct), 2)
            high_p = round(max(open_p, close_p) * (1 + random.uniform(0, 0.01)), 2)
            low_p = round(min(open_p, close_p) * (1 - random.uniform(0, 0.01)), 2)
            volume = random.randint(500_000, 5_000_000)
            rows.append(
                {
                    "date":   dt,
                    "open":   open_p,
                    "high":   high_p,
                    "low":    low_p,
                    "close":  close_p,
                    "volume": volume,
                }
            )
            price = close_p
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df

    # ─── Market-hours helper ─────────────────────────────────────────────────

    @staticmethod
    def is_market_open() -> bool:
        """Return True if the current IST time is within NSE market hours."""
        from config import (
            MARKET_CLOSE_HOUR,
            MARKET_CLOSE_MINUTE,
            MARKET_OPEN_HOUR,
            MARKET_OPEN_MINUTE,
        )

        now = datetime.now()
        # Skip weekends
        if now.weekday() >= 5:
            return False
        open_time = now.replace(
            hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0
        )
        close_time = now.replace(
            hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0
        )
        return open_time <= now <= close_time

    # ─── Instrument search helper ─────────────────────────────────────────────

    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[int]:
        """Return the instrument token for a given trading symbol."""
        if DEMO_MODE:
            return _DEMO_TOKENS.get(symbol, 999)
        return self._instrument_tokens.get(symbol)
