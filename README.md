# PA — Personal Assistant

A Claude-powered personal assistant that lives in your browser. Ask for your morning briefing and get today's calendar, important emails, weather, and top headlines streamed back in real time. Or just chat, and Claude will pull in whatever data you need.

Built with FastAPI, vanilla JS, and the Anthropic API. Runs on localhost only.

## What it does

- **Morning briefing** — say "good morning" and get a single summary of your calendar, unread emails, Austin weather, and news from Google News, KXAN, Bloomberg, and TechCrunch
- **Conversational tools** — ask about specific emails, weather, news sources, or Ireland rental listings and Claude fetches the data live
- **Email send** — draft and send emails through Gmail with confirmation before dispatch
- **Real-time streaming** — responses stream token-by-token via SSE, no waiting for the full response

## Quick start

```bash
# Clone and install
git clone https://github.com/rileystevend/PA.git
cd PA
pip install -r requirements.txt

# Set up credentials
cp .env.example .env
# Edit .env with your API keys (see below)

# Connect your Google account
uvicorn main:app --host 127.0.0.1 --reload
# Visit http://localhost:8000/auth/google to authorize Gmail + Calendar
```

## API keys you need

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| `GOOGLE_CLIENT_ID` / `SECRET` | [Google Cloud Console](https://console.cloud.google.com/) — OAuth 2.0 credentials with Gmail + Calendar scopes |
| `OPENWEATHER_API_KEY` | [openweathermap.org](https://openweathermap.org/api) — free tier works |

Optional: `MICROSOFT_CLIENT_ID` / `SECRET` / `TENANT_ID` for Outlook integration, `ACCESS_TOKEN` for Tailscale/mobile access.

## Running

```bash
# Local only (default, recommended)
uvicorn main:app --host 127.0.0.1 --reload

# Open http://localhost:8000
```

The server binds to `127.0.0.1` only. Your email and calendar are accessible through this endpoint, so never expose it to the network without the `ACCESS_TOKEN` gate.

## Running tests

```bash
pytest              # 79+ unit tests, all mocked
pytest -m integration  # hits real APIs (use sparingly)
```

## How it works

```
"good morning"
      |
      v
  Detect briefing intent
      |
      v
  Parallel fetch: Gmail + Calendar + Weather + News
      |
      v
  Single Claude API call: "Summarize this data"
      |
      v
  Token-by-token SSE stream to browser
```

For conversational queries, Claude decides which tools to call in a loop (up to 10 iterations), fetches the data, and streams the response.

## Project structure

```
agent/assistant.py     — Claude agentic loop + AsyncAnthropic streaming
agent/tools.py         — Tool schemas for Claude API
integrations/          — Gmail, Calendar, Weather, News (RSS), Daft.ie (rentals)
auth/                  — Google + Microsoft OAuth flows + token storage
static/index.html      — Chat UI (vanilla JS, SSE)
main.py                — FastAPI entry point
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture, patterns, and integration docs. See [DESIGN.md](DESIGN.md) for the visual design system.
