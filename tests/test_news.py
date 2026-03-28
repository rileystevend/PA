"""Tests for integrations/news.py"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations import news


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "CACHE_DIR", tmp_path)


def _make_feed_xml(prefix: str) -> str:
    return f"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>{prefix} Feed</title>
    <item>
      <title>{prefix} Article One</title>
      <link>https://{prefix}.example.com/1</link>
      <pubDate>Thu, 27 Mar 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>{prefix} Article Two</title>
      <link>https://{prefix}.example.com/2</link>
      <pubDate>Thu, 27 Mar 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_FEED_XML = _make_feed_xml("generic")


def _make_http_resp(text):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


class TestGetHeadlines:
    def test_returns_articles_from_all_sources(self, monkeypatch):
        def fake_httpx_get(url, **kwargs):
            if "bloomberg" in url:
                return _make_http_resp(_make_feed_xml("bloomberg"))
            if "techcrunch" in url:
                return _make_http_resp(_make_feed_xml("techcrunch"))
            if "kxan" in url:
                return _make_http_resp(_make_feed_xml("kxan"))
            return _make_http_resp(_make_feed_xml("austin"))

        with patch("integrations.news.httpx.get", side_effect=fake_httpx_get):
            results = news.get_headlines()

        sources = {r.get("source") for r in results if "source" in r}
        assert "bloomberg" in sources
        assert "techcrunch" in sources
        assert "austin" in sources
        assert "kxan" in sources

    def test_returns_partial_when_one_source_fails(self, monkeypatch):
        def fake_httpx_get(url, **kwargs):
            if "bloomberg" in url:
                return _make_http_resp(_make_feed_xml("bloomberg"))
            if "techcrunch" in url:
                return _make_http_resp(_make_feed_xml("techcrunch"))
            raise Exception("Austin feed down")

        with patch("integrations.news.httpx.get", side_effect=fake_httpx_get):
            results = news.get_headlines()

        assert any(r.get("source") in ("bloomberg", "techcrunch") for r in results)
        error_items = [r for r in results if "error" in r]
        assert len(error_items) >= 1

    def test_deduplicates_by_url(self, monkeypatch):
        # All feeds return the same articles — only unique URLs should appear
        good_resp = _make_http_resp(SAMPLE_FEED_XML)

        with patch("integrations.news.httpx.get", return_value=good_resp):
            results = news.get_headlines()

        urls = [r.get("url") for r in results if "url" in r]
        assert len(urls) == len(set(urls))

    def test_uses_cache_within_ttl(self, tmp_path, monkeypatch):
        cached_articles = [{"title": "Cached", "url": "https://example.com/c",
                            "source": "bloomberg", "published": ""}]
        cache_file = tmp_path / "news_bloomberg.json"
        cache_file.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "articles": cached_articles,
        }))

        with patch("integrations.news.httpx.get") as mock_get:
            news._fetch_feed("bloomberg", news.FEEDS["bloomberg"])

        mock_get.assert_not_called()

    def test_refetches_when_cache_expired(self, tmp_path, monkeypatch):
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        cache_file = tmp_path / "news_bloomberg.json"
        cache_file.write_text(json.dumps({
            "fetched_at": old_time,
            "articles": [{"title": "Old", "url": "https://old.com", "source": "bloomberg"}],
        }))
        good_resp = _make_http_resp(SAMPLE_FEED_XML)

        with patch("integrations.news.httpx.get", return_value=good_resp) as mock_get:
            news._fetch_feed("bloomberg", news.FEEDS["bloomberg"])

        mock_get.assert_called_once()
