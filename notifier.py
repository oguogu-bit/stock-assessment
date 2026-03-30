"""
通知モジュール。Slack Webhook / LINE Notify に分析結果を送信する。
環境変数未設定の場合はスキップ（エラーにならない）。
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)


def send_slack(all_results: dict, analysis_text: str, report_path: str) -> None:
    """
    Slack Incoming Webhook で通知を送信する。
    SLACK_WEBHOOK_URL が未設定の場合はスキップ。
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.debug("SLACK_WEBHOOK_URL 未設定 — Slack通知をスキップ")
        return

    vix_info = all_results.get("vix_flag", {})
    stocks = all_results.get("stocks", {})
    fx = all_results.get("fx", {})

    nikkei = stocks.get("indices", {}).get("^N225", {})
    sp500 = stocks.get("indices", {}).get("^GSPC", {})
    usdjpy = fx.get("fx", {}).get("USDJPY=X", {})

    # 分析テキストの先頭500文字をサマリーとして使用
    summary = (
        analysis_text[:500] + "…"
        if len(analysis_text) > 500
        else analysis_text
    )

    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 株式・為替 日次アセスメント",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*日経225*: {nikkei.get('current_close', 0):,.0f}円 "
                            f"({nikkei.get('change_pct', 0):+.2f}%)"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*S&P500*: {sp500.get('current_close', 0):,.2f} "
                            f"({sp500.get('change_pct', 0):+.2f}%)"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*USD/JPY*: {usdjpy.get('current', 0):.2f} "
                            f"({usdjpy.get('change_pct', 0):+.2f}%)"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*VIX*: {vix_info.get('vix', 0):.1f} "
                            f"[{vix_info.get('badge_text', '-')}]"
                        ),
                    },
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary},
            },
        ]
    }

    try:
        resp = requests.post(webhook_url, json=message, timeout=10)
        resp.raise_for_status()
        logger.info("Slack通知: 送信完了")
    except Exception as e:
        logger.warning(f"Slack通知エラー: {e}")


def send_line(all_results: dict, analysis_text: str, report_date: str = None) -> None:
    """
    LINE Notify でテキスト通知を送信する。
    GitHub Pages が設定されている場合はレポートURLも含める。
    LINE_NOTIFY_TOKEN が未設定の場合はスキップ。
    """
    token = os.getenv("LINE_NOTIFY_TOKEN", "")
    if not token:
        logger.debug("LINE_NOTIFY_TOKEN 未設定 — LINE通知をスキップ")
        return

    from datetime import datetime
    today = report_date or datetime.now().strftime("%Y-%m-%d")

    vix_info = all_results.get("vix_flag", {})
    stocks = all_results.get("stocks", {})
    nikkei = stocks.get("indices", {}).get("^N225", {})
    sp500 = stocks.get("indices", {}).get("^GSPC", {})
    fx = all_results.get("fx", {})
    usdjpy = fx.get("fx", {}).get("USDJPY=X", {})
    macro = fx.get("macro", {})
    gold = macro.get("GC=F", {})
    tnx = macro.get("^TNX", {})

    # 評価サマリーをテキストから抽出
    import re
    jp_eval = "中立"
    us_eval = "中立"
    fx_eval = "横ばい"
    jp_m = re.search(r'日本株評価[：:]\s*\[?([強弱中]{1,2}気?)\]?', analysis_text)
    us_m = re.search(r'米国株評価[：:]\s*\[?([強弱中]{1,2}気?)\]?', analysis_text)
    fx_m = re.search(r'ドル円方向[：:]\s*\[?([円高円安横ばい]+)\]?', analysis_text)
    if jp_m:
        jp_eval = jp_m.group(1)
    if us_m:
        us_eval = us_m.group(1)
    if fx_m:
        fx_eval = fx_m.group(1)

    # GitHub Pages URL（設定されている場合）
    pages_base = os.getenv(
        "GITHUB_PAGES_URL",
        "https://oguogu-bit.github.io/stock-assessment"
    )
    report_url = f"{pages_base}/reports/{today}.html"

    # LINE メッセージ本文（最大1000文字）
    message = (
        f"\n📊 株式・為替 日次アセスメント {today}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🇯🇵 日経225: {nikkei.get('current_close', 0):,.0f}円 "
        f"({nikkei.get('change_pct', 0):+.2f}%)\n"
        f"🇺🇸 S&P500: {sp500.get('current_close', 0):,.2f} "
        f"({sp500.get('change_pct', 0):+.2f}%)\n"
        f"💱 USD/JPY: {usdjpy.get('current', 0):.2f} "
        f"({usdjpy.get('change_pct', 0):+.2f}%)\n"
        f"📉 VIX: {vix_info.get('vix', 0):.1f} [{vix_info.get('badge_text', '-')}]\n"
        f"🥇 金: ${gold.get('current', 0):,.0f} / 米10年債: {tnx.get('current', 0):.2f}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"【評価】\n"
        f"日本株: {jp_eval} | 米国株: {us_eval} | ドル円: {fx_eval}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📱 詳細レポート（グラフ付き）:\n"
        f"{report_url}\n"
        f"━━━━━━━━━━━━━━━━"
    )

    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"LINE通知: 送信完了 | レポートURL: {report_url}")
    except Exception as e:
        logger.warning(f"LINE通知エラー: {e}")


def send_all(all_results: dict, analysis_text: str, report_path: str) -> None:
    """全通知チャンネルへ送信（設定済みのもののみ）"""
    import os
    # report_path からレポート日付を取得（例: reports/2026-03-31.html → 2026-03-31）
    report_date = os.path.basename(report_path).replace(".html", "") if report_path else None
    send_slack(all_results, analysis_text, report_path)
    send_line(all_results, analysis_text, report_date)
