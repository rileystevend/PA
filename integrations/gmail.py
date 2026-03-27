"""
Gmail integration (read-only).

Fetch strategy: unread messages from last 24 hours, max 20.
Returns subject + sender + snippet only (no full body) to control token cost.
"""

import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from auth import token_store

logger = logging.getLogger(__name__)

MAX_MESSAGES = 20


def get_recent_emails() -> list[dict]:
    """
    Return up to 20 unread emails from the last 24 hours.
    Each item: {subject, from, snippet, date, id}
    """
    token = token_store.get_valid("google")
    creds = _credentials_from_token(token)
    service = build("gmail", "v1", credentials=creds)

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            q="is:unread newer_than:1d",
            maxResults=MAX_MESSAGES,
        )
        .execute()
    )

    messages = results.get("messages", [])
    if not messages:
        return []

    emails = []
    for msg in messages:
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata",
                 metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        emails.append(
            {
                "id": msg["id"],
                "subject": headers.get("Subject", "(no subject)"),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "snippet": detail.get("snippet", ""),
            }
        )

    return emails


def _credentials_from_token(token: dict) -> Credentials:
    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
    )
