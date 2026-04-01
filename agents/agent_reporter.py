"""
SubAgent K: HTMLレポート生成エージェント。
初心者にも見やすい、モバイル対応のダッシュボード形式HTMLを生成する。
"""
import os
import re
import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ──────────────────────────────────────────────
# チャート生成関数
# ──────────────────────────────────────────────

def _make_candlestick_chart(stocks_data: dict, tech_data: dict) -> str:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        targets = [
            ("^N225", "日経225"),
            ("^GSPC", "S&P500"),
            ("^IXIC", "NASDAQ"),
            ("^DJI", "DOW"),
        ]

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[t[1] for t in targets],
            vertical_spacing=0.14,
            horizontal_spacing=0.08,
        )

        for i, (symbol, name) in enumerate(targets):
            row = i // 2 + 1
            col = i % 2 + 1
            data = stocks_data.get("indices", {}).get(symbol, {})
            close = data.get("close")
            high = data.get("high")
            low = data.get("low")
            open_ = data.get("open")

            if close is None or not isinstance(close, pd.Series) or close.empty:
                continue

            fig.add_trace(go.Candlestick(
                x=close.index, open=open_, high=high, low=low, close=close,
                name=name, showlegend=False,
                increasing_line_color='#ef5350',
                decreasing_line_color='#26a69a',
            ), row=row, col=col)

            ma20 = close.rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=close.index, y=ma20,
                line=dict(color='#ff9800', width=1.5),
                name='20日移動平均', showlegend=(i == 0),
            ), row=row, col=col)

            ma60 = close.rolling(60).mean()
            fig.add_trace(go.Scatter(
                x=close.index, y=ma60,
                line=dict(color='#2196f3', width=1.5, dash='dash'),
                name='60日移動平均', showlegend=(i == 0),
            ), row=row, col=col)

        fig.update_layout(
            title=dict(text='📊 日米主要指数チャート（過去60日）', font=dict(size=16)),
            height=600,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(248,249,250,1)',
            legend=dict(orientation='h', y=-0.05),
            xaxis_rangeslider_visible=False,
            xaxis2_rangeslider_visible=False,
            xaxis3_rangeslider_visible=False,
            xaxis4_rangeslider_visible=False,
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    except Exception as e:
        logger.warning(f"ローソク足チャート生成エラー: {e}")
        return "<p class='text-muted'>チャート生成エラー</p>"


def _make_fx_chart(fx_data: dict) -> str:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fx_pairs = fx_data.get("fx", {})
        macro = fx_data.get("macro", {})

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        colors = {
            'USDJPY=X': '#1565c0',
            'EURJPY=X': '#e65100',
            'GBPJPY=X': '#2e7d32',
        }

        for symbol, color in colors.items():
            data = fx_pairs.get(symbol, {})
            close = data.get("close")
            if close is not None and isinstance(close, pd.Series) and not close.empty:
                fig.add_trace(go.Scatter(
                    x=close.index, y=close,
                    name=data.get("name", symbol),
                    line=dict(color=color, width=2.5),
                    hovertemplate='%{y:.2f}円<extra>%{fullData.name}</extra>',
                ), secondary_y=False)

        dxy_data = macro.get("DX-Y.NYB", {})
        dxy_close = dxy_data.get("close")
        if dxy_close is not None and isinstance(dxy_close, pd.Series) and not dxy_close.empty:
            fig.add_trace(go.Scatter(
                x=dxy_close.index, y=dxy_close,
                name='ドル指数(DXY)',
                line=dict(color='#7b1fa2', width=1.5, dash='dot'),
                hovertemplate='%{y:.2f}<extra>DXY</extra>',
            ), secondary_y=True)

        fig.update_layout(
            title=dict(text='💱 為替チャート（過去30日）', font=dict(size=16)),
            height=380,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', y=-0.15),
        )
        fig.update_yaxes(title_text="円換算レート（円）", secondary_y=False)
        fig.update_yaxes(title_text="ドル指数 DXY", secondary_y=True)

        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"為替チャート生成エラー: {e}")
        return "<p class='text-muted'>チャート生成エラー</p>"


