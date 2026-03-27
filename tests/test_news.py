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


SAMPLE_FEED_XML = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/1</link>
      <pubDate>Thu, 27 Mar 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/2</link>
      <pubDate>Thu, 27 Mar 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


def _make_http_resp(text):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


class TestGetHeadlines:
    def test_returns_articles_from_all_sources(self, monkeypatch, tmp_path):
        mock_resp = _make_http_resp(SAMPLE_FEED_XML)
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        with patch("integrations.news.httpx.get", return_value=mock_resp):
            with patch("integrations.news.statesman_auth.get_session", return_value=mock_session):
                results = news.get_headlines()

        # 2 articles * 3 sources (statesman, bloomberg, techcrunch) but deduplicated
        assert len(results) > 0
        sources = {r.get("source") for r in results if "source" in r}
        assert "bloomberg" in sources or "techcrunch" in sources

    def test_returns_partial_when_one_source_fails(self, monkeypatch):
        good_resp = _make_http_resp(SAMPLE_FEED_XML)
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Statesman down")

        def fake_httpx_get(url, **kwargs):
            if "bloomberg" in url or "techcrunch" in url:
                return good_resp
            raise Exception("unexpected")

        with patch("integrations.news.httpx.get", side_effect=fake_httpx_get):
            with patch("integrations.news.statesman_auth.get_session", return_value=mock_session):
                results = news.get_headlines()

        # Should still have results from working feeds
        assert any(r.get("source") in ("bloomberg", "techcrunch") for r in results)
        # Failed source returns an error dict, not an exception
        error_items = [r for r in results if "error" in r]
        assert len(error_items) >= 1

    def test_deduplicates_by_url(self, monkeypatch):
        # Both bloomberg and techcrunch return the same URL
        dup_feed = SAMPLE_FEED_XML  # same articles
        good_resp = _make_http_resp(dup_feed)
        mock_session = MagicMock()
        mock_session.get.return_value = good_resp

        with patch("integrations.news.httpx.get", return_value=good_resp):
            with patch("integrations.news.statesman_auth.get_session", return_value=mock_session):
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
            with patch("integrations.news.statesman_auth.get_session"):
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
