"""
PA — Personal Assistant Bot
FastAPI entry point.

Local (default):
  uvicorn main:app --host 127.0.0.1 --reload

Tailscale (accessible from iPhone):
  uvicorn main:app --host 0.0.0.0 --port 8000

Visit http://localhost:8000 (or http://<tailscale-ip>:8000) to open the chat UI.
First-time setup: connect your accounts at /auth/google and /auth/microsoft.

Set ACCESS_TOKEN in .env to require a token on first visit (?token=...).
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agent.assistant import stream_response
from auth.google import router as google_router

app = FastAPI(title="PA — Personal Assistant")
app.include_router(google_router)
# Outlook/Microsoft router excluded until MS app credentials are available

STATIC_DIR = Path(__file__).parent / "static"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")

_UNPROTECTED = {"/health", "/favicon.ico"}
_STATIC_EXTS = {".png", ".svg", ".json", ".ico", ".webmanifest"}


@app.middleware("http")
async def token_auth(request: Request, call_next):
    """
    Optional token auth. Only active when ACCESS_TOKEN is set in .env.
    First visit: GET /?token=<token> sets a session cookie and redirects to /.
    Subsequent visits: cookie is checked automatically.
    Static assets and /health are always allowed.
    """
    if not ACCESS_TOKEN:
        return await call_next(request)

    path = request.url.path
    if path in _UNPROTECTED or Path(path).suffix in _STATIC_EXTS:
        return await call_next(request)

    # Valid session cookie → allow
    if request.cookies.get("pa_session") == ACCESS_TOKEN:
        return await call_next(request)

    # Token in query param → set cookie and redirect to clean URL
    token = request.query_params.get("token", "")
    if secrets.compare_digest(token.encode(), ACCESS_TOKEN.encode()):
        response = Response(status_code=302, headers={"Location": "/"})
        response.set_cookie(
            "pa_session", ACCESS_TOKEN,
            max_age=30 * 24 * 3600,
            httponly=True,
            samesite="lax",
        )
        return response

    return Response(
        "Unauthorized. Add ?token=YOUR_TOKEN to the URL on first visit.",
        status_code=401,
        media_type="text/plain",
    )


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


class ChatRequest(BaseModel):
    message: str
    history: list = []


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Stream Claude's response as Server-Sent Events.
    Frontend connects via EventSource and reads data: {...} chunks.
    """
    return StreamingResponse(
        stream_response(req.message, req.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/icon-180.png")
def icon_180():
    return FileResponse(STATIC_DIR / "icon-180.png", media_type="image/png")


@app.get("/icon-512.png")
def icon_512():
    return FileResponse(STATIC_DIR / "icon-512.png", media_type="image/png")


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/health")
def health():
    return {"status": "ok"}
