"""Tests for integrations/gcal.py"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations import gcal


def _mock_token():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return {"token": "tok", "refresh_token": "rt",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "cid", "client_secret": "cs", "expiry": future}


def _mock_service(events=None):
    service = MagicMock()
    calendars = [{"id": "primary", "summary": "My Calendar"}]
    service.calendarList().list().execute.return_value = {"items": calendars}
    service.events().list().execute.return_value = {"items": events or []}
    return service


class TestGetTodaysEvents:
    def test_returns_events_happy_path(self):
        events = [
            {
                "summary": "Team standup",
                "start": {"dateTime": "2026-03-27T09:00:00-05:00"},
                "end": {"dateTime": "2026-03-27T09:30:00-05:00"},
                "location": "Zoom",
                "description": "",
            }
        ]
        service = _mock_service(events)

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                results = gcal.get_todays_events()

        assert len(results) == 1
        assert results[0]["title"] == "Team standup"
        assert results[0]["calendar"] == "My Calendar"

    def test_returns_empty_list_when_no_events(self):
        service = _mock_service(events=[])

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                results = gcal.get_todays_events()

        assert results == []

    def test_raises_when_token_missing(self):
        with patch("integrations.gcal.token_store.get_valid",
                   side_effect=RuntimeError("No google token found")):
            with pytest.raises(RuntimeError, match="No google token"):
                gcal.get_todays_events()

    @pytest.mark.integration
    def test_real_gcal_fetch(self):
        results = gcal.get_todays_events()
        assert isinstance(results, list)
