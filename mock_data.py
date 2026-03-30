"""
--mock フラグ時に使用するモックデータ。
APIキーなしでシステム全体の動作確認が可能。
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_price_series(start: float, n: int = 60, volatility: float = 0.01) -> pd.Series:
    """ランダムウォークで価格系列を生成"""
    np.random.seed(42)
    returns = np.random.normal(0, volatility, n)
    prices = start * np.cumprod(1 + returns)
    dates = [datetime.now() - timedelta(days=n - i) for i in range(n)]
    return pd.Series(prices, index=pd.DatetimeIndex(dates))


def get_mock_stocks() -> dict:
    """モック株価データ"""
    return {
        "indices": {
            "^N225": {
                "name": "日経225",
                "close": generate_price_series(38000, volatility=0.012),
                "high": generate_price_series(38500, volatility=0.012),
                "low": generate_price_series(37500, volatility=0.012),
                "open": generate_price_series(38100, volatility=0.012),
                "volume": pd.Series(np.random.randint(int(1e8), int(1e9), 60)),
                "current_close": 38250.0,
                "prev_close": 38100.0,
                "change_pct": 0.39,
                "week_high_52": 41000.0,
                "week_low_52": 30500.0,
            },
            "^TOPX": {
                "name": "TOPIX",
                "close": generate_price_series(2700, volatility=0.010),
                "current_close": 2712.5,
                "prev_close": 2698.0,
                "change_pct": 0.54,
                "week_high_52": 2944.0,
                "week_low_52": 2150.0,
            },
            "^GSPC": {
                "name": "S&P500",
                "close": generate_price_series(5100, volatility=0.011),
                "current_close": 5234.2,
                "prev_close": 5180.6,
                "change_pct": 1.03,
                "week_high_52": 5667.0,
                "week_low_52": 4100.0,
            },
            "^IXIC": {
                "name": "NASDAQ",
                "close": generate_price_series(16000, volatility=0.014),
                "current_close": 16440.5,
                "prev_close": 16200.0,
                "change_pct": 1.48,
                "week_high_52": 18671.0,
                "week_low_52": 12500.0,
            },
            "^DJI": {
                "name": "DOW",
                "close": generate_price_series(39000, volatility=0.009),
                "current_close": 39800.0,
                "prev_close": 39600.0,
                "change_pct": 0.51,
                "week_high_52": 42000.0,
                "week_low_52": 32500.0,
            },
            "^RUT": {
                "name": "Russell2000",
                "close": generate_price_series(2050, volatility=0.013),
                "current_close": 2089.3,
                "prev_close": 2070.0,
                "change_pct": 0.93,
                "week_high_52": 2442.0,
                "week_low_52": 1700.0,
            },
        },
        "jp_stocks": {
            "7203.T": {"name": "トヨタ", "current_close": 3250.0, "change_pct": 0.62},
            "6758.T": {"name": "ソニー", "current_close": 12800.0, "change_pct": 1.15},
            "7974.T": {"name": "任天堂", "current_close": 7900.0, "change_pct": -0.25},
        },
        "us_stocks": {
            "AAPL": {"name": "Apple", "current_close": 215.3, "change_pct": 0.82},
            "NVDA": {"name": "NVIDIA", "current_close": 875.0, "change_pct": 2.14},
            "MSFT": {"name": "Microsoft", "current_close": 430.5, "change_pct": 0.55},
        },
    }


def get_mock_fx() -> dict:
    """モック為替・マクロデータ"""
    return {
        "fx": {
            "USDJPY=X": {
                "name": "USD/JPY",
                "close": generate_price_series(149.5, volatility=0.004),
                "current": 150.25,
                "prev": 149.80,
                "change_pct": 0.30,
                "range_pos_30d": 0.65,
            },
            "EURJPY=X": {
                "name": "EUR/JPY",
                "close": generate_price_series(162.0, volatility=0.004),
                "current": 162.85,
                "prev": 162.30,
                "change_pct": 0.34,
                "range_pos_30d": 0.58,
            },
            "GBPJPY=X": {
                "name": "GBP/JPY",
                "close": generate_price_series(190.0, volatility=0.005),
                "current": 190.45,
                "prev": 189.90,
                "change_pct": 0.29,
                "range_pos_30d": 0.62,
            },
            "AUDJPY=X": {
                "name": "AUD/JPY",
                "close": generate_price_series(98.5, volatility=0.006),
                "current": 98.75,
                "prev": 98.20,
                "change_pct": 0.56,
                "range_pos_30d": 0.48,
            },
            "EURUSD=X": {
                "name": "EUR/USD",
                "close": generate_price_series(1.085, volatility=0.003),
                "current": 1.0836,
                "prev": 1.0825,
                "change_pct": 0.10,
                "range_pos_30d": 0.42,
            },
        },
        "macro": {
            "^VIX": {"name": "VIX", "current": 18.5, "prev": 19.2, "change_pct": -3.65,
                     "close": generate_price_series(18.5, volatility=0.03)},
            "DX-Y.NYB": {"name": "DXY", "current": 104.25, "prev": 104.10, "change_pct": 0.14,
                         "close": generate_price_series(104.25, volatility=0.003)},
            "GC=F": {"name": "Gold", "current": 2042.0, "prev": 2030.0, "change_pct": 0.59,
                     "close": generate_price_series(2042.0, volatility=0.008)},
            "^TNX": {"name": "US10Y", "current": 4.32, "prev": 4.28, "change_pct": 0.93,
                     "close": generate_price_series(4.32, volatility=0.01)},
            "CL=F": {"name": "WTI", "current": 78.45, "prev": 77.90, "change_pct": 0.71,
                     "close": generate_price_series(78.45, volatility=0.012)},
        },
    }


def get_mock_news() -> list:
    """モックニュースデータ"""
    return [
        {
            "id": "news_001",
            "title": "Fed議長、利下げは慎重に進める方針を示唆",
            "summary": "パウエルFRB議長は本日の議会証言で、インフレ目標達成までは金利を高水準に維持する可能性を示唆した。市場では年内の利下げ回数見通しが後退している。",
            "url": "https://example.com/fed-rate-cut",
            "published": "2026-03-30T10:00:00Z",
            "source": "Reuters",
        },
        {
            "id": "news_002",
            "title": "日銀、追加利上げを検討か — 植田総裁発言に注目",
            "summary": "日本銀行の植田総裁が次回の政策決定会合での追加利上げの可能性を示唆したと報じられ、円高・日本株安の展開となった。",
            "url": "https://example.com/boj-rate",
            "published": "2026-03-30T09:30:00Z",
            "source": "NHK経済",
        },
        {
            "id": "news_003",
            "title": "NVIDIA、AI需要好調で四半期最高売上を更新",
            "summary": "NVIDIAが発表した第4四半期決算は、AIチップ需要の拡大を背景に売上高が過去最高を更新。株価は時間外取引で5%超の上昇となった。",
            "url": "https://example.com/nvidia-earnings",
            "published": "2026-03-30T08:00:00Z",
            "source": "AP Business",
        },
        {
            "id": "news_004",
            "title": "米中貿易摩擦、半導体規制をめぐり再燃の兆し",
            "summary": "米商務省が中国向け半導体輸出規制を強化する新たな規則を検討していると報じられ、テクノロジーセクターに警戒感が広がっている。",
            "url": "https://example.com/us-china-trade",
            "published": "2026-03-30T07:00:00Z",
            "source": "Reuters",
        },
        {
            "id": "news_005",
            "title": "米2月雇用統計、予想を上回る強い結果",
            "summary": "2月の米非農業部門雇用者数は前月比30万人増と市場予想の20万人を大幅に上回り、労働市場の底堅さが確認された。ドル高・円安が進行。",
            "url": "https://example.com/jobs-report",
            "published": "2026-03-30T06:30:00Z",
            "source": "AP Business",
        },
    ]
