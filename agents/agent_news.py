"""
SubAgent C: ニュース収集エージェント。
RSSフィードと（任意で）NewsAPIからニュースを収集する。
"""
import feedparser
import os
import logging
import hashlib
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)

MAX_ARTICLES = 30


def _parse_rss(feed_info: dict) -> list:
    """RSSフィードを解析して記事リストを返す"""
    articles = []
    try:
        feed = feedparser.parse(feed_info["url"])
        for entry in feed.entries[:10]:  # 各フィードから最大10件
            article_id = hashlib.md5(
                (entry.get('link', '') + entry.get('title', '')).encode()
            ).hexdigest()[:8]

            articles.append({
                "id": f"{feed_info['source']}_{article_id}",
                "title": entry.get('title', '').strip(),
                "summary": entry.get('summary', entry.get('description', '')).strip()[:500],
                "url": entry.get('link', ''),
                "published": entry.get('published', datetime.now().isoformat()),
                "source": feed_info['source'],
            })
    except Exception as e:
        logger.warning(f"RSS取得エラー ({feed_info['source']}): {e}")
    return articles


def _fetch_newsapi(api_key: str) -> list:
    """NewsAPIからニュースを取得"""
    try:
        import requests
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": config.NEWS_KEYWORDS,
            "language": "ja,en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": api_key,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for art in data.get('articles', []):
            article_id = hashlib.md5(art.get('url', '').encode()).hexdigest()[:8]
            articles.append({
                "id": f"newsapi_{article_id}",
                "title": art.get('title', '').strip(),
                "summary": art.get('description', '').strip()[:500] if art.get('description') else '',
                "url": art.get('url', ''),
                "published": art.get('publishedAt', datetime.now().isoformat()),
                "source": art.get('source', {}).get('name', 'NewsAPI'),
            })
        return articles
    except Exception as e:
        logger.warning(f"NewsAPI取得エラー: {e}")
        return []


def run() -> list:
    """ニュース収集メイン処理"""
    logger.info("SubAgent C: ニュース収集開始")
    all_articles = []

    # RSSフィード収集
    for feed_info in config.RSS_FEEDS:
        articles = _parse_rss(feed_info)
        all_articles.extend(articles)
        logger.info(f"  {feed_info['source']}: {len(articles)}件取得")

    # NewsAPI（キーがある場合）
    news_api_key = os.getenv('NEWS_API_KEY', '')
    if news_api_key:
        api_articles = _fetch_newsapi(news_api_key)
        all_articles.extend(api_articles)
        logger.info(f"  NewsAPI: {len(api_articles)}件取得")

    # 重複除去（タイトルベース）
    seen_titles = set()
    unique_articles = []
    for art in all_articles:
        title_key = art['title'][:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(art)

    # 最大30件に制限
    result = unique_articles[:MAX_ARTICLES]

    if not result:
        logger.warning("ニュースが0件でした。ダミーエントリを挿入します。")
        result = [{
            "id": "no_news",
            "title": "本日ニュース取得不可",
            "summary": "RSSフィードからのニュース取得に失敗しました。",
            "url": "",
            "published": datetime.now().isoformat(),
            "source": "system",
        }]

    logger.info(f"SubAgent C: 完了 — {len(result)}件")
    return result
