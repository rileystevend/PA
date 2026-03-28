# Design System — PA (Personal Assistant)

## Product Context
- **What this is:** A Claude-powered personal AI assistant for daily use — morning briefings, email triage, calendar review, local news, and weather. Single-user, localhost-only.
- **Who it's for:** The owner. One person who wants a polished private workspace, not a SaaS product.
- **Space/industry:** Personal productivity / AI assistant
- **Project type:** Web chat app with sidebar navigation

## Aesthetic Direction
- **Direction:** Warm Command Center
- **Decoration level:** Minimal — typography carries everything
- **Mood:** Dark, precise, and warm. The tool feels handcrafted and personal, like a premium private workspace — not a generic AI chat window. The morning context (briefings, weather, news) informs the warmth: amber over cold blue, readable serifs over geometric sans.
- **Key insight:** PA's primary output is editorial content (morning briefings, news summaries, email digests). This is a newspaper, not a chatbot. The design honors that — Instrument Serif for reading, Fraunces for moments that stop you cold.

## Typography

- **Display / Greeting:** [Fraunces](https://fonts.google.com/specimen/Fraunces) — optical old-style serif, weight 300. Used for "Good morning." and section headings. Nothing else in the AI chat space uses this. That's the point.
- **Assistant responses:** [Instrument Serif](https://fonts.google.com/specimen/Instrument+Serif) — modern readable serif, regular and italic. Long-form briefings read like a quality newsletter, not a Slack message.
- **UI chrome (sidebar, input, labels, status):** [Geist](https://fonts.google.com/specimen/Geist) — crisp, technical, precise. Weights 400 / 500 / 600. No personality fight with the serifs.
- **Code / data:** [Geist Mono](https://fonts.google.com/specimen/Geist+Mono) — tabular-nums for data display.
- **Loading:** Google Fonts CDN via `<link>` preconnect + stylesheet

### Type Scale
| Level | Font | Size | Weight | Use |
|-------|------|------|--------|-----|
| Display | Fraunces | 42px | 300 | "Good morning." greeting |
| Heading 1 | Fraunces | 28px | 300 | Section titles |
| Heading 2 | Geist | 15px | 600 | Briefing section labels |
| Body | Instrument Serif | 15px | 400 | Assistant response text |
| UI | Geist | 13-14px | 400/500 | Sidebar, input, buttons |
| Label | Geist | 10-11px | 600/700 | Uppercase section headers |
| Mono | Geist Mono | 13px | 400 | Code, data, hex values |

## Color

- **Approach:** Restrained — one amber accent, warm near-black backgrounds, warm off-white text
- **Background:** `#0d0d0b` — barely-warm near-black. More interesting than flat #0f0f0f.
- **Surface:** `#141412` — message cards and content areas
- **Surface 2:** `#1a1a16` — hover states, sidebar items
- **Border:** `#222218` — subtle warm separator
- **Border 2:** `#2a2a22` — more visible borders (inputs, cards)
- **Text primary:** `#e8e4d4` — warm off-white. Easier on eyes than pure #ffffff or cold #e8e8e8.
- **Text muted:** `#70685a` — warm gray for descriptions and secondary content
- **Text dim:** `#48443a` — sidebar labels, placeholder text
- **Accent:** `#c8974a` — amber. Morning light. Nothing else in the AI chat category uses this. Used for: send button, active sidebar items, section headers, focus rings.
- **Accent light:** `#f0c878` — lighter amber for text on dark backgrounds (briefing section labels in assistant responses)
- **Accent dim:** `#1e180a` — very dark amber for accent background (active sidebar item fill)
- **User messages bg:** `#12120e` with border `#2a2218`
- **Semantic:** success `#4a7c5a` · warning `#b87a2a` · error `#8b3a3a` · info `#3a5a8b`

### Dark Mode CSS Variables
```css
:root {
  --bg:           #0d0d0b;
  --surface:      #141412;
  --surface-2:    #1a1a16;
  --border:       #222218;
  --border-2:     #2a2a22;
  --text:         #e8e4d4;
  --text-muted:   #70685a;
  --text-dim:     #48443a;
  --accent:       #c8974a;
  --accent-light: #f0c878;
  --accent-dim:   #1e180a;
  --user-bg:      #12120e;
  --user-border:  #2a2218;
  --success:      #4a7c5a;
  --warning:      #b87a2a;
  --error:        #8b3a3a;
  --info:         #3a5a8b;
}
```

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** Grid-disciplined
- **Sidebar:** 220px fixed, collapses on mobile (existing behavior preserved)
- **Max content width:** 720px (tighter than current 780px — better for long-form reading)
- **Border radius:** sm(4px) md(7-8px) lg(10-12px) — conservative, avoids bubbly AI-slop aesthetic
- **Grid:** Single column at mobile, sidebar + chat at ≥600px

## Motion
- **Approach:** Minimal-functional
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150ms) medium(200-250ms)
- **Existing:** Streaming cursor blink and sidebar collapse transition are correct — keep as-is. Do not add decorative animations.

## Design Risks (intentional departures from category norms)
1. **Warm amber accent instead of blue/purple** — Every AI tool defaults to blue/purple. Amber signals morning, warmth, and premium. Deliberate and distinctive.
2. **Serif typography for assistant responses** — No AI chat app uses serif body text. PA's briefings are long-form reading content. Instrument Serif makes them genuinely pleasant to read.
3. **Warm-shifted near-black** (#0d0d0b not #0f0f0f) — Subtle but the tool feels handcrafted rather than templated. No one notices consciously; everyone feels it.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-27 | Initial design system created | /design-consultation — Warm Command Center direction selected. Research showed all AI chat tools converge on cold gray + blue. PA's editorial content (briefings, news) earns serif typography and amber accent. |
