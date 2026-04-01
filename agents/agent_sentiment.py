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
    """Claude CLI失敗時のフォールバック（キーワードベースでスコアを付与）"""
    POS = ['好調', '上昇', '増益', '好決算', '利下げ', '回復', '改善', '反発',
           '買い', '強気', '最高', '最大', '突破', 'AI需要', '半導体好調']
    NEG = ['下落', '減益', 'リスク', '懸念', '警戒', '悪化', '売り', '弱気',
           '制裁', '規制', '紛争', '戦争', '利上げ', '景気後退', 'インフレ']
    CAT_MAP = [
        (['日銀', 'Fed', '金利', '利上げ', '利下げ', '金融政策'], '金融政策'),
        (['決算', '売上', '利益', '増収', '減収', 'EPS'], '企業決算'),
        (['GDP', 'CPI', '雇用', '物価', '景気', '貿易'], '経済指標'),
        (['戦争', '紛争', '制裁', '地政学', '外交', '安保'], '地政学リスク'),
        (['介入', '為替', '円安', '円高', 'ドル', 'FX'], '為替介入'),
        (['AI', '半導体', 'NVIDIA', 'テクノロジー', '生成AI'], 'テクノロジー'),
        (['原油', 'エネルギー', 'OPEC', '天然ガス'], 'エネルギー'),
    ]

    results = []
    for art in news_list:
        text = (art.get('title', '') + ' ' + art.get('summary', ''))
        score = sum(0.25 for kw in POS if kw in text) - sum(0.25 for kw in NEG if kw in text)
        score = max(-1.0, min(1.0, score))

        category = 'その他'
        for keywords, cat in CAT_MAP:
            if any(kw in text for kw in keywords):
                category = cat
                break

        markets = []
        if any(kw in text for kw in ['日経', '東証', 'TOPIX', '日本株']): markets.append('日本株')
        if any(kw in text for kw in ['S&P', 'NASDAQ', 'NYSE', '米国株']): markets.append('米国株')
        if any(kw in text for kw in ['ドル', '円', '為替', 'USD', 'JPY']): markets.append('ドル円')
        if any(kw in text for kw in ['金', 'ゴールド', 'Gold']): markets.append('金')
        if not markets: markets = ['日本株', '米国株']

        results.append({
            **art,
            'sentiment_score': round(score, 2),
            'impact_category': category,
            'affected_markets': markets,
            'impact_duration': '短期（1日）',
            'confidence': 0.4,
        })
    return results


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
