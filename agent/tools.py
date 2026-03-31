"""
Claude tool definitions for conversational (Mode 2) queries.

These are JSON schemas passed to the Anthropic API tool_use feature.
The assistant loop in assistant.py dispatches calls to the matching integration.
"""

TOOLS = [
    {
        "name": "get_emails",
        "description": (
            "Fetch recent unread emails from Gmail (last 24 hours, max 20). "
            "Returns subject, sender, date, and snippet for each email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Fetch calendar events from Google Calendar. "
            "Default: today only (days=1). Use days=7 for the week ahead, days=14 for two weeks, days=30 for a month, etc. Max 90 days."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead. 1 = today only (default), 7 = this week, 30 = this month. Max 90.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather for Austin, TX.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Fetch top headlines from Google News (Austin, TX), KXAN (local Austin TV news), Bloomberg, and TechCrunch. "
            "Each result has title, url, source, and published fields. "
            "When presenting headlines to the user, format each as a markdown link: [title](url)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["austin", "kxan", "bloomberg", "techcrunch", "all"],
                    "description": "Which news source to fetch. Default: all.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_email_thread",
        "description": (
            "Fetch the full body of a specific email by its Gmail message ID. "
            "Use this before drafting a reply so you have the full context of the original message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The Gmail message ID (from a prior get_emails call).",
                }
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "get_health_summary",
        "description": (
            "Get a summary of recent health data from Garmin (sleep, HRV, Body Battery, "
            "steps, VO2 max, activity) and body composition from Hume scale (weight, body fat %, "
            "lean mass). Returns standardized metrics with keys like sleep_hours, hrv_ms, "
            "body_battery, steps, body_fat_pct, weight_lbs, weight_trend."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_ireland_rentals",
        "description": (
            "Search Daft.ie for rental properties in the Dublin/Wicklow corridor (Ireland). "
            "Defaults: Bray, Greystones, Dún Laoghaire, Sandyford — 2+ beds — max €2,800/month. "
            "Returns listings with address, price, beds, baths, and Daft.ie URL. "
            "When presenting results, format each as a markdown link: [address](url). "
            "If the result contains a 'fallback_note' key, show it to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_beds": {
                    "type": "integer",
                    "description": "Minimum number of bedrooms. Default: 2.",
                },
                "max_price": {
                    "type": "integer",
                    "description": "Maximum monthly rent in euros. Default: 2800.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a new event on the user's Google Calendar. "
            "IMPORTANT: Before calling this tool, you MUST present the event details to the user "
            "(title, date, start time, end time, and any description/location) and explicitly ask for confirmation. "
            "Only call create_calendar_event after the user has said 'yes', 'looks good', 'add it', or similar. "
            "Never create an event without explicit approval. "
            "All times must be ISO 8601 with timezone offset (e.g. 2026-03-30T14:00:00-05:00)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title/summary.",
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format with timezone (e.g. 2026-03-30T14:00:00-05:00).",
                },
                "end": {
                    "type": "string",
                    "description": "End time in ISO 8601 format with timezone (e.g. 2026-03-30T15:00:00-05:00).",
                },
                "description": {
                    "type": "string",
                    "description": "Optional event description.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional event location.",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of email addresses to invite as guests.",
                },
            },
            "required": ["title", "start", "end"],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send an email via Gmail. "
            "IMPORTANT: Before calling this tool, you MUST present the full draft to the user "
            "(to, subject, and body) and explicitly ask for confirmation. "
            "Only call send_email after the user has said 'yes', 'send it', 'looks good', or similar. "
            "Never send without explicit approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Plain-text email body.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]
