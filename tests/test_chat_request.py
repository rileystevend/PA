"""Tests for ChatRequest validation in main.py"""

from main import ChatRequest, MAX_HISTORY_TURNS, MAX_HISTORY_CHARS


class TestChatRequestHistoryCap:
    def test_truncates_to_max_turns(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(100)]
        req = ChatRequest(message="hi", history=history)
        assert len(req.history) == MAX_HISTORY_TURNS

    def test_allows_short_history(self):
        history = [{"role": "user", "content": "hello"}]
        req = ChatRequest(message="hi", history=history)
        assert len(req.history) == 1

    def test_truncates_oversized_content(self):
        big = "x" * (MAX_HISTORY_CHARS + 1)
        history = [{"role": "user", "content": big}]
        req = ChatRequest(message="hi", history=history)
        assert len(req.history) <= 20

    def test_empty_history_ok(self):
        req = ChatRequest(message="hi")
        assert req.history == []
