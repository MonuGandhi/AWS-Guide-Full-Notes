"""
Technical Analysis Module
=========================
Calculates technical indicators and generates trend-based signals.

Indicators implemented:
    - Simple Moving Average (SMA)
    - Exponential Moving Average (EMA)
    - Moving Average Convergence Divergence (MACD)
    - Relative Strength Index (RSI)
    - Bollinger Bands
    - Average True Range (ATR) for volatility

Signals:
    - STRONG_BUY / BUY  – uptrend detected
    - STRONG_SELL / SELL – downtrend detected
    - NEUTRAL            – no clear direction
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import (
    BB_PERIOD,
    BB_STD_DEV,
    EMA_LONG,
    EMA_SHORT,
    LONG_MA_PERIOD,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MIN_CANDLES_REQUIRED,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    SHORT_MA_PERIOD,
    SIGNAL_LINE,
)

logger = logging.getLogger(__name__)

# ─── Signal constants ────────────────────────────────────────────────────────
STRONG_BUY  = "STRONG_BUY"
BUY         = "BUY"
NEUTRAL     = "NEUTRAL"
SELL        = "SELL"
STRONG_SELL = "STRONG_SELL"


@dataclass
class TechnicalSignal:
    """Container for a technical analysis signal."""

    symbol: str
    signal: str                    # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    confidence: float              # 0.0 – 1.0
    trend_direction: str           # "UP" | "DOWN" | "SIDEWAYS"
    trend_strength: float          # 0.0 – 1.0
    indicators: Dict = field(default_factory=dict)
    reason: str = ""


class TechnicalAnalyzer:
    """Compute technical indicators and derive trading signals from OHLCV data."""

    # ─── Moving Averages ─────────────────────────────────────────────────────

    @staticmethod
    def calculate_sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period).mean()

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    # ─── MACD ────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_macd(
        series: pd.Series,
        fast: int = MACD_FAST,
        slow: int = MACD_SLOW,
        signal: int = MACD_SIGNAL,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Returns:
            macd_line, signal_line, histogram
        """
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    # ─── RSI ─────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
        """Relative Strength Index (Wilder smoothing)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    # ─── Bollinger Bands ─────────────────────────────────────────────────────

    @staticmethod
    def calculate_bollinger_bands(
        series: pd.Series,
        period: int = BB_PERIOD,
        std_dev: float = BB_STD_DEV,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Returns:
            upper_band, middle_band, lower_band
        """
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower

    # ─── ATR (Volatility) ────────────────────────────────────────────────────

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        high_low   = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close  = (df["low"]  - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    # ─── Full Analysis ───────────────────────────────────────────────────────

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[TechnicalSignal]:
        """
        Run all indicators on the OHLCV DataFrame and return a TechnicalSignal.

        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            symbol: Trading symbol (for labelling)

        Returns:
            TechnicalSignal or None if insufficient data.
        """
        if df is None or len(df) < MIN_CANDLES_REQUIRED:
            logger.warning(
                "Insufficient candles for %s (%d < %d required).",
                symbol, len(df) if df is not None else 0, MIN_CANDLES_REQUIRED,
            )
            return None

        df = df.copy()
        close = df["close"]

        # ── Compute indicators ──────────────────────────────────────────────
        df["sma_short"]  = self.calculate_sma(close, SHORT_MA_PERIOD)
        df["sma_long"]   = self.calculate_sma(close, LONG_MA_PERIOD)
        df["ema_short"]  = self.calculate_ema(close, EMA_SHORT)
        df["ema_long"]   = self.calculate_ema(close, EMA_LONG)
        df["rsi"]        = self.calculate_rsi(close)
        macd, sig, hist  = self.calculate_macd(close)
        df["macd"]       = macd
        df["macd_signal"]= sig
        df["macd_hist"]  = hist
        df["atr"]        = self.calculate_atr(df)
        bb_up, bb_mid, bb_low = self.calculate_bollinger_bands(close)
        df["bb_upper"]   = bb_up
        df["bb_middle"]  = bb_mid
        df["bb_lower"]   = bb_low

        # ── Latest values ───────────────────────────────────────────────────
        last        = df.iloc[-1]
        prev        = df.iloc[-2]
        price       = last["close"]
        sma_s       = last["sma_short"]
        sma_l       = last["sma_long"]
        ema_s       = last["ema_short"]
        ema_l       = last["ema_long"]
        rsi_val     = last["rsi"]
        macd_val    = last["macd"]
        macd_sig    = last["macd_signal"]
        macd_h      = last["macd_hist"]
        prev_macd_h = prev["macd_hist"]
        atr_val     = last["atr"]
        bb_upper    = last["bb_upper"]
        bb_lower    = last["bb_lower"]

        # ── Score individual signals (−1 bearish ↔ +1 bullish) ───────────────
        scores: List[float] = []
        reasons: List[str] = []

        # 1. MA cross
        if sma_s > sma_l:
            scores.append(1.0)
            reasons.append("SMA bullish cross")
        else:
            scores.append(-1.0)
            reasons.append("SMA bearish cross")

        # 2. EMA cross
        if ema_s > ema_l:
            scores.append(1.0)
            reasons.append("EMA bullish cross")
        else:
            scores.append(-1.0)
            reasons.append("EMA bearish cross")

        # 3. Price vs SMA
        if price > sma_l:
            scores.append(0.5)
            reasons.append("Price above long SMA")
        else:
            scores.append(-0.5)
            reasons.append("Price below long SMA")

        # 4. RSI
        if rsi_val < RSI_OVERSOLD:
            scores.append(1.0)
            reasons.append(f"RSI oversold ({rsi_val:.1f})")
        elif rsi_val > RSI_OVERBOUGHT:
            scores.append(-1.0)
            reasons.append(f"RSI overbought ({rsi_val:.1f})")
        else:
            norm = (rsi_val - 50) / 50        # −1 to +1
            scores.append(norm * 0.5)
            reasons.append(f"RSI neutral ({rsi_val:.1f})")

        # 5. MACD histogram direction
        if macd_h > 0 and macd_h > prev_macd_h:
            scores.append(1.0)
            reasons.append("MACD histogram rising above zero")
        elif macd_h < 0 and macd_h < prev_macd_h:
            scores.append(-1.0)
            reasons.append("MACD histogram falling below zero")
        elif macd_val > macd_sig:
            scores.append(0.5)
            reasons.append("MACD above signal line")
        else:
            scores.append(-0.5)
            reasons.append("MACD below signal line")

        # 6. Bollinger Band position
        if price < bb_lower:
            scores.append(0.75)
            reasons.append("Price below lower BB (oversold)")
        elif price > bb_upper:
            scores.append(-0.75)
            reasons.append("Price above upper BB (overbought)")
        else:
            pct = (price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) else 0.5
            scores.append((pct - 0.5) * 0.5)   # small contribution near middle
            reasons.append("Price within BB")

        # ── Aggregate ────────────────────────────────────────────────────────
        avg_score = float(np.mean(scores))         # −1.0 to +1.0
        confidence = min(abs(avg_score), 1.0)

        if avg_score >= 0.60:
            signal = STRONG_BUY
            direction = "UP"
        elif avg_score >= 0.25:
            signal = BUY
            direction = "UP"
        elif avg_score <= -0.60:
            signal = STRONG_SELL
            direction = "DOWN"
        elif avg_score <= -0.25:
            signal = SELL
            direction = "DOWN"
        else:
            signal = NEUTRAL
            direction = "SIDEWAYS"

        trend_strength = abs(avg_score)

        indicators = {
            "price":       round(price, 2),
            "sma_short":   round(sma_s, 2),
            "sma_long":    round(sma_l, 2),
            "ema_short":   round(ema_s, 2),
            "ema_long":    round(ema_l, 2),
            "rsi":         round(rsi_val, 2),
            "macd":        round(macd_val, 4),
            "macd_signal": round(macd_sig, 4),
            "macd_hist":   round(macd_h, 4),
            "atr":         round(atr_val, 2),
            "bb_upper":    round(bb_upper, 2),
            "bb_lower":    round(bb_lower, 2),
            "score":       round(avg_score, 4),
        }

        return TechnicalSignal(
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 4),
            trend_direction=direction,
            trend_strength=round(trend_strength, 4),
            indicators=indicators,
            reason="; ".join(reasons),
        )

    # ─── Multi-stock analysis ────────────────────────────────────────────────

    def analyze_multiple(
        self,
        historical_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, TechnicalSignal]:
        """
        Analyse multiple stocks at once.

        Args:
            historical_data: {symbol: DataFrame}

        Returns:
            {symbol: TechnicalSignal}
        """
        results: Dict[str, TechnicalSignal] = {}
        for symbol, df in historical_data.items():
            sig = self.analyze(df, symbol)
            if sig:
                results[symbol] = sig
        return results

    # ─── Convenience helpers ──────────────────────────────────────────────────

    @staticmethod
    def signal_to_emoji(signal: str) -> str:
        """Return an emoji representing the signal strength."""
        return {
            STRONG_BUY:  "🟢🟢",
            BUY:         "🟢",
            NEUTRAL:     "⚪",
            SELL:        "🔴",
            STRONG_SELL: "🔴🔴",
        }.get(signal, "❓")

    @staticmethod
    def is_bullish(signal: str) -> bool:
        return signal in (BUY, STRONG_BUY)

    @staticmethod
    def is_bearish(signal: str) -> bool:
        return signal in (SELL, STRONG_SELL)
