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
    def test_logs_in_on_first_call(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_EMAIL", "test@test.com")
        monkeypatch.setenv("STATESMAN_PASSWORD", "pass")
        mock_client = MagicMock()
        with patch.object(statesman_auth, "_login", return_value=mock_client) as mock_login:
            with patch.object(statesman_auth, "_is_alive", return_value=True):
                # First call: no existing session → login
                result = statesman_auth.get_session()
        mock_login.assert_called_once()
        assert result is mock_client

    def test_reuses_alive_session(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_EMAIL", "test@test.com")
        monkeypatch.setenv("STATESMAN_PASSWORD", "pass")
        existing = MagicMock()
        statesman_auth._session_client = existing
        with patch.object(statesman_auth, "_is_alive", return_value=True):
            with patch.object(statesman_auth, "_login") as mock_login:
                result = statesman_auth.get_session()
        mock_login.assert_not_called()
        assert result is existing

    def test_re_logins_when_session_dead(self, monkeypatch):
        monkeypatch.setenv("STATESMAN_EMAIL", "test@test.com")
        monkeypatch.setenv("STATESMAN_PASSWORD", "pass")
        old_client = MagicMock()
        new_client = MagicMock()
        statesman_auth._session_client = old_client
        with patch.object(statesman_auth, "_is_alive", return_value=False):
            with patch.object(statesman_auth, "_login", return_value=new_client):
                result = statesman_auth.get_session()
        assert result is new_client


class TestLogin:
    def test_raises_when_credentials_missing(self, monkeypatch):
        monkeypatch.delenv("STATESMAN_EMAIL", raising=False)
        monkeypatch.delenv("STATESMAN_PASSWORD", raising=False)
        with pytest.raises(RuntimeError, match="STATESMAN_EMAIL"):
            statesman_auth._login()

    def test_raises_on_401(self, monkeypatch):
        import httpx
        monkeypatch.setenv("STATESMAN_EMAIL", "bad@bad.com")
        monkeypatch.setenv("STATESMAN_PASSWORD", "wrong")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        with patch("integrations.statesman_auth.httpx.Client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Statesman login failed"):
                statesman_auth._login()


class TestInvalidate:
    def test_clears_session(self):
        statesman_auth._session_client = MagicMock()
        statesman_auth.invalidate()
        assert statesman_auth._session_client is None
