"""
Austin American-Statesman session authentication.

Statesman now uses Hearst's OIDC identity platform (realm.hearstnp.com),
which requires a real browser flow. Instead of automating that, we read
session cookies that were manually extracted from Chrome after logging in.

How to extract cookies:
  1. Log in to statesman.com in Chrome
  2. Open DevTools → Application → Cookies → https://www.statesman.com
  3. Copy the values for the cookies listed in STATESMAN_COOKIES below
  4. Paste them into your .env file
  5. Session typically lasts days to weeks — re-extract when login fails

Required env vars:
  STATESMAN_COOKIE_<NAME>=<value>   one var per cookie (see .env.example)
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Cookie names to pull from env. Add more if needed after inspecting DevTools.
_COOKIE_NAMES = [
    "hnpauths",
    "hnpauthp",
    "hnpdiudpf1",
    "hnpdiudpf2",
]

_session_client: httpx.Client | None = None


def get_session() -> httpx.Client:
    """
    Return an httpx.Client with Statesman session cookies loaded from env.
    Re-creates the client if the session has expired.
    """
    global _session_client
    if _session_client is not None and _is_alive(_session_client):
        return _session_client
    _session_client = _build_client()
    return _session_client


def invalidate() -> None:
    """Force re-creation on the next get_session() call."""
    global _session_client
    _session_client = None


def _build_client() -> httpx.Client:
    cookies = {}
    for name in _COOKIE_NAMES:
        env_key = f"STATESMAN_COOKIE_{name.upper()}"
        value = os.environ.get(env_key, "")
        if value:
            cookies[name] = value

    if not cookies:
        raise RuntimeError(
            "No Statesman cookies found. Set STATESMAN_COOKIE_HNPAUTHS (and others) "
            "in .env. See integrations/statesman_auth.py for instructions."
        )

    client = httpx.Client(follow_redirects=True, cookies=cookies)
    logger.info("Statesman client built with %d cookie(s)", len(cookies))
    return client


def _is_alive(client: httpx.Client) -> bool:
    """
    Probe whether the session is still valid.
    Returns False if we get a redirect to the login page.
    """
    try:
        resp = client.get(
            "https://www.statesman.com/arcio/rss/",
            timeout=5,
            follow_redirects=False,
        )
        if resp.is_redirect:
            location = resp.headers.get("location", "")
            if "signin" in location or "login" in location or "realm" in location:
                logger.info("Statesman session expired — update cookies in .env")
                return False
        return True
    except httpx.RequestError:
        return False
