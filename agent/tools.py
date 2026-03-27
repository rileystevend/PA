"""
Claude tool definitions for conversational (Mode 2) queries.

These are JSON schemas passed to the Anthropic API tool_use feature.
The assistant loop in assistant.py dispatches calls to the matching integration.
"""

TOOLS = [
    {
        "name": "get_emails",
        "description": (
            "Fetch recent unread emails from Gmail and Outlook (last 24 hours, max 20 each). "
            "Returns subject, sender, date, and snippet for each email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["gmail", "outlook", "both"],
                    "description": "Which email provider to fetch from. Default: both.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Fetch today's calendar events from Google Calendar and/or Outlook Calendar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["google", "outlook", "both"],
                    "description": "Which calendar to fetch from. Default: both.",
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
            "Fetch top headlines from Austin American-Statesman, Bloomberg, and TechCrunch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["statesman", "bloomberg", "techcrunch", "all"],
                    "description": "Which news source to fetch. Default: all.",
                }
            },
            "required": [],
        },
    },
]
