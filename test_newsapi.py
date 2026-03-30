"""
NewsAPI 動作確認スクリプト。
使い方: python3 test_newsapi.py <YOUR_NEWS_API_KEY>
"""
import sys
import requests
import json
from datetime import datetime

def test_newsapi(api_key: str) -> None:
    """NewsAPIの動作確認"""
    print(f"NewsAPI テスト開始...")
    print(f"キー: {api_key[:8]}****")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "Fed OR 日銀 OR 金利 OR 株価 OR 為替",
        "language": "ja",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if resp.status_code == 200:
            articles = data.get("articles", [])
            print(f"\n✓ 成功！ {data.get('totalResults', 0)}件ヒット（表示: {len(articles)}件）\n")
            for i, art in enumerate(articles, 1):
                print(f"[{i}] {art.get('title', 'タイトルなし')}")
                print(f"    ソース: {art.get('source', {}).get('name', '不明')}")
                print(f"    日時: {art.get('publishedAt', '')}")
                print()
        else:
            print(f"\n✗ エラー: {data.get('message', '不明')}")
            print(f"  ステータスコード: {resp.status_code}")
            if resp.status_code == 401:
                print("  → APIキーが無効です。https://newsapi.org/ で確認してください。")
            elif resp.status_code == 426:
                print("  → 無料プランは開発者テスト用途のみ（localhostからのみ動作）。")
                print("    本番環境（GitHub Actions等）では有料プランが必要です。")

    except requests.RequestException as e:
        print(f"\n✗ 接続エラー: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python3 test_newsapi.py <YOUR_NEWS_API_KEY>")
        print("\nAPIキーの取得方法:")
        print("  1. https://newsapi.org/register にアクセス")
        print("  2. 無料アカウントを作成")
        print("  3. 発行されたAPIキーをコピー")
        sys.exit(1)

    test_newsapi(sys.argv[1])
