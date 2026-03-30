"""
Garmin Connect integration.

Fetches health data via python-garminconnect (uses garth for session auth).
Caches to ~/.pa/cache/health_garmin.json for 30 minutes.

First-time auth:
    python -c "from garminconnect import Garmin; g = Garmin('email', 'pass'); g.login()"
    Complete MFA if prompted. garth caches the session in ~/.garth/.
"""

import logging
import os
from datetime import date

from integrations import cache

logger = logging.getLogger(__name__)

CACHE_NAME = "health_garmin"
CACHE_TTL_MINUTES = 30


def get_summary() -> dict:
    """
    Return yesterday's health summary from Garmin Connect.
    Uses persistent file cache (30 min TTL).

    Returns standardized keys:
        sleep_hours, sleep_deep_min, sleep_rem_min, sleep_awake_min,
        hrv_ms, body_battery, vo2_max, steps, calories_total,
        active_minutes, training_load, source
    """
    cached = cache.load(CACHE_NAME, CACHE_TTL_MINUTES)
    if cached is not None:
        return cached

    try:
        from garminconnect import Garmin
    except ImportError:
        return {"source": "garmin", "error": "garminconnect not installed. Run: pip install garminconnect"}

    email = os.environ.get("GARMIN_EMAIL", "")

    try:
        client = Garmin(email=email or None)
        client.login()
    except Exception as e:
        logger.warning("Garmin auth failed: %s", e)
        return {"source": "garmin", "error": f"Garmin unavailable — {e}. Re-run garmin login if session expired."}

    try:
        result = _fetch_health_data(client)
        # Don't cache empty results — all sub-fetches may have silently failed
        data_keys = [k for k in result if k != "source"]
        if data_keys:
            cache.save(CACHE_NAME, result)
        else:
            result["error"] = "All Garmin data endpoints returned empty. Session may be stale."
        return result
    except Exception as e:
        logger.warning("Garmin data fetch failed: %s", e)
        return {"source": "garmin", "error": f"Garmin data fetch failed — {e}"}


def _fetch_health_data(client) -> dict:
    """Pull health metrics from Garmin and normalize to standard keys."""
    today = date.today().isoformat()

    result = {"source": "garmin"}

    # Sleep data
    try:
        sleep = client.get_sleep_data(today)
        if sleep and "dailySleepDTO" in sleep:
            dto = sleep["dailySleepDTO"]
            total_seconds = dto.get("sleepTimeSeconds", 0) or 0
            result["sleep_hours"] = round(total_seconds / 3600, 1)
            result["sleep_deep_min"] = round((dto.get("deepSleepSeconds", 0) or 0) / 60)
            result["sleep_rem_min"] = round((dto.get("remSleepSeconds", 0) or 0) / 60)
            result["sleep_awake_min"] = round((dto.get("awakeSleepSeconds", 0) or 0) / 60)
    except Exception as e:
        logger.debug("Garmin sleep fetch failed: %s", e)

    # HRV
    try:
        hrv_data = client.get_hrv_data(today)
        if hrv_data and "hrvSummary" in hrv_data:
            result["hrv_ms"] = hrv_data["hrvSummary"].get("lastNightAvg")
    except Exception as e:
        logger.debug("Garmin HRV fetch failed: %s", e)

    # Body Battery
    try:
        bb_data = client.get_body_battery(today)
        if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
            # Get most recent reading
            latest = bb_data[-1]
            result["body_battery"] = latest.get("chargedValue", latest.get("bodyBatteryLevel"))
    except Exception as e:
        logger.debug("Garmin Body Battery fetch failed: %s", e)

    # Steps and activity
    try:
        stats = client.get_stats(today)
        if stats:
            result["steps"] = stats.get("totalSteps", 0)
            result["calories_total"] = stats.get("totalKilocalories", 0)
            result["active_minutes"] = (
                (stats.get("highlyActiveSeconds", 0) or 0)
                + (stats.get("activeSeconds", 0) or 0)
            ) // 60
    except Exception as e:
        logger.debug("Garmin stats fetch failed: %s", e)

    # VO2 Max
    try:
        vo2 = client.get_max_metrics(today)
        if vo2 and "maxMetData" in vo2:
            entries = vo2["maxMetData"]
            if isinstance(entries, list) and entries:
                result["vo2_max"] = entries[-1].get("generic", {}).get("vo2MaxValue")
    except Exception as e:
        logger.debug("Garmin VO2 max fetch failed: %s", e)

    # Weight (latest) — Garmin API returns weight in grams
    try:
        weight_data = client.get_body_composition(today)
        if weight_data and "weight" in weight_data:
            weight_g = weight_data["weight"]
            if weight_g and weight_g > 0:
                weight_lbs = round(weight_g / 453.592, 1)
                # Sanity check: skip if outside reasonable range (unit may have changed)
                if 50 <= weight_lbs <= 500:
                    result["weight_lbs"] = weight_lbs
                else:
                    logger.warning("Garmin weight value outside reasonable range: %s g → %s lbs", weight_g, weight_lbs)
    except Exception as e:
        logger.debug("Garmin weight fetch failed: %s", e)

    return result
