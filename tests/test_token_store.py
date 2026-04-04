"""Tests for auth/token_store.py"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auth import token_store


@pytest.fixture(autouse=True)
def tmp_token_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(token_store, "TOKEN_DIR", tmp_path)


def _write_token(tmp_path, provider, data):
    (tmp_path / f"{provider}.json").write_text(json.dumps(data))


class TestLoad:
    def test_returns_none_when_missing(self):
        assert token_store.load("google") is None

    def test_returns_token_when_exists(self, tmp_path):
        _write_token(tmp_path, "google", {"token": "abc"})
        result = token_store.load("google")
        assert result == {"token": "abc"}


class TestSave:
    def test_creates_file(self, tmp_path):
        token_store.save("google", {"token": "xyz"})
        path = tmp_path / "google.json"
        assert path.exists()
        assert json.loads(path.read_text())["token"] == "xyz"

    def test_overwrites_existing(self, tmp_path):
        _write_token(tmp_path, "google", {"token": "old"})
        token_store.save("google", {"token": "new"})
        assert token_store.load("google")["token"] == "new"

    def test_sets_restrictive_permissions(self, tmp_path):
        token_store.save("google", {"token": "secret"})
        path = tmp_path / "google.json"
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


class TestIsExpired:
    def test_expired_iso_string(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert token_store.is_expired({"expiry": past}) is True

    def test_not_expired_iso_string(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert token_store.is_expired({"expiry": future}) is False

    def test_missing_expiry_returns_true(self):
        assert token_store.is_expired({}) is True

    def test_expired_unix_timestamp(self):
        past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        assert token_store.is_expired({"expires_on": past_ts}) is True

    def test_not_expired_unix_timestamp(self):
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        assert token_store.is_expired({"expires_on": future_ts}) is False


class TestGetValid:
    def test_raises_when_no_token(self):
        with pytest.raises(RuntimeError, match="No google token"):
            token_store.get_valid("google")

    def test_returns_token_when_not_expired(self, tmp_path):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        _write_token(tmp_path, "google", {"token": "valid", "expiry": future})
        result = token_store.get_valid("google")
        assert result["token"] == "valid"

    def test_refreshes_when_expired(self, tmp_path):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        old_token = {"token": "old", "expiry": past, "refresh_token": "rt"}
        _write_token(tmp_path, "google", old_token)
        fresh = {"token": "new", "expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        with patch.object(token_store, "refresh", return_value=fresh) as mock_refresh:
            result = token_store.get_valid("google")
        mock_refresh.assert_called_once_with("google", old_token)
        assert result["token"] == "new"

    def test_raises_unknown_provider(self):
        with pytest.raises(ValueError):
            token_store.refresh("unknown", {})
