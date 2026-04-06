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
        with patch("agent.assistant.gcal.get_events", return_value=gcal_events):
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

    def test_create_calendar_event(self):
        created = {"title": "Lunch", "start": "2026-03-30T12:00:00-05:00",
                   "end": "2026-03-30T13:00:00-05:00", "link": "https://cal/abc"}
        with patch("agent.assistant.gcal.create_event", return_value=created):
            result = _dispatch_tool("create_calendar_event", {
                "title": "Lunch", "start": "2026-03-30T12:00:00-05:00",
                "end": "2026-03-30T13:00:00-05:00",
            })
        assert result["title"] == "Lunch"
        assert result["link"] == "https://cal/abc"

    def test_create_calendar_event_missing_fields(self):
        with pytest.raises(ValueError, match="title, start, and end"):
            _dispatch_tool("create_calendar_event", {"title": "Lunch"})

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

    def test_search_ireland_rentals(self):
        listings = [{"title": "2 Bed Apt, Bray", "price_per_month": 1800, "url": "https://daft.ie/1"}]
        with patch("agent.assistant.daft.search_rentals", return_value=listings):
            result = _dispatch_tool("search_ireland_rentals", {})
        assert result == listings

    def test_search_ireland_rentals_passes_params(self):
        with patch("agent.assistant.daft.search_rentals", return_value=[]) as mock_fn:
            _dispatch_tool("search_ireland_rentals", {"min_beds": 3, "max_price": 3000})
        mock_fn.assert_called_once_with(min_beds=3, max_price=3000)

    def test_get_health_summary(self):
        garmin_data = {"source": "garmin", "sleep_hours": 7.2, "steps": 8500}
        bodycomp_data = {"source": "apple_health", "weight_lbs": 180.0, "body_fat_pct": 18.5}
        with patch("agent.assistant.garmin.get_summary", return_value=garmin_data), \
             patch("agent.assistant.apple_health.get_summary", return_value=bodycomp_data):
            result = _dispatch_tool("get_health_summary", {})
        assert result["garmin"]["sleep_hours"] == 7.2
        assert result["body_composition"]["body_fat_pct"] == 18.5

    def test_get_health_summary_partial_failure(self):
        garmin_data = {"source": "garmin", "error": "Garmin unavailable"}
        bodycomp_data = {"source": "apple_health", "weight_lbs": 180.0}
        with patch("agent.assistant.garmin.get_summary", return_value=garmin_data), \
             patch("agent.assistant.apple_health.get_summary", return_value=bodycomp_data):
            result = _dispatch_tool("get_health_summary", {})
        assert "error" in result["garmin"]
        assert result["body_composition"]["weight_lbs"] == 180.0

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


class TestStreamConversationalLoopCeiling:
    """Tests for the 10-iteration ceiling on the tool-use loop."""

    def _collect(self, coro):
        async def _run():
            chunks = []
            async for chunk in coro:
                chunks.append(chunk)
            return chunks
        return asyncio.run(_run())

    def test_loop_ceiling_yields_error_after_10_iterations(self):
        """If Claude keeps returning tool_use, loop errors out after 10 turns."""
        from unittest.mock import AsyncMock, MagicMock
        from agent.assistant import _stream_conversational

        fake_tool_block = MagicMock()
        fake_tool_block.type = "tool_use"
        fake_tool_block.name = "get_weather"
        fake_tool_block.input = {}
        fake_tool_block.id = "tool_abc"

        fake_final_msg = MagicMock()
        fake_final_msg.stop_reason = "tool_use"
        fake_final_msg.content = [fake_tool_block]

        async def empty_text_stream():
            return
            yield

        def make_stream():
            stream = AsyncMock()
            stream.__aenter__ = AsyncMock(return_value=stream)
            stream.__aexit__ = AsyncMock(return_value=False)
            stream.text_stream = empty_text_stream()
            stream.get_final_message = AsyncMock(return_value=fake_final_msg)
            return stream

        with patch("agent.assistant.client.messages.stream", side_effect=lambda **kw: make_stream()), \
             patch("agent.assistant._dispatch_tool", return_value={"temp_f": 72}):
            chunks = self._collect(_stream_conversational("what's the weather?"))

        error_chunks = [c for c in chunks if '"error"' in c]
        assert len(error_chunks) == 1
        payload = json.loads(error_chunks[0].replace("data: ", "").strip())
        assert "maximum iterations" in payload["error"]
        assert chunks[-1].strip() == "data: [DONE]"


class TestStreamConversationalRetry:
    """Tests for retry on 429/529 Anthropic API errors."""

    def _collect(self, coro):
        async def _run():
            chunks = []
            async for chunk in coro:
                chunks.append(chunk)
            return chunks
        return asyncio.run(_run())

    def test_retries_on_529_overloaded(self):
        """A 529 overloaded error retries and succeeds on the second attempt."""
        from unittest.mock import AsyncMock, MagicMock
        from anthropic import APIStatusError
        from agent.assistant import _stream_conversational

        fake_final_msg = MagicMock()
        fake_final_msg.stop_reason = "end_turn"
        fake_final_msg.content = [MagicMock(text="Hello", type="text")]

        async def text_stream():
            yield "Hello"

        call_count = [0]

        def make_stream(**kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise APIStatusError(
                    message="Overloaded",
                    response=MagicMock(status_code=529, headers={}),
                    body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
                )
            stream = AsyncMock()
            stream.__aenter__ = AsyncMock(return_value=stream)
            stream.__aexit__ = AsyncMock(return_value=False)
            stream.text_stream = text_stream()
            stream.get_final_message = AsyncMock(return_value=fake_final_msg)
            return stream

        with patch("agent.assistant.client.messages.stream", side_effect=make_stream), \
             patch("agent.assistant.asyncio.sleep", new_callable=AsyncMock):
            chunks = self._collect(_stream_conversational("hi"))

        text_chunks = [c for c in chunks if '"text"' in c and "Retrying" not in c]
        assert any("Hello" in c for c in text_chunks)
        assert call_count[0] == 2  # first failed, second succeeded

    def test_gives_up_after_max_retries(self):
        """After MAX_RETRIES 529 errors, the error propagates to stream_response."""
        from unittest.mock import AsyncMock
        from anthropic import APIStatusError
        from agent.assistant import stream_response

        def always_fail(**kw):
            raise APIStatusError(
                message="Overloaded",
                response=MagicMock(status_code=529, headers={}),
                body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
            )

        with patch("agent.assistant.client.messages.stream", side_effect=always_fail), \
             patch("agent.assistant.asyncio.sleep", new_callable=AsyncMock):
            chunks = []
            async def collect():
                async for c in stream_response("hi"):
                    chunks.append(c)
            asyncio.run(collect())

        # Should get an error SSE event (from the outer try/except in stream_response)
        assert any('"error"' in c for c in chunks)
        assert any("[DONE]" in c for c in chunks)
