"""
Claude assistant — two modes:

Mode 1 (Morning Briefing):
  Detected by keyword. Fetches all sources in parallel, passes to Claude for
  summarization in a single call. Streams the response via SSE.

Mode 2 (Conversational):
  Standard agentic tool-use loop. Claude decides which tools to call.
  Independent tools dispatched concurrently. Uses AsyncAnthropic for true
  token-by-token streaming — no buffering, no double API calls.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import anthropic

from agent.tools import TOOLS
from integrations import gcal, gmail, news, weather

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic()
MODEL = "claude-sonnet-4-6"

BRIEFING_KEYWORDS = {"morning briefing", "morning brief", "good morning", "briefing"}


def is_briefing_intent(message: str) -> bool:
    lower = message.lower().strip()
    return any(kw in lower for kw in BRIEFING_KEYWORDS)


async def stream_response(message: str, history: list = None) -> AsyncGenerator[str, None]:
    """
    Main entry point. Detects intent and routes to the appropriate mode.
    Yields SSE-formatted strings. Errors are surfaced as SSE error events
    so the frontend can display them instead of hanging.
    """
    try:
        if is_briefing_intent(message):
            async for chunk in _stream_briefing():
                yield chunk
        else:
            async for chunk in _stream_conversational(message, history or []):
                yield chunk
    except Exception as e:
        logger.exception("stream_response error")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Mode 1 — Morning Briefing
# ---------------------------------------------------------------------------

async def _stream_briefing() -> AsyncGenerator[str, None]:
    """
    Fetch all sources in parallel, pass to Claude, stream the summary.
    """
    # Run all fetches concurrently; capture exceptions rather than crashing
    results = await asyncio.gather(
        asyncio.to_thread(gmail.get_recent_emails),
        asyncio.to_thread(gcal.get_todays_events),
        asyncio.to_thread(weather.get_weather),
        asyncio.to_thread(news.get_headlines),
        return_exceptions=True,
    )

    gmail_emails, gcal_events, wx, headlines = results

    # Build context block — include error notes for failed sources
    context_parts = []

    context_parts.append(_format_result("Gmail emails", gmail_emails))
    context_parts.append(_format_result("Google Calendar events", gcal_events))
    context_parts.append(_format_result("Weather", wx))
    context_parts.append(_format_result("News headlines", headlines))

    context = "\n\n".join(context_parts)

    prompt = (
        "You are a personal assistant. The user asked for their morning briefing. "
        "Here is all the data:\n\n"
        f"{context}\n\n"
        "Write a concise, friendly morning briefing. Lead with the weather and calendar, "
        "then highlight the most important emails (flag anything urgent), "
        "then give the top news headlines grouped by source. "
        "For each headline, format it as a markdown link using its url field: [Title](url). "
        "If a headline has no url, show the title as plain text. "
        "If any source was unavailable, mention it briefly. "
        "Use markdown formatting."
    )

    async for chunk in _stream_claude(prompt):
        yield chunk


def _format_result(label: str, result: Any) -> str:
    if isinstance(result, Exception):
        return f"**{label}:** unavailable ({type(result).__name__}: {result})"
    if isinstance(result, list) and len(result) == 0:
        return f"**{label}:** none"
    return f"**{label}:**\n{json.dumps(result, indent=2, default=str)}"


# ---------------------------------------------------------------------------
# Mode 2 — Conversational tool-use loop
# ---------------------------------------------------------------------------

async def _stream_conversational(message: str, history: list = None) -> AsyncGenerator[str, None]:
    """
    Agentic loop: Claude calls tools, we dispatch them (in parallel when independent),
    feed results back, repeat until Claude returns plain text.
    Uses AsyncAnthropic for true token-by-token streaming on the final turn.
    history is a list of {"role": "user"|"assistant", "content": "..."} dicts.
    """
    messages = list(history or []) + [{"role": "user", "content": message}]

    while True:
        async with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
            response = await stream.get_final_message()

        if response.stop_reason == "tool_use":
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            # Dispatch all tool calls concurrently
            tool_results = await asyncio.gather(
                *[asyncio.to_thread(_dispatch_tool, tc.name, tc.input) for tc in tool_calls],
                return_exceptions=True,
            )

            # Build tool result blocks
            result_blocks = []
            for tc, result in zip(tool_calls, tool_results):
                if isinstance(result, Exception):
                    content = f"Error: {result}"
                else:
                    content = json.dumps(result, default=str)
                result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": content,
                    }
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": result_blocks})

        else:
            yield "data: [DONE]\n\n"
            return


async def _stream_claude(prompt: str) -> AsyncGenerator[str, None]:
    """Stream a single Claude message and yield SSE chunks."""
    async with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'text': text})}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, inputs: dict) -> Any:
    source = inputs.get("source", "both")

    if name == "get_emails":
        return gmail.get_recent_emails()

    elif name == "get_calendar_events":
        return gcal.get_todays_events()

    elif name == "get_weather":
        return weather.get_weather()

    elif name == "get_news":
        all_headlines = news.get_headlines()
        if source == "all":
            return all_headlines
        return [h for h in all_headlines if h.get("source") == source]

    elif name == "get_email_thread":
        message_id = inputs.get("message_id", "")
        if not message_id:
            raise ValueError("message_id is required for get_email_thread")
        return gmail.get_email_thread(message_id)

    elif name == "send_email":
        to = inputs.get("to", "")
        subject = inputs.get("subject", "")
        body = inputs.get("body", "")
        if not all([to, subject, body]):
            raise ValueError("to, subject, and body are all required for send_email")
        return gmail.send_email(to=to, subject=subject, body=body)

    else:
        raise ValueError(f"Unknown tool: {name}")
