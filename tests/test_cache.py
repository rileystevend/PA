"""Tests for integrations/cache.py"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from integrations.cache import load, save, CACHE_DIR


class TestLoadCache:
    def test_returns_data_within_ttl(self, tmp_path):
        cache_file = tmp_path / "test_source.json"
        cache_file.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": {"temp": 72},
        }))
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            result = load("test_source", ttl_minutes=10)
        assert result == {"temp": 72}

    def test_returns_none_when_expired(self, tmp_path):
        cache_file = tmp_path / "test_source.json"
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        cache_file.write_text(json.dumps({
            "fetched_at": old_time,
            "data": {"temp": 72},
        }))
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            result = load("test_source", ttl_minutes=10)
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path):
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            result = load("nonexistent", ttl_minutes=10)
        assert result is None

    def test_returns_none_on_corrupt_json(self, tmp_path):
        cache_file = tmp_path / "test_source.json"
        cache_file.write_text("not valid json {{{")
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            result = load("test_source", ttl_minutes=10)
        assert result is None

    def test_returns_list_data(self, tmp_path):
        cache_file = tmp_path / "test_source.json"
        cache_file.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": [{"title": "Article 1"}],
        }))
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            result = load("test_source", ttl_minutes=10)
        assert result == [{"title": "Article 1"}]


class TestSaveCache:
    def test_creates_file(self, tmp_path):
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            save("test_source", {"temp": 72})
        cache_file = tmp_path / "test_source.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["data"] == {"temp": 72}
        assert "fetched_at" in data

    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        with patch("integrations.cache.CACHE_DIR", nested):
            save("test_source", {"temp": 72})
        assert (nested / "test_source.json").exists()

    def test_overwrites_existing(self, tmp_path):
        with patch("integrations.cache.CACHE_DIR", tmp_path):
            save("test_source", {"temp": 72})
            save("test_source", {"temp": 85})
        data = json.loads((tmp_path / "test_source.json").read_text())
        assert data["data"]["temp"] == 85
