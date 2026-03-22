"""
BankNifty Trading Bot – Main Entry Point
=========================================
Orchestrates all modules in a continuous loop:

    1. Fetch BankNifty index quote
    2. Fetch individual banking stock quotes
    3. Fetch / refresh historical OHLCV data
    4. Run technical analysis (MA, RSI, MACD)
    5. Fetch / refresh news sentiment
    6. Compute volatility metrics
    7. Generate composite BUY / SELL signals
    8. Render dashboard and log results

Usage:
    python main.py

Set DEMO_MODE = False in config.py and fill in your API keys to connect to
live Zerodha KiteConnect and NewsAPI feeds.
"""

import logging
import sys
import time
from datetime import datetime
from typing import Dict, Optional

from config import (
    BANKING_STOCKS,
    DASHBOARD_REFRESH_SECONDS,
    DEMO_MODE,
    HISTORICAL_DATA_DAYS,
    MARKET_DATA_INTERVAL_SECONDS,
)
from dashboard import Dashboard
from data_fetcher import DataFetcher
from logger_reporter import TradeReporter, setup_logging
from news_sentiment import NewsSentimentAnalyzer
from signal_generator import SignalGenerator, TradingSignal
from technical_analysis import TechnicalAnalyzer
from volatility_analysis import VolatilityAnalyzer

logger = logging.getLogger(__name__)


def _print_startup_banner() -> None:
    print(
        """
╔══════════════════════════════════════════════════════════╗
║        BankNifty Algorithmic Trading Bot                 ║
║                                                          ║
║  • Zerodha KiteConnect  – real-time market data          ║
║  • NewsAPI              – banking sector news            ║
║  • Technical Analysis   – MA / RSI / MACD                ║
║  • Volatility Analysis  – HV / ATR per stock             ║
║  • Signal Generation    – BUY / SELL with confidence     ║
╚══════════════════════════════════════════════════════════╝
"""
    )
    if DEMO_MODE:
        print("  ⚠️  Running in DEMO MODE – all data is simulated.\n")
    else:
        print("  🔴  LIVE MODE – connected to Zerodha KiteConnect.\n")


class BankNiftyBot:
    """Main bot orchestrator."""

    def __init__(self) -> None:
        setup_logging()
        logger.info("Initialising BankNifty Trading Bot…")

        self.data_fetcher  = DataFetcher()
        self.tech_analyzer = TechnicalAnalyzer()
        self.news_analyzer = NewsSentimentAnalyzer()
        self.vol_analyzer  = VolatilityAnalyzer()
        self.sig_generator = SignalGenerator()
        self.reporter      = TradeReporter()
        self.dashboard     = Dashboard()

        # In-memory historical data cache
        self._hist_cache: Dict = {}
        self._last_hist_fetch: Optional[datetime] = None

    # ─── Main loop ───────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the bot's main loop."""
        _print_startup_banner()
        logger.info("Bot started. Press Ctrl+C to stop.")

        try:
            while True:
                self._cycle()
                logger.debug("Sleeping %ds until next cycle.", DASHBOARD_REFRESH_SECONDS)
                time.sleep(DASHBOARD_REFRESH_SECONDS)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (KeyboardInterrupt).")
            print("\n  Bot stopped. Goodbye! 👋\n")

    # ─── Single cycle ────────────────────────────────────────────────────────

    def _cycle(self) -> None:
        """Execute one full analysis-and-display cycle."""
        cycle_start = datetime.now()
        logger.info("─── Cycle start: %s", cycle_start.strftime("%H:%M:%S"))

        # 1. BankNifty index quote
        banknifty_quote = self.data_fetcher.fetch_banknifty_quote()
        if banknifty_quote:
            self.reporter.log_banknifty_quote(banknifty_quote)
            logger.info(
                "BankNifty: %.2f  (%+.2f%%)",
                banknifty_quote["last_price"],
                banknifty_quote.get("change_pct", 0),
            )

        # 2. Banking stock quotes
        stock_quotes = self.data_fetcher.fetch_all_stock_quotes()
        logger.info("Fetched %d stock quotes.", len(stock_quotes))

        # 3. Historical data (refresh every HISTORICAL_DATA_DAYS refresh)
        self._refresh_historical_data()

        # 4. Technical analysis
        technical_signals = self.tech_analyzer.analyze_multiple(self._hist_cache)
        logger.info("Technical signals computed for %d symbols.", len(technical_signals))

        # 5. News sentiment
        sentiment = self.news_analyzer.get_sentiment()
        logger.info(
            "News sentiment: %s  (score=%.3f, articles=%d)",
            sentiment.sentiment_label,
            sentiment.composite_score,
            sentiment.article_count,
        )

        # 6. Volatility
        volatility_map = self.vol_analyzer.analyze_multiple(self._hist_cache)
        logger.info("Volatility computed for %d symbols.", len(volatility_map))

        # 7. Signal generation
        signals = self.sig_generator.generate_multiple(
            technical_signals, sentiment, volatility_map
        )

        # 8. Log all signals
        for sym, sig in signals.items():
            self.reporter.log_signal(sig)
            logger.info(SignalGenerator.format_signal(sig))

        # 9. Render dashboard
        self.dashboard.render(
            banknifty_quote=banknifty_quote,
            stock_quotes=stock_quotes,
            signals=signals,
            sentiment=sentiment,
            volatility_map=volatility_map,
            signal_history=self.reporter.get_signal_history(),
        )

        elapsed = (datetime.now() - cycle_start).total_seconds()
        logger.debug("Cycle complete in %.2fs", elapsed)

    # ─── Historical data helpers ─────────────────────────────────────────────

    def _refresh_historical_data(self) -> None:
        """
        Refresh the historical OHLCV cache.  In a real deployment this would
        only re-fetch once per day; in demo mode every cycle is fine.
        """
        # Refresh if cache is empty or in demo mode (fast)
        if self._hist_cache and not DEMO_MODE:
            return

        logger.debug("Refreshing historical data for %d symbols…", len(BANKING_STOCKS))
        for stock in BANKING_STOCKS:
            sym = stock["symbol"]
            df = self.data_fetcher.fetch_historical_data(
                symbol=sym,
                exchange=stock["exchange"],
                days=HISTORICAL_DATA_DAYS,
            )
            if df is not None:
                self._hist_cache[sym] = df

        # Also fetch BankNifty historical
        bn_df = self.data_fetcher.fetch_historical_data(
            symbol="NIFTY BANK",
            exchange="NSE",
            days=HISTORICAL_DATA_DAYS,
        )
        if bn_df is not None:
            self._hist_cache["NIFTY BANK"] = bn_df

        self._last_hist_fetch = datetime.now()
        logger.info(
            "Historical data cache updated (%d symbols).", len(self._hist_cache)
        )


if __name__ == "__main__":
    bot = BankNiftyBot()
    bot.run()
