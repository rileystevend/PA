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
            "Fetch top headlines from Google News (Austin, TX), Bloomberg, and TechCrunch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["austin", "bloomberg", "techcrunch", "all"],
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
