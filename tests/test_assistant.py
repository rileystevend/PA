"""Tests for agent/assistant.py"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from agent.assistant import is_briefing_intent, _dispatch_tool, stream_response


class TestIsBriefingIntent:
    def test_detects_morning_briefing(self):
        assert is_briefing_intent("morning briefing") is True
        assert is_briefing_intent("Morning Briefing") is True
        assert is_briefing_intent("Give me my morning briefing") is True

    def test_detects_good_morning(self):
        assert is_briefing_intent("good morning") is True
        assert is_briefing_intent("Good morning!") is True

    def test_does_not_trigger_on_other_messages(self):
        assert is_briefing_intent("what's the weather?") is False
        assert is_briefing_intent("any emails from Bob?") is False
        assert is_briefing_intent("schedule a meeting") is False


class TestDispatchTool:
    def test_get_weather(self):
        mock_weather = {"location": "Austin", "temp_f": 72}
        with patch("agent.assistant.weather.get_weather", return_value=mock_weather):
            result = _dispatch_tool("get_weather", {})
        assert result["temp_f"] == 72

    def test_get_emails(self):
        gmail_emails = [{"subject": "Gmail msg"}]
        with patch("agent.assistant.gmail.get_recent_emails", return_value=gmail_emails):
            result = _dispatch_tool("get_emails", {})
        assert len(result) == 1
        assert result[0]["subject"] == "Gmail msg"

    def test_get_calendar_events(self):
        gcal_events = [{"title": "Standup"}]
        with patch("agent.assistant.gcal.get_todays_events", return_value=gcal_events):
            result = _dispatch_tool("get_calendar_events", {})
        assert len(result) == 1

    def test_get_news(self):
        headlines = [{"title": "Breaking", "source": "bloomberg"}]
        with patch("agent.assistant.news.get_headlines", return_value=headlines):
            result = _dispatch_tool("get_news", {"source": "all"})
        assert result[0]["title"] == "Breaking"

    def test_get_news_filtered_by_source(self):
        headlines = [
            {"title": "Tech", "source": "techcrunch"},
            {"title": "Markets", "source": "bloomberg"},
        ]
        with patch("agent.assistant.news.get_headlines", return_value=headlines):
            result = _dispatch_tool("get_news", {"source": "techcrunch"})
        assert len(result) == 1
        assert result[0]["source"] == "techcrunch"

    def test_get_email_thread(self):
        thread = {"id": "msg1", "subject": "Hello", "body": "Hi there"}
        with patch("agent.assistant.gmail.get_email_thread", return_value=thread):
            result = _dispatch_tool("get_email_thread", {"message_id": "msg1"})
        assert result["subject"] == "Hello"

    def test_get_email_thread_missing_id(self):
        with pytest.raises(ValueError, match="message_id is required"):
            _dispatch_tool("get_email_thread", {})

    def test_send_email(self):
        sent = {"message_id": "sent1", "thread_id": "t1"}
        with patch("agent.assistant.gmail.send_email", return_value=sent):
            result = _dispatch_tool("send_email", {
                "to": "a@b.com", "subject": "Hey", "body": "Body text"
            })
        assert result["message_id"] == "sent1"

    def test_send_email_missing_fields(self):
        with pytest.raises(ValueError, match="to, subject, and body"):
            _dispatch_tool("send_email", {"to": "a@b.com"})

    def test_raises_on_unknown_tool(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            _dispatch_tool("nonexistent_tool", {})


class TestStreamResponseErrorHandling:
    """Tests for FINDING-002 fix: SSE errors surfaced as error events instead of hanging."""

    def _collect(self, coro):
        async def _run():
            chunks = []
            async for chunk in coro:
                chunks.append(chunk)
            return chunks
        return asyncio.run(_run())

    def test_exception_yields_error_sse_event(self):
        """When _stream_briefing raises, stream_response yields an error SSE event."""
        async def boom():
            raise RuntimeError("No google token found")
            yield  # make it an async generator

        with patch("agent.assistant._stream_briefing", side_effect=boom):
            chunks = self._collect(stream_response("morning briefing"))

        # Should get an error event + DONE, not an empty stream
        assert any('"error"' in c for c in chunks)
        assert any("[DONE]" in c for c in chunks)

    def test_exception_error_event_contains_message(self):
        """The error SSE event contains the exception message."""
        async def boom():
            raise RuntimeError("No google token found")
            yield

        with patch("agent.assistant._stream_briefing", side_effect=boom):
            chunks = self._collect(stream_response("morning briefing"))

        error_chunks = [c for c in chunks if '"error"' in c]
        assert len(error_chunks) == 1
        payload = json.loads(error_chunks[0].replace("data: ", "").strip())
        assert "No google token found" in payload["error"]

    def test_done_sent_after_error(self):
        """[DONE] is always the last chunk even on error, so the frontend can clean up."""
        async def boom():
            raise ValueError("token expired")
            yield

        with patch("agent.assistant._stream_briefing", side_effect=boom):
            chunks = self._collect(stream_response("morning briefing"))

        assert chunks[-1].strip() == "data: [DONE]"
