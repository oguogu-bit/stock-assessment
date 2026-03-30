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


def send_line(all_results: dict, analysis_text: str) -> None:
    """
    LINE Notify でテキスト通知を送信する。
    LINE_NOTIFY_TOKEN が未設定の場合はスキップ。
    """
    token = os.getenv("LINE_NOTIFY_TOKEN", "")
    if not token:
        logger.debug("LINE_NOTIFY_TOKEN 未設定 — LINE通知をスキップ")
        return

    vix_info = all_results.get("vix_flag", {})
    stocks = all_results.get("stocks", {})
    nikkei = stocks.get("indices", {}).get("^N225", {})
    fx = all_results.get("fx", {})
    usdjpy = fx.get("fx", {}).get("USDJPY=X", {})

    message = (
        f"\n📊 株式・為替 日次アセスメント\n"
        f"日経225: {nikkei.get('current_close', 0):,.0f}円 "
        f"({nikkei.get('change_pct', 0):+.2f}%)\n"
        f"USD/JPY: {usdjpy.get('current', 0):.2f} "
        f"({usdjpy.get('change_pct', 0):+.2f}%)\n"
        f"VIX: {vix_info.get('vix', 0):.1f} "
        f"[{vix_info.get('badge_text', '-')}]\n\n"
        + analysis_text[:400]
    )

    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("LINE通知: 送信完了")
    except Exception as e:
        logger.warning(f"LINE通知エラー: {e}")


def send_all(all_results: dict, analysis_text: str, report_path: str) -> None:
    """全通知チャンネルへ送信（設定済みのもののみ）"""
    send_slack(all_results, analysis_text, report_path)
    send_line(all_results, analysis_text)
