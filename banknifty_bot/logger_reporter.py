"""
Logger & Reporter Module
=========================
Configures application-wide logging and provides trade-signal reporting.

Features:
    - Rotating file handler for application logs
    - Separate rotating file handler for trade signals
    - Console (stdout) handler with colour support
    - Structured trade-signal records (JSON-lines)
    - HTML / text report generation
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime
from typing import Dict, List

from config import (
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    MAX_SIGNAL_HISTORY,
    TRADE_LOG_FILE,
)


# ─── ANSI colour codes ────────────────────────────────────────────────────────
_COLOURS = {
    "DEBUG":    "\033[36m",   # Cyan
    "INFO":     "\033[32m",   # Green
    "WARNING":  "\033[33m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[35m",   # Magenta
    "RESET":    "\033[0m",
}


class ColouredFormatter(logging.Formatter):
    """Formatter that adds ANSI colour codes to level names."""

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        reset  = _COLOURS["RESET"]
        record.levelname = f"{colour}{record.levelname:<8}{reset}"
        return super().format(record)


def setup_logging() -> None:
    """
    Initialise root logger with:
        - Coloured console handler
        - Rotating file handler for all application logs
        - Rotating file handler specifically for trade signals
    """
    # Ensure log directories exist
    for log_path in (LOG_FILE, TRADE_LOG_FILE):
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    if root.handlers:
        return   # Already configured

    # ── Console handler ───────────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setFormatter(
        ColouredFormatter(
            fmt="%(asctime)s  %(levelname)s  %(name)-20s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console)

    # ── Application file handler ───────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


# ─── Trade Reporter ───────────────────────────────────────────────────────────

class TradeReporter:
    """Logs and aggregates trading signals for reporting."""

    def __init__(self) -> None:
        self._signal_history: List[Dict] = []
        self._trade_logger = self._build_trade_logger()

    # ─── Trade logger setup ───────────────────────────────────────────────────

    @staticmethod
    def _build_trade_logger() -> logging.Logger:
        logger = logging.getLogger("trade_signals")
        if not logger.handlers:
            handler = logging.handlers.RotatingFileHandler(
                TRADE_LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.propagate = False
        return logger

    # ─── Public API ──────────────────────────────────────────────────────────

    def log_signal(self, signal_obj) -> None:
        """
        Persist a TradingSignal to the trade log (JSON-lines) and in-memory
        history.

        Args:
            signal_obj: TradingSignal dataclass instance
        """
        record = {
            "timestamp":         signal_obj.timestamp.isoformat(),
            "symbol":            signal_obj.symbol,
            "signal":            signal_obj.signal,
            "confidence":        signal_obj.confidence,
            "combined_score":    signal_obj.combined_score,
            "technical_score":   signal_obj.technical_score,
            "sentiment_score":   signal_obj.sentiment_score,
            "vol_modifier":      signal_obj.volatility_modifier,
            "trend_direction":   signal_obj.trend_direction,
            "trend_strength":    signal_obj.trend_strength,
            "technical_signal":  signal_obj.technical_signal,
            "news_sentiment":    signal_obj.news_sentiment,
            "volatility_label":  signal_obj.volatility_label,
            "reasons":           signal_obj.reasons,
        }
        self._trade_logger.info(json.dumps(record))

        # Keep in-memory history (bounded)
        self._signal_history.append(record)
        if len(self._signal_history) > MAX_SIGNAL_HISTORY:
            self._signal_history.pop(0)

    def get_signal_history(self) -> List[Dict]:
        """Return a copy of the in-memory signal history."""
        return list(self._signal_history)

    def log_banknifty_quote(self, quote: Dict) -> None:
        """Write a BankNifty quote record to the trade log."""
        record = {
            "type":      "BANKNIFTY_QUOTE",
            "timestamp": datetime.now().isoformat(),
            **{k: v for k, v in quote.items() if k != "timestamp"},
        }
        self._trade_logger.info(json.dumps(record))

    # ─── Text report ─────────────────────────────────────────────────────────

    def print_summary_report(
        self,
        signals: Dict,
        banknifty_quote: Dict,
        sentiment_result,
        volatility_map: Dict,
    ) -> None:
        """
        Print a formatted summary report to stdout.

        Args:
            signals:          {symbol: TradingSignal}
            banknifty_quote:  BankNifty quote dict
            sentiment_result: NewsSentimentResult
            volatility_map:   {symbol: VolatilityMetrics}
        """
        from signal_generator import SignalGenerator

        sep = "─" * 80
        print(f"\n{sep}")
        print(f"  📊  BankNifty Trading Bot  │  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(sep)

        # BankNifty index
        if banknifty_quote:
            chg_icon = "▲" if banknifty_quote.get("change_pct", 0) >= 0 else "▼"
            print(
                f"\n  🏦  NIFTY BANK : {banknifty_quote['last_price']:,.2f}  "
                f"{chg_icon} {abs(banknifty_quote.get('change_pct', 0)):.2f} %"
            )

        # News sentiment
        if sentiment_result:
            from news_sentiment import NewsSentimentAnalyzer
            emoji = NewsSentimentAnalyzer.sentiment_to_emoji(
                sentiment_result.sentiment_label
            )
            print(
                f"\n  {emoji}  News Sentiment : {sentiment_result.sentiment_label}  "
                f"│  score={sentiment_result.composite_score:+.3f}  "
                f"│  articles={sentiment_result.article_count}"
            )

        # Signals table
        print(f"\n  {'Symbol':<14}  {'Signal':<14}  {'Conf':>6}  {'Trend':>8}  "
              f"{'Tech Signal':<14}  {'Volatility'}")
        print(f"  {'─' * 14}  {'─' * 14}  {'─' * 6}  {'─' * 8}  {'─' * 14}  {'─' * 12}")
        for sym, ts in sorted(signals.items()):
            vol_lbl = ts.volatility_label or "N/A"
            print(
                f"  {sym:<14}  {ts.signal:<14}  {ts.confidence:>5.1%}  "
                f"{ts.trend_direction:>8}  {ts.technical_signal or 'N/A':<14}  {vol_lbl}"
            )

        # Volatility heatmap
        if volatility_map:
            from volatility_analysis import VolatilityAnalyzer

            print(f"\n  {'─' * 60}")
            print("  🌡️  Volatility Heatmap")
            print(f"  {'─' * 60}")
            heatmap = VolatilityAnalyzer.get_volatility_heatmap_data(volatility_map)
            for row in heatmap:
                print(
                    f"  {row['symbol']:<14}  {row['bar']}  "
                    f"HV={row['hv_annual']:.1%}  [{row['label']}]"
                )

        # Recent signal history
        history = self.get_signal_history()
        if history:
            print(f"\n  {'─' * 60}")
            print(f"  📋  Recent Signals (last {min(5, len(history))})")
            print(f"  {'─' * 60}")
            for rec in history[-5:]:
                print(
                    f"  {rec['timestamp'][11:19]}  {rec['symbol']:<12}  "
                    f"{rec['signal']:<14}  conf={rec['confidence']:.1%}"
                )

        print(f"\n{sep}\n")
