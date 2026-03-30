# PA — Personal Assistant Bot

Claude-powered personal assistant integrating Gmail, Google Calendar, Outlook, local news, and weather. Runs as a web chat interface.

## Project Overview

A conversational web-based assistant that can read/send email, manage calendar events, fetch Austin-area news, and check weather. The user interacts via a browser chat UI backed by a FastAPI server running the Claude agentic loop.

**V1 focus:** Morning briefing (read-only). One query returns today's calendar, important emails, weather, and top headlines. Claude streams the response word-by-word.

## Tech Stack

- **Runtime:** Python 3.12+
- **AI:** Anthropic Claude API (`claude-sonnet-4-6`)
- **Web framework:** FastAPI + Uvicorn
- **Frontend:** Vanilla HTML/JS chat UI (served by FastAPI), streaming via SSE
- **Email/Calendar:** Google Gmail API, Google Calendar API, Microsoft Graph API (Outlook)
- **Weather:** OpenWeatherMap API
- **News:** RSS feeds via `feedparser` + `httpx` (Google News, KXAN, Bloomberg, TechCrunch)
- **Rentals:** Daft.ie gateway API via `httpx` (Ireland rental search)

## Environment Variables

```
ANTHROPIC_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=
OPENWEATHER_API_KEY=
USER_LOCATION=Austin,TX,US   # passed to OpenWeatherMap
ACCESS_TOKEN=               # optional: require token on first visit (?token=...)
GARMIN_EMAIL=               # Garmin Connect email for health data
GARMIN_PASSWORD=            # Garmin Connect password (first login only, then garth caches session)
APPLE_HEALTH_EXPORT_PATH=   # path to Apple Health XML export (default: ~/.pa/health/export.xml)
```

Store in `.env` (never commit). Load with `python-dotenv`.

## Project Structure

```
PA/
├── CLAUDE.md
├── .env                         # secrets — gitignored
├── .env.example                 # template to commit
├── requirements.txt
├── main.py                      # FastAPI app entry point
├── agent/
│   ├── __init__.py
│   ├── assistant.py             # Claude agentic loop + parallel tool dispatch
│   └── tools.py                 # tool schemas for Claude API tool use
├── integrations/
│   ├── gmail.py                 # Gmail read via google-api-python-client
│   ├── gcal.py                  # Google Calendar read
│   ├── outlook.py               # Outlook mail + calendar via Microsoft Graph
│   ├── weather.py               # OpenWeatherMap current + forecast (10 min cache)
│   ├── news.py                  # RSS feed reader (feedparser), 15 min cache
│   ├── daft.py                  # Daft.ie rental search (gateway API), 30 min cache
│   ├── garmin.py                # Garmin Connect health data (garminconnect), 30 min cache
│   ├── apple_health.py          # Apple Health body composition (XML export), 24h cache
│   └── cache.py                 # Shared persistent file cache helper
├── auth/
│   ├── token_store.py           # Shared: load/save/is_expired for OAuth tokens
│   ├── google.py                # Google OAuth2 flow (calls token_store)
│   └── microsoft.py             # Microsoft OAuth2 flow via MSAL (calls token_store)
├── static/
│   └── index.html               # chat UI (SSE streaming support)
├── cache/                       # persistent file cache (gitignored)
│   ├── weather.json             # OpenWeatherMap cache
│   └── news_{source}.json       # RSS feed caches
└── tests/
    ├── test_assistant.py
    ├── test_briefing_integration.py  # full briefing loop with mocked APIs
    ├── test_gmail.py
    ├── test_gcal.py
    ├── test_outlook.py
    ├── test_weather.py
    ├── test_news.py
    ├── test_daft.py
    └── test_token_store.py
```

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web server — localhost ONLY (binds to 127.0.0.1 for security)
uvicorn main:app --host 127.0.0.1 --reload

# Run tests
pytest

