# Changelog

All notable changes to PA (Personal Assistant) will be documented in this file.

## [0.2.1.1] - 2026-03-29

### Fixed
- Daft.ie scraper switched from HTML page scraping to gateway API (`gateway.daft.ie/old/v1/listings`) — Cloudflare was blocking all direct page requests with 403

## [0.2.1.0] - 2026-03-29

### Added
- Ireland rental search via Daft.ie integration (`integrations/daft.py`) with 30-min cache, dedup, and fallback sentinel
- `search_ireland_rentals` tool for Claude conversational mode (Bray, Greystones, Dún Laoghaire, Sandyford)
- Sidebar quick action for Ireland apartment search
- Test coverage for dispatch handler and all-areas-fail fallback

## [0.2.0.0] - 2026-03-29

### Added
- KXAN Austin RSS feed for local TV news coverage (replaces Statesman)
- Tool-use loop iteration ceiling (max 10 turns) to prevent runaway API costs
- SSE error surfacing: backend errors display as red text in chat UI instead of hanging
- News headlines rendered as clickable markdown links in morning briefing
- TODOS.md tracking security, API, and infrastructure improvements

### Changed
- Switched to AsyncAnthropic for true token-by-token streaming (no double API call)
- Removed `_stream_claude_from_messages` dead code
- Tool `get_news` source default changed from `"both"` to `"all"` (was returning empty list)
- Added `"kxan"` to `get_news` tool source enum

### Fixed
- Error objects no longer mixed into news article list (failed feeds logged, excluded from results)
- `innerHTML` XSS in error display replaced with safe `textContent`
- Empty state stacking on repeated clear
- Header toggle blocked by backdrop on mobile (z-index fix)

### Removed
- Statesman auth integration (`statesman_auth.py` and tests) — Hearst OIDC migration made it unmaintainable
- `STATESMAN_EMAIL`/`STATESMAN_PASSWORD` env vars
