"""
システム設定ファイル。銘柄・通貨ペア・RSSリストなどをカスタマイズ可能。
"""

# 日本株指数
JP_INDICES = {
    "^N225": "日経225",
    "^TOPX": "TOPIX",
}

# 米国株指数
US_INDICES = {
    "^GSPC": "S&P500",
    "^IXIC": "NASDAQ",
    "^DJI": "DOW",
    "^RUT": "Russell2000",
}

# 日本個別銘柄（デフォルト）
JP_STOCKS = {
    "7203.T": "トヨタ",
    "6758.T": "ソニー",
    "7974.T": "任天堂",
}

# 米国個別銘柄（デフォルト）
US_STOCKS = {
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "MSFT": "Microsoft",
}

# 通貨ペア
FX_PAIRS = {
    "USDJPY=X": "USD/JPY",
    "EURJPY=X": "EUR/JPY",
    "GBPJPY=X": "GBP/JPY",
    "AUDJPY=X": "AUD/JPY",
    "EURUSD=X": "EUR/USD",
}

# マクロ指標
MACRO_TICKERS = {
    "^VIX": "VIX",
    "DX-Y.NYB": "DXY",
    "GC=F": "Gold",
    "^TNX": "US10Y",
    "CL=F": "WTI",
}

# RSSフィード
RSS_FEEDS = [
    {"url": "https://www.nhk.or.jp/rss/news/cat4.xml", "source": "NHK経済"},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters"},
    {"url": "https://feeds.apnews.com/rss/business", "source": "AP Business"},
]

# NewsAPIキーワード
NEWS_KEYWORDS = "Fed,日銀,金利,地政学,貿易摩擦,決算,インフレ,雇用統計"

# データ取得期間（日）
DATA_PERIOD_DAYS = 60

# テクニカル指標設定
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
MA_SHORT = 20
MA_LONG = 60

# ディレクトリ設定
DATA_DIR = "data"
CACHE_DIR = "data/cache"
REPORTS_DIR = "reports"
LOGS_DIR = "logs"
PATTERNS_CSV = "data/news_patterns.csv"