def _make_sentiment_chart(stocks_data: dict, news_with_scores: list) -> str:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        nikkei = stocks_data.get("indices", {}).get("^N225", {})
        close = nikkei.get("close")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        if close is not None and isinstance(close, pd.Series) and not close.empty:
            fig.add_trace(go.Scatter(
                x=close.index, y=close,
                name='日経225',
                line=dict(color='#1565c0', width=2.5),
                fill='tozeroy',
                fillcolor='rgba(21,101,192,0.07)',
                hovertemplate='%{y:,.0f}円<extra>日経225</extra>',
            ), secondary_y=False)

        if news_with_scores:
            score_by_date: dict = {}
            for art in news_with_scores:
                try:
                    pub = pd.Timestamp(art.get('published', '')).date()
                    score = art.get('sentiment_score', 0)
                    score_by_date.setdefault(pub, []).append(score)
                except Exception:
                    pass

            if score_by_date:
                dates = list(score_by_date.keys())
                avg_scores = [sum(v) / len(v) for v in score_by_date.values()]
                bar_colors = ['rgba(239,83,80,0.7)' if s < 0 else 'rgba(38,166,154,0.7)' for s in avg_scores]

                fig.add_trace(go.Bar(
                    x=dates, y=avg_scores,
                    name='ニュース感情（平均）',
                    marker_color=bar_colors,
                    hovertemplate='感情スコア: %{y:+.2f}<extra></extra>',
                ), secondary_y=True)

        fig.add_hline(y=0, line_dash="dash", line_color="gray",
                      line_width=1, secondary_y=True)

        fig.update_layout(
            title=dict(text='📰 日経225 × ニュース感情スコア', font=dict(size=16)),
            height=380,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', y=-0.15),
        )
        fig.update_yaxes(title_text="日経225（円）", secondary_y=False)
        fig.update_yaxes(title_text="感情スコア（±1.0）", secondary_y=True,
                         range=[-1.5, 1.5])

        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"感情スコアチャート生成エラー: {e}")
        return "<p class='text-muted'>チャート生成エラー</p>"


def _make_technical_chart(stocks_data: dict, tech_data: dict) -> str:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        nikkei = stocks_data.get("indices", {}).get("^N225", {})
        close = nikkei.get("close")
        tech_nikkei = tech_data.get("indices", {}).get("^N225", {})

        if close is None or not isinstance(close, pd.Series) or close.empty:
            return "<p class='text-muted'>データなし</p>"

        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=[
                '日経225 + ボリンジャーバンド（値動きの幅）',
                'RSI（14日）— 70以上:買われすぎ / 30以下:売られすぎ',
                'MACD — ゴールデンクロスで上昇シグナル',
            ],
            row_heights=[0.5, 0.25, 0.25],
            vertical_spacing=0.1,
        )

        # 価格 + ボリンジャーバンド
        fig.add_trace(go.Scatter(
            x=close.index, y=close,
            name='日経225', line=dict(color='#1565c0', width=2.5),
        ), row=1, col=1)

        bb = tech_nikkei.get("bb", {})
        if 'series_upper' in bb:
            fig.add_trace(go.Scatter(
                x=close.index, y=bb['series_upper'],
                name='上限', line=dict(color='#e53935', dash='dash', width=1),
                showlegend=True,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=close.index, y=bb['series_lower'],
                name='下限', line=dict(color='#43a047', dash='dash', width=1),
                fill='tonexty', fillcolor='rgba(33,150,243,0.06)',
                showlegend=True,
            ), row=1, col=1)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        # RSIを色分け
        rsi_colors = rsi.apply(
            lambda v: '#e53935' if v >= 70 else ('#43a047' if v <= 30 else '#1565c0')
        )
        fig.add_trace(go.Scatter(
            x=close.index, y=rsi,
            name='RSI', line=dict(color='#7b1fa2', width=2),
            showlegend=False,
        ), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor='rgba(239,83,80,0.08)',
                      line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor='rgba(38,166,154,0.08)',
                      line_width=0, row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#e53935",
                      line_width=1, row=2, col=1,
                      annotation_text="買われすぎ(70)", annotation_position="left")
        fig.add_hline(y=30, line_dash="dash", line_color="#43a047",
                      line_width=1, row=2, col=1,
                      annotation_text="売られすぎ(30)", annotation_position="left")

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line

        fig.add_trace(go.Bar(
            x=close.index, y=histogram,
            name='ヒストグラム',
            marker_color=['rgba(239,83,80,0.7)' if h < 0 else 'rgba(38,166,154,0.7)'
                          for h in histogram.fillna(0)],
            showlegend=False,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=close.index, y=macd_line,
            name='MACD', line=dict(color='#1565c0', width=2),
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=close.index, y=signal_line,
            name='シグナル', line=dict(color='#e53935', width=2),
        ), row=3, col=1)

        fig.update_layout(
            title=dict(text='📈 テクニカル指標（日経225）', font=dict(size=16)),
            height=680,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', y=-0.04),
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"テクニカルチャート生成エラー: {e}")
        return "<p class='text-muted'>チャート生成エラー</p>"


