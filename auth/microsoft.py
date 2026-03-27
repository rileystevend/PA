"""
Microsoft OAuth2 flow via MSAL.

Routes:
  GET /auth/microsoft          → redirect to Microsoft consent screen
  GET /auth/microsoft/callback → handle code, save token, redirect to /
"""

import os

import msal
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from auth import token_store

router = APIRouter()

SCOPES = ["Mail.Read", "Calendars.Read"]


def _build_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        os.environ["MICROSOFT_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ['MICROSOFT_TENANT_ID']}",
        client_credential=os.environ["MICROSOFT_CLIENT_SECRET"],
    )


def _redirect_uri() -> str:
    return "http://localhost:8000/auth/microsoft/callback"


router = APIRouter()


@router.get("/auth/microsoft")
def microsoft_auth():
    app = _build_app()
    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )
    return RedirectResponse(auth_url)


@router.get("/auth/microsoft/callback")
def microsoft_callback(code: str):
    app = _build_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )
    if "error" in result:
        raise RuntimeError(
            f"Microsoft auth failed: {result.get('error_description', result['error'])}"
        )
    token_store.save("microsoft", result)
    return RedirectResponse("/?connected=microsoft")
