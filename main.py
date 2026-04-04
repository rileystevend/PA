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
from pydantic import BaseModel, Field, model_validator

load_dotenv()

from agent.assistant import stream_response
from auth.google import router as google_router

app = FastAPI(title="PA — Personal Assistant")
app.include_router(google_router)
# Outlook/Microsoft router excluded until MS app credentials are available

STATIC_DIR = Path(__file__).parent / "static"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")

_UNPROTECTED = {"/health", "/health/ingest", "/favicon.ico", "/manifest.json"}
_STATIC_EXTS = {".png", ".svg", ".ico", ".webmanifest"}


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


MAX_HISTORY_TURNS = 50
MAX_HISTORY_CHARS = 200_000


class ChatRequest(BaseModel):
    message: str
    history: list = []

    @model_validator(mode="after")
    def cap_history(self):
        self.history = self.history[:MAX_HISTORY_TURNS]
        total = sum(len(str(m.get("content", ""))) for m in self.history if isinstance(m, dict))
        if total > MAX_HISTORY_CHARS:
            self.history = self.history[-20:]
        return self


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


class HealthIngestRequest(BaseModel):
    """
    Accepts body composition data POSTed from an iOS Shortcut.
    Fields match what Apple Health HealthKit provides via Shortcuts.
    All fields optional — send whatever you have, but at least one field required.
    """
    weight_lbs: float | None = Field(None, ge=50, le=500)
    weight_kg: float | None = Field(None, ge=20, le=230)
    body_fat_pct: float | None = Field(None, ge=1, le=70)
    lean_mass_lbs: float | None = Field(None, ge=30, le=400)
    lean_mass_kg: float | None = Field(None, ge=15, le=180)


@app.post("/health/ingest")
def health_ingest(req: HealthIngestRequest):
    """
    Receive body composition data from an iOS Shortcut and cache it.
    This replaces the manual Apple Health XML export flow.
    The cached data is read by apple_health.get_summary().
    """
    from integrations import cache as health_cache

    data = {"source": "apple_health_shortcut"}

    # Normalize to lbs
    if req.weight_lbs is not None:
        data["weight_lbs"] = round(req.weight_lbs, 1)
    elif req.weight_kg is not None:
        data["weight_lbs"] = round(req.weight_kg * 2.20462, 1)

    if req.body_fat_pct is not None:
        data["body_fat_pct"] = round(req.body_fat_pct, 1)

    if req.lean_mass_lbs is not None:
        data["lean_mass_lbs"] = round(req.lean_mass_lbs, 1)
    elif req.lean_mass_kg is not None:
        data["lean_mass_lbs"] = round(req.lean_mass_kg * 2.20462, 1)

    # Reject empty payloads — don't overwrite good cached data with nothing
    if len(data) == 1:  # only "source" key
        return {"status": "error", "message": "At least one measurement field is required"}

    health_cache.save("health_bodycomp", data)
    return {"status": "ok", "saved": data}
