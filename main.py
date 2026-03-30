"""
日米株価・為替 × ニュース・政治イベント 日次アセスメントシステム
メインオーケストレーター。全サブエージェントを順次・並列で制御する。

実行例:
  python main.py --mock          # モックデータで動作確認
  python main.py --date today    # 当日分析
  python main.py --date 2026-03-31
"""
import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from dotenv import load_dotenv

# 環境変数読み込み（.env ファイルがある場合）
load_dotenv()

# ログディレクトリ作成
os.makedirs("logs", exist_ok=True)
date_str_global = datetime.now().strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(
            f"logs/{date_str_global}.log", encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# サブエージェントのインポート（agents パッケージから直接）
from agents import agent_stocks
from agents import agent_fx
from agents import agent_news
from agents import agent_technical
from agents import agent_vix_flag
from agents import agent_sentiment
from agents import agent_pattern_db
from agents import agent_analyst
from agents import agent_reporter

import mock_data
import notifier


def run_analysis(use_mock: bool = False, target_date: str = None) -> None:
    """
    メイン分析フロー（5フェーズ）を実行する。

    Args:
        use_mock: True の場合はモックデータを使用（API不要）
        target_date: 対象日付文字列（YYYY-MM-DD）
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(
        f"━━ 日次アセスメント開始 {target_date} "
        f"{'[モード: mock]' if use_mock else '[モード: live]'} ━━"
    )

    all_results: dict = {}

    # ─────────────────────────────────────────────
    # Phase 1: 並列データ収集
    # concurrent.futures で株価・為替・ニュースを同時取得
    # ─────────────────────────────────────────────
    logger.info("── Phase 1: 並列データ収集 ──")

    if use_mock:
        # モックデータを使用（APIキー・ネット接続不要）
        stocks_result = mock_data.get_mock_stocks()
        fx_result = mock_data.get_mock_fx()
        news_result = mock_data.get_mock_news()
        logger.info("  モックデータを使用")
    else:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(agent_stocks.run): "stocks",
                executor.submit(agent_fx.run): "fx",
                executor.submit(agent_news.run): "news",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    all_results[key] = future.result()
                    logger.info(f"  ✓ {key} 取得完了")
                except Exception as e:
                    logger.error(f"  ✗ {key} 取得失敗: {e}")
                    # 取得失敗時は空データで続行
                    all_results[key] = {} if key != "news" else []

        stocks_result = all_results.get("stocks", {})
        fx_result = all_results.get("fx", {})
        news_result = all_results.get("news", [])

    all_results["stocks"] = stocks_result
    all_results["fx"] = fx_result
    all_results["news"] = news_result

    # ─────────────────────────────────────────────
    # Phase 2: 順次処理（前フェーズの結果に依存）
    # ─────────────────────────────────────────────
    logger.info("── Phase 2: 順次処理 ──")

    # E: テクニカル指標計算
    logger.info("  E: テクニカル指標計算中...")
    try:
        tech_result = agent_technical.run(stocks_result, fx_result)
        all_results["technical"] = tech_result
        logger.info("  ✓ テクニカル指標計算完了")
    except Exception as e:
        logger.error(f"  ✗ テクニカル指標エラー: {e}")
        all_results["technical"] = {"indices": {}, "fx": {}, "correlations": {}}

    # F: VIX判定フラグ
    logger.info("  F: VIX判定中...")
    vix_value = (
        fx_result.get("macro", {}).get("^VIX", {}).get("current", 20.0)
    )
    try:
        vix_result = agent_vix_flag.run(vix_value)
        all_results["vix_flag"] = vix_result
        logger.info(f"  ✓ VIX判定完了: {vix_result.get('badge_text', '-')}")
    except Exception as e:
        logger.error(f"  ✗ VIX判定エラー: {e}")
        all_results["vix_flag"] = {
            "vix": vix_value, "level": "moderate",
            "badge_color": "info", "badge_text": "やや不安定",
            "context_text": f"VIX={vix_value:.1f}",
        }

    # G: 感情スコア計算（Claude CLI使用）
    logger.info("  G: 感情スコア計算中（Claude CLI）...")
    try:
        sentiment_result = agent_sentiment.run(news_result)
        all_results["sentiment"] = sentiment_result
        logger.info(f"  ✓ 感情スコア付与: {len(sentiment_result)}件")
    except Exception as e:
        logger.error(f"  ✗ 感情スコアエラー: {e}")
        # スコアなしのニュースリストで続行
        all_results["sentiment"] = news_result

    # ─────────────────────────────────────────────
    # Phase 3: パターンDB更新・Few-shot例構築
    # ─────────────────────────────────────────────
    logger.info("── Phase 3: パターンDB更新 ──")
    try:
        pattern_result = agent_pattern_db.run(all_results)
        all_results["pattern_db"] = pattern_result
        logger.info(
            f"  ✓ DB更新完了: 累計{pattern_result.get('total_records', 0)}件, "
            f"類似パターン{pattern_result.get('similar_count', 0)}件"
        )
    except Exception as e:
        logger.error(f"  ✗ パターンDB更新エラー: {e}")
        all_results["pattern_db"] = {
            "few_shot_text": "（DB更新エラー）",
            "similar_count": 0,
            "total_records": 0,
        }

    # ─────────────────────────────────────────────
    # Phase 4: メイン分析（Claude CLI使用）
    # ─────────────────────────────────────────────
    logger.info("── Phase 4: メイン分析（Claude CLI）──")
    try:
        analysis_text = agent_analyst.run(all_results)
        all_results["analysis"] = analysis_text
        logger.info("  ✓ 分析完了")
    except Exception as e:
        logger.error(f"  ✗ メイン分析エラー: {e}")
        analysis_text = (
            "## 市場現状サマリー\n"
            "分析中にエラーが発生しました。データを確認してください。"
        )
        all_results["analysis"] = analysis_text

    # ─────────────────────────────────────────────
    # Phase 5: 並列出力（レポート生成 + 通知）
    # ─────────────────────────────────────────────
    logger.info("── Phase 5: 並列出力 ──")

    def generate_report() -> str:
        return agent_reporter.run(all_results, analysis_text, target_date)

    def send_notifications(report_path: str) -> None:
        notifier.send_all(all_results, analysis_text, report_path)

    report_path = None
    with ThreadPoolExecutor(max_workers=2) as executor:
        report_future = executor.submit(generate_report)
        try:
            report_path = report_future.result()
            logger.info(f"  ✓ レポート生成: {report_path}")
        except Exception as e:
            logger.error(f"  ✗ レポート生成失敗: {e}")

    # 通知は同期で実行（エラーでも分析自体は成功とみなす）
    if report_path:
        try:
            send_notifications(report_path)
        except Exception as e:
            logger.warning(f"  通知送信エラー（継続）: {e}")

    # ─────────────────────────────────────────────
    # 完了サマリー
    # ─────────────────────────────────────────────
    logger.info(f"━━ 日次アセスメント完了 {target_date} ━━")
    if report_path:
        logger.info(f"レポートファイル: {report_path}")

    pd_info = all_results.get("pattern_db", {})
    logger.info(
        f"パターンDB: 累計{pd_info.get('total_records', 0)}件 | "
        f"類似パターン参照: {pd_info.get('similar_count', 0)}件"
    )

    # 分析テキストの冒頭をコンソールに表示
    print("\n" + "=" * 60)
    print("【分析結果サマリー】")
    print("=" * 60)
    # 最初の500文字を表示
    print(analysis_text[:500])
    if len(analysis_text) > 500:
        print("...(省略)...")
    print("=" * 60)
    if report_path:
        print(f"\nHTMLレポート: {os.path.abspath(report_path)}")


def main() -> None:
    """コマンドライン引数を解析してメイン処理を実行"""
    parser = argparse.ArgumentParser(
        description='日米株価・為替 日次アセスメントシステム',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --mock              # モックデータで動作確認（推奨: 初回）
  python main.py --date today        # 当日のライブデータで分析
  python main.py --date 2026-03-31   # 特定日付を指定
        """,
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='モックデータを使用（APIキー・ネット接続不要）',
    )
    parser.add_argument(
        '--date',
        default='today',
        help='対象日付（YYYY-MM-DD または today）',
    )
    args = parser.parse_args()

    target_date = (
        datetime.now().strftime("%Y-%m-%d")
        if args.date == 'today'
        else args.date
    )

    run_analysis(use_mock=args.mock, target_date=target_date)


if __name__ == "__main__":
    main()