# Run a single test file
pytest tests/test_gmail.py -v

# Run integration tests (hits real APIs — use sparingly)
pytest -m integration
```

## Testing

- Unit tests live in `tests/` mirroring the module structure
- Mock all external API calls — no real emails, events, or HTTP requests during unit tests
- Use `pytest-mock` / `unittest.mock` for patching
- `tests/test_briefing_integration.py` — wires up the full agentic loop with all APIs mocked; tests tool dispatch, JSON schema correctness, and response formatting
- Integration tests (hitting real APIs) are tagged `@pytest.mark.integration` and skipped by default
- Run integration tests manually: `pytest -m integration`
- Never send real emails or modify real calendar events during tests

## Key Patterns

### Claude Tool Use (Two Modes)

**Mode 1 — Morning Briefing (direct fetch):**

"Morning briefing" intent is detected before hitting Claude. All 5 sources are fetched in parallel directly (`asyncio.gather()`), results assembled, then passed to Claude in a single message for summarization. No tool-use loop — Claude just writes.

```
"morning briefing" detected
    │
    ▼
asyncio.gather(*coroutines, return_exceptions=True)
    │
    ├── Each result: if isinstance(result, Exception)
    │       → log it, include "Source unavailable" note in context
    │
    ▼
Single Claude API call: "Here is all the data. Write a briefing."
    │
    ▼
Stream response via SSE
```

**Partial failure handling:** Always use `return_exceptions=True` in `asyncio.gather()`. Check each result — if it's an exception, include a note in the Claude context: "Gmail: unavailable (fetch failed)". Claude should mention which sources were unavailable in the briefing. Never let one failing source crash the whole briefing.

This is faster, cheaper (fewer Claude round-trips), and simpler to debug.

**Mode 2 — Conversational (tool-use loop):**

For all other queries, use the standard agentic tool loop:

```
User message
    │
    ▼
Claude API (with tool definitions)
    │
    ├── tool_use blocks returned?
    │       │
    │       ▼ YES
    │   Detect independent tools → asyncio.gather() parallel fetch
    │   Feed all results back to Claude
    │   Repeat loop
    │
    └── plain text response?
            │
            ▼
        Stream via SSE to web UI
```

**Streaming:** Use `client.messages.stream()` from the Anthropic SDK. Return a FastAPI `StreamingResponse` with `text/event-stream` content type. The frontend connects via `EventSource`.

### Web API
- `POST /chat` — accepts `{"message": "..."}`, returns SSE stream
- `GET /auth/google` — starts Google OAuth flow
- `GET /auth/google/callback` — handles Google redirect, saves token
- `GET /auth/microsoft` — starts Microsoft OAuth flow
- `GET /auth/microsoft/callback` — handles Microsoft redirect, saves token
- `GET /` — serves the chat UI (`static/index.html`)

**Security:** Server binds to `127.0.0.1` only (`--host 127.0.0.1`). Never bind to `0.0.0.0` — the chat endpoint has access to your email and calendar.

### Token Storage (`auth/token_store.py`)

Shared module used by both `auth/google.py` and `auth/microsoft.py`. Handles:
- `load(provider)` — reads `~/.pa/tokens/{provider}.json`
- `save(provider, token)` — writes token to disk
- `is_expired(token)` — checks expiry timestamp
- `refresh(provider, token)` — refreshes the token using the provider-specific method:
  - Google: `google.oauth2.credentials.Credentials.refresh(Request())`
  - Microsoft: `msal.PublicClientApplication.acquire_token_by_refresh_token()`
  - After refresh, calls `save(provider, new_token)` automatically

Both auth modules call `token_store.refresh()` when `is_expired()` returns True. Tokens expire in ~1 hour. This is non-negotiable — without refresh, the app silently stops working.

### Rate Limits & Caching
- Gmail: 250 quota units/user/second
- Graph API: 10,000 requests/10 minutes per app
- OpenWeatherMap free tier: 60 calls/minute — **cache 10 minutes**
- RSS feeds: **cache 15 minutes** — no re-fetch within window
- Email and calendar: no cache — must be fresh

**Persistent file cache** (`~/.pa/cache/`): Weather and news caches survive server restarts. Format: `{source}.json` containing `{data: ..., fetched_at: ISO8601}`. On load, check if `fetched_at` is within TTL — use cached data if yes, re-fetch and overwrite if no. This prevents unnecessary API calls during development restarts.

## Integrations

### Gmail
- Library: `google-api-python-client`, `google-auth-oauthlib`
- Scopes (v1, read-only): `gmail.readonly`
- Key methods: `users.messages.list`, `users.messages.get`
- **Fetch strategy:** Unread messages from the last 24 hours, max 20, sorted by date descending
- Query: `is:unread newer_than:1d`
- Pass subject + sender + snippet to Claude (not full body) to control token cost

### Google Calendar
- Library: `google-api-python-client`
- Scopes (v1, read-only): `calendar.readonly`
- Key methods: `calendarList.list`, `events.list`
- **Fetch strategy:** Events for today (midnight to midnight local time)

### Outlook (Microsoft Graph)
- Library: `msal`, `httpx`
- Scopes (v1, read-only): `Mail.Read`, `Calendars.Read`
- Base URL: `https://graph.microsoft.com/v1.0/me/`
- **Email fetch strategy:** Unread from last 24 hours, max 20
- Filter: `$filter=isRead eq false and receivedDateTime ge {yesterday_iso}`
- Pass subject + sender + bodyPreview to Claude (not full body)

