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


class TestGetEmailThread:
    def _mock_full_message(self, subject="Re: Hello", body_text="Original message body"):
        import base64
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode().rstrip("=")
        return {
            "id": "msg123",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": subject},
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "To", "value": "bob@example.com"},
                    {"name": "Date", "value": "Thu, 27 Mar 2026 10:00:00 +0000"},
                ],
                "body": {"data": encoded},
            },
        }

    def test_returns_thread_with_body(self):
        mock_service = MagicMock()
        mock_service.users().messages().get().execute.return_value = self._mock_full_message()

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                result = gmail.get_email_thread("msg123")

        assert result["id"] == "msg123"
        assert result["subject"] == "Re: Hello"
        assert result["from"] == "alice@example.com"
        assert result["to"] == "bob@example.com"
        assert "Original message body" in result["body"]

    def test_body_capped_at_4000_chars(self):
        import base64
        long_body = "x" * 5000
        encoded = base64.urlsafe_b64encode(long_body.encode()).decode().rstrip("=")
        msg = {
            "id": "msg456",
            "payload": {
                "mimeType": "text/plain",
                "headers": [],
                "body": {"data": encoded},
            },
        }
        mock_service = MagicMock()
        mock_service.users().messages().get().execute.return_value = msg

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                result = gmail.get_email_thread("msg456")

        assert len(result["body"]) == 4000


class TestSendEmail:
    def test_returns_message_id_on_success(self):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {
            "id": "sent_msg_1",
            "threadId": "thread_abc",
        }

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                result = gmail.send_email(
                    to="recipient@example.com",
                    subject="Test subject",
                    body="Test body content",
                )

        assert result["message_id"] == "sent_msg_1"
        assert result["thread_id"] == "thread_abc"

    def test_send_called_with_raw_payload(self):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "x", "threadId": "y"}

        with patch("integrations.gmail.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gmail.build", return_value=mock_service):
                gmail.send_email("to@example.com", "Subject", "Body")

        call_kwargs = mock_service.users().messages().send.call_args
        assert "raw" in call_kwargs.kwargs.get("body", call_kwargs.args[0] if call_kwargs.args else {})


class TestExtractBody:
    def test_extracts_plain_text_body(self):
        import base64
        text = "Hello world"
        encoded = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        payload = {"mimeType": "text/plain", "body": {"data": encoded}}
        assert gmail._extract_body(payload) == "Hello world"

    def test_extracts_from_multipart(self):
        import base64
        text = "Nested plain text"
        encoded = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/html", "body": {"data": "ignored"}},
                {"mimeType": "text/plain", "body": {"data": encoded}},
            ],
        }
        assert gmail._extract_body(payload) == "Nested plain text"

    def test_returns_empty_when_no_body(self):
        payload = {"mimeType": "multipart/mixed", "parts": []}
        assert gmail._extract_body(payload) == ""
