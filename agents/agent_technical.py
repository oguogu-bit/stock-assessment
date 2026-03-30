"""
SubAgent E: テクニカル指標計算エージェント。
RSI、MACD、移動平均、ボリンジャーバンド、相関係数を計算する。
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    """RSIを計算して最新値を返す"""
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def _calc_macd(series: pd.Series, fast=12, slow=26, signal=9) -> dict:
    """MACDを計算"""
    if len(series) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
    }


def _calc_bb(series: pd.Series, period=20, std=2) -> dict:
    """ボリンジャーバンドを計算"""
    if len(series) < period:
        return {"upper": 0.0, "middle": 0.0, "lower": 0.0, "position": 0.5}
    ma = series.rolling(period).mean()
    std_dev = series.rolling(period).std()
    upper = ma + std * std_dev
    lower = ma - std * std_dev
    current = float(series.iloc[-1])
    u = float(upper.iloc[-1])
    l = float(lower.iloc[-1])
    position = (current - l) / (u - l) if u != l else 0.5
    return {
        "upper": u,
        "middle": float(ma.iloc[-1]),
        "lower": l,
        "position": max(0.0, min(1.0, position)),
        "series_upper": upper,
        "series_middle": ma,
        "series_lower": lower,
    }


def _calc_ma_deviation(series: pd.Series, period: int) -> float:
    """移動平均乖離率（%）を計算"""
    if len(series) < period:
        return 0.0
    ma = float(series.rolling(period).mean().iloc[-1])
    current = float(series.iloc[-1])
    return (current - ma) / ma * 100 if ma != 0 else 0.0


def _calc_correlation(s1: pd.Series, s2: pd.Series, period: int = 30) -> float:
    """過去N日の相関係数を計算"""
    try:
        s1_ret = s1.tail(period).pct_change().dropna()
        s2_ret = s2.tail(period).pct_change().dropna()
        min_len = min(len(s1_ret), len(s2_ret))
        if min_len < 5:
            return 0.0
        return float(s1_ret.tail(min_len).corr(s2_ret.tail(min_len)))
    except Exception:
        return 0.0


def run(stocks_data: dict, fx_data: dict) -> dict:
    """テクニカル指標計算メイン処理"""
    logger.info("SubAgent E: テクニカル指標計算開始")
    result = {"indices": {}, "fx": {}, "correlations": {}}

    # 株価指数のテクニカル指標
    for symbol, data in stocks_data.get("indices", {}).items():
        close = data.get("close")
        if close is None or not isinstance(close, pd.Series) or close.empty:
            continue

        result["indices"][symbol] = {
            "rsi": _calc_rsi(close),
            "macd": _calc_macd(close),
            "bb": _calc_bb(close),
            "ma20": float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else 0.0,
            "ma60": float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else 0.0,
            "ma20_dev": _calc_ma_deviation(close, 20),
            "ma60_dev": _calc_ma_deviation(close, 60),
        }

    # 為替のテクニカル指標
    for symbol, data in fx_data.get("fx", {}).items():
        close = data.get("close")
        if close is None or not isinstance(close, pd.Series) or close.empty:
            continue

        result["fx"][symbol] = {
            "rsi": _calc_rsi(close),
            "macd": _calc_macd(close),
            "bb": _calc_bb(close),
            "ma20": float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else 0.0,
            "ma20_dev": _calc_ma_deviation(close, 20),
        }

    # 相関係数計算
    nikkei_close = stocks_data.get("indices", {}).get("^N225", {}).get("close")
    sp500_close = stocks_data.get("indices", {}).get("^GSPC", {}).get("close")
    usdjpy_close = fx_data.get("fx", {}).get("USDJPY=X", {}).get("close")
    vix_close = fx_data.get("macro", {}).get("^VIX", {}).get("close")

    if nikkei_close is not None and usdjpy_close is not None:
        result["correlations"]["fx_nikkei"] = _calc_correlation(usdjpy_close, nikkei_close)

    if sp500_close is not None and usdjpy_close is not None:
        result["correlations"]["sp_fx"] = _calc_correlation(sp500_close, usdjpy_close)

    if vix_close is not None and usdjpy_close is not None:
        result["correlations"]["vix_fx"] = _calc_correlation(vix_close, usdjpy_close)

    logger.info("SubAgent E: 完了")
    return result
