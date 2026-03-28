"""
Gmail integration — read and send.

Read strategy: unread messages from last 24 hours, max 20.
Returns subject + sender + snippet only (no full body) to control token cost.

Send: composes and sends via Gmail API. Always called after user confirmation
in the agentic loop — never fires autonomously.
"""

import base64
import logging
from email.mime.text import MIMEText

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


def get_email_thread(message_id: str) -> dict:
    """
    Return the full body of a specific email by message ID.
    Used so Claude can read the original before drafting a reply.
    Returns {id, subject, from, to, date, body}.
    """
    token = token_store.get_valid("google")
    creds = _credentials_from_token(token)
    service = build("gmail", "v1", credentials=creds)

    detail = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = {
        h["name"]: h["value"]
        for h in detail.get("payload", {}).get("headers", [])
    }

    body = _extract_body(detail.get("payload", {}))

    return {
        "id": message_id,
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "body": body[:4000],  # cap to control token cost
    }


def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail on behalf of the authenticated user.
    Returns {message_id, thread_id} on success.

    This must only be called after explicit user confirmation in the UI.
    The agentic loop enforces this — Claude drafts, user approves, then this fires.
    """
    token = token_store.get_valid("google")
    creds = _credentials_from_token(token)
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )

    logger.info("Email sent: id=%s to=%s subject=%s", result.get("id"), to, subject)
    return {"message_id": result.get("id"), "thread_id": result.get("threadId")}


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


def _credentials_from_token(token: dict) -> Credentials:
    return Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
    )
