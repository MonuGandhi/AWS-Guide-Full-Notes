"""
Configuration settings for BankNifty Trading Bot.
Set your API keys and preferences here.
"""

# ─── Zerodha KiteConnect Credentials ────────────────────────────────────────
ZERODHA_API_KEY = "your_api_key_here"
ZERODHA_API_SECRET = "your_api_secret_here"
ZERODHA_ACCESS_TOKEN = "your_access_token_here"  # Generated after login

# ─── NewsAPI Credentials ─────────────────────────────────────────────────────
NEWS_API_KEY = "your_newsapi_key_here"

# ─── BankNifty Index Symbol (NSE) ────────────────────────────────────────────
BANKNIFTY_SYMBOL = "NIFTY BANK"
BANKNIFTY_EXCHANGE = "NSE"
BANKNIFTY_INSTRUMENT_TOKEN = 260105  # Standard token for NIFTY BANK index

# ─── Banking Sector Stocks to Monitor ────────────────────────────────────────
BANKING_STOCKS = [
    {"symbol": "HDFCBANK",  "exchange": "NSE", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "exchange": "NSE", "name": "ICICI Bank"},
    {"symbol": "KOTAKBANK", "exchange": "NSE", "name": "Kotak Mahindra Bank"},
    {"symbol": "AXISBANK",  "exchange": "NSE", "name": "Axis Bank"},
    {"symbol": "SBIN",      "exchange": "NSE", "name": "State Bank of India"},
    {"symbol": "BANKBARODA","exchange": "NSE", "name": "Bank of Baroda"},
    {"symbol": "PNB",       "exchange": "NSE", "name": "Punjab National Bank"},
    {"symbol": "INDUSINDBK","exchange": "NSE", "name": "IndusInd Bank"},
    {"symbol": "FEDERALBNK","exchange": "NSE", "name": "Federal Bank"},
    {"symbol": "IDFCFIRSTB","exchange": "NSE", "name": "IDFC First Bank"},
    {"symbol": "BANDHANBNK","exchange": "NSE", "name": "Bandhan Bank"},
    {"symbol": "AUBANK",    "exchange": "NSE", "name": "AU Small Finance Bank"},
]

# ─── Technical Indicator Settings ────────────────────────────────────────────
# Moving Averages
SHORT_MA_PERIOD = 9
LONG_MA_PERIOD = 21
EMA_SHORT = 12
EMA_LONG = 26
SIGNAL_LINE = 9

# RSI settings
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# MACD settings
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Bollinger Bands
BB_PERIOD = 20
BB_STD_DEV = 2

# Minimum candles needed for analysis
MIN_CANDLES_REQUIRED = 50

# ─── Signal Thresholds ───────────────────────────────────────────────────────
# Signal strength thresholds (0.0 - 1.0)
STRONG_SIGNAL_THRESHOLD = 0.70
MODERATE_SIGNAL_THRESHOLD = 0.50
WEAK_SIGNAL_THRESHOLD = 0.30

# Confidence score weights (must sum to 1.0)
TECHNICAL_WEIGHT = 0.50
NEWS_SENTIMENT_WEIGHT = 0.30
VOLATILITY_WEIGHT = 0.20

# ─── News Fetching Settings ───────────────────────────────────────────────────
NEWS_FETCH_INTERVAL_MINUTES = 15     # How often to refresh news
NEWS_MAX_ARTICLES = 20               # Max articles to fetch per query
NEWS_LOOKBACK_HOURS = 6              # Look back period for news relevance
NEWS_LANGUAGE = "en"
NEWS_QUERIES = [
    "BankNifty",
    "India banking sector",
    "RBI monetary policy",
    "HDFC ICICI Kotak Axis SBI bank results",
    "Indian bank stocks",
    "NPA banking India",
]

# ─── Volatility Settings ──────────────────────────────────────────────────────
VOLATILITY_WINDOW = 20          # Days for historical volatility calculation
HIGH_VOLATILITY_THRESHOLD = 0.03    # 3 % daily volatility → high
LOW_VOLATILITY_THRESHOLD = 0.01     # 1 % daily volatility → low

# ─── Data Fetch Intervals ────────────────────────────────────────────────────
MARKET_DATA_INTERVAL_SECONDS = 60   # Real-time data refresh (seconds)
HISTORICAL_DATA_DAYS = 60           # Days of historical OHLCV to fetch
CANDLE_INTERVAL = "day"             # "minute", "3minute", "5minute", "15minute", "30minute", "60minute", "day"

# ─── Market Hours (IST) ──────────────────────────────────────────────────────
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# ─── Logging Settings ────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE = "logs/banknifty_bot.log"
TRADE_LOG_FILE = "logs/trade_signals.log"
LOG_MAX_BYTES = 10 * 1024 * 1024    # 10 MB
LOG_BACKUP_COUNT = 5

# ─── Dashboard Settings ──────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS = 30
SHOW_VOLATILITY_HEATMAP = True
SHOW_NEWS_TRACKER = True
SHOW_SIGNAL_HISTORY = True
MAX_SIGNAL_HISTORY = 50             # Keep last N signals in history

# ─── Demo / Simulation Mode ──────────────────────────────────────────────────
DEMO_MODE = True   # Set to False for live trading signals using real API data
