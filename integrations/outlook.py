"""
Microsoft Outlook integration via Graph API (read-only).

Email fetch: unread from last 24 hours, max 20.
Calendar fetch: today's events.
Returns subject + sender + bodyPreview only (no full body).
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from auth import token_store

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0/me"
MAX_MESSAGES = 20


def get_recent_emails() -> list[dict]:
    """
    Return up to 20 unread emails from the last 24 hours.
    Each item: {subject, from, snippet, date, id}
    """
    token = token_store.get_valid("microsoft")
    headers = _auth_headers(token)

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    params = {
        "$filter": f"isRead eq false and receivedDateTime ge {yesterday}",
        "$orderby": "receivedDateTime desc",
        "$top": MAX_MESSAGES,
        "$select": "id,subject,from,receivedDateTime,bodyPreview",
    }

    resp = httpx.get(f"{GRAPH_BASE}/messages", headers=headers, params=params, timeout=10)
    resp.raise_for_status()

    emails = []
    for msg in resp.json().get("value", []):
        sender = msg.get("from", {}).get("emailAddress", {})
        emails.append(
            {
                "id": msg["id"],
                "subject": msg.get("subject", "(no subject)"),
                "from": f"{sender.get('name', '')} <{sender.get('address', '')}>",
                "date": msg.get("receivedDateTime", ""),
                "snippet": msg.get("bodyPreview", ""),
            }
        )

    return emails


def get_todays_events() -> list[dict]:
    """
    Return all Outlook calendar events for today.
    Each item: {title, start, end, location}
    """
    token = token_store.get_valid("microsoft")
    headers = _auth_headers(token)

    now = datetime.now().astimezone()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    params = {
        "startDateTime": start_of_day.isoformat(),
        "endDateTime": end_of_day.isoformat(),
        "$select": "subject,start,end,location",
        "$orderby": "start/dateTime",
    }

    resp = httpx.get(
        f"{GRAPH_BASE}/calendarView", headers=headers, params=params, timeout=10
    )
    resp.raise_for_status()

    events = []
    for event in resp.json().get("value", []):
        events.append(
            {
                "title": event.get("subject", "(no title)"),
                "start": event.get("start", {}).get("dateTime", ""),
                "end": event.get("end", {}).get("dateTime", ""),
                "location": event.get("location", {}).get("displayName", ""),
            }
        )

    return events


def _auth_headers(token: dict) -> dict:
    access_token = token.get("access_token") or token.get("token", "")
    return {"Authorization": f"Bearer {access_token}"}
