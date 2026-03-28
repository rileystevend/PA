"""Tests for integrations/statesman_auth.py"""

from unittest.mock import MagicMock, patch

import pytest

from integrations import statesman_auth


@pytest.fixture(autouse=True)
def reset_session():
    statesman_auth._session_client = None
    yield
    statesman_auth._session_client = None


class TestGetSession:
    def test_builds_client_on_first_call(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_COOKIE_HNPAUTHS", "abc123")
        mock_client = MagicMock()
        with patch.object(statesman_auth, "_build_client", return_value=mock_client) as mock_build:
            with patch.object(statesman_auth, "_is_alive", return_value=True):
                result = statesman_auth.get_session()
        mock_build.assert_called_once()
        assert result is mock_client

    def test_reuses_alive_session(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_COOKIE_HNPAUTHS", "abc123")
        existing = MagicMock()
        statesman_auth._session_client = existing
        with patch.object(statesman_auth, "_is_alive", return_value=True):
            with patch.object(statesman_auth, "_build_client") as mock_build:
                result = statesman_auth.get_session()
        mock_build.assert_not_called()
        assert result is existing

    def test_rebuilds_when_session_dead(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_COOKIE_HNPAUTHS", "abc123")
        old_client = MagicMock()
        new_client = MagicMock()
        statesman_auth._session_client = old_client
        with patch.object(statesman_auth, "_is_alive", return_value=False):
            with patch.object(statesman_auth, "_build_client", return_value=new_client):
                result = statesman_auth.get_session()
        assert result is new_client


class TestBuildClient:
    def test_raises_when_no_cookies(self, monkeypatch):
        for name in statesman_auth._COOKIE_NAMES:
            monkeypatch.delenv(f"STATESMAN_COOKIE_{name.upper()}", raising=False)
        with pytest.raises(RuntimeError, match="No Statesman cookies found"):
            statesman_auth._build_client()

    def test_builds_client_with_cookies(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_COOKIE_HNPAUTHS", "token123")
        monkeypatch.setenv("STATESMAN_COOKIE_HNPAUTHP", "profile456")
        with patch("integrations.statesman_auth.httpx.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = statesman_auth._build_client()
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["cookies"]["hnpauths"] == "token123"
        assert call_kwargs["cookies"]["hnpauthp"] == "profile456"


class TestInvalidate:
    def test_clears_session(self):
        statesman_auth._session_client = MagicMock()
        statesman_auth.invalidate()
        assert statesman_auth._session_client is None