# ──────────────────────────────────────────────
# 補助関数
# ──────────────────────────────────────────────

def _parse_analysis_sections(analysis_text: str) -> dict:
    sections = {
        "jp_eval": "中立", "jp_confidence": "中",
        "us_eval": "中立", "us_confidence": "中",
        "fx_eval": "横ばい", "fx_confidence": "中",
    }

    jp_match = re.search(
        r'日本株評価[：:]\s*\[?([強弱中]{1,2}気?)\]?.*?確信度[：:]\s*\[?([高中低])\]?',
        analysis_text
    )
    if jp_match:
        sections["jp_eval"] = jp_match.group(1)
        sections["jp_confidence"] = jp_match.group(2)

    us_match = re.search(
        r'米国株評価[：:]\s*\[?([強弱中]{1,2}気?)\]?.*?確信度[：:]\s*\[?([高中低])\]?',
        analysis_text
    )
    if us_match:
        sections["us_eval"] = us_match.group(1)
        sections["us_confidence"] = us_match.group(2)

    fx_match = re.search(
        r'ドル円方向[：:]\s*\[?([円高円安横ばい]+)\]?.*?確信度[：:]\s*\[?([高中低])\]?',
        analysis_text
    )
    if fx_match:
        sections["fx_eval"] = fx_match.group(1)
        sections["fx_confidence"] = fx_match.group(2)

    return sections


def _eval_to_style(eval_text: str) -> dict:
    """評価テキストをカラー・アイコン・説明に変換"""
    if '強気' in eval_text:
        return {'color': 'success', 'icon': '↑', 'gradient': 'linear-gradient(135deg,#e8f5e9,#c8e6c9)'}
    elif '弱気' in eval_text or '円高' in eval_text:
        return {'color': 'danger', 'icon': '↓', 'gradient': 'linear-gradient(135deg,#ffebee,#ffcdd2)'}
    elif '円安' in eval_text:
        return {'color': 'warning', 'icon': '↑', 'gradient': 'linear-gradient(135deg,#fff8e1,#ffecb3)'}
    else:
        return {'color': 'secondary', 'icon': '→', 'gradient': 'linear-gradient(135deg,#f5f5f5,#eeeeee)'}


def _analysis_to_html(analysis_text: str) -> str:
    """分析テキストをきれいなHTMLに変換"""
    lines = analysis_text.split('\n')
    html_parts = []
    in_list = False

    for line in lines:
        line = line.rstrip()

        # ## 見出し
        if line.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            title = line[3:]
            icon = _section_icon(title)
            html_parts.append(
                f'<h5 class="section-heading mt-4 mb-2">{icon} {title}</h5>'
                f'<hr class="section-hr">'
            )

        # ### 小見出し
        elif line.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<h6 class="sub-heading mt-3 mb-1">{line[4:]}</h6>')

        # 箇条書き
        elif line.startswith('- ') or line.startswith('• '):
            if not in_list:
                html_parts.append('<ul class="analysis-list">')
                in_list = True
            content = _inline_format(line[2:])
            html_parts.append(f'<li>{content}</li>')

        # 空行
        elif line == '':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append('<div class="py-1"></div>')

        # 通常行
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            content = _inline_format(line)
            html_parts.append(f'<p class="mb-1">{content}</p>')

    if in_list:
        html_parts.append('</ul>')

    return '\n'.join(html_parts)


