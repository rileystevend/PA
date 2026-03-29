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
        "description": "Fetch today's calendar events from Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {},
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
