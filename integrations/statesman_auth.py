"""
Austin American-Statesman session authentication.

The Statesman uses Arc Publishing. All articles are paywalled.
This module handles login and returns an authenticated httpx.Client.

Credentials come from env vars STATESMAN_EMAIL / STATESMAN_PASSWORD.

Arc Publishing login endpoint (verify via network tab if this breaks):
  POST https://www.statesman.com/identity/api/v1/signin
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.statesman.com/identity/api/v1/signin"
_session_client: httpx.Client | None = None


def get_session() -> httpx.Client:
    """
    Return an httpx.Client with a valid Statesman session cookie.
    Re-authenticates if the session has expired.
    """
    global _session_client
    if _session_client is not None and _is_alive(_session_client):
        return _session_client
    _session_client = _login()
    return _session_client


def invalidate() -> None:
    """Force re-authentication on the next get_session() call."""
    global _session_client
    _session_client = None


def _login() -> httpx.Client:
    email = os.environ.get("STATESMAN_EMAIL", "")
    password = os.environ.get("STATESMAN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "STATESMAN_EMAIL and STATESMAN_PASSWORD must be set in .env"
        )

    client = httpx.Client(follow_redirects=True)
    try:
        resp = client.post(
            LOGIN_URL,
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Statesman login succeeded")
        return client
    except httpx.HTTPStatusError as e:
        client.close()
        raise RuntimeError(
            f"Statesman login failed ({e.response.status_code}). "
            "Check STATESMAN_EMAIL / STATESMAN_PASSWORD."
        ) from e
    except httpx.RequestError as e:
        client.close()
        raise RuntimeError(f"Statesman login network error: {e}") from e


def _is_alive(client: httpx.Client) -> bool:
    """
    Probe whether the session is still valid by hitting a lightweight endpoint.
    Returns False if we get a redirect to the login page.
    """
    try:
        resp = client.get(
            "https://www.statesman.com/arcio/rss/",
            timeout=5,
            follow_redirects=False,
        )
        # A redirect to a login URL means the session expired
        if resp.is_redirect:
            location = resp.headers.get("location", "")
            if "signin" in location or "login" in location:
                logger.info("Statesman session expired, re-authenticating")
                return False
        return True
    except httpx.RequestError:
        return False