def _inline_format(text: str) -> str:
    """インライン装飾（太字・評価キーワードの色付け）"""
    # **太字**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # `コード`
    text = re.sub(r'`(.+?)`', r'<code class="inline-code">\1</code>', text)
    # 上昇・強気キーワード
    for kw in ['強気', '上昇', '好転', 'ゴールデンクロス']:
        text = text.replace(kw, f'<span class="kw-up">{kw}</span>')
    # 下落・弱気キーワード
    for kw in ['弱気', '下落', '悪化', 'デッドクロス', 'リスク']:
        text = text.replace(kw, f'<span class="kw-down">{kw}</span>')
    return text


def _section_icon(title: str) -> str:
    icons = {
        '市場現状': '📊', '日本株': '🇯🇵', '米国株': '🇺🇸', '為替': '💱',
        'ドル円': '💱', '注目': '⚠️', 'リスク': '🚨', 'シナリオ': '🗺️',
        '推奨': '💡', 'まとめ': '📝', 'サマリー': '📋',
    }
    for key, icon in icons.items():
        if key in title:
            return icon
    return '📌'


def _confidence_bar(level: str) -> str:
    """確信度をプログレスバーで表示"""
    pct = {'高': 80, '中': 50, '低': 25}.get(level, 50)
    color = {'高': '#43a047', '中': '#fb8c00', '低': '#e53935'}.get(level, '#9e9e9e')
    return (
        f'<div class="d-flex align-items-center gap-2">'
        f'  <div class="flex-grow-1" style="background:#e0e0e0;border-radius:4px;height:6px;">'
        f'    <div style="width:{pct}%;background:{color};height:6px;border-radius:4px;"></div>'
        f'  </div>'
        f'  <small class="text-muted" style="min-width:24px">{level}</small>'
        f'</div>'
    )


def _vix_description(vix: float) -> str:
    if vix >= 30:
        return "市場が非常に不安定な状態です。急落リスクが高い局面です。"
    elif vix >= 20:
        return "市場に不安感があります。慎重な判断が必要です。"
    elif vix >= 15:
        return "やや不安定な状態です。引き続き状況を注視してください。"
    else:
        return "市場は比較的落ち着いています。通常の投資判断が可能です。"


def _format_change(val: float, unit: str = '%') -> str:
    """変化率を色付きHTMLで返す"""
    if val > 0:
        return f'<span style="color:#43a047;font-weight:600">▲{val:+.2f}{unit}</span>'
    elif val < 0:
        return f'<span style="color:#e53935;font-weight:600">▼{val:.2f}{unit}</span>'
    else:
        return f'<span style="color:#9e9e9e">±0.00{unit}</span>'


# ──────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────

