"""Tests for integrations/outlook.py"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations import outlook


def _mock_token():
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
    return {"access_token": "bearer-tok", "refresh_token": "rt",
            "expires_on": future_ts}


class TestGetRecentEmails:
    def test_returns_emails_happy_path(self):
        graph_response = {
            "value": [
                {
                    "id": "msg1",
                    "subject": "Hello",
                    "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
                    "receivedDateTime": "2026-03-27T10:00:00Z",
                    "bodyPreview": "Hi there",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = graph_response
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.outlook.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.outlook.httpx.get", return_value=mock_resp):
                results = outlook.get_recent_emails()

        assert len(results) == 1
        assert results[0]["subject"] == "Hello"
        assert "alice@example.com" in results[0]["from"]
        assert results[0]["snippet"] == "Hi there"

    def test_returns_empty_list_when_no_messages(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.outlook.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.outlook.httpx.get", return_value=mock_resp):
                results = outlook.get_recent_emails()

        assert results == []

    def test_raises_when_token_missing(self):
        with patch("integrations.outlook.token_store.get_valid",
                   side_effect=RuntimeError("No microsoft token found")):
            with pytest.raises(RuntimeError, match="No microsoft token"):
                outlook.get_recent_emails()


class TestGetTodaysEvents:
    def test_returns_events_happy_path(self):
        graph_response = {
            "value": [
                {
                    "subject": "1:1 with manager",
                    "start": {"dateTime": "2026-03-27T14:00:00"},
                    "end": {"dateTime": "2026-03-27T14:30:00"},
                    "location": {"displayName": "Teams"},
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = graph_response
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.outlook.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.outlook.httpx.get", return_value=mock_resp):
                results = outlook.get_todays_events()

        assert len(results) == 1
        assert results[0]["title"] == "1:1 with manager"

    def test_returns_empty_list_when_no_events(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.outlook.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.outlook.httpx.get", return_value=mock_resp):
                results = outlook.get_todays_events()

        assert results == []

    @pytest.mark.integration
    def test_real_outlook_fetch(self):
        results = outlook.get_recent_emails()
        assert isinstance(results, list)
