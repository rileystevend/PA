"""
RSS news feed reader.

Sources:
  - Google News (Austin, TX)
  - Bloomberg Markets
  - TechCrunch

Caches to ~/.pa/cache/news_{source}.json for 15 minutes.
If one feed fails, the others are still returned (partial result).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".pa" / "cache"
CACHE_TTL_MINUTES = 15

FEEDS = {
    "austin": "https://news.google.com/rss/search?q=Austin+Texas&hl=en-US&gl=US&ceid=US:en",
    "bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "techcrunch": "https://techcrunch.com/feed/",
}

MAX_ARTICLES_PER_SOURCE = 10


def get_headlines() -> list[dict]:
    """
    Fetch and merge headlines from all sources.
    Returns list of {title, url, source, published} dicts.
    Deduplicates by URL across sources.
    """
    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    for source, url in FEEDS.items():
        try:
            articles = _fetch_feed(source, url)
            for article in articles:
                if article["url"] not in seen_urls:
                    seen_urls.add(article["url"])
                    all_articles.append(article)
        except Exception as e:
            logger.warning("News feed %s failed: %s", source, e)
            all_articles.append({"source": source, "error": str(e)})

    return all_articles


def _fetch_feed(source: str, url: str) -> list[dict]:
    cached = _load_cache(source)
    if cached is not None:
        return cached

    articles = _fetch_public(url, source)
    _save_cache(source, articles)
    return articles


def _fetch_public(url: str, source: str) -> list[dict]:
    resp = httpx.get(url, timeout=10, follow_redirects=True)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    return _parse_entries(feed.entries, source)[:MAX_ARTICLES_PER_SOURCE]


def _parse_entries(entries, source: str) -> list[dict]:
    articles = []
    for entry in entries:
        articles.append(
            {
                "title": entry.get("title", "(no title)"),
                "url": entry.get("link", ""),
                "source": source,
                "published": entry.get("published", ""),
            }
        )
    return articles


def _cache_path(source: str) -> Path:
    return CACHE_DIR / f"news_{source}.json"


def _load_cache(source: str) -> list[dict] | None:
    path = _cache_path(source)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at < timedelta(minutes=CACHE_TTL_MINUTES):
            return data["articles"]
    except Exception:
        pass
    return None


def _save_cache(source: str, articles: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(source)
    path.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "articles": articles},
            indent=2,
        )
    )