### Weather (OpenWeatherMap)
- Library: `httpx`
- Endpoint: `https://api.openweathermap.org/data/2.5/weather` (current) + `/forecast` (5-day)
- Location: from `USER_LOCATION` env var
- Cache 10 minutes in memory

### News (RSS)
- Library: `feedparser`, `httpx`
- Sources:
  - Google News Austin: `https://news.google.com/rss/search?q=Austin+Texas&hl=en-US&gl=US&ceid=US:en`
  - KXAN Austin: `https://www.kxan.com/feed/` (local TV news — original Austin reporting)
  - Bloomberg: `https://feeds.bloomberg.com/markets/news.rss`
  - TechCrunch: `https://techcrunch.com/feed/`
- Cache 15 minutes in memory
- Deduplicate by URL across all sources
- If one feed fails, return the others (partial result, not an error)
- Stale cache note: if you see `~/.pa/cache/news_statesman.json`, it's safe to delete — `rm -f ~/.pa/cache/news_statesman.json`

### Ireland Rentals (Daft.ie)
- Library: `httpx`
- Method: Daft.ie internal gateway API (`gateway.daft.ie`) with text-based location search
- Default areas: Bray, Greystones, Dún Laoghaire, Sandyford (Dublin/Wicklow corridor)
- Default filters: 2+ beds, max €2,800/month
- Cache 30 minutes in memory
- Fallback: returns a `fallback_note` sentinel if all areas fail (site may have changed structure)
- Tool name: `search_ireland_rentals` (params: `min_beds`, `max_price`)

## What Claude Should Know

- This is an agentic app — Claude drives tool calls in a loop until the task is done
- Never expose raw API credentials in tool responses or conversation context
- V1 is read-only — no email sending, no calendar writes. Do not use write scopes.
- Always confirm before sending email or creating/deleting calendar events (Phase 2+)
- The web UI is single-user (no auth layer on /chat needed for MVP — but server is localhost-only)

## NOT in Scope (v1)

- Sending or replying to email (Phase 2)
- Creating or modifying calendar events (Phase 3)
- Proactive scheduled briefings / push notifications (Phase 4)
- Multi-user support
- Deployment / hosting (runs locally only)
- Mobile interface

## Design System
Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.
