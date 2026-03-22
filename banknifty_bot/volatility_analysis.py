"""
Volatility Analysis Module
===========================
Calculates and compares volatility metrics across individual banking stocks.

Metrics:
    - Historical Volatility (HV) – annualised log-return std dev
    - Average True Range (ATR) – normalised as % of price
    - Intraday Range – (High − Low) / Close
    - Volatility Rank – stock's current HV percentile over its own history
    - Volatility comparison dashboard across all banking stocks

Volatility is also used as a weight modifier in signal generation:
    - High volatility → lower confidence in signals
    - Low volatility → higher confidence, but watch for breakouts
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import (
    HIGH_VOLATILITY_THRESHOLD,
    LOW_VOLATILITY_THRESHOLD,
    VOLATILITY_WINDOW,
)

logger = logging.getLogger(__name__)


@dataclass
class VolatilityMetrics:
    """Volatility metrics for a single stock."""

    symbol: str
    historical_volatility: float    # Annualised HV (e.g. 0.25 = 25 %)
    atr_pct: float                  # ATR as % of current price
    intraday_range_pct: float       # (High − Low) / Close
    volatility_rank: float          # Percentile rank 0.0 – 1.0
    volatility_label: str           # "HIGH" | "NORMAL" | "LOW"
    daily_returns: List[float] = field(default_factory=list)
    current_price: float = 0.0


class VolatilityAnalyzer:
    """Compute and compare volatility across banking stocks."""

    # ─── Single-stock analysis ───────────────────────────────────────────────

    def calculate(
        self, df: pd.DataFrame, symbol: str = "", window: int = VOLATILITY_WINDOW
    ) -> Optional[VolatilityMetrics]:
        """
        Compute volatility metrics for a single OHLCV DataFrame.

        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            symbol: Trading symbol label
            window: Lookback window for historical volatility

        Returns:
            VolatilityMetrics or None if insufficient data.
        """
        if df is None or len(df) < window + 1:
            logger.warning(
                "Insufficient data for volatility calculation: %s (%d rows).",
                symbol, len(df) if df is not None else 0,
            )
            return None

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # Daily log returns
        log_returns = np.log(close / close.shift(1)).dropna()

        # ── Historical Volatility ────────────────────────────────────────────
        recent_returns = log_returns.iloc[-window:]
        hv_daily = float(recent_returns.std())
        hv_annual = hv_daily * np.sqrt(252)   # annualise

        # ── ATR % ────────────────────────────────────────────────────────────
        high_low   = high - low
        high_close = (high - close.shift()).abs()
        low_close  = (low  - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = float(tr.rolling(window=14).mean().iloc[-1])
        current_price = float(close.iloc[-1])
        atr_pct = (atr / current_price) if current_price else 0.0

        # ── Intraday Range ───────────────────────────────────────────────────
        last_close = float(close.iloc[-1])
        last_high  = float(high.iloc[-1])
        last_low   = float(low.iloc[-1])
        intraday_range_pct = (last_high - last_low) / last_close if last_close else 0.0

        # ── Volatility Rank (percentile of current HV over last N windows) ───
        rolling_hv = log_returns.rolling(window=window).std().dropna()
        if len(rolling_hv) > 0:
            rank = float((rolling_hv < hv_daily).sum() / len(rolling_hv))
        else:
            rank = 0.5

        # ── Label ─────────────────────────────────────────────────────────────
        if hv_daily > HIGH_VOLATILITY_THRESHOLD:
            label = "HIGH"
        elif hv_daily < LOW_VOLATILITY_THRESHOLD:
            label = "LOW"
        else:
            label = "NORMAL"

        return VolatilityMetrics(
            symbol=symbol,
            historical_volatility=round(hv_annual, 4),
            atr_pct=round(atr_pct, 4),
            intraday_range_pct=round(intraday_range_pct, 4),
            volatility_rank=round(rank, 4),
            volatility_label=label,
            daily_returns=recent_returns.tolist(),
            current_price=round(current_price, 2),
        )

    # ─── Multi-stock analysis ────────────────────────────────────────────────

    def analyze_multiple(
        self,
        historical_data: Dict[str, pd.DataFrame],
        window: int = VOLATILITY_WINDOW,
    ) -> Dict[str, VolatilityMetrics]:
        """
        Compute volatility metrics for all provided stocks.

        Args:
            historical_data: {symbol: DataFrame}
            window: Lookback window

        Returns:
            {symbol: VolatilityMetrics}
        """
        results: Dict[str, VolatilityMetrics] = {}
        for symbol, df in historical_data.items():
            metrics = self.calculate(df, symbol, window)
            if metrics:
                results[symbol] = metrics
        return results

    # ─── Comparison helpers ──────────────────────────────────────────────────

    @staticmethod
    def rank_by_volatility(
        volatility_map: Dict[str, VolatilityMetrics],
        ascending: bool = False,
    ) -> List[Tuple[str, VolatilityMetrics]]:
        """
        Return a list of (symbol, metrics) sorted by historical volatility.

        Args:
            ascending: If True, lowest volatility first.
        """
        return sorted(
            volatility_map.items(),
            key=lambda x: x[1].historical_volatility,
            reverse=not ascending,
        )

    @staticmethod
    def get_volatility_heatmap_data(
        volatility_map: Dict[str, VolatilityMetrics],
    ) -> List[Dict]:
        """
        Return a list of dicts suitable for rendering a text-based heatmap.
        """
        items = []
        for symbol, m in volatility_map.items():
            items.append(
                {
                    "symbol":    symbol,
                    "hv_annual": m.historical_volatility,
                    "atr_pct":   m.atr_pct,
                    "rank":      m.volatility_rank,
                    "label":     m.volatility_label,
                    "price":     m.current_price,
                    "bar":       VolatilityAnalyzer._bar(m.volatility_rank),
                }
            )
        items.sort(key=lambda x: x["hv_annual"], reverse=True)
        return items

    @staticmethod
    def _bar(rank: float, width: int = 20) -> str:
        """Render a simple ASCII progress bar for volatility rank."""
        filled = int(rank * width)
        return "█" * filled + "░" * (width - filled)

    # ─── Signal modifier ─────────────────────────────────────────────────────

    @staticmethod
    def get_confidence_modifier(metrics: VolatilityMetrics) -> float:
        """
        Return a multiplier (0.5 – 1.0) to adjust signal confidence based on
        volatility.

        High volatility → signals less reliable → lower multiplier.
        """
        if metrics.volatility_label == "HIGH":
            return 0.70
        if metrics.volatility_label == "LOW":
            return 0.90
        return 1.00

    @staticmethod
    def volatility_label_emoji(label: str) -> str:
        return {"HIGH": "🌡️🔴", "NORMAL": "🌡️🟡", "LOW": "🌡️🟢"}.get(label, "🌡️")
