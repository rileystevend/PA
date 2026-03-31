"""
Google Calendar integration.

Read: all events for today (midnight to midnight local time).
Write: create events on the user's primary calendar.
"""

import logging
from datetime import datetime, timedelta, timezone

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


def create_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
) -> dict:
    """
    Create a calendar event on the user's primary calendar.

    Args:
        title: Event summary/title.
        start: ISO 8601 datetime string (e.g. "2026-03-29T14:00:00-05:00").
        end: ISO 8601 datetime string.
        description: Optional event description.
        location: Optional location string.
        attendees: Optional list of email addresses to invite.

    Returns:
        dict with {title, start, end, link, attendees} of the created event.
    """
    token = token_store.get_valid("google")
    creds = _credentials_from_token(token)
    service = build("calendar", "v3", credentials=creds)

    body = {
        "summary": title,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]

    event = service.events().insert(calendarId="primary", body=body).execute()

    return {
        "title": event.get("summary", ""),
        "start": event["start"].get("dateTime", ""),
        "end": event["end"].get("dateTime", ""),
        "link": event.get("htmlLink", ""),
        "attendees": [a.get("email", "") for a in event.get("attendees", [])],
    }


def _credentials_from_token(token: dict) -> Credentials:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
    )
