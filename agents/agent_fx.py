"""
SubAgent B: 為替・マクロ指標取得エージェント。
yfinance で通貨ペア・VIX・金・債券・原油などを取得する。
"""
import yfinance as yf
import pandas as pd
import json
import os
import logging
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


def _calc_range_position(series: pd.Series, period: int = 30) -> float:
    """直近N日のレンジ内での現在値の位置（0〜1）を計算"""
    recent = series.tail(period)
    if recent.empty or recent.max() == recent.min():
        return 0.5
    current = float(series.iloc[-1])
    return (current - float(recent.min())) / (float(recent.max()) - float(recent.min()))


def run() -> dict:
    """為替・マクロデータ収集メイン処理"""
    logger.info("SubAgent B: 為替・マクロデータ収集開始")
    result = {"fx": {}, "macro": {}}
    end = datetime.now()
    start = end - timedelta(days=config.DATA_PERIOD_DAYS + 5)

    # 通貨ペア取得
    for symbol, name in config.FX_PAIRS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start, end=end)
            if hist.empty:
                raise ValueError(f"{symbol}: データが空")

            close = hist['Close'].dropna()
            current = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else current

            result["fx"][symbol] = {
                "name": name,
                "close": close,
                "current": current,
                "prev": prev,
                "change_pct": (current - prev) / prev * 100,
                "range_pos_30d": _calc_range_position(close, 30),
            }
        except Exception as e:
            logger.error(f"FX取得失敗 {symbol}: {e}")

    # マクロ指標取得
    for symbol, name in config.MACRO_TICKERS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start, end=end)
            if hist.empty:
                raise ValueError(f"{symbol}: データが空")

            close = hist['Close'].dropna()
            current = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else current

            result["macro"][symbol] = {
                "name": name,
                "close": close,
                "current": current,
                "prev": prev,
                "change_pct": (current - prev) / prev * 100,
            }
        except Exception as e:
            logger.error(f"マクロ指標取得失敗 {symbol}: {e}")

    vix = result["macro"].get("^VIX", {}).get("current", 0)
    logger.info(f"SubAgent B: 完了 — VIX={vix:.1f}")
    return result
