"""
SubAgent K: HTMLレポート生成エージェント。
Plotly を使って対話型チャートを含む自己完結型HTMLを生成する。
"""
import os
import re
import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# config のインポート（相対パス対応）
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _make_candlestick_chart(stocks_data: dict, tech_data: dict) -> str:
    """日米4指数ローソク足チャート（2×2サブプロット、MA付き）"""
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
            vertical_spacing=0.12,
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

            # ローソク足
            fig.add_trace(go.Candlestick(
                x=close.index, open=open_, high=high, low=low, close=close,
                name=name, showlegend=False,
                increasing_line_color='#ef5350',
                decreasing_line_color='#26a69a',
            ), row=row, col=col)

            # 20日移動平均線
            ma20 = close.rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=close.index, y=ma20,
                line=dict(color='orange', width=1.5),
                name='20MA', showlegend=(i == 0),
            ), row=row, col=col)

            # 60日移動平均線
            ma60 = close.rolling(60).mean()
            fig.add_trace(go.Scatter(
                x=close.index, y=ma60,
                line=dict(color='blue', width=1.5, dash='dash'),
                name='60MA', showlegend=(i == 0),
            ), row=row, col=col)

        fig.update_layout(
            title='日米主要指数チャート（60日）',
            height=700,
            template='plotly_white',
            xaxis_rangeslider_visible=False,
            xaxis2_rangeslider_visible=False,
            xaxis3_rangeslider_visible=False,
            xaxis4_rangeslider_visible=False,
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    except Exception as e:
        logger.warning(f"ローソク足チャート生成エラー: {e}")
        return "<p>チャート生成エラー</p>"


def _make_fx_chart(fx_data: dict) -> str:
    """為替ダッシュボード（USD/JPY・EUR/JPY・GBP/JPY + DXY右軸）"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fx_pairs = fx_data.get("fx", {})
        macro = fx_data.get("macro", {})

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        colors = {
            'USDJPY=X': '#1f77b4',
            'EURJPY=X': '#ff7f0e',
            'GBPJPY=X': '#2ca02c',
        }

        for symbol, color in colors.items():
            data = fx_pairs.get(symbol, {})
            close = data.get("close")
            if close is not None and isinstance(close, pd.Series) and not close.empty:
                fig.add_trace(go.Scatter(
                    x=close.index, y=close,
                    name=data.get("name", symbol),
                    line=dict(color=color, width=2),
                ), secondary_y=False)

        # DXY（右軸）
        dxy_data = macro.get("DX-Y.NYB", {})
        dxy_close = dxy_data.get("close")
        if dxy_close is not None and isinstance(dxy_close, pd.Series) and not dxy_close.empty:
            fig.add_trace(go.Scatter(
                x=dxy_close.index, y=dxy_close,
                name='DXY', line=dict(color='purple', width=1.5, dash='dot'),
            ), secondary_y=True)

        fig.update_layout(
            title='為替ダッシュボード（30日推移）',
            height=400,
            template='plotly_white',
            xaxis=dict(range=[
                pd.Timestamp.now() - pd.Timedelta(days=30),
                pd.Timestamp.now(),
            ]),
        )
        fig.update_yaxes(title_text="円換算レート", secondary_y=False)
        fig.update_yaxes(title_text="DXY", secondary_y=True)

        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"為替チャート生成エラー: {e}")
        return "<p>チャート生成エラー</p>"


def _make_sentiment_chart(stocks_data: dict, news_with_scores: list) -> str:
    """株価 × ニュース感情スコア重ね表示"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        nikkei = stocks_data.get("indices", {}).get("^N225", {})
        close = nikkei.get("close")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        if close is not None and isinstance(close, pd.Series) and not close.empty:
            fig.add_trace(go.Scatter(
                x=close.index, y=close,
                name='日経225', line=dict(color='#1f77b4', width=2),
            ), secondary_y=False)

        # 日次感情スコア集計
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
                colors = ['red' if s < 0 else 'green' for s in avg_scores]

                fig.add_trace(go.Bar(
                    x=dates, y=avg_scores,
                    name='感情スコア（平均）',
                    marker_color=colors,
                    opacity=0.6,
                ), secondary_y=True)

        fig.update_layout(
            title='日経225 × ニュース感情スコア',
            height=400,
            template='plotly_white',
        )
        fig.update_yaxes(title_text="日経225（円）", secondary_y=False)
        fig.update_yaxes(title_text="感情スコア", secondary_y=True)

        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"感情スコアチャート生成エラー: {e}")
        return "<p>チャート生成エラー</p>"


