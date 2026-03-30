"""
SubAgent J: メイン分析エージェント（Claude CLI使用）。
全データを統合してプロの株式・為替アナリスト視点の分析レポートを生成する。
"""
import json
import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claude_client import call_claude

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたはプロの株式・為替アナリストです。
日本市場と米国市場の双方、および為替が株価に与える影響を深く理解しています。
提供されたデータを客観的・多角的に分析し、日本語でレポートを作成してください。

【必須出力フォーマット】
## 市場現状サマリー
## 日本株評価: [強気/弱気/中立] 確信度:[高/中/低]
## 米国株評価: [強気/弱気/中立] 確信度:[高/中/低]
## ドル円方向: [円高/円安/横ばい] 確信度:[高/中/低]
## 主要ニュース解説（上位3件）
## 為替が日本株に与える影響分析
## 今週の注目リスクシナリオ（強気・弱気）
## 注目すべきイベント・指標"""


def _format_news_with_scores(news_with_scores: list) -> str:
    """スコア付きニュースをプロンプト用にフォーマット"""
    lines = []
    sorted_news = sorted(
        news_with_scores,
        key=lambda x: abs(x.get('sentiment_score', 0)),
        reverse=True
    )[:15]

    for art in sorted_news:
        score = art.get('sentiment_score', 0)
        category = art.get('impact_category', '不明')
        markets = ', '.join(art.get('affected_markets', []))
        lines.append(
            f"[{score:+.2f}] [{category}] {art['title']}\n"
            f"  影響市場: {markets} | {art.get('source', '')}"
        )

    return "\n".join(lines) if lines else "ニュースなし"


def _build_prompt(all_results: dict) -> str:
    """分析用プロンプトを構築"""
    stocks = all_results.get("stocks", {})
    fx = all_results.get("fx", {})
    tech = all_results.get("technical", {})
    vix_info = all_results.get("vix_flag", {})
    news_with_scores = all_results.get("sentiment", [])
    pattern_result = all_results.get("pattern_db", {})

    indices = stocks.get("indices", {})
    fx_pairs = fx.get("fx", {})
    macro = fx.get("macro", {})
    tech_indices = tech.get("indices", {})
    tech_fx = tech.get("fx", {})
    correlations = tech.get("correlations", {})

    nikkei = indices.get("^N225", {})
    topix = indices.get("^TOPX", {})
    sp500 = indices.get("^GSPC", {})
    nasdaq = indices.get("^IXIC", {})
    dow = indices.get("^DJI", {})

    nikkei_tech = tech_indices.get("^N225", {})
    sp500_tech = tech_indices.get("^GSPC", {})
    usdjpy_tech = tech_fx.get("USDJPY=X", {})

    usdjpy = fx_pairs.get("USDJPY=X", {})
    eurjpy = fx_pairs.get("EURJPY=X", {})
    gbpjpy = fx_pairs.get("GBPJPY=X", {})
    audjpy = fx_pairs.get("AUDJPY=X", {})

    vix = macro.get("^VIX", {})
    dxy = macro.get("DX-Y.NYB", {})
    gold = macro.get("GC=F", {})
    tnx = macro.get("^TNX", {})
    wti = macro.get("CL=F", {})

    macd_nikkei = nikkei_tech.get("macd", {})
    macd_str = (
        f"MACD: {macd_nikkei.get('macd', 0):+.2f} / "
        f"シグナル: {macd_nikkei.get('signal', 0):+.2f}"
    )

    # 52週レンジ内位置の安全な計算
    nikkei_cur = nikkei.get('current_close', 0)
    nikkei_low = nikkei.get('week_low_52', 0)
    nikkei_high = nikkei.get('week_high_52', 1)
    nikkei_range = max(nikkei_high - nikkei_low, 1)
    nikkei_range_pct = (nikkei_cur - nikkei_low) / nikkei_range * 100

    prompt = f"""━━ 市場環境 ━━
{vix_info.get('context_text', '')}

━━ 日本株 ━━
日経225: {nikkei.get('current_close', 0):,.0f}円 前日比{nikkei.get('change_pct', 0):+.2f}%
TOPIX: {topix.get('current_close', 0):,.1f} 前日比{topix.get('change_pct', 0):+.2f}%
RSI: {nikkei_tech.get('rsi', 50):.1f} / {macd_str} / 20MA乖離: {nikkei_tech.get('ma20_dev', 0):+.2f}%
52週レンジ内位置: {nikkei_range_pct:.0f}%

━━ 米国株 ━━
S&P500: {sp500.get('current_close', 0):,.2f} 前日比{sp500.get('change_pct', 0):+.2f}%
NASDAQ: {nasdaq.get('current_close', 0):,.2f} 前日比{nasdaq.get('change_pct', 0):+.2f}%
DOW: {dow.get('current_close', 0):,.0f} 前日比{dow.get('change_pct', 0):+.2f}%
RSI(S&P): {sp500_tech.get('rsi', 50):.1f} / 20MA乖離: {sp500_tech.get('ma20_dev', 0):+.2f}%

━━ 為替 ━━
USD/JPY: {usdjpy.get('current', 0):.2f} 前日比{usdjpy.get('change_pct', 0):+.2f}%
EUR/JPY: {eurjpy.get('current', 0):.2f} 前日比{eurjpy.get('change_pct', 0):+.2f}%
GBP/JPY: {gbpjpy.get('current', 0):.2f} 前日比{gbpjpy.get('change_pct', 0):+.2f}%
AUD/JPY: {audjpy.get('current', 0):.2f} 前日比{audjpy.get('change_pct', 0):+.2f}%
USD/JPY RSI: {usdjpy_tech.get('rsi', 50):.1f} / 20MA乖離: {usdjpy_tech.get('ma20_dev', 0):+.2f}%

━━ マクロ指標 ━━
VIX: {vix.get('current', 0):.1f} / DXY: {dxy.get('current', 0):.2f} / 金: ${gold.get('current', 0):,.0f} / WTI: ${wti.get('current', 0):.2f} / 米10年債: {tnx.get('current', 0):.2f}%

━━ 相関分析（過去30日）━━
USD/JPY↑時の日経平均変化: {correlations.get('fx_nikkei', 0):+.2f}
S&P500↑時のUSD/JPY変化: {correlations.get('sp_fx', 0):+.2f}
VIX↑時のUSD/JPY変化: {correlations.get('vix_fx', 0):+.2f}

━━ 本日のニュース（感情スコア付き）━━
{_format_news_with_scores(news_with_scores)}

━━ 過去の類似パターン ━━
{pattern_result.get('few_shot_text', '（パターンDB未蓄積）')}
"""
    return prompt


def run(all_results: dict) -> str:
    """メイン分析実行"""
    logger.info("SubAgent J: メイン分析開始（Claude CLI呼び出し）")

    prompt = _build_prompt(all_results)
    analysis = call_claude(prompt, system=SYSTEM_PROMPT)

    if not analysis:
        logger.error("Claude CLIからの分析結果が空でした")
        analysis = "## 市場現状サマリー\nデータ取得・分析中にエラーが発生しました。"

    logger.info("SubAgent J: 分析完了")
    return analysis
