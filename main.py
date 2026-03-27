"""
PA — Personal Assistant Bot
FastAPI entry point.

Run with:
  uvicorn main:app --host 127.0.0.1 --reload

Visit http://localhost:8000 to open the chat UI.
First-time setup: connect your accounts at /auth/google and /auth/microsoft.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agent.assistant import stream_response
from auth.google import router as google_router
from auth.microsoft import router as microsoft_router

app = FastAPI(title="PA — Personal Assistant")
app.include_router(google_router)
app.include_router(microsoft_router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Stream Claude's response as Server-Sent Events.
    Frontend connects via EventSource and reads data: {...} chunks.
    """
    return StreamingResponse(
        stream_response(req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
