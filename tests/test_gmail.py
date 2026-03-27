"""Tests for integrations/gmail.py"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations import gmail


def _mock_token():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return {
        "token": "tok", "refresh_token": "rt",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid", "client_secret": "cs", "expiry": future,
    }


class TestGetRecentEmails:
    def test_returns_emails_happy_path(self):
        mock_messages = {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
        mock_detail = {
            "id": "msg1",
            "snippet": "Hey there",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Date", "value": "Thu, 27 Mar 2026 10:00:00 +0000"},
                ]
            },
        }

        mock_service = MagicMock()
        (mock_service.users().messages().list().execute
         .return_value) = mock_messages
        (mock_service.users().messages().get().execute
         .return_value) = mock_detail

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                results = gmail.get_recent_emails()

        assert len(results) == 2
        assert results[0]["subject"] == "Test Subject"
        assert results[0]["from"] == "sender@example.com"
        assert results[0]["snippet"] == "Hey there"

    def test_returns_empty_list_when_no_messages(self):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {}

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                results = gmail.get_recent_emails()

        assert results == []

    def test_raises_when_token_missing(self):
        with patch("integrations.gmail.token_store.get_valid",
                   side_effect=RuntimeError("No google token found")):
            with pytest.raises(RuntimeError, match="No google token"):
                gmail.get_recent_emails()

    @pytest.mark.integration
    def test_real_gmail_fetch(self):
        """Hits real Gmail API — requires valid ~/.pa/tokens/google.json"""
        results = gmail.get_recent_emails()
        assert isinstance(results, list)
