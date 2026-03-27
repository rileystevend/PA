"""
Integration test for the full morning briefing loop.

Wires up the actual agent/assistant.py briefing flow with all external
APIs mocked. Verifies tool dispatch, data assembly, and that Claude
receives all sources (or graceful error notes on failure).
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import assistant


MOCK_GMAIL = [{"subject": "Budget review", "from": "boss@co.com",
               "date": "Thu, 27 Mar 2026", "snippet": "Please review"}]
MOCK_OUTLOOK_MAIL = [{"subject": "Outlook msg", "from": "alice@co.com",
                      "date": "Thu, 27 Mar 2026", "snippet": "Hi"}]
MOCK_GCAL = [{"title": "Standup", "start": "2026-03-27T09:00:00", "end": "2026-03-27T09:30:00",
              "calendar": "Work", "location": "", "description": ""}]
MOCK_OUTLOOK_CAL = [{"title": "1:1", "start": "2026-03-27T14:00:00",
                     "end": "2026-03-27T14:30:00", "location": "Teams"}]
MOCK_WEATHER = {"location": "Austin", "temp_f": 72, "feels_like_f": 70,
                "description": "Partly cloudy", "humidity_pct": 55, "wind_mph": 8}
MOCK_NEWS = [{"title": "Austin flooding", "url": "https://statesman.com/1",
              "source": "statesman", "published": ""},
             {"title": "Markets up", "url": "https://bloomberg.com/1",
              "source": "bloomberg", "published": ""}]


def _collect_stream(coro):
    """Run an async generator and collect all yielded values."""
    async def _run():
        chunks = []
        async for chunk in coro:
            chunks.append(chunk)
        return chunks
    return asyncio.run(_run())


class TestBriefingFlow:
    def test_all_sources_passed_to_claude(self):
        """Full briefing: all sources fetched, Claude called with combined context."""
        captured_prompt = []

        async def fake_stream_claude(prompt):
            captured_prompt.append(prompt)
            yield f"data: {json.dumps({'text': 'Good morning!'})}\n\n"
            yield "data: [DONE]\n\n"

        with patch("agent.assistant.gmail.get_recent_emails", return_value=MOCK_GMAIL), \
             patch("agent.assistant.gcal.get_todays_events", return_value=MOCK_GCAL), \
             patch("agent.assistant.outlook.get_recent_emails", return_value=MOCK_OUTLOOK_MAIL), \
             patch("agent.assistant.outlook.get_todays_events", return_value=MOCK_OUTLOOK_CAL), \
             patch("agent.assistant.weather.get_weather", return_value=MOCK_WEATHER), \
             patch("agent.assistant.news.get_headlines", return_value=MOCK_NEWS), \
             patch("agent.assistant._stream_claude", side_effect=fake_stream_claude):
            chunks = _collect_stream(assistant._stream_briefing())

        assert len(chunks) > 0
        assert len(captured_prompt) == 1
        prompt = captured_prompt[0]
        # All sources should appear in the prompt
        assert "Gmail" in prompt
        assert "Google Calendar" in prompt
        assert "Outlook" in prompt
        assert "Weather" in prompt
        assert "News" in prompt

    def test_partial_failure_does_not_crash(self):
        """One source failing should still produce a briefing."""
        async def fake_stream_claude(prompt):
            yield f"data: {json.dumps({'text': 'Partial briefing'})}\n\n"
            yield "data: [DONE]\n\n"

        with patch("agent.assistant.gmail.get_recent_emails",
                   side_effect=RuntimeError("Gmail API error")), \
             patch("agent.assistant.gcal.get_todays_events", return_value=MOCK_GCAL), \
             patch("agent.assistant.outlook.get_recent_emails", return_value=MOCK_OUTLOOK_MAIL), \
             patch("agent.assistant.outlook.get_todays_events", return_value=MOCK_OUTLOOK_CAL), \
             patch("agent.assistant.weather.get_weather", return_value=MOCK_WEATHER), \
             patch("agent.assistant.news.get_headlines", return_value=MOCK_NEWS), \
             patch("agent.assistant._stream_claude", side_effect=fake_stream_claude):
            # Should not raise
            chunks = _collect_stream(assistant._stream_briefing())

        assert len(chunks) > 0

    def test_gmail_error_noted_in_prompt(self):
        """When Gmail fails, the prompt should note it as unavailable."""
        captured_prompt = []

        async def fake_stream_claude(prompt):
            captured_prompt.append(prompt)
            yield f"data: {json.dumps({'text': 'ok'})}\n\n"
            yield "data: [DONE]\n\n"

        with patch("agent.assistant.gmail.get_recent_emails",
                   side_effect=RuntimeError("token expired")), \
             patch("agent.assistant.gcal.get_todays_events", return_value=[]), \
             patch("agent.assistant.outlook.get_recent_emails", return_value=[]), \
             patch("agent.assistant.outlook.get_todays_events", return_value=[]), \
             patch("agent.assistant.weather.get_weather", return_value=MOCK_WEATHER), \
             patch("agent.assistant.news.get_headlines", return_value=[]), \
             patch("agent.assistant._stream_claude", side_effect=fake_stream_claude):
            _collect_stream(assistant._stream_briefing())

        assert "unavailable" in captured_prompt[0].lower()

    def test_sse_output_format(self):
        """Output should be valid SSE chunks ending with [DONE]."""
        async def fake_stream_claude(prompt):
            yield f"data: {json.dumps({'text': 'Hello'})}\n\n"
            yield "data: [DONE]\n\n"

        with patch("agent.assistant.gmail.get_recent_emails", return_value=[]), \
             patch("agent.assistant.gcal.get_todays_events", return_value=[]), \
             patch("agent.assistant.outlook.get_recent_emails", return_value=[]), \
             patch("agent.assistant.outlook.get_todays_events", return_value=[]), \
             patch("agent.assistant.weather.get_weather", return_value=MOCK_WEATHER), \
             patch("agent.assistant.news.get_headlines", return_value=[]), \
             patch("agent.assistant._stream_claude", side_effect=fake_stream_claude):
            chunks = _collect_stream(assistant._stream_briefing())

        assert any("data:" in c for c in chunks)
        assert any("[DONE]" in c for c in chunks)