def _make_technical_chart(stocks_data: dict, tech_data: dict) -> str:
    """テクニカルチャート（ボリンジャーバンド・RSI・MACD）"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        nikkei = stocks_data.get("indices", {}).get("^N225", {})
        close = nikkei.get("close")
        tech_nikkei = tech_data.get("indices", {}).get("^N225", {})

        if close is None or not isinstance(close, pd.Series) or close.empty:
            return "<p>データなし</p>"

        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=[
                '日経225 + ボリンジャーバンド',
                'RSI(14)',
                'MACD(12/26/9)',
            ],
            row_heights=[0.5, 0.25, 0.25],
            vertical_spacing=0.08,
        )

        # ローソク足 + ボリンジャーバンド
        fig.add_trace(go.Scatter(
            x=close.index, y=close,
            name='日経225', line=dict(color='blue', width=2),
        ), row=1, col=1)

        bb = tech_nikkei.get("bb", {})
        if 'series_upper' in bb:
            fig.add_trace(go.Scatter(
                x=close.index, y=bb['series_upper'],
                name='BB Upper', line=dict(color='gray', dash='dash', width=1),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=close.index, y=bb['series_lower'],
                name='BB Lower', line=dict(color='gray', dash='dash', width=1),
                fill='tonexty', fillcolor='rgba(128,128,128,0.1)',
            ), row=1, col=1)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        fig.add_trace(go.Scatter(
            x=close.index, y=rsi,
            name='RSI', line=dict(color='purple', width=1.5),
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line

        fig.add_trace(go.Scatter(
            x=close.index, y=macd_line,
            name='MACD', line=dict(color='blue', width=1.5),
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=close.index, y=signal_line,
            name='Signal', line=dict(color='red', width=1.5),
        ), row=3, col=1)
        fig.add_trace(go.Bar(
            x=close.index, y=histogram,
            name='Histogram',
            marker_color=['red' if h < 0 else 'green' for h in histogram.fillna(0)],
        ), row=3, col=1)

        fig.update_layout(
            title='テクニカル指標（日経225）',
            height=700,
            template='plotly_white',
            showlegend=False,
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.warning(f"テクニカルチャート生成エラー: {e}")
        return "<p>チャート生成エラー</p>"


def _parse_analysis_sections(analysis_text: str) -> dict:
    """分析テキストから評価セクションを抽出"""
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


def _eval_to_badge(eval_text: str) -> tuple:
    """評価テキストをBootstrapバッジカラーに変換"""
    if '強気' in eval_text or '円安' in eval_text:
        return 'success', eval_text
    elif '弱気' in eval_text or '円高' in eval_text:
        return 'danger', eval_text
    else:
        return 'secondary', eval_text


def run(all_results: dict, analysis_text: str, date_str: str = None) -> str:
    """HTMLレポート生成メイン処理"""
    logger.info("SubAgent K: HTMLレポート生成開始")

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    stocks_data = all_results.get("stocks", {})
    fx_data = all_results.get("fx", {})
    tech_data = all_results.get("technical", {})
    vix_info = all_results.get("vix_flag", {})
    news_with_scores = all_results.get("sentiment", [])

    vix = fx_data.get("macro", {}).get("^VIX", {}).get("current", 0)
    badge_color = vix_info.get("badge_color", "secondary")
    badge_text = vix_info.get("badge_text", "不明")

    # 各チャート生成
    chart_candle = _make_candlestick_chart(stocks_data, tech_data)
    chart_fx = _make_fx_chart(fx_data)
    chart_sentiment = _make_sentiment_chart(stocks_data, news_with_scores)
    chart_tech = _make_technical_chart(stocks_data, tech_data)

    # 評価セクション解析
    sections = _parse_analysis_sections(analysis_text)
    jp_color, jp_label = _eval_to_badge(sections["jp_eval"])
    us_color, us_label = _eval_to_badge(sections["us_eval"])
    fx_color, fx_label = _eval_to_badge(sections["fx_eval"])

    # 分析テキストをHTML用に整形
    analysis_html = analysis_text
    analysis_html = re.sub(r'^## (.+)$', r'<h5>\1</h5>', analysis_html, flags=re.MULTILINE)
    analysis_html = analysis_html.replace('\n', '<br>\n')

    # ニュース一覧HTML生成
    news_rows = ""
    sorted_news = sorted(
        news_with_scores,
        key=lambda x: abs(x.get('sentiment_score', 0)),
        reverse=True,
    )[:10]
    for art in sorted_news:
        score = art.get('sentiment_score', 0)
        score_color = (
            'text-danger fw-bold' if score < -0.3
            else ('text-success fw-bold' if score > 0.3 else 'text-secondary')
        )
        category = art.get('impact_category', '-')
        url = art.get('url', '#') or '#'
        title = art.get('title', '')[:80]
        source = art.get('source', '-')
        news_rows += f"""
        <tr>
          <td><span class="{score_color}">{score:+.2f}</span></td>
          <td><span class="badge bg-info text-dark">{category}</span></td>
          <td><a href="{url}" target="_blank" rel="noopener">{title}</a></td>
          <td><small class="text-muted">{source}</small></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>株式・為替 日次アセスメント {date_str}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }}
    .header-band {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: white; padding: 1.5rem 2rem;
    }}
    .card-eval {{ border-left: 5px solid; }}
    .analysis-box {{
      background: white; border-radius: 8px; padding: 1.5rem;
      line-height: 1.9; font-size: 0.95rem;
    }}
    .chart-container {{
      background: white; border-radius: 8px;
      padding: 1rem; margin-bottom: 1.5rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    h5 {{ color: #333; margin-top: 1rem; }}
  </style>
</head>
<body>
  <!-- ヘッダーバー -->
  <div class="header-band mb-4">
    <div class="container-fluid">
      <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
          <h1 class="h3 mb-1">株式・為替 日次アセスメント</h1>
          <p class="mb-0 opacity-75 small">{date_str} | Claude Code CLI分析</p>
        </div>
        <span class="badge bg-{badge_color} fs-5 px-3 py-2">
          VIX {vix:.1f} — {badge_text}
        </span>
      </div>
    </div>
  </div>

  <div class="container-fluid px-4">

    <!-- 評価サマリーカード -->
    <div class="row mb-4 g-3">
      <div class="col-md-4">
        <div class="card card-eval h-100 border-{jp_color}">
          <div class="card-body">
            <h6 class="card-subtitle mb-2 text-muted">日本株</h6>
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-{jp_color} fs-6">{jp_label}</span>
              <small class="text-muted">確信度: {sections['jp_confidence']}</small>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card card-eval h-100 border-{us_color}">
          <div class="card-body">
            <h6 class="card-subtitle mb-2 text-muted">米国株</h6>
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-{us_color} fs-6">{us_label}</span>
              <small class="text-muted">確信度: {sections['us_confidence']}</small>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card card-eval h-100 border-{fx_color}">
          <div class="card-body">
            <h6 class="card-subtitle mb-2 text-muted">ドル円</h6>
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-{fx_color} fs-6">{fx_label}</span>
              <small class="text-muted">確信度: {sections['fx_confidence']}</small>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI分析レポート -->
    <div class="chart-container mb-4">
      <h5 class="mb-3">AI分析レポート</h5>
      <div class="analysis-box">{analysis_html}</div>
    </div>

    <!-- ニュース一覧 -->
    <div class="chart-container mb-4">
      <h5 class="mb-3">本日のニュース（感情スコア付き・上位10件）</h5>
      <div class="table-responsive">
        <table class="table table-hover table-sm align-middle">
          <thead class="table-dark">
            <tr>
              <th style="width:70px">スコア</th>
              <th style="width:130px">カテゴリ</th>
              <th>ヘッドライン</th>
              <th style="width:100px">ソース</th>
            </tr>
          </thead>
          <tbody>{news_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- チャート群 -->
    <div class="chart-container">{chart_candle}</div>
    <div class="chart-container">{chart_fx}</div>
    <div class="chart-container">{chart_sentiment}</div>
    <div class="chart-container">{chart_tech}</div>

    <!-- フッター -->
    <footer class="text-center text-muted py-4 border-top mt-2">
      <small>
        データソース: Yahoo Finance / NHK / Reuters / AP Business |
        生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} JST |
        Claude Pro サブスクリプション枠で分析（API追加課金なし）
      </small>
    </footer>
  </div>
</body>
</html>"""

    # レポートディレクトリ確認・保存
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(config.REPORTS_DIR, f"{date_str}.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"SubAgent K: HTMLレポート保存完了 → {report_path}")
    return report_path