def run(all_results: dict, analysis_text: str, date_str: str = None) -> str:
    logger.info("SubAgent K: HTMLレポート生成開始")

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    stocks_data = all_results.get("stocks", {})
    fx_data = all_results.get("fx", {})
    tech_data = all_results.get("technical", {})
    vix_info = all_results.get("vix_flag", {})
    news_with_scores = all_results.get("sentiment", [])

    # 主要数値の取得
    indices = stocks_data.get("indices", {})
    fx_pairs = fx_data.get("fx", {})
    macro = fx_data.get("macro", {})

    nikkei   = indices.get("^N225", {})
    sp500    = indices.get("^GSPC", {})
    nasdaq   = indices.get("^IXIC", {})
    topix    = indices.get("^TOPX", {})
    usdjpy   = fx_pairs.get("USDJPY=X", {})
    eurjpy   = fx_pairs.get("EURJPY=X", {})
    vix_val  = vix_info.get("vix", 0)
    gold     = macro.get("GC=F", {})
    tnx      = macro.get("^TNX", {})

    badge_color = vix_info.get("badge_color", "secondary")
    badge_text  = vix_info.get("badge_text", "不明")

    # チャート生成
    chart_candle    = _make_candlestick_chart(stocks_data, tech_data)
    chart_fx        = _make_fx_chart(fx_data)
    chart_sentiment = _make_sentiment_chart(stocks_data, news_with_scores)
    chart_tech      = _make_technical_chart(stocks_data, tech_data)

    # 評価解析
    sections = _parse_analysis_sections(analysis_text)
    jp_style = _eval_to_style(sections["jp_eval"])
    us_style = _eval_to_style(sections["us_eval"])
    fx_style = _eval_to_style(sections["fx_eval"])

    # 分析テキスト整形
    analysis_html = _analysis_to_html(analysis_text)

    # ニュース一覧
    sorted_news = sorted(
        news_with_scores,
        key=lambda x: abs(x.get('sentiment_score', 0)),
        reverse=True,
    )[:10]

    news_rows = ""
    for art in sorted_news:
        score = art.get('sentiment_score', 0)
        if score > 0.3:
            score_badge = f'<span class="badge" style="background:#e8f5e9;color:#2e7d32;font-size:.85rem">{score:+.2f} 好材料</span>'
        elif score < -0.3:
            score_badge = f'<span class="badge" style="background:#ffebee;color:#c62828;font-size:.85rem">{score:+.2f} 悪材料</span>'
        else:
            score_badge = f'<span class="badge" style="background:#f5f5f5;color:#616161;font-size:.85rem">{score:+.2f} 中立</span>'

        category = art.get('impact_category', '-')
        url = art.get('url', '#') or '#'
        title = art.get('title', '')[:80]
        source = art.get('source', '-')

        news_rows += f"""
        <tr>
          <td class="ps-3">{score_badge}</td>
          <td><span class="cat-badge">{category}</span></td>
          <td><a href="{url}" target="_blank" rel="noopener" class="news-link">{title}</a></td>
          <td class="text-muted small pe-3">{source}</td>
        </tr>"""

    # 数値カード用のデータ
    def price_card(label, value, change_pct, unit="", flag=""):
        arrow = "▲" if change_pct >= 0 else "▼"
        clr = "#43a047" if change_pct >= 0 else "#e53935"
        return f"""
        <div class="metric-card">
          <div class="metric-flag">{flag}</div>
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}{unit}</div>
          <div class="metric-change" style="color:{clr}">{arrow} {change_pct:+.2f}%</div>
        </div>"""

    nikkei_card  = price_card("日経225",   f"{nikkei.get('current_close',0):,.0f}",  nikkei.get('change_pct',0),  "円",  "🇯🇵")
    topix_card   = price_card("TOPIX",     f"{topix.get('current_close',0):,.1f}",   topix.get('change_pct',0),   "",    "🇯🇵")
    sp500_card   = price_card("S&P500",    f"{sp500.get('current_close',0):,.2f}",   sp500.get('change_pct',0),   "",    "🇺🇸")
    nasdaq_card  = price_card("NASDAQ",    f"{nasdaq.get('current_close',0):,.2f}",  nasdaq.get('change_pct',0),  "",    "🇺🇸")
    usdjpy_card  = price_card("USD/JPY",   f"{usdjpy.get('current',0):.2f}",         usdjpy.get('change_pct',0),  "円",  "💱")
    eurjpy_card  = price_card("EUR/JPY",   f"{eurjpy.get('current',0):.2f}",         eurjpy.get('change_pct',0),  "円",  "💱")
    gold_card    = price_card("金 (Gold)", f"${gold.get('current',0):,.0f}",          gold.get('change_pct',0),   "",    "🥇")
    tnx_card     = price_card("米10年債利回り", f"{tnx.get('current',0):.2f}",        tnx.get('change_pct',0),   "%",   "📈")

    # 評価カード
    def eval_card(flag, market, eval_text, confidence, style):
        return f"""
        <div class="eval-card" style="background:{style['gradient']};border-left:5px solid var(--bs-{style['color']})">
          <div class="eval-flag">{flag}</div>
          <div class="eval-market">{market}</div>
          <div class="eval-result text-{style['color']}">{style['icon']} {eval_text}</div>
          <div class="mt-2">
            <div class="confidence-label">確信度</div>
            {_confidence_bar(confidence)}
          </div>
        </div>"""

    jp_card = eval_card("🇯🇵", "日本株", sections["jp_eval"], sections["jp_confidence"], jp_style)
    us_card = eval_card("🇺🇸", "米国株", sections["us_eval"], sections["us_confidence"], us_style)
    fx_card = eval_card("💱",  "ドル円", sections["fx_eval"],  sections["fx_confidence"], fx_style)

    vix_desc = _vix_description(vix_val)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📊 株式・為替アセスメント {date_str}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root {{
      --primary: #1565c0;
      --bg: #f0f2f5;
      --card-bg: #ffffff;
      --border: #e0e0e0;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      background: var(--bg);
      font-family: 'Helvetica Neue', 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
      color: #212121;
      font-size: 15px;
    }}

    /* ── ヘッダー ── */
    .site-header {{
      background: linear-gradient(120deg, #0d1b3e 0%, #1a3a6e 60%, #1565c0 100%);
      color: white;
      padding: 1.8rem 1.5rem 1.5rem;
    }}
    .site-header h1 {{ font-size: 1.5rem; font-weight: 700; margin: 0 0 .25rem; }}
    .site-header .sub {{ opacity: .75; font-size: .85rem; }}
    .vix-badge {{
      display: inline-flex; align-items: center; gap: .4rem;
      padding: .5rem 1.1rem; border-radius: 2rem; font-weight: 700;
      font-size: 1rem; border: 2px solid rgba(255,255,255,.3);
      background: rgba(255,255,255,.15); color: white;
      backdrop-filter: blur(4px);
    }}

    /* ── セクションタイトル ── */
    .sec-title {{
      font-size: 1rem; font-weight: 700; color: #555;
      text-transform: uppercase; letter-spacing: .05em;
      margin-bottom: .75rem; padding-bottom: .4rem;
      border-bottom: 2px solid var(--border);
    }}

    /* ── 数値メトリクスカード ── */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: .75rem;
    }}
    .metric-card {{
      background: var(--card-bg);
      border-radius: 12px;
      padding: .9rem 1rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      border: 1px solid var(--border);
      transition: transform .15s;
    }}
    .metric-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,.1); }}
    .metric-flag {{ font-size: 1.3rem; margin-bottom: .2rem; }}
    .metric-label {{ font-size: .73rem; color: #888; font-weight: 600; text-transform: uppercase; }}
    .metric-value {{ font-size: 1.3rem; font-weight: 700; color: #212121; line-height: 1.2; margin: .2rem 0; }}
    .metric-change {{ font-size: .82rem; font-weight: 600; }}

    /* ── 評価カード ── */
    .eval-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: .75rem;
    }}
    .eval-card {{
      border-radius: 12px;
      padding: 1.1rem 1.2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      border: 1px solid var(--border);
    }}
    .eval-flag {{ font-size: 1.5rem; }}
    .eval-market {{ font-size: .8rem; color: #666; font-weight: 600; text-transform: uppercase; margin: .2rem 0; }}
    .eval-result {{ font-size: 1.3rem; font-weight: 800; }}
    .confidence-label {{ font-size: .72rem; color: #888; margin-bottom: .25rem; }}

    /* ── VIXカード ── */
    .vix-card {{
      background: white;
      border-radius: 12px;
      padding: 1.1rem 1.4rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      border: 1px solid var(--border);
      display: flex; align-items: center; gap: 1rem;
    }}
    .vix-number {{ font-size: 2.5rem; font-weight: 800; color: var(--primary); }}
    .vix-label {{ font-size: .75rem; color: #888; font-weight: 600; text-transform: uppercase; }}
    .vix-desc {{ font-size: .85rem; color: #555; line-height: 1.5; }}

    /* ── 分析テキスト ── */
    .analysis-box {{
      background: white;
      border-radius: 12px;
      padding: 1.5rem 1.8rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      border: 1px solid var(--border);
      line-height: 1.9;
    }}
    .section-heading {{
      font-size: 1.05rem; font-weight: 700; color: #1565c0; margin-top: 1.5rem;
    }}
    .section-hr {{ border-color: #e3eaf5; margin: .3rem 0 .8rem; }}
    .sub-heading {{ font-size: .95rem; font-weight: 700; color: #444; }}
    .analysis-list {{ padding-left: 1.4rem; }}
    .analysis-list li {{ margin-bottom: .4rem; }}
    .kw-up {{ color: #2e7d32; font-weight: 600; }}
    .kw-down {{ color: #c62828; font-weight: 600; }}
    .inline-code {{
      background: #f5f5f5; border-radius: 3px;
      padding: .1em .4em; font-size: .9em; color: #455a64;
    }}

    /* ── チャートコンテナ ── */
    .chart-box {{
      background: white;
      border-radius: 12px;
      padding: 1rem 1.2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      border: 1px solid var(--border);
    }}
    .chart-desc {{
      font-size: .82rem; color: #777;
      background: #f8f9fa; border-radius: 6px;
      padding: .5rem .9rem; margin-top: .5rem;
    }}

    /* ── ニューステーブル ── */
    .news-table {{ width: 100%; border-collapse: collapse; }}
    .news-table thead tr {{ background: #1565c0; color: white; }}
    .news-table thead th {{ padding: .65rem .75rem; font-weight: 600; font-size: .85rem; }}
    .news-table tbody tr {{ border-bottom: 1px solid #f0f0f0; }}
    .news-table tbody tr:hover {{ background: #f8f9fa; }}
    .news-table tbody td {{ padding: .6rem .75rem; vertical-align: middle; }}
    .news-link {{ color: #1565c0; text-decoration: none; font-size: .9rem; }}
    .news-link:hover {{ text-decoration: underline; }}
    .cat-badge {{
      display: inline-block;
      background: #e3eaf5; color: #1565c0;
      border-radius: 4px; font-size: .75rem;
      padding: .15rem .5rem; font-weight: 600; white-space: nowrap;
    }}

    /* ── 初心者向けヒント ── */
    .hint-box {{
      background: #fffde7;
      border: 1px solid #ffe082;
      border-left: 4px solid #ffb300;
      border-radius: 8px;
      padding: .75rem 1rem;
      font-size: .83rem;
      color: #555;
    }}
    .hint-box strong {{ color: #e65100; }}

    /* ── フッター ── */
    .site-footer {{
      text-align: center; font-size: .78rem;
      color: #aaa; padding: 2rem 1rem;
      border-top: 1px solid #e0e0e0;
      margin-top: 1rem;
    }}

    /* ── レスポンシブ ── */
    @media (max-width: 600px) {{
      .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .eval-grid {{ grid-template-columns: 1fr; }}
      .metric-value {{ font-size: 1.1rem; }}
      .site-header h1 {{ font-size: 1.2rem; }}
    }}
  </style>
</head>
<body>

  <!-- ヘッダー -->
  <div class="site-header">
    <div style="max-width:1100px;margin:auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.75rem">
      <div>
        <h1>📊 株式・為替 日次アセスメント</h1>
        <p class="sub">{date_str} &nbsp;|&nbsp; Claude AI による自動分析 &nbsp;|&nbsp; API追加課金なし</p>
      </div>
      <div class="vix-badge">VIX {vix_val:.1f} &nbsp; {badge_text}</div>
    </div>
  </div>

  <div style="max-width:1100px;margin:auto;padding:1.2rem 1rem">

    <!-- ① 本日の数値サマリー -->
    <div class="sec-title">本日の主要数値</div>
    <div class="metrics-grid mb-4">
      {nikkei_card}
      {topix_card}
      {sp500_card}
      {nasdaq_card}
      {usdjpy_card}
      {eurjpy_card}
      {gold_card}
      {tnx_card}
    </div>

    <!-- ② AI評価サマリー + VIX -->
    <div class="sec-title">AI 総合評価</div>
    <div class="eval-grid mb-3">
      {jp_card}
      {us_card}
      {fx_card}
      <div class="vix-card">
        <div>
          <div class="vix-label">恐怖指数 VIX</div>
          <div class="vix-number">{vix_val:.1f}</div>
          <span class="badge bg-{badge_color}">{badge_text}</span>
        </div>
        <div class="vix-desc">{vix_desc}</div>
      </div>
    </div>
    <div class="hint-box mb-4">
      💡 <strong>評価の見方:</strong>
      「確信度: 高」は根拠が多く揃っているシグナルです。
      VIXは「市場の恐怖指数」で、<strong>30以上が警戒域・15未満が安定</strong>の目安です。
    </div>

    <!-- ③ AI詳細分析 -->
    <div class="sec-title">AI 詳細分析レポート</div>
    <div class="analysis-box mb-4">
      {analysis_html}
    </div>

    <!-- ④ ニュース一覧 -->
    <div class="sec-title">本日のニュース（感情スコア付き・影響度上位10件）</div>
    <div class="chart-box mb-2">
      <div class="table-responsive">
        <table class="news-table">
          <thead>
            <tr>
              <th style="width:130px">市場への影響</th>
              <th style="width:120px">カテゴリ</th>
              <th>ヘッドライン</th>
              <th style="width:100px">ソース</th>
            </tr>
          </thead>
          <tbody>{news_rows}</tbody>
        </table>
      </div>
    </div>
    <div class="hint-box mb-4">
      💡 <strong>感情スコアの見方:</strong>
      +0.3以上が市場にポジティブ（株高・円安要因）、-0.3以下がネガティブ（株安・円高要因）の目安です。
    </div>

    <!-- ⑤ チャート群 -->
    <div class="sec-title">チャート</div>

    <div class="chart-box mb-3">
      {chart_candle}
      <div class="chart-desc">
        🕯️ <strong>ローソク足チャート:</strong> 赤=上昇日・緑=下落日。
        橙線=20日移動平均（短期トレンド）、青破線=60日移動平均（中期トレンド）。
      </div>
    </div>

    <div class="chart-box mb-3">
      {chart_fx}
      <div class="chart-desc">
        💱 <strong>為替チャート:</strong> 上がるほど円安（ドル高）。
        右軸のDXYはドル全体の強さを示す指標です（上昇=ドル高）。
      </div>
    </div>

    <div class="chart-box mb-3">
      {chart_sentiment}
      <div class="chart-desc">
        📰 <strong>感情スコア × 日経225:</strong>
        緑の棒=ポジティブニュース日、赤の棒=ネガティブニュース日。
        株価との相関を視覚的に確認できます。
      </div>
    </div>

    <div class="chart-box mb-4">
      {chart_tech}
      <div class="chart-desc">
        📈 <strong>テクニカル指標:</strong>
        RSI70超=過熱気味（売り検討）、RSI30未満=売られすぎ（反発期待）。
        MACDがシグナルを上抜けると上昇シグナル（ゴールデンクロス）。
      </div>
    </div>

    <!-- フッター -->
    <div class="site-footer">
      データソース: Yahoo Finance / NHK / Reuters / AP Business &nbsp;|&nbsp;
      生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')} JST &nbsp;|&nbsp;
      Claude Pro サブスクリプション枠で分析（API追加課金なし）
    </div>
  </div>

</body>
</html>"""

    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(config.REPORTS_DIR, f"{date_str}.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"SubAgent K: HTMLレポート保存完了 → {report_path}")
    return report_path
