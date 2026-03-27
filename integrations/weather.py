"""
OpenWeatherMap integration.

Fetches current weather for USER_LOCATION (default: Austin,TX,US).
Caches to ~/.pa/cache/weather.json for 10 minutes.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".pa" / "cache"
CACHE_PATH = CACHE_DIR / "weather.json"
CACHE_TTL_MINUTES = 10
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def get_weather() -> dict:
    """
    Return current weather for USER_LOCATION.
    Uses persistent file cache (10 min TTL).
    """
    cached = _load_cache()
    if cached is not None:
        return cached

    location = os.environ.get("USER_LOCATION", "Austin,TX,US")
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")

    resp = httpx.get(
        BASE_URL,
        params={"q": location, "appid": api_key, "units": "imperial"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    result = {
        "location": data.get("name", location),
        "temp_f": round(data["main"]["temp"]),
        "feels_like_f": round(data["main"]["feels_like"]),
        "description": data["weather"][0]["description"].capitalize(),
        "humidity_pct": data["main"]["humidity"],
        "wind_mph": round(data["wind"]["speed"]),
    }
    _save_cache(result)
    return result


def _load_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at < timedelta(minutes=CACHE_TTL_MINUTES):
            return data["weather"]
    except Exception:
        pass
    return None


def _save_cache(weather: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "weather": weather},
            indent=2,
        )
    )
