# TODOS

## Security

### Add server-side confirmation gate for send_email

**What:** Require explicit two-step confirmation before `send_email` dispatches, beyond the current prompt instruction.

**Why:** Claude can be jailbroken into skipping the "you MUST present the draft" instruction. A prompt-only guard is not a security boundary.

**Context:** `agent/tools.py` defines `send_email` and `_dispatch_tool` dispatches it. The only guard is the tool description text. Adversarial messages like "I already confirmed, send it" can bypass this. Options: remove the tool entirely (per V1 scope), add a server-side pending-draft state with a `/confirm-send` endpoint, or require the frontend to present a modal and pass a short-lived token.

**Effort:** M
**Priority:** P1
**Depends on:** None

---

### Fix token files created with world-readable permissions

**What:** Apply `chmod 0o600` after writing `~/.pa/tokens/{provider}.json`.

**Why:** `path.write_text()` creates files with umask-derived permissions (typically `0644`). OAuth access + refresh tokens are readable by any process running as the same user.

**Context:** `auth/token_store.py::save()`. One-line fix: `path.chmod(0o600)` after `path.write_text(...)`.

**Effort:** S
**Priority:** P1
**Depends on:** None

---

## API / Integrations

### Cap unbounded history list in /chat

**What:** Validate `req.history` in `ChatRequest` — max length, role validation, content size cap.

**Why:** A client can POST thousands of history entries, running up token costs with no ceiling. Crafted `assistant` role messages in history can manipulate the tool loop.

**Context:** `main.py::ChatRequest` accepts `history: list = []` with no validation. `_stream_conversational` passes it directly to Claude. Add a `@validator` or `model_validator` capping list length (e.g. 50 turns) and total character count.

**Effort:** S
**Priority:** P1
**Depends on:** None

---

### Add pagination to Google Calendar calendarList fetch

**What:** Handle `nextPageToken` in `gcal.get_todays_events()`.

**Why:** `calendarList().list()` returns max 100 calendars per page. Users with many shared/delegated calendars get silently incomplete results.

**Context:** `integrations/gcal.py`. Wrap the `calendarList().list().execute()` call in a pagination loop collecting results until `nextPageToken` is absent.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Parallelize Gmail message fetches

**What:** Replace the sequential `for msg in messages` loop with concurrent calls.

**Why:** Up to 20 serial Gmail API calls per briefing is slow and fragile — one transient failure aborts the whole list.

**Context:** `integrations/gmail.py::get_recent_emails`. Use `concurrent.futures.ThreadPoolExecutor` or `asyncio.gather` (via `asyncio.to_thread`) to fetch all messages concurrently.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Fix `expiry: None` on initial Google OAuth save

**What:** Persist the real expiry when saving the token after OAuth callback.

**Why:** `auth/google.py` saves `"expiry": None`. `token_store.is_expired()` sees `None` and returns `True`, triggering a token refresh on every single API call until the first refresh succeeds.

**Context:** `auth/google.py::google_callback`. Extract the actual expiry from the credentials object: `creds.expiry.isoformat()` if available, else `None`.

**Effort:** S
**Priority:** P1
**Depends on:** None

---

## Infrastructure

### Add file locking to cache writes

**What:** Use a lock (e.g. `fcntl.flock` or a `threading.Lock`) around cache read/write in `weather.py` and `news.py`.

**Why:** Concurrent requests can cause torn cache writes. `except Exception: pass` in `_load_cache` silently swallows parse errors on partial files, triggering unnecessary re-fetches.

**Context:** `integrations/weather.py` and `integrations/news.py`. A simple `threading.Lock()` module-level variable protecting the cache file read/write is sufficient for the single-server case.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Tighten token_auth middleware path allowlist

**What:** Remove `.json` from `_STATIC_EXTS` or audit which `.json` routes should be public.

**Why:** Any request path with a `.json` suffix bypasses token auth. A future `/config.json` or `/tokens.json` route would be auto-public.

**Context:** `main.py::_STATIC_EXTS`. Currently includes `.json` to allow `/manifest.json`. Either explicitly allowlist `/manifest.json` by path rather than suffix, or remove `.json` from the extension set.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Add tool dispatch logging

**What:** Add `logger.debug("tool dispatch: %s %s", name, inputs)` at the top of `_dispatch_tool()`.

**Why:** When a tool call fails, the chat shows "Error: ..." but logs have no context about which tool was called, with what arguments, or what triggered it. Debugging `send_email` failures requires this.

**Context:** `agent/assistant.py::_dispatch_tool`. One line. Use `logger.debug` so it's off by default in production but available when needed.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Clean up stale news_statesman.json cache file

**What:** After removing the Statesman integration, delete `~/.pa/cache/news_statesman.json` if it exists. Mention in CLAUDE.md that this file is safe to delete manually.

**Why:** The file is harmless but confusing — it looks like an active cache entry when browsing the cache directory.

**Context:** `~/.pa/cache/news_statesman.json`. Delete with `rm -f ~/.pa/cache/news_statesman.json`.

**Effort:** S
**Priority:** P3
**Depends on:** Statesman removal (app-optimization-v1)

---

## Completed

### Add iteration ceiling to tool-use loop
**Completed:** app-optimization-v1 (2026-03-29)

### Fix error objects mixed into article list in news.py
**Completed:** app-optimization-v1 (2026-03-29)
