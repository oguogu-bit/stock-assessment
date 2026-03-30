"""
SubAgent G: 感情スコア計算エージェント（Claude CLI使用）。
ニュース記事に感情スコア・影響カテゴリ等の属性を付与する。
"""
import json
import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claude_client import call_claude

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは金融ニュース分析の専門家です。
与えられたニュースリストを分析し、JSONのみで返答してください。
前置きや説明文は一切不要です。"""

USER_PROMPT_TEMPLATE = """以下のニュース記事を分析し、各記事に属性を付与してください。

属性:
- sentiment_score: 市場への影響スコア（-1.0〜+1.0、正=強気、負=弱気）
- impact_category: 以下から1つ選択
  ["金融政策","地政学リスク","企業決算","経済指標","政治動向","為替介入","エネルギー","テクノロジー","その他"]
- affected_markets: 以下から複数選択
  ["日本株","米国株","ドル円","ユーロ円","金","原油","債券"]
- impact_duration: 以下から1つ選択
  ["短期（1日）","中期（1週間）","長期（1ヶ月以上）"]
- confidence: 確信度（0.0〜1.0）

ニュース:
{news_json}

JSONのみ返答: [{{"id":"...","sentiment_score":0.0,"impact_category":"...","affected_markets":[],"impact_duration":"...","confidence":0.0}}]"""


def _fallback_scores(news_list: list) -> list:
    """Claude CLI失敗時のフォールバック（中立スコアを付与）"""
    return [
        {
            "id": art["id"],
            "sentiment_score": 0.0,
            "impact_category": "その他",
            "affected_markets": [],
            "impact_duration": "短期（1日）",
            "confidence": 0.0,
        }
        for art in news_list
    ]


def run(news_list: list) -> list:
    """感情スコア計算メイン処理"""
    logger.info(f"SubAgent G: 感情スコア計算開始 ({len(news_list)}件)")

    if not news_list:
        return []

    # ニュースリストを簡潔な形式に変換
    news_for_prompt = [
        {"id": art["id"], "title": art["title"], "summary": art.get("summary", "")[:200]}
        for art in news_list
    ]

    prompt = USER_PROMPT_TEMPLATE.format(
        news_json=json.dumps(news_for_prompt, ensure_ascii=False, indent=2)
    )

    response = call_claude(prompt, system=SYSTEM_PROMPT)

    if not response:
        logger.warning("Claude CLIからの応答が空でした。フォールバックを使用します。")
        return _fallback_scores(news_list)

    # JSON部分を抽出
    try:
        # レスポンスからJSONアレイを抽出
        start = response.find('[')
        end = response.rfind(']') + 1
        if start == -1 or end == 0:
            raise ValueError("JSONアレイが見つかりません")

        scores = json.loads(response[start:end])

        # 元のニュースリストとマージ
        score_map = {s["id"]: s for s in scores}
        result = []
        for art in news_list:
            merged = {**art}
            if art["id"] in score_map:
                merged.update(score_map[art["id"]])
            else:
                merged.update(_fallback_scores([art])[0])
            result.append(merged)

        logger.info(f"SubAgent G: 完了 — {len(result)}件スコア付与")
        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"JSONパースエラー: {e}。フォールバックを使用します。")
        return _fallback_scores(news_list)
