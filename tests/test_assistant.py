"""Tests for agent/assistant.py"""

from unittest.mock import MagicMock, patch

import pytest

from agent.assistant import is_briefing_intent, _dispatch_tool


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

    def test_raises_on_unknown_tool(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            _dispatch_tool("nonexistent_tool", {})
