"""
Signal Generator Module
========================
Combines technical analysis, news sentiment, and volatility metrics to
produce final BUY / SELL trading signals with confidence levels.

Signal classification:
    STRONG_BUY  – combined score ≥ 0.70
    BUY         – combined score ≥ 0.50
    NEUTRAL     – combined score between 0.35 and 0.50
    SELL        – combined score ≤ 0.30
    STRONG_SELL – combined score ≤ 0.20

Weights (configurable in config.py):
    - Technical indicators : TECHNICAL_WEIGHT
    - News sentiment        : NEWS_SENTIMENT_WEIGHT
    - Volatility adjustment : VOLATILITY_WEIGHT
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    NEWS_SENTIMENT_WEIGHT,
    STRONG_SIGNAL_THRESHOLD,
    TECHNICAL_WEIGHT,
    VOLATILITY_WEIGHT,
)
from news_sentiment import NewsSentimentResult
from technical_analysis import TechnicalSignal
from volatility_analysis import VolatilityMetrics

logger = logging.getLogger(__name__)

# ─── Signal labels ───────────────────────────────────────────────────────────
STRONG_BUY  = "STRONG_BUY"
BUY         = "BUY"
NEUTRAL     = "NEUTRAL"
SELL        = "SELL"
STRONG_SELL = "STRONG_SELL"


@dataclass
class TradingSignal:
    """Final composite trading signal for a symbol."""

    symbol: str
    signal: str                     # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    confidence: float               # 0.0 – 1.0
    combined_score: float           # Raw combined score (0.0 – 1.0 where 0.5 = neutral)
    technical_score: float
    sentiment_score: float
    volatility_modifier: float
    trend_direction: str            # "UP" | "DOWN" | "SIDEWAYS"
    trend_strength: float
    technical_signal: Optional[str] = None
    news_sentiment: Optional[str]   = None
    volatility_label: Optional[str] = None
    reasons: List[str]              = field(default_factory=list)
    timestamp: datetime             = field(default_factory=datetime.now)


class SignalGenerator:
    """Generate composite BUY / SELL signals from multiple data sources."""

    def generate(
        self,
        symbol: str,
        technical: Optional[TechnicalSignal],
        sentiment: Optional[NewsSentimentResult],
        volatility: Optional[VolatilityMetrics],
    ) -> TradingSignal:
        """
        Combine technical, sentiment, and volatility inputs into a final signal.

        Args:
            symbol:     Trading symbol
            technical:  Output of TechnicalAnalyzer.analyze()
            sentiment:  Output of NewsSentimentAnalyzer.get_sentiment()
            volatility: Output of VolatilityAnalyzer.calculate()

        Returns:
            TradingSignal
        """
        reasons: List[str] = []

        # ── Technical score (0.0 – 1.0, 0.5 = neutral) ─────────────────────
        if technical:
            # TechnicalSignal.confidence is abs(score), direction via trend_direction
            raw_conf = technical.confidence
            if technical.trend_direction == "UP":
                tech_score = 0.5 + raw_conf * 0.5
            elif technical.trend_direction == "DOWN":
                tech_score = 0.5 - raw_conf * 0.5
            else:
                tech_score = 0.5
            reasons.append(
                f"Technical: {technical.signal} "
                f"(conf={technical.confidence:.2f}, {technical.trend_direction})"
            )
        else:
            tech_score = 0.5
            reasons.append("Technical: no data (neutral assumed)")

        # ── News sentiment score (0.0 – 1.0) ─────────────────────────────────
        if sentiment:
            sent_score = sentiment.signal_contribution   # already 0.0 – 1.0
            reasons.append(
                f"Sentiment: {sentiment.sentiment_label} "
                f"(score={sentiment.composite_score:.3f}, "
                f"{sentiment.article_count} articles)"
            )
        else:
            sent_score = 0.5
            reasons.append("Sentiment: no data (neutral assumed)")

        # ── Volatility modifier ───────────────────────────────────────────────
        if volatility:
            from volatility_analysis import VolatilityAnalyzer
            vol_modifier = VolatilityAnalyzer.get_confidence_modifier(volatility)
            reasons.append(
                f"Volatility: {volatility.volatility_label} "
                f"(HV={volatility.historical_volatility:.1%}, "
                f"modifier={vol_modifier:.2f})"
            )
        else:
            vol_modifier = 1.0

        # ── Weighted combination ──────────────────────────────────────────────
        combined = (
            tech_score * TECHNICAL_WEIGHT
            + sent_score * NEWS_SENTIMENT_WEIGHT
            + 0.5 * VOLATILITY_WEIGHT          # volatility is a modifier, not direction
        )
        # Apply volatility modifier to confidence (not direction)
        effective_confidence = abs(combined - 0.5) * 2.0 * vol_modifier  # 0.0 – 1.0

        # ── Classify signal ───────────────────────────────────────────────────
        if combined >= 0.70:
            signal = STRONG_BUY
            direction = "UP"
        elif combined >= 0.55:
            signal = BUY
            direction = "UP"
        elif combined <= 0.20:
            signal = STRONG_SELL
            direction = "DOWN"
        elif combined <= 0.35:
            signal = SELL
            direction = "DOWN"
        else:
            signal = NEUTRAL
            direction = "SIDEWAYS"

        trend_strength = effective_confidence
        if technical:
            direction   = technical.trend_direction
            trend_strength = technical.trend_strength

        return TradingSignal(
            symbol=symbol,
            signal=signal,
            confidence=round(min(effective_confidence, 1.0), 4),
            combined_score=round(combined, 4),
            technical_score=round(tech_score, 4),
            sentiment_score=round(sent_score, 4),
            volatility_modifier=round(vol_modifier, 4),
            trend_direction=direction,
            trend_strength=round(trend_strength, 4),
            technical_signal=technical.signal if technical else None,
            news_sentiment=sentiment.sentiment_label if sentiment else None,
            volatility_label=volatility.volatility_label if volatility else None,
            reasons=reasons,
        )

    def generate_multiple(
        self,
        technical_signals: Dict[str, TechnicalSignal],
        sentiment: Optional[NewsSentimentResult],
        volatility_map: Dict[str, VolatilityMetrics],
    ) -> Dict[str, TradingSignal]:
        """
        Generate signals for all available symbols.

        Args:
            technical_signals: {symbol: TechnicalSignal}
            sentiment:          Shared NewsSentimentResult
            volatility_map:    {symbol: VolatilityMetrics}

        Returns:
            {symbol: TradingSignal}
        """
        results: Dict[str, TradingSignal] = {}
        all_symbols = set(technical_signals) | set(volatility_map)
        for sym in all_symbols:
            ts   = technical_signals.get(sym)
            vm   = volatility_map.get(sym)
            sig  = self.generate(sym, ts, sentiment, vm)
            results[sym] = sig
        return results

    # ─── Convenience ─────────────────────────────────────────────────────────

    @staticmethod
    def signal_emoji(signal: str) -> str:
        return {
            STRONG_BUY:  "🟢🟢 STRONG BUY",
            BUY:         "🟢 BUY",
            NEUTRAL:     "⚪ NEUTRAL",
            SELL:        "🔴 SELL",
            STRONG_SELL: "🔴🔴 STRONG SELL",
        }.get(signal, "❓ UNKNOWN")

    @staticmethod
    def format_signal(ts: TradingSignal) -> str:
        """Return a compact one-line representation of the signal."""
        emoji = SignalGenerator.signal_emoji(ts.signal)
        return (
            f"[{ts.timestamp.strftime('%H:%M:%S')}] {ts.symbol:<12} "
            f"{emoji:<20}  conf={ts.confidence:.1%}  "
            f"trend={ts.trend_direction}  "
            f"tech={ts.technical_signal or 'N/A':<12}  "
            f"news={ts.news_sentiment or 'N/A':<10}  "
            f"vol={ts.volatility_label or 'N/A'}"
        )
