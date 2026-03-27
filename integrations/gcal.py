"""
Google Calendar integration (read-only).

Fetch strategy: all events for today (midnight to midnight local time).
"""

import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from auth import token_store

logger = logging.getLogger(__name__)


def get_todays_events() -> list[dict]:
    """
    Return all calendar events for today.
    Each item: {title, start, end, calendar, location, description}
    """
    token = token_store.get_valid("google")
    creds = _credentials_from_token(token)
    service = build("calendar", "v3", credentials=creds)

    # Today's bounds in local time, converted to UTC for the API
    now = datetime.now().astimezone()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    time_min = start_of_day.isoformat()
    time_max = end_of_day.isoformat()

    calendars = service.calendarList().list().execute().get("items", [])
    events = []

    for cal in calendars:
        cal_events = (
            service.events()
            .list(
                calendarId=cal["id"],
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )
        for event in cal_events:
            start = event.get("start", {})
            end = event.get("end", {})
            events.append(
                {
                    "title": event.get("summary", "(no title)"),
                    "start": start.get("dateTime") or start.get("date", ""),
                    "end": end.get("dateTime") or end.get("date", ""),
                    "calendar": cal.get("summary", ""),
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                }
            )

    events.sort(key=lambda e: e["start"])
    return events


def _credentials_from_token(token: dict) -> Credentials:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
    )
