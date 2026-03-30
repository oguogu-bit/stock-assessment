"""
SubAgent H: パターンDB管理エージェント。
news_patterns.csv の更新・参照・Few-shot例生成を担当する。
"""
import pandas as pd
import csv
import os
import logging
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "date", "news_headline", "impact_category", "sentiment_score",
    "nikkei_1d_change_pct", "sp500_1d_change_pct", "usdjpy_1d_change_pct",
    "vix_level", "predicted_direction", "actual_direction", "accuracy_label"
]


def _ensure_csv() -> pd.DataFrame:
    """CSVファイルが存在しない場合はヘッダーのみの空CSVを作成"""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.PATTERNS_CSV):
        logger.info(f"パターンDB新規作成: {config.PATTERNS_CSV}")
        df = pd.DataFrame(columns=CSV_COLUMNS)
        df.to_csv(config.PATTERNS_CSV, index=False, encoding='utf-8-sig')

    try:
        return pd.read_csv(config.PATTERNS_CSV, encoding='utf-8-sig')
    except Exception as e:
        logger.error(f"パターンDB読み込みエラー: {e}")
        return pd.DataFrame(columns=CSV_COLUMNS)


def _update_accuracy(df: pd.DataFrame, stocks_data: dict, fx_data: dict) -> pd.DataFrame:
    """前日の予測と当日実績を照合してaccuracy_labelを更新"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    mask = (df['date'] == yesterday) & (df['accuracy_label'].isna() | (df['accuracy_label'] == ''))

    if not mask.any():
        return df

    # 当日の実際の変動を取得
    nikkei_chg = stocks_data.get("indices", {}).get("^N225", {}).get("change_pct", 0)

    for idx in df[mask].index:
        predicted = df.at[idx, 'predicted_direction']
        actual_direction = "上昇" if nikkei_chg > 0.3 else ("下落" if nikkei_chg < -0.3 else "横ばい")
        df.at[idx, 'actual_direction'] = actual_direction
        df.at[idx, 'nikkei_1d_change_pct'] = nikkei_chg

        if predicted == actual_direction:
            df.at[idx, 'accuracy_label'] = "的中"
        else:
            df.at[idx, 'accuracy_label'] = "外れ"

    return df


def _register_today(df: pd.DataFrame, news_with_scores: list, stocks_data: dict, fx_data: dict, vix: float) -> pd.DataFrame:
    """当日のニュース（スコア上位10件）を仮登録"""
    today = datetime.now().strftime("%Y-%m-%d")

    # スコアでソートして上位10件
    sorted_news = sorted(
        [n for n in news_with_scores if "sentiment_score" in n],
        key=lambda x: abs(x.get("sentiment_score", 0)),
        reverse=True
    )[:10]

    nikkei_chg = stocks_data.get("indices", {}).get("^N225", {}).get("change_pct", 0)
    sp500_chg = stocks_data.get("indices", {}).get("^GSPC", {}).get("change_pct", 0)
    usdjpy_chg = fx_data.get("fx", {}).get("USDJPY=X", {}).get("change_pct", 0)

    predicted = "上昇" if nikkei_chg > 0 else ("下落" if nikkei_chg < 0 else "横ばい")

    new_rows = []
    for news in sorted_news:
        # 同日・同ヘッドラインの重複チェック
        exists = (
            (df['date'] == today) &
            (df['news_headline'] == news['title'][:100])
        ).any() if not df.empty else False

        if not exists:
            new_rows.append({
                "date": today,
                "news_headline": news['title'][:100],
                "impact_category": news.get('impact_category', 'その他'),
                "sentiment_score": news.get('sentiment_score', 0.0),
                "nikkei_1d_change_pct": None,  # 翌日に更新
                "sp500_1d_change_pct": sp500_chg,
                "usdjpy_1d_change_pct": usdjpy_chg,
                "vix_level": vix,
                "predicted_direction": predicted,
                "actual_direction": None,
                "accuracy_label": None,
            })

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        df = pd.concat([df, new_df], ignore_index=True)

    return df


def _get_similar_patterns(df: pd.DataFrame, impact_categories: list) -> list:
    """類似カテゴリの過去パターンを取得（的中優先）"""
    if df.empty or not impact_categories:
        return []

    # カテゴリでフィルタ
    mask = df['impact_category'].isin(impact_categories)
    similar = df[mask].copy()

    if similar.empty:
        return []

    # 的中で高信頼度のものを優先
    hits = similar[
        (similar['accuracy_label'] == '的中') &
        (similar['sentiment_score'].abs() >= 0.5)
    ].tail(5)

    if len(hits) < 5:
        others = similar[similar['accuracy_label'] != '的中'].tail(5 - len(hits))
        hits = pd.concat([hits, others])

    return hits.tail(5).to_dict('records')


def _format_few_shot(patterns: list) -> str:
    """Few-shot例テキストを生成"""
    if not patterns:
        return "（過去の類似パターンはまだ蓄積されていません）"

    lines = ["【過去の類似パターン】"]
    for i, p in enumerate(patterns, 1):
        nikkei = p.get('nikkei_1d_change_pct')
        usdjpy = p.get('usdjpy_1d_change_pct')
        nikkei_str = f"{nikkei:+.2f}%" if nikkei is not None else "未確定"
        usdjpy_str = f"{usdjpy:+.2f}%" if usdjpy is not None else "未確定"
        label = p.get('accuracy_label', '未確定')

        lines.append(
            f"例{i}: {p.get('date', '?')} | {p.get('news_headline', '')}\n"
            f"     感情スコア: {p.get('sentiment_score', 0):+.2f} | "
            f"翌日変動: 日経{nikkei_str} USD/JPY{usdjpy_str}\n"
            f"     結果: {label}"
        )

    return "\n".join(lines)


def run(all_results: dict) -> dict:
    """パターンDB管理メイン処理"""
    logger.info("SubAgent H: パターンDB管理開始")

    stocks_data = all_results.get("stocks", {})
    fx_data = all_results.get("fx", {})
    news_with_scores = all_results.get("sentiment", [])
    vix = fx_data.get("macro", {}).get("^VIX", {}).get("current", 20.0)

    df = _ensure_csv()

    # 前日予測の精度更新
    df = _update_accuracy(df, stocks_data, fx_data)

    # 当日ニュース仮登録
    df = _register_today(df, news_with_scores, stocks_data, fx_data, vix)

    # CSV保存
    try:
        df.to_csv(config.PATTERNS_CSV, index=False, encoding='utf-8-sig')
        logger.info(f"パターンDB保存完了: {len(df)}レコード")
    except Exception as e:
        logger.error(f"パターンDB保存エラー: {e}")

    # 類似パターン抽出
    current_categories = list(set(
        n.get('impact_category', 'その他')
        for n in news_with_scores
        if n.get('confidence', 0) >= 0.5
    ))

    similar_patterns = _get_similar_patterns(df, current_categories)
    few_shot_text = _format_few_shot(similar_patterns)

    logger.info(f"SubAgent H: 完了 — {len(similar_patterns)}件の類似パターン抽出")
    return {
        "few_shot_text": few_shot_text,
        "similar_count": len(similar_patterns),
        "total_records": len(df),
    }
