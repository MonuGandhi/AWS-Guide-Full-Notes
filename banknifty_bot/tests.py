"""
Unit tests for BankNifty Trading Bot modules.

Run with:
    cd banknifty_bot
    python -m pytest tests.py -v
"""

import sys
import os

# Make sure the banknifty_bot package is importable
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_ohlcv(n: int = 60, base_price: float = 1000.0) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame with a slight upward trend."""
    dates = [datetime.now() - timedelta(days=n - i) for i in range(n)]
    price = base_price
    rows = []
    rng = np.random.default_rng(seed=42)
    for dt in dates:
        chg = rng.uniform(-0.02, 0.025)
        open_p  = round(price, 2)
        close_p = round(price * (1 + chg), 2)
        high_p  = round(max(open_p, close_p) * (1 + rng.uniform(0, 0.005)), 2)
        low_p   = round(min(open_p, close_p) * (1 - rng.uniform(0, 0.005)), 2)
        rows.append({"date": dt, "open": open_p, "high": high_p,
                     "low": low_p, "close": close_p, "volume": 1_000_000})
        price = close_p
    return pd.DataFrame(rows)


# ─── config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_demo_mode_default(self):
        import config
        assert config.DEMO_MODE is True

    def test_banking_stocks_non_empty(self):
        import config
        assert len(config.BANKING_STOCKS) > 0

    def test_weights_sum_to_one(self):
        import config
        total = config.TECHNICAL_WEIGHT + config.NEWS_SENTIMENT_WEIGHT + config.VOLATILITY_WEIGHT
        assert abs(total - 1.0) < 1e-9

    def test_rsi_thresholds(self):
        import config
        assert config.RSI_OVERSOLD < config.RSI_OVERBOUGHT


# ─── data_fetcher ─────────────────────────────────────────────────────────────

class TestDataFetcher:
    def setup_method(self):
        from data_fetcher import DataFetcher
        self.fetcher = DataFetcher()

    def test_fetch_banknifty_quote_structure(self):
        quote = self.fetcher.fetch_banknifty_quote()
        assert quote is not None
        for key in ("symbol", "last_price", "open", "high", "low", "close",
                    "volume", "change", "change_pct", "timestamp"):
            assert key in quote, f"Missing key: {key}"

    def test_banknifty_quote_price_positive(self):
        quote = self.fetcher.fetch_banknifty_quote()
        assert quote["last_price"] > 0

    def test_fetch_all_stock_quotes_count(self):
        import config
        quotes = self.fetcher.fetch_all_stock_quotes()
        assert len(quotes) == len(config.BANKING_STOCKS)

    def test_historical_data_structure(self):
        df = self.fetcher.fetch_historical_data("HDFCBANK", days=30)
        assert df is not None
        for col in ("date", "open", "high", "low", "close", "volume"):
            assert col in df.columns

    def test_historical_data_row_count(self):
        df = self.fetcher.fetch_historical_data("HDFCBANK", days=30)
        assert len(df) == 30

    def test_high_ge_low(self):
        df = self.fetcher.fetch_historical_data("ICICIBANK", days=30)
        assert (df["high"] >= df["low"]).all()


# ─── technical_analysis ───────────────────────────────────────────────────────

class TestTechnicalAnalysis:
    def setup_method(self):
        from technical_analysis import TechnicalAnalyzer
        self.analyzer = TechnicalAnalyzer()
        self.df = make_ohlcv(60)

    def test_sma_length(self):
        sma = self.analyzer.calculate_sma(self.df["close"], 9)
        assert len(sma) == len(self.df)

    def test_ema_length(self):
        ema = self.analyzer.calculate_ema(self.df["close"], 12)
        assert len(ema) == len(self.df)

    def test_rsi_range(self):
        rsi = self.analyzer.calculate_rsi(self.df["close"])
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_macd_returns_three_series(self):
        macd, sig, hist = self.analyzer.calculate_macd(self.df["close"])
        assert len(macd) == len(self.df)
        assert len(sig)  == len(self.df)
        assert len(hist) == len(self.df)

    def test_bollinger_bands_ordering(self):
        upper, mid, lower = self.analyzer.calculate_bollinger_bands(self.df["close"])
        valid_idx = upper.dropna().index
        assert (upper[valid_idx] >= mid[valid_idx]).all()
        assert (mid[valid_idx]   >= lower[valid_idx]).all()

    def test_analyze_returns_signal(self):
        from technical_analysis import TechnicalSignal
        result = self.analyzer.analyze(self.df, "TEST")
        assert result is not None
        assert isinstance(result, TechnicalSignal)

    def test_analyze_confidence_range(self):
        result = self.analyzer.analyze(self.df, "TEST")
        assert 0.0 <= result.confidence <= 1.0

    def test_analyze_valid_signal_label(self):
        from technical_analysis import STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
        result = self.analyzer.analyze(self.df, "TEST")
        assert result.signal in (STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL)

    def test_analyze_insufficient_data_returns_none(self):
        tiny_df = make_ohlcv(10)
        result = self.analyzer.analyze(tiny_df, "TINY")
        assert result is None

    def test_analyze_multiple_returns_dict(self):
        data = {"A": make_ohlcv(60), "B": make_ohlcv(60)}
        results = self.analyzer.analyze_multiple(data)
        assert set(results.keys()) == {"A", "B"}


# ─── news_sentiment ───────────────────────────────────────────────────────────

class TestNewsSentiment:
    def setup_method(self):
        from news_sentiment import NewsSentimentAnalyzer
        self.analyzer = NewsSentimentAnalyzer()

    def test_get_sentiment_returns_result(self):
        from news_sentiment import NewsSentimentResult
        result = self.analyzer.get_sentiment()
        assert isinstance(result, NewsSentimentResult)

    def test_composite_score_range(self):
        result = self.analyzer.get_sentiment()
        assert -1.0 <= result.composite_score <= 1.0

    def test_signal_contribution_range(self):
        result = self.analyzer.get_sentiment()
        assert 0.0 <= result.signal_contribution <= 1.0

    def test_article_counts_consistent(self):
        result = self.analyzer.get_sentiment()
        assert (result.positive_count + result.negative_count + result.neutral_count
                == result.article_count)

    def test_sentiment_label_valid(self):
        result = self.analyzer.get_sentiment()
        assert result.sentiment_label in ("POSITIVE", "NEGATIVE", "NEUTRAL")

    def test_cache_returns_same_object(self):
        r1 = self.analyzer.get_sentiment()
        r2 = self.analyzer.get_sentiment()
        assert r1 is r2   # cached object

    def test_force_refresh(self):
        r1 = self.analyzer.get_sentiment()
        r2 = self.analyzer.get_sentiment(force_refresh=True)
        assert r2 is not r1   # should be a new object

    def test_relevance_score_banking(self):
        score = self.analyzer._relevance_score("hdfc bank npa profit rise")
        assert score > 0.0

    def test_relevance_score_non_banking(self):
        score = self.analyzer._relevance_score("football match result goals scored")
        assert score == 0.0

    def test_sentiment_score_positive(self):
        label, score = self.analyzer._sentiment_score("profit surge gain rally strong buy")
        assert label == "POSITIVE"
        assert score > 0

    def test_sentiment_score_negative(self):
        label, score = self.analyzer._sentiment_score("loss crash decline npa fraud weak")
        assert label == "NEGATIVE"
        assert score < 0


# ─── volatility_analysis ──────────────────────────────────────────────────────

class TestVolatilityAnalysis:
    def setup_method(self):
        from volatility_analysis import VolatilityAnalyzer
        self.analyzer = VolatilityAnalyzer()
        self.df = make_ohlcv(60)

    def test_calculate_returns_metrics(self):
        from volatility_analysis import VolatilityMetrics
        result = self.analyzer.calculate(self.df, "TEST")
        assert isinstance(result, VolatilityMetrics)

    def test_hv_positive(self):
        result = self.analyzer.calculate(self.df, "TEST")
        assert result.historical_volatility > 0

    def test_atr_pct_positive(self):
        result = self.analyzer.calculate(self.df, "TEST")
        assert result.atr_pct > 0

    def test_volatility_rank_range(self):
        result = self.analyzer.calculate(self.df, "TEST")
        assert 0.0 <= result.volatility_rank <= 1.0

    def test_volatility_label_valid(self):
        result = self.analyzer.calculate(self.df, "TEST")
        assert result.volatility_label in ("HIGH", "NORMAL", "LOW")

    def test_insufficient_data_returns_none(self):
        tiny = make_ohlcv(5)
        result = self.analyzer.calculate(tiny, "TINY")
        assert result is None

    def test_analyze_multiple_returns_all(self):
        data = {"X": make_ohlcv(60), "Y": make_ohlcv(60)}
        results = self.analyzer.analyze_multiple(data)
        assert set(results.keys()) == {"X", "Y"}

    def test_confidence_modifier_range(self):
        result = self.analyzer.calculate(self.df, "TEST")
        mod = self.analyzer.get_confidence_modifier(result)
        assert 0.0 < mod <= 1.0

    def test_rank_sorted_descending(self):
        data = {f"S{i}": make_ohlcv(60, base_price=500 + i * 100) for i in range(3)}
        vm = self.analyzer.analyze_multiple(data)
        ranked = self.analyzer.rank_by_volatility(vm)
        hvs = [m.historical_volatility for _, m in ranked]
        assert hvs == sorted(hvs, reverse=True)


# ─── signal_generator ─────────────────────────────────────────────────────────

class TestSignalGenerator:
    def setup_method(self):
        from signal_generator import SignalGenerator
        from technical_analysis import TechnicalAnalyzer
        from news_sentiment import NewsSentimentAnalyzer
        from volatility_analysis import VolatilityAnalyzer

        self.gen = SignalGenerator()
        df = make_ohlcv(60)
        self.tech   = TechnicalAnalyzer().analyze(df, "TEST")
        self.news   = NewsSentimentAnalyzer().get_sentiment()
        self.vol    = VolatilityAnalyzer().calculate(df, "TEST")

    def test_generate_returns_signal(self):
        from signal_generator import TradingSignal
        sig = self.gen.generate("TEST", self.tech, self.news, self.vol)
        assert isinstance(sig, TradingSignal)

    def test_signal_label_valid(self):
        from signal_generator import STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
        sig = self.gen.generate("TEST", self.tech, self.news, self.vol)
        assert sig.signal in (STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL)

    def test_confidence_range(self):
        sig = self.gen.generate("TEST", self.tech, self.news, self.vol)
        assert 0.0 <= sig.confidence <= 1.0

    def test_combined_score_range(self):
        sig = self.gen.generate("TEST", self.tech, self.news, self.vol)
        assert 0.0 <= sig.combined_score <= 1.0

    def test_no_technical_data_gives_neutral_tech(self):
        sig = self.gen.generate("TEST", None, self.news, self.vol)
        assert sig.technical_signal is None

    def test_no_sentiment_data(self):
        sig = self.gen.generate("TEST", self.tech, None, self.vol)
        assert sig.news_sentiment is None

    def test_generate_multiple_keys(self):
        from data_fetcher import DataFetcher
        from technical_analysis import TechnicalAnalyzer
        from volatility_analysis import VolatilityAnalyzer

        data = {"A": make_ohlcv(60), "B": make_ohlcv(60), "C": make_ohlcv(60)}
        tech_sigs = TechnicalAnalyzer().analyze_multiple(data)
        vol_map   = VolatilityAnalyzer().analyze_multiple(data)
        signals   = self.gen.generate_multiple(tech_sigs, self.news, vol_map)
        assert set(signals.keys()) == {"A", "B", "C"}

    def test_reasons_non_empty(self):
        sig = self.gen.generate("TEST", self.tech, self.news, self.vol)
        assert len(sig.reasons) > 0


# ─── logger_reporter ─────────────────────────────────────────────────────────

class TestLoggerReporter:
    def test_setup_logging_idempotent(self):
        from logger_reporter import setup_logging
        import logging
        setup_logging()
        setup_logging()   # second call should not raise
        assert logging.getLogger().handlers  # at least one handler

    def test_log_signal_adds_to_history(self):
        from logger_reporter import TradeReporter, setup_logging
        from signal_generator import SignalGenerator
        from technical_analysis import TechnicalAnalyzer
        from news_sentiment import NewsSentimentAnalyzer
        from volatility_analysis import VolatilityAnalyzer

        setup_logging()
        reporter = TradeReporter()
        df = make_ohlcv(60)
        tech = TechnicalAnalyzer().analyze(df, "TEST")
        news = NewsSentimentAnalyzer().get_sentiment()
        vol  = VolatilityAnalyzer().calculate(df, "TEST")
        sig  = SignalGenerator().generate("TEST", tech, news, vol)

        before = len(reporter.get_signal_history())
        reporter.log_signal(sig)
        after  = len(reporter.get_signal_history())
        assert after == before + 1

    def test_history_bounded(self):
        from logger_reporter import TradeReporter, setup_logging
        from signal_generator import SignalGenerator
        from technical_analysis import TechnicalAnalyzer
        from news_sentiment import NewsSentimentAnalyzer
        from volatility_analysis import VolatilityAnalyzer
        import config

        setup_logging()
        reporter = TradeReporter()
        tech = TechnicalAnalyzer().analyze(make_ohlcv(60), "X")
        news = NewsSentimentAnalyzer().get_sentiment()
        vol  = VolatilityAnalyzer().calculate(make_ohlcv(60), "X")
        sig  = SignalGenerator().generate("X", tech, news, vol)

        for _ in range(config.MAX_SIGNAL_HISTORY + 10):
            reporter.log_signal(sig)
        assert len(reporter.get_signal_history()) <= config.MAX_SIGNAL_HISTORY
