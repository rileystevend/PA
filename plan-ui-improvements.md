<!-- /autoplan restore point: /Users/sdriley/.gstack/projects/rileystevend-PA/main-autoplan-restore-20260327-205644.md -->
# Plan: UI Improvements — PA Personal Assistant

## Problem
The current chat UI is functional but minimal. After getting the core briefing and chat working,
the UI has several gaps that make the experience feel rough:

1. **No conversation history** — every page refresh wipes all messages. Close the tab and you lose everything.
2. **No streaming indicator** — while the backend is thinking (tool calls, API latency), the user sees a blank box with a cursor. No indication that work is happening.
3. **No table styling** — just fixed (today), but tables need CSS to look readable.
4. **Greeting is always "Good morning"** — hardcoded string, wrong at noon, wrong at night.
5. **Suggestion chips disappear forever** — once you send one message, the chips never come back even if you clear the conversation.
6. **No clear/reset button** — no way to start a fresh conversation without reloading the page.
7. **No copy button on responses** — for a briefing tool, being able to copy the text matters.
8. **Links in responses aren't clickable** — Bloomberg and news headlines stream as text, but `[title](url)` markdown links are not rendered as `<a>` tags.

## Proposed Changes

### 1. Conversation History (localStorage)
Save the full message history to `localStorage` on every message. On page load, restore it.
- Key: `pa_conversation`
- Format: `[{role, text, timestamp}]`
- Cap: last 50 messages (older ones drop off)
- Clear button wipes localStorage and resets the UI

### 2. Streaming Status Indicator
Show a status line below the header while a response is in-flight:
- "Thinking..." while waiting for the first token
- "Responding..." once tokens start streaming
- Hidden when idle

### 3. Table Styling
Add CSS for `table`, `th`, `td` inside `.message.assistant`:
- Bordered cells, alternating row shading
- Horizontal scroll on overflow (for narrow screens)

### 4. Dynamic Greeting
`greeting()` function returns:
- 5am–11am: "Good morning."
- 11am–5pm: "Good afternoon."
- 5pm–9pm: "Good evening."
- 9pm–5am: "Working late?"

### 5. Persistent Suggestion Chips + Clear Button
- Chips reappear whenever the message list is empty (i.e., after clear)
- Add a "Clear" button (icon only, top-right of header) that wipes localStorage and reloads the chat state

### 6. Copy Button on Assistant Messages
Each assistant message gets a copy icon (top-right of the bubble) that copies the raw text to clipboard.
- Icon: clipboard SVG
- Feedback: "Copied!" tooltip for 1.5s

### 7. Markdown Link Rendering
Add `[text](url)` → `<a href="url" target="_blank" rel="noopener">text</a>` to the inline renderer.
Only render http/https URLs (block javascript: and data:).

## Out of Scope
- Backend changes — all changes are in `static/index.html`
- Auth / multi-user
- Custom themes
- Markdown code block syntax highlighting (separate effort)

## Files Changed
- `static/index.html` — all changes live here

## Success Criteria
- Page refresh restores last 50 messages
- Streaming indicator visible during API call
- Tables have visible borders and alternating rows
- Greeting matches time of day
- Clear button works and chips reappear
- Copy button copies assistant response to clipboard
- News headline links are clickable

## Decision Audit Trail

| # | Phase | Decision | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Include all 7 improvements | P1 Completeness | All are small, contained, high-value | Shipping subset |
| 2 | CEO | Stay single-file vanilla JS | P5 Explicit | No bundler for single-user app | React/Vue |
| 3 | CEO | Add localStorage try/catch | P3 Pragmatic | Corrupted JSON → blank page | Ignore error |
| 4 | Design | Copy button hover-only desktop, always-on touch | P5 Explicit | Standard copy button UX | Always visible |
| 5 | Design | Save conversation in finally block only | P3 Pragmatic | Avoids saving partial streaming messages | Save per-token |
| 6 | Design | aria-live="polite" on #status | P1 Completeness | Screen readers need live region | Skip a11y |
| 7 | Design | Table overflow-x wrapper div | P5 Explicit | CSS on table doesn't scroll; wrapper does | overflow on table |
| 8 | Eng | Block javascript:/data: URLs | P1 Completeness | XSS risk — allowlist https?:// only | Trust all URLs |
| 9 | Eng | Defer frontend unit tests | P5 Explicit | No build system; /qa covers this | Add Vitest |

## GSTACK REVIEW REPORT

| Review | Trigger | Runs | Status | Findings |
|--------|---------|------|--------|----------|
| CEO Review | /autoplan | 1 | clean | 0 critical, 1 medium (auto-fixed) |
| Design Review | /autoplan | 1 | issues_found | 6 auto-fixed, 1 taste decision |
| Eng Review | /autoplan | 1 | issues_found | 1 critical XSS (auto-fixed), 3 medium (auto-fixed) |

**VERDICT:** APPROVED pending taste decision on Clear button behavior.
