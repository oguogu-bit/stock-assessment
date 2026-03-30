"""
SubAgent A: 日米株価取得エージェント。
yfinance で日米の主要株価指数・個別銘柄データを取得する。
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


def _load_cache(ticker: str) -> dict | None:
    """前日キャッシュからデータを読み込む"""
    cache_dir = config.CACHE_DIR
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    cache_path = os.path.join(cache_dir, f"stocks_{yesterday}.json")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if ticker in cache:
                logger.info(f"キャッシュからデータ読み込み: {ticker}")
                return cache[ticker]
        except Exception as e:
            logger.warning(f"キャッシュ読み込みエラー: {e}")
    return None


def _save_cache(data: dict) -> None:
    """当日データをキャッシュに保存"""
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    cache_path = os.path.join(config.CACHE_DIR, f"stocks_{today}.json")

    # DataFrameをJSONシリアライズ可能な形式に変換
    serializable = {}
    for ticker, info in data.items():
        serializable[ticker] = {
            k: (v.to_dict() if isinstance(v, pd.Series) else v)
            for k, v in info.items()
        }

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"キャッシュ保存エラー: {e}")


def _fetch_ticker(symbol: str, name: str) -> dict:
    """単一銘柄のデータを取得"""
    try:
        ticker = yf.Ticker(symbol)
        end = datetime.now()
        start = end - timedelta(days=config.DATA_PERIOD_DAYS + 5)
        hist = ticker.history(start=start, end=end)

        if hist.empty:
            raise ValueError(f"{symbol}: データが空です")

        close_series = hist['Close'].dropna()
        current_close = float(close_series.iloc[-1])
        prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else current_close
        change_pct = (current_close - prev_close) / prev_close * 100

        # 52週高値・安値
        info = ticker.info
        week_high_52 = info.get('fiftyTwoWeekHigh', float(close_series.max()))
        week_low_52 = info.get('fiftyTwoWeekLow', float(close_series.min()))

        return {
            "name": name,
            "close": close_series,
            "high": hist['High'].dropna(),
            "low": hist['Low'].dropna(),
            "open": hist['Open'].dropna(),
            "volume": hist['Volume'].dropna(),
            "current_close": current_close,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "week_high_52": float(week_high_52),
            "week_low_52": float(week_low_52),
        }
    except Exception as e:
        logger.error(f"{symbol} データ取得失敗: {e}")
        # キャッシュにフォールバック
        cached = _load_cache(symbol)
        if cached:
            return cached
        raise


def run() -> dict:
    """株価データ収集メイン処理"""
    logger.info("SubAgent A: 株価データ収集開始")
    result = {"indices": {}, "jp_stocks": {}, "us_stocks": {}}

    # 日本株指数
    for symbol, name in config.JP_INDICES.items():
        try:
            result["indices"][symbol] = _fetch_ticker(symbol, name)
        except Exception as e:
            logger.error(f"指数取得失敗 {symbol}: {e}")

    # 米国株指数
    for symbol, name in config.US_INDICES.items():
        try:
            result["indices"][symbol] = _fetch_ticker(symbol, name)
        except Exception as e:
            logger.error(f"指数取得失敗 {symbol}: {e}")

    # 日本個別銘柄
    for symbol, name in config.JP_STOCKS.items():
        try:
            result["jp_stocks"][symbol] = _fetch_ticker(symbol, name)
        except Exception as e:
            logger.error(f"銘柄取得失敗 {symbol}: {e}")

    # 米国個別銘柄
    for symbol, name in config.US_STOCKS.items():
        try:
            result["us_stocks"][symbol] = _fetch_ticker(symbol, name)
        except Exception as e:
            logger.error(f"銘柄取得失敗 {symbol}: {e}")

    _save_cache({**result["indices"], **result["jp_stocks"], **result["us_stocks"]})
    logger.info(
        f"SubAgent A: 完了 — 指数{len(result['indices'])}件, "
        f"JP銘柄{len(result['jp_stocks'])}件, US銘柄{len(result['us_stocks'])}件"
    )
    return result
