"""
News Sentiment Analysis Module
===============================
Fetches banking-sector news via NewsAPI and performs keyword-based
sentiment analysis to generate a market-sentiment score.

Responsibilities:
    - Fetch recent news articles from NewsAPI
    - Filter articles relevant to Indian banking / BankNifty
    - Score each article as POSITIVE / NEGATIVE / NEUTRAL
    - Aggregate sentiment into a composite signal
    - Cache results to respect NewsAPI rate limits
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import (
    DEMO_MODE,
    NEWS_API_KEY,
    NEWS_FETCH_INTERVAL_MINUTES,
    NEWS_LANGUAGE,
    NEWS_LOOKBACK_HOURS,
    NEWS_MAX_ARTICLES,
    NEWS_QUERIES,
)

logger = logging.getLogger(__name__)

# ─── Sentiment word lists ────────────────────────────────────────────────────
_POSITIVE_WORDS = {
    "surge", "gain", "profit", "growth", "rally", "bullish", "positive",
    "increase", "rise", "high", "strong", "recovery", "outperform", "upgrade",
    "beat", "record", "expansion", "boost", "buy", "opportunity", "upside",
    "rebound", "momentum", "breakout", "inflow", "dividend", "acquisition",
    "green", "up", "higher", "better", "good", "excellent", "robust",
}

_NEGATIVE_WORDS = {
    "fall", "drop", "loss", "decline", "bearish", "negative", "decrease",
    "low", "weak", "crash", "downgrade", "miss", "below", "slump",
    "contraction", "concern", "risk", "warning", "fraud", "npa", "default",
    "write-off", "penalty", "fine", "probe", "investigation", "sell",
    "red", "down", "lower", "worse", "bad", "poor", "terrible", "crisis",
    "recession", "inflation", "stress", "uncertainty", "volatile",
}

_BANKING_KEYWORDS = {
    "bank", "banking", "nifty", "rbi", "reserve bank", "npa",
    "hdfc", "icici", "kotak", "axis", "sbi", "pnb", "bandhan",
    "idfc", "federal", "indusind", "au bank", "monetary policy",
    "interest rate", "credit", "loan", "deposit", "repo rate",
    "liquidity", "capital adequacy", "net interest margin",
}


@dataclass
class NewsArticle:
    """Represents a single news article with its sentiment."""

    title: str
    description: str
    url: str
    published_at: datetime
    source: str
    sentiment_score: float = 0.0       # −1.0 (very negative) to +1.0 (very positive)
    sentiment_label: str = "NEUTRAL"
    relevance_score: float = 0.0


@dataclass
class NewsSentimentResult:
    """Aggregated sentiment across a set of articles."""

    articles: List[NewsArticle] = field(default_factory=list)
    composite_score: float = 0.0       # −1.0 to +1.0
    sentiment_label: str = "NEUTRAL"   # POSITIVE / NEGATIVE / NEUTRAL
    signal_contribution: float = 0.0   # Normalised 0.0 – 1.0 for signal weighting
    article_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class NewsSentimentAnalyzer:
    """Fetch and analyse banking-sector news for trading signals."""

    def __init__(self) -> None:
        self._last_fetch: Optional[datetime] = None
        self._cached_result: Optional[NewsSentimentResult] = None
        self._newsapi = None
        self._init_newsapi()

    # ─── Initialisation ──────────────────────────────────────────────────────

    def _init_newsapi(self) -> None:
        if DEMO_MODE:
            logger.info("DEMO_MODE – news sentiment will use simulated articles.")
            return
        if not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here":
            logger.warning(
                "NEWS_API_KEY not configured – using simulated news sentiment."
            )
            return
        try:
            from newsapi import NewsApiClient  # type: ignore

            self._newsapi = NewsApiClient(api_key=NEWS_API_KEY)
            logger.info("NewsAPI client initialised.")
        except ImportError:
            logger.error(
                "newsapi-python not installed. Run: pip install newsapi-python"
            )

    # ─── Public API ──────────────────────────────────────────────────────────

    def get_sentiment(self, force_refresh: bool = False) -> NewsSentimentResult:
        """
        Return aggregated news sentiment.  Uses cache if last fetch was
        within NEWS_FETCH_INTERVAL_MINUTES.
        """
        if not force_refresh and self._is_cache_valid():
            logger.debug("Returning cached news sentiment.")
            return self._cached_result  # type: ignore

        if DEMO_MODE or self._newsapi is None:
            result = self._demo_sentiment()
        else:
            articles = self._fetch_articles()
            result = self._aggregate(articles)

        self._cached_result = result
        self._last_fetch = datetime.now()
        return result

    # ─── Article Fetching ────────────────────────────────────────────────────

    def _fetch_articles(self) -> List[NewsArticle]:
        """Download articles for all configured queries."""
        articles: List[NewsArticle] = []
        from_date = datetime.now() - timedelta(hours=NEWS_LOOKBACK_HOURS)

        for query in NEWS_QUERIES:
            try:
                response = self._newsapi.get_everything(  # type: ignore
                    q=query,
                    language=NEWS_LANGUAGE,
                    from_param=from_date.strftime("%Y-%m-%dT%H:%M:%S"),
                    sort_by="publishedAt",
                    page_size=min(NEWS_MAX_ARTICLES, 20),
                )
                for raw in response.get("articles", []):
                    article = self._parse_article(raw)
                    if article:
                        articles.append(article)
            except Exception as exc:
                logger.error("NewsAPI fetch error for query '%s': %s", query, exc)

        # De-duplicate by URL
        seen_urls: set = set()
        unique: List[NewsArticle] = []
        for art in articles:
            if art.url not in seen_urls:
                seen_urls.add(art.url)
                unique.append(art)

        logger.info("Fetched %d unique news articles.", len(unique))
        return unique

    def _parse_article(self, raw: Dict) -> Optional[NewsArticle]:
        """Parse a raw NewsAPI article dict into a NewsArticle."""
        title = raw.get("title") or ""
        description = raw.get("description") or ""
        url = raw.get("url") or ""
        source = raw.get("source", {}).get("name") or "Unknown"

        published_str = raw.get("publishedAt") or ""
        try:
            published_at = datetime.fromisoformat(
                published_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            published_at = datetime.now()

        text = f"{title} {description}".lower()
        relevance = self._relevance_score(text)
        if relevance == 0.0:
            return None                      # Skip non-banking articles

        sentiment, score = self._sentiment_score(text)

        return NewsArticle(
            title=title,
            description=description,
            url=url,
            published_at=published_at,
            source=source,
            sentiment_score=score,
            sentiment_label=sentiment,
            relevance_score=relevance,
        )

    # ─── Scoring helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _relevance_score(text: str) -> float:
        """Return 0.0 if not banking-related, else a 0.1–1.0 relevance score."""
        matches = sum(1 for kw in _BANKING_KEYWORDS if kw in text)
        return min(matches / 3.0, 1.0) if matches else 0.0

    @staticmethod
    def _sentiment_score(text: str) -> tuple:
        """
        Simple keyword-based sentiment.

        Returns:
            (label, score)  where score ∈ [−1.0, +1.0]
        """
        words = re.findall(r"\b\w+\b", text.lower())
        pos = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
        total = pos + neg
        if total == 0:
            return "NEUTRAL", 0.0
        score = (pos - neg) / total
        if score > 0.15:
            label = "POSITIVE"
        elif score < -0.15:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"
        return label, round(score, 4)

    # ─── Aggregation ─────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(articles: List[NewsArticle]) -> NewsSentimentResult:
        if not articles:
            return NewsSentimentResult()

        weighted_scores: List[float] = []
        positive = negative = neutral = 0

        for art in articles:
            weighted_scores.append(art.sentiment_score * art.relevance_score)
            if art.sentiment_label == "POSITIVE":
                positive += 1
            elif art.sentiment_label == "NEGATIVE":
                negative += 1
            else:
                neutral += 1

        composite = (
            sum(weighted_scores) / len(weighted_scores) if weighted_scores else 0.0
        )

        if composite > 0.15:
            label = "POSITIVE"
        elif composite < -0.15:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        # Normalise to 0.0 – 1.0 for signal weighting
        signal_contribution = (composite + 1.0) / 2.0

        return NewsSentimentResult(
            articles=articles,
            composite_score=round(composite, 4),
            sentiment_label=label,
            signal_contribution=round(signal_contribution, 4),
            article_count=len(articles),
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
        )

    # ─── Demo simulation ─────────────────────────────────────────────────────

    @staticmethod
    def _demo_sentiment() -> NewsSentimentResult:
        """Generate plausible fake news articles for demo mode."""
        import random

        sample_articles = [
            ("HDFC Bank Q3 profit surges 18% YoY, beats estimates", "POSITIVE", 0.7),
            ("RBI keeps repo rate unchanged at 6.5%, signals cautious stance", "NEUTRAL", 0.1),
            ("ICICI Bank NPA ratio improves to 2.1%, best in 5 years", "POSITIVE", 0.65),
            ("BankNifty rallies 2% as banking stocks witness strong buying", "POSITIVE", 0.8),
            ("SBI reports record quarterly profit driven by retail loans", "POSITIVE", 0.75),
            ("Axis Bank under regulatory scrutiny for KYC violations", "NEGATIVE", -0.6),
            ("Kotak Bank upgrades FY25 loan growth guidance to 18%", "POSITIVE", 0.55),
            ("Banking sector faces NPA headwinds amid global slowdown", "NEGATIVE", -0.5),
            ("IndusInd Bank stock falls 4% on weak NIMs guidance", "NEGATIVE", -0.65),
            ("PNB reports 30% rise in net profit on lower provisions", "POSITIVE", 0.6),
        ]

        selected = random.sample(sample_articles, k=random.randint(4, 7))
        articles: List[NewsArticle] = []
        for title, label, score in selected:
            articles.append(
                NewsArticle(
                    title=title,
                    description="",
                    url="https://demo.example.com",
                    published_at=datetime.now() - timedelta(hours=random.randint(0, 5)),
                    source="Demo News",
                    sentiment_score=score + random.uniform(-0.1, 0.1),
                    sentiment_label=label,
                    relevance_score=random.uniform(0.7, 1.0),
                )
            )

        return NewsSentimentAnalyzer._aggregate(articles)

    # ─── Cache helper ─────────────────────────────────────────────────────────

    def _is_cache_valid(self) -> bool:
        if self._last_fetch is None or self._cached_result is None:
            return False
        age = (datetime.now() - self._last_fetch).total_seconds() / 60.0
        return age < NEWS_FETCH_INTERVAL_MINUTES

    # ─── Convenience ─────────────────────────────────────────────────────────

    @staticmethod
    def sentiment_to_emoji(label: str) -> str:
        return {"POSITIVE": "📰✅", "NEGATIVE": "📰❌", "NEUTRAL": "📰⚪"}.get(
            label, "📰"
        )
