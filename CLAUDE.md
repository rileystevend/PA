# PA — Personal Assistant Bot

Claude-powered personal assistant integrating Gmail, Google Calendar, Outlook, local news, and weather. Runs as a web chat interface.

## Project Overview

A conversational web-based assistant that can read/send email, manage calendar events, fetch Austin-area news, and check weather. The user interacts via a browser chat UI backed by a FastAPI server running the Claude agentic loop.

## Tech Stack

- **Runtime:** Python 3.12+
- **AI:** Anthropic Claude API (`claude-sonnet-4-6`)
- **Web framework:** FastAPI + Uvicorn
- **Frontend:** Vanilla HTML/JS chat UI (served by FastAPI)
- **Email/Calendar:** Google Gmail API, Google Calendar API, Microsoft Graph API (Outlook)
- **Weather:** OpenWeatherMap API
- **News:** RSS feeds via `feedparser` (Austin American-Statesman, Bloomberg, TechCrunch)

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
STATESMAN_EMAIL=
STATESMAN_PASSWORD=
```

Store in `.env` (never commit). Load with `python-dotenv`.

## Project Structure

```
PA/
├── CLAUDE.md
├── .env                        # secrets — gitignored
├── .env.example                # template to commit
├── requirements.txt
├── main.py                     # FastAPI app entry point (uvicorn main:app)
├── agent/
│   ├── __init__.py
│   ├── assistant.py            # Claude agentic loop + tool dispatch
│   └── tools.py                # tool schemas for Claude API tool use
├── integrations/
│   ├── gmail.py                # Gmail read/send via google-api-python-client
│   ├── gcal.py                 # Google Calendar CRUD
│   ├── outlook.py              # Outlook mail + calendar via Microsoft Graph
│   ├── weather.py              # OpenWeatherMap current + forecast
│   └── news.py                 # RSS feed reader (feedparser)
├── auth/
│   ├── google.py               # OAuth2 flow for Google
│   └── microsoft.py            # OAuth2 flow for Microsoft (MSAL)
├── static/
│   └── index.html              # chat UI
└── tests/
    ├── test_gmail.py
    ├── test_gcal.py
    ├── test_outlook.py
    ├── test_weather.py
    ├── test_news.py
    └── test_assistant.py
```

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web server (http://localhost:8000)
uvicorn main:app --reload

# Run tests
pytest

# Run a single test file
pytest tests/test_gmail.py -v

# Run integration tests (hits real APIs — use sparingly)
pytest -m integration
```

## Testing

- Unit tests live in `tests/` mirroring the `integrations/` and `agent/` structure
- Mock all external API calls — no real emails, events, or API requests during unit tests
- Use `pytest-mock` / `unittest.mock` for patching
- Integration tests are tagged `@pytest.mark.integration` and skipped by default in CI
- Run integration tests manually: `pytest -m integration`
- Never send real emails or modify real calendar events during tests

## Key Patterns

### Claude Tool Use (Agentic Loop)
All integrations are exposed as Claude API tools defined in `agent/tools.py`. The loop in `agent/assistant.py`:
1. Sends user message + tool definitions to Claude
2. If Claude returns `tool_use` blocks, dispatch to the matching integration
3. Feed tool results back to Claude
4. Repeat until Claude returns a plain `text` response
5. Stream or return the final response to the web UI

### Web API
- `POST /chat` — accepts `{"message": "..."}`, returns `{"response": "..."}`
- `GET /auth/google` — starts Google OAuth flow
- `GET /auth/google/callback` — handles Google redirect
- `GET /auth/microsoft` — starts Microsoft OAuth flow
- `GET /auth/microsoft/callback` — handles Microsoft redirect
- `GET /` — serves the chat UI (`static/index.html`)

### OAuth Tokens
Google and Microsoft tokens are stored in `~/.pa/tokens/` (never in the repo). Auth modules handle refresh automatically. On first run, direct the user to `/auth/google` and `/auth/microsoft` to complete the OAuth flows.

### Rate Limits
- Gmail: 250 quota units/user/second — batch reads where possible
- Graph API: 10,000 requests/10 minutes per app
- OpenWeatherMap free tier: 60 calls/minute — cache responses for 10 minutes
- RSS feeds: poll at most every 15 minutes — cache in memory

## Integrations

### Gmail
- Library: `google-api-python-client`, `google-auth-oauthlib`
- Scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`
- Key methods: `users.messages.list`, `users.messages.get`, `users.messages.send`

### Google Calendar
- Library: `google-api-python-client`
- Scopes: `calendar.readonly`, `calendar.events`
- Key methods: `calendarList.list`, `events.list`, `events.insert`, `events.update`, `events.delete`

### Outlook (Microsoft Graph)
- Library: `msal`, `httpx`
- Scopes: `Mail.Read`, `Mail.Send`, `Calendars.Read`, `Calendars.ReadWrite`
- Base URL: `https://graph.microsoft.com/v1.0/me/`

### Weather (OpenWeatherMap)
- Library: `httpx`
- Endpoint: `https://api.openweathermap.org/data/2.5/weather` (current) + `/forecast` (5-day)
- Location: resolved from `USER_LOCATION` env var
- Cache responses for 10 minutes

### News (RSS)
- Library: `feedparser`, `httpx` (with cookie session for Statesman)
- Sources:
  - Austin American-Statesman: requires authenticated session (all articles paywalled)
    - Login via POST to Statesman auth endpoint, store session cookie
    - Use cookie in subsequent RSS/article fetch requests
    - Credentials in `.env` as `STATESMAN_EMAIL` / `STATESMAN_PASSWORD`
  - Bloomberg: `https://feeds.bloomberg.com/markets/news.rss`
  - TechCrunch: `https://techcrunch.com/feed/`
- Poll interval: 15 minutes, cached in memory
- Deduplicate by URL across sources
- Statesman session should be refreshed if a fetch returns a redirect to login

## What Claude Should Know

- This is an agentic app — Claude drives tool calls in a loop until the task is done
- Never expose raw API credentials in tool responses or conversation context
- Always confirm with the user before sending email or creating/deleting calendar events
- Prefer read-only operations unless the user explicitly requests a write action
- The web UI is single-user (no auth layer on the chat endpoint needed for MVP)
