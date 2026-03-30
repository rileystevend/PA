"""
Shared persistent file cache for integrations.

Each integration stores its cached data in ~/.pa/cache/{name}.json
with a fetched_at timestamp. Data is returned from cache if within TTL.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".pa" / "cache"


def load(name: str, ttl_minutes: int) -> dict | list | None:
    """
    Load cached data if it exists and is within TTL.
    Returns None if missing, expired, or corrupt.
    """
    path = CACHE_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(raw["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at < timedelta(minutes=ttl_minutes):
            return raw["data"]
    except Exception:
        pass
    return None


def save(name: str, data: dict | list) -> None:
    """Save data to cache with current timestamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    path.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "data": data},
            indent=2,
            default=str,
        )
    )
