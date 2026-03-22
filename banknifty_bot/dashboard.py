"""
Dashboard Module
================
Renders a real-time terminal dashboard for the BankNifty Trading Bot.

Components:
    - BankNifty index ticker
    - Banking sector comparison table
    - Volatility heatmap
    - News sentiment tracker
    - Live trading signals with confidence levels
    - Signal history

The dashboard clears and redraws the terminal on each refresh cycle.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from config import BANKING_STOCKS, DEMO_MODE, SHOW_NEWS_TRACKER, SHOW_VOLATILITY_HEATMAP
from news_sentiment import NewsSentimentResult
from signal_generator import TradingSignal
from volatility_analysis import VolatilityMetrics

logger = logging.getLogger(__name__)

# ─── ANSI helpers ─────────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_WHITE  = "\033[97m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"


def _colour(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _clear_screen() -> None:
    """Clear the terminal screen (cross-platform)."""
    os.system("cls" if sys.platform == "win32" else "clear")


class Dashboard:
    """Terminal dashboard for real-time bot monitoring."""

    def __init__(self) -> None:
        self._refresh_count = 0

    # ─── Main render ─────────────────────────────────────────────────────────

    def render(
        self,
        banknifty_quote: Optional[Dict],
        stock_quotes: Dict[str, Dict],
        signals: Dict[str, TradingSignal],
        sentiment: Optional[NewsSentimentResult],
        volatility_map: Dict[str, VolatilityMetrics],
        signal_history: List[Dict],
    ) -> None:
        """
        Clear the screen and redraw the complete dashboard.

        Args:
            banknifty_quote: Latest BankNifty index quote
            stock_quotes:    Latest quotes for all banking stocks
            signals:         {symbol: TradingSignal}
            sentiment:       Aggregated news sentiment
            volatility_map:  {symbol: VolatilityMetrics}
            signal_history:  List of recent signal records
        """
        _clear_screen()
        self._refresh_count += 1
        width = 84

        self._header(width)
        self._banknifty_ticker(banknifty_quote, width)
        self._mode_banner(width)
        self._signals_table(signals, stock_quotes, width)
        if SHOW_VOLATILITY_HEATMAP:
            self._volatility_heatmap(volatility_map, width)
        if SHOW_NEWS_TRACKER and sentiment:
            self._news_tracker(sentiment, width)
        self._signal_history_panel(signal_history, width)
        self._footer(width)

    # ─── Sections ────────────────────────────────────────────────────────────

    def _header(self, width: int) -> None:
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        title = "  📊  BankNifty Trading Bot"
        demo = "  [DEMO MODE]" if DEMO_MODE else ""
        print(_colour("═" * width, _CYAN))
        print(
            _colour(f"{title}{demo}", _BOLD + _WHITE)
            + _colour(f"{'Refresh #' + str(self._refresh_count):>{width - len(title) - len(demo) - 1}}", _DIM)
        )
        print(_colour(f"  {now}", _DIM))
        print(_colour("═" * width, _CYAN))

    def _banknifty_ticker(self, quote: Optional[Dict], width: int) -> None:
        if not quote:
            print(_colour("  BankNifty: data unavailable", _YELLOW))
            return
        chg = quote.get("change_pct", 0.0)
        arrow = "▲" if chg >= 0 else "▼"
        colour = _GREEN if chg >= 0 else _RED
        price_str = f"{quote['last_price']:,.2f}"
        chg_str   = f"{arrow} {abs(chg):.2f} %"
        print(
            _colour(f"\n  🏦  NIFTY BANK", _WHITE + _BOLD)
            + "   "
            + _colour(price_str, colour + _BOLD)
            + "   "
            + _colour(chg_str, colour)
            + _colour(
                f"   O:{quote.get('open', 0):,.0f}  "
                f"H:{quote.get('high', 0):,.0f}  "
                f"L:{quote.get('low', 0):,.0f}",
                _DIM,
            )
        )
        print()

    def _mode_banner(self, width: int) -> None:
        if DEMO_MODE:
            print(
                _colour(
                    "  ⚠️  DEMO MODE – simulated data only.  "
                    "Set DEMO_MODE = False and configure API keys for live data.",
                    _YELLOW,
                )
            )
            print()

    def _signals_table(
        self, signals: Dict[str, TradingSignal], stock_quotes: Dict[str, Dict], width: int
    ) -> None:
        print(_colour("  Trading Signals", _BOLD + _CYAN))
        print(_colour("  " + "─" * (width - 2), _DIM))
        hdr = (
            f"  {'Symbol':<13}  {'Price':>9}  {'Chg%':>6}  "
            f"{'Signal':<14}  {'Conf':>5}  {'Trend':<9}  {'News':<10}  Vol"
        )
        print(_colour(hdr, _DIM))
        print(_colour("  " + "─" * (width - 2), _DIM))

        for sym in sorted(signals):
            ts = signals[sym]
            q  = stock_quotes.get(sym, {})
            price   = q.get("last_price", 0.0)
            chg_pct = q.get("change_pct", 0.0)
            chg_col = _GREEN if chg_pct >= 0 else _RED

            sig_col = self._signal_colour(ts.signal)
            row = (
                f"  {sym:<13}  "
                + _colour(f"{price:>9,.2f}", _WHITE)
                + "  "
                + _colour(f"{chg_pct:>+5.2f}%", chg_col)
                + "  "
                + _colour(f"{ts.signal:<14}", sig_col)
                + _colour(f"  {ts.confidence:>4.0%}", sig_col)
                + f"  {ts.trend_direction:<9}"
                + f"  {ts.news_sentiment or 'N/A':<10}"
                + f"  {ts.volatility_label or 'N/A'}"
            )
            print(row)

        print()

    def _volatility_heatmap(
        self, volatility_map: Dict[str, VolatilityMetrics], width: int
    ) -> None:
        from volatility_analysis import VolatilityAnalyzer

        print(_colour("  Volatility Heatmap", _BOLD + _CYAN))
        print(_colour("  " + "─" * (width - 2), _DIM))
        hdr = f"  {'Symbol':<13}  {'HV (ann)':<9}  {'ATR%':<7}  {'Rank':<6}  Bar"
        print(_colour(hdr, _DIM))
        print(_colour("  " + "─" * (width - 2), _DIM))

        items = VolatilityAnalyzer.get_volatility_heatmap_data(volatility_map)
        for item in items:
            col = _RED if item["label"] == "HIGH" else (_GREEN if item["label"] == "LOW" else _YELLOW)
            print(
                f"  {item['symbol']:<13}  "
                + _colour(f"{item['hv_annual']:<9.1%}", col)
                + f"  {item['atr_pct']:<7.2%}"
                + f"  {item['rank']:<6.0%}"
                + "  "
                + _colour(item["bar"], col)
            )
        print()

    def _news_tracker(self, sentiment: NewsSentimentResult, width: int) -> None:
        from news_sentiment import NewsSentimentAnalyzer

        label_col = (
            _GREEN if sentiment.sentiment_label == "POSITIVE"
            else (_RED if sentiment.sentiment_label == "NEGATIVE" else _YELLOW)
        )
        emoji = NewsSentimentAnalyzer.sentiment_to_emoji(sentiment.sentiment_label)

        print(_colour("  News Sentiment Tracker", _BOLD + _CYAN))
        print(_colour("  " + "─" * (width - 2), _DIM))
        print(
            f"  {emoji}  Overall: "
            + _colour(sentiment.sentiment_label, label_col + _BOLD)
            + f"   Score: {sentiment.composite_score:+.3f}"
            + f"   Articles: {sentiment.article_count}"
            + f"   ✅ {sentiment.positive_count}"
            + f"  ❌ {sentiment.negative_count}"
            + f"  ⚪ {sentiment.neutral_count}"
        )

        # Print latest 5 headlines
        for art in sentiment.articles[:5]:
            art_col = (
                _GREEN if art.sentiment_label == "POSITIVE"
                else (_RED if art.sentiment_label == "NEGATIVE" else _DIM)
            )
            title_trunc = (art.title[:65] + "…") if len(art.title) > 66 else art.title
            print(_colour(f"    • {title_trunc}", art_col))
        print()

    def _signal_history_panel(self, history: List[Dict], width: int) -> None:
        if not history:
            return
        print(_colour("  Recent Signal Log", _BOLD + _CYAN))
        print(_colour("  " + "─" * (width - 2), _DIM))
        for rec in history[-8:]:
            sig_col = self._signal_colour(rec.get("signal", ""))
            print(
                f"  {rec.get('timestamp', '')[:19]}  "
                + f"{rec.get('symbol', ''):<13}  "
                + _colour(f"{rec.get('signal', ''):<14}", sig_col)
                + f"  conf={rec.get('confidence', 0):.1%}"
                + f"  {rec.get('trend_direction', '')}"
            )
        print()

    def _footer(self, width: int) -> None:
        print(_colour("═" * width, _CYAN))
        print(_colour(f"  Press Ctrl+C to stop the bot.", _DIM))
        print(_colour("═" * width, _CYAN))

    @staticmethod
    def _signal_colour(signal: str) -> str:
        return {
            "STRONG_BUY":  _GREEN + _BOLD,
            "BUY":         _GREEN,
            "NEUTRAL":     _WHITE,
            "SELL":        _RED,
            "STRONG_SELL": _RED + _BOLD,
        }.get(signal, _WHITE)
