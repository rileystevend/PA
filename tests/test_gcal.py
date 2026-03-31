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


class TestCreateEvent:
    def test_creates_event_happy_path(self):
        fake_event = {
            "summary": "Lunch with Amy",
            "start": {"dateTime": "2026-03-30T12:00:00-05:00"},
            "end": {"dateTime": "2026-03-30T13:00:00-05:00"},
            "htmlLink": "https://calendar.google.com/event?eid=abc",
        }
        service = MagicMock()
        service.events().insert().execute.return_value = fake_event

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                result = gcal.create_event(
                    title="Lunch with Amy",
                    start="2026-03-30T12:00:00-05:00",
                    end="2026-03-30T13:00:00-05:00",
                )

        assert result["title"] == "Lunch with Amy"
        assert result["link"] == "https://calendar.google.com/event?eid=abc"
        service.events().insert.assert_called_with(
            calendarId="primary",
            body={
                "summary": "Lunch with Amy",
                "start": {"dateTime": "2026-03-30T12:00:00-05:00"},
                "end": {"dateTime": "2026-03-30T13:00:00-05:00"},
            },
        )

    def test_creates_event_with_description_and_location(self):
        fake_event = {
            "summary": "Dentist",
            "start": {"dateTime": "2026-03-30T10:00:00-05:00"},
            "end": {"dateTime": "2026-03-30T11:00:00-05:00"},
            "htmlLink": "https://calendar.google.com/event?eid=xyz",
        }
        service = MagicMock()
        service.events().insert().execute.return_value = fake_event

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                result = gcal.create_event(
                    title="Dentist",
                    start="2026-03-30T10:00:00-05:00",
                    end="2026-03-30T11:00:00-05:00",
                    description="Annual cleaning",
                    location="123 Main St",
                )

        call_body = service.events().insert.call_args[1]["body"]
        assert call_body["description"] == "Annual cleaning"
        assert call_body["location"] == "123 Main St"

    def test_creates_event_with_attendees(self):
        fake_event = {
            "summary": "Team sync",
            "start": {"dateTime": "2026-03-31T15:00:00-05:00"},
            "end": {"dateTime": "2026-03-31T16:00:00-05:00"},
            "htmlLink": "https://calendar.google.com/event?eid=inv",
            "attendees": [
                {"email": "alice@example.com"},
                {"email": "bob@example.com"},
            ],
        }
        service = MagicMock()
        service.events().insert().execute.return_value = fake_event

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                result = gcal.create_event(
                    title="Team sync",
                    start="2026-03-31T15:00:00-05:00",
                    end="2026-03-31T16:00:00-05:00",
                    attendees=["alice@example.com", "bob@example.com"],
                )

        call_body = service.events().insert.call_args[1]["body"]
        assert call_body["attendees"] == [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ]
        assert result["attendees"] == ["alice@example.com", "bob@example.com"]

    def test_no_attendees_key_when_none(self):
        fake_event = {
            "summary": "Solo work",
            "start": {"dateTime": "2026-03-31T10:00:00-05:00"},
            "end": {"dateTime": "2026-03-31T11:00:00-05:00"},
            "htmlLink": "https://calendar.google.com/event?eid=solo",
        }
        service = MagicMock()
        service.events().insert().execute.return_value = fake_event

        with patch("integrations.gcal.token_store.get_valid", return_value=_mock_token()):
            with patch("integrations.gcal.build", return_value=service):
                result = gcal.create_event(
                    title="Solo work",
                    start="2026-03-31T10:00:00-05:00",
                    end="2026-03-31T11:00:00-05:00",
                )

        call_body = service.events().insert.call_args[1]["body"]
        assert "attendees" not in call_body
        assert result["attendees"] == []

    def test_raises_when_token_missing(self):
        with patch("integrations.gcal.token_store.get_valid",
                   side_effect=RuntimeError("No google token found")):
            with pytest.raises(RuntimeError, match="No google token"):
                gcal.create_event(
                    title="Test", start="2026-03-30T10:00:00-05:00",
                    end="2026-03-30T11:00:00-05:00",
                )
