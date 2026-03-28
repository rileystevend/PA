"""
Shared OAuth token storage for Google and Microsoft providers.

Token files live at ~/.pa/tokens/{provider}.json
Handles load, save, expiry check, and refresh.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

TOKEN_DIR = Path.home() / ".pa" / "tokens"


def load(provider: str) -> dict | None:
    """Load token from disk. Returns None if not found."""
    path = TOKEN_DIR / f"{provider}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save(provider: str, token: dict) -> None:
    """Write token to disk."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    path = TOKEN_DIR / f"{provider}.json"
    path.write_text(json.dumps(token, indent=2))


def is_expired(token: dict) -> bool:
    """Return True if the token is expired or has no expiry info."""
    # Google: ISO string in "expiry"
    expiry_str = token.get("expiry")
    if expiry_str and isinstance(expiry_str, str):
        exp_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= exp_dt

    # Microsoft: unix timestamp in "expires_on"
    expires_on = token.get("expires_on")
    if expires_on is not None:
        return datetime.now(timezone.utc).timestamp() >= expires_on

    # No expiry info — assume expired
    return True


def refresh(provider: str, token: dict) -> dict:
    """
    Refresh an expired token. Saves the new token to disk and returns it.

    Google: uses google-auth-oauthlib Credentials.refresh()
    Microsoft: uses msal acquire_token_by_refresh_token()
    """
    if provider == "google":
        return _refresh_google(token)
    elif provider == "microsoft":
        return _refresh_microsoft(token)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_valid(provider: str) -> dict:
    """
    Load token, refresh if expired, return valid token.
    Raises RuntimeError if no token exists (user needs to OAuth).
    """
    token = load(provider)
    if token is None:
        raise RuntimeError(
            f"No {provider} token found. "
            f"Visit /auth/{provider} to connect your account."
        )
    if is_expired(token):
        token = refresh(provider, token)
    return token


def _refresh_google(token: dict) -> dict:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=token.get("token"),
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
    )
    creds.refresh(Request())
    new_token = {
        "token": creds.token,
        "refresh_token": creds.refresh_token or token.get("refresh_token"),
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "expiry": creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else None,
    }
    save("google", new_token)
    return new_token


def _refresh_microsoft(token: dict) -> dict:
    import msal

    app = msal.PublicClientApplication(
        os.environ["MICROSOFT_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ['MICROSOFT_TENANT_ID']}",
    )
    result = app.acquire_token_by_refresh_token(
        token["refresh_token"],
        scopes=["Mail.Read", "Calendars.Read"],
    )
    if "error" in result:
        raise RuntimeError(
            f"Microsoft token refresh failed: {result.get('error_description', result['error'])}"
        )
    new_token = {**token, **result}
    save("microsoft", new_token)
    return new_token
