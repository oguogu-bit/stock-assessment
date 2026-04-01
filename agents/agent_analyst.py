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


def _template_analysis(all_results: dict) -> str:
    """Claude CLI不使用のテンプレートベース分析（GitHub Actions用フォールバック）"""
    stocks  = all_results.get("stocks", {})
    fx      = all_results.get("fx", {})
    tech    = all_results.get("technical", {})
    vix_inf = all_results.get("vix_flag", {})
    news    = all_results.get("sentiment", [])

    idx   = stocks.get("indices", {})
    nikkei = idx.get("^N225", {});  topix  = idx.get("^TOPX", {})
    sp500  = idx.get("^GSPC", {});  nasdaq = idx.get("^IXIC", {})
    dow    = idx.get("^DJI",  {})

    fp     = fx.get("fx", {});   macro  = fx.get("macro", {})
    usdjpy = fp.get("USDJPY=X", {})
    gold   = macro.get("GC=F",  {});  tnx = macro.get("^TNX", {})
    vix    = vix_inf.get("vix", 0)

    tech_n  = tech.get("indices", {}).get("^N225", {})
    tech_sp = tech.get("indices", {}).get("^GSPC", {})
    tech_fx = tech.get("fx", {}).get("USDJPY=X", {})
    corr    = tech.get("correlations", {})

    nchg = nikkei.get("change_pct", 0)
    schg = sp500.get("change_pct",  0)
    uchg = usdjpy.get("change_pct", 0)
    rsi_n = tech_n.get("rsi", 50)
    rsi_s = tech_sp.get("rsi", 50)
    macd_d = tech_n.get("macd", {})

    # ── 評価ロジック ──
    def _eval_stock(chg, rsi, vix_val):
        bull = (chg > 0.8 and rsi < 70) or (chg > 0 and rsi < 50 and vix_val < 20)
        bear = chg < -0.8 or vix_val > 28 or rsi > 75
        if bull: return "強気", ("高" if abs(chg) > 1.5 else "中")
        if bear: return "弱気", ("高" if abs(chg) > 1.5 else "中")
        return "中立", ("中" if abs(chg) > 0.3 else "低")

    def _eval_fx(chg):
        if chg > 0.5: return "円安", ("高" if chg > 1 else "中")
        if chg < -0.5: return "円高", ("高" if chg < -1 else "中")
        return "横ばい", "低"

    jp_eval, jp_conf = _eval_stock(nchg, rsi_n, vix)
    us_eval, us_conf = _eval_stock(schg, rsi_s, vix)
    fx_eval, fx_conf = _eval_fx(uchg)

    # ── RSI 解説 ──
    def _rsi_comment(r):
        if r >= 70: return f"**{r:.1f}（買われすぎ圏）** 短期的な過熱に注意"
        if r <= 30: return f"**{r:.1f}（売られすぎ圏）** 反発の可能性あり"
        if r >= 55: return f"{r:.1f}（中立やや強め）"
        if r <= 45: return f"{r:.1f}（中立やや弱め）"
        return f"{r:.1f}（中立圏）"

    # ── MACD 解説 ──
    macd_val = macd_d.get("macd", 0); sig_val = macd_d.get("signal", 0)
    if macd_val > sig_val and macd_val > 0:
        macd_comment = "**ゴールデンクロス維持・上昇モメンタム継続**"
    elif macd_val > sig_val and macd_val <= 0:
        macd_comment = "シグナル上抜け（ゴールデンクロス接近）"
    elif macd_val < sig_val and macd_val < 0:
        macd_comment = "デッドクロス継続・下落圧力あり"
    else:
        macd_comment = "シグナル下抜け（デッドクロス警戒）"

    # ── ニュース上位3件 ──
    top3 = sorted(news, key=lambda x: abs(x.get("sentiment_score", 0)), reverse=True)[:3]
    news_lines = ""
    for i, art in enumerate(top3, 1):
        sc   = art.get("sentiment_score", 0)
        cat  = art.get("impact_category", "その他")
        mark = "📈" if sc > 0.2 else ("📉" if sc < -0.2 else "➡️")
        news_lines += f"- {mark} **{art['title'][:60]}**（{cat}、スコア{sc:+.2f}）\n"
    if not news_lines:
        news_lines = "- 本日の主要ニュースなし\n"

    # ── 為替影響 ──
    corr_fx_n = corr.get("fx_nikkei", 0)
    if abs(corr_fx_n) > 0.5:
        corr_txt = f"相関係数 **{corr_fx_n:+.2f}**（{'正相関：円安→日経高の傾向' if corr_fx_n > 0 else '逆相関：円安→日経安の傾向'}）"
    else:
        corr_txt = f"相関係数 {corr_fx_n:+.2f}（現在、為替と株価の連動性は低い）"

    # ── リスクシナリオ ──
    bull_scenario = []
    bear_scenario = []
    if schg > 0: bull_scenario.append("米国株の上昇モメンタム継続による日本株の追い風")
    if uchg > 0: bull_scenario.append(f"ドル円{usdjpy.get('current', 0):.2f}円台の円安が輸出企業の業績を支援")
    if rsi_n < 50: bull_scenario.append("テクニカル的な売られすぎ圏からの反発余地")
    if not bull_scenario: bull_scenario.append("世界経済の底堅さと企業業績の回復継続")

    if vix > 20: bear_scenario.append(f"VIX {vix:.1f}の高止まりが示す市場不安定リスク")
    if uchg < -0.5: bear_scenario.append("急速な円高進行による輸出企業の業績下押し")
    if rsi_n > 65: bear_scenario.append("過熱圏での利益確定売り圧力")
    bear_scenario.append("地政学リスク・金融政策の想定外変化による急変動")

    summary = (
        f"日経225は{nikkei.get('current_close',0):,.0f}円（前日比{nchg:+.2f}%）、"
        f"S&P500は{sp500.get('current_close',0):,.2f}（{schg:+.2f}%）で推移。"
        f"ドル円は{usdjpy.get('current',0):.2f}円（{uchg:+.2f}%）、"
        f"VIXは{vix:.1f}（{vix_inf.get('badge_text','不明')}）。"
        f"金は${gold.get('current',0):,.0f}、米10年債利回りは{tnx.get('current',0):.2f}%。"
    )

    return f"""## 市場現状サマリー
{summary}

---

## 日本株評価: {jp_eval} 確信度:{jp_conf}

- **日経225**: {nikkei.get('current_close',0):,.0f}円 （前日比 {nchg:+.2f}%）
- **TOPIX**: {topix.get('current_close',0):,.1f}（{topix.get('change_pct',0):+.2f}%）
- **RSI(14)**: {_rsi_comment(rsi_n)}
- **MACD**: {macd_comment}
- **20MA乖離**: {tech_n.get('ma20_dev',0):+.2f}%
- **52週レンジ内位置**: {max(0, (nikkei.get('current_close',0) - nikkei.get('week_low_52',0)) / max(nikkei.get('week_high_52',1) - nikkei.get('week_low_52',0), 1) * 100):.0f}%

---

## 米国株評価: {us_eval} 確信度:{us_conf}

- **S&P500**: {sp500.get('current_close',0):,.2f}（{schg:+.2f}%）
- **NASDAQ**: {nasdaq.get('current_close',0):,.2f}（{nasdaq.get('change_pct',0):+.2f}%）
- **DOW**: {dow.get('current_close',0):,.0f}（{dow.get('change_pct',0):+.2f}%）
- **RSI(14)**: {_rsi_comment(rsi_s)}
- **20MA乖離**: {tech_sp.get('ma20_dev',0):+.2f}%

---

## ドル円方向: {fx_eval} 確信度:{fx_conf}

- **USD/JPY**: {usdjpy.get('current',0):.2f}円（{uchg:+.2f}%）
- **RSI(14)**: {tech_fx.get('rsi',50):.1f}
- **20MA乖離**: {tech_fx.get('ma20_dev',0):+.2f}%
- **DXY（ドル指数）**: {macro.get('DX-Y.NYB',{}).get('current',0):.2f}

---

## 主要ニュース解説（上位3件）

{news_lines}
---

## 為替が日本株に与える影響分析

過去30日のUSD/JPYと日経225の相関: {corr_txt}

円安は輸出企業（自動車・電機）の収益拡大要因となる一方、輸入コスト上昇で内需企業にはマイナス。
現在のドル円水準（{usdjpy.get('current',0):.2f}円）は{"円安方向で輸出企業に有利" if usdjpy.get('current',0) > 145 else "円高方向で輸入コスト低下"}な水準。

---

## 今週の注目リスクシナリオ（強気・弱気）

**強気シナリオ:**
{chr(10).join(f'- {s}' for s in bull_scenario)}

**弱気シナリオ:**
{chr(10).join(f'- {s}' for s in bear_scenario)}

---

## 注目すべきイベント・指標

- 米FOMC議事録・要人発言（金利見通しに影響）
- 国内企業決算発表（業績トレンドの確認）
- 米雇用統計・CPI（Fed政策判断の材料）
- 日銀政策決定会合・植田総裁発言
- VIX指数の動向（20超が続く場合はリスクオフ注意）

※ このレポートはデータ自動集計による分析です。
"""


def run(all_results: dict) -> str:
    """メイン分析実行"""
    logger.info("SubAgent J: メイン分析開始（Claude CLI呼び出し）")

    prompt = _build_prompt(all_results)
    analysis = call_claude(prompt, system=SYSTEM_PROMPT)

    if not analysis:
        logger.warning("Claude CLI利用不可 — テンプレート分析にフォールバック")
        analysis = _template_analysis(all_results)

    logger.info("SubAgent J: 分析完了")
    return analysis
