"""
Apple Health body composition integration (Hume scale data).

Parses an Apple Health XML export for body composition metrics only:
  - Body mass (weight)
  - Body fat percentage
  - Lean body mass

Uses iterparse() for memory-safe parsing of large exports (1-5 GB).
Only processes records from the last 30 days.
Caches to ~/.pa/cache/health_bodycomp.json for 24 hours.

Export path: APPLE_HEALTH_EXPORT_PATH env var (default: ~/.pa/health/export.xml)
"""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from integrations import cache

logger = logging.getLogger(__name__)

CACHE_NAME = "health_bodycomp"
CACHE_TTL_MINUTES = 60 * 24  # 24 hours — body comp doesn't change fast

# Only these HK types are extracted (body composition from Hume scale)
BODY_COMP_TYPES = {
    "HKQuantityTypeIdentifierBodyMass",
    "HKQuantityTypeIdentifierBodyFatPercentage",
    "HKQuantityTypeIdentifierLeanBodyMass",
}

LOOKBACK_DAYS = 30


def get_summary() -> dict:
    """
    Return body composition summary from Apple Health export.
    Uses persistent file cache (24h TTL).

    Returns standardized keys:
        weight_lbs, body_fat_pct, lean_mass_lbs,
        weight_trend (up/down/stable), source, export_age_days
    """
    cached = cache.load(CACHE_NAME, CACHE_TTL_MINUTES)
    if cached is not None:
        return cached

    export_path = Path(
        os.environ.get("APPLE_HEALTH_EXPORT_PATH", str(Path.home() / ".pa" / "health" / "export.xml"))
    )

    if not export_path.exists():
        return {
            "source": "apple_health",
            "error": f"No Apple Health export found at {export_path}. Export from iPhone: Health → profile → Export All Health Data.",
        }

    try:
        result = _parse_body_comp(export_path)
        cache.save(CACHE_NAME, result)
        return result
    except Exception as e:
        logger.warning("Apple Health parse failed: %s", e)
        return {"source": "apple_health", "error": f"Failed to parse Apple Health export — {e}"}


def _parse_body_comp(path: Path) -> dict:
    """
    Parse Apple Health XML for body composition records.
    Uses iterparse + elem.clear() to handle multi-GB files without OOM.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    records: dict[str, list[tuple[datetime, float]]] = {t: [] for t in BODY_COMP_TYPES}

    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag != "Record":
            elem.clear()
            continue

        record_type = elem.get("type", "")
        if record_type not in BODY_COMP_TYPES:
            elem.clear()
            continue

        try:
            date_str = elem.get("startDate", "")
            # Apple Health format: 2026-03-15 07:30:00 -0500
            # Parse the full string including timezone offset
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
            if dt < cutoff:
                elem.clear()
                continue

            value = float(elem.get("value", "0"))
            unit = elem.get("unit", "")

            # Convert kg to lbs for weight and lean mass
            if unit == "kg" and record_type in (
                "HKQuantityTypeIdentifierBodyMass",
                "HKQuantityTypeIdentifierLeanBodyMass",
            ):
                value = value * 2.20462

            records[record_type].append((dt, value))
        except (ValueError, TypeError):
            pass

        elem.clear()

    return _summarize(records, path)


def _summarize(records: dict[str, list], path: Path) -> dict:
    """Build a standardized summary from parsed records."""
    result: dict = {"source": "apple_health"}

    # Export age
    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime).days
    result["export_age_days"] = age_days
    if age_days > 7:
        result["export_warning"] = f"Export is {age_days} days old. Re-export from iPhone for fresher data."

    # Weight
    weight_records = sorted(records.get("HKQuantityTypeIdentifierBodyMass", []))
    if weight_records:
        result["weight_lbs"] = round(weight_records[-1][1], 1)
        if len(weight_records) >= 2:
            first = weight_records[0][1]
            last = weight_records[-1][1]
            diff = last - first
            if abs(diff) < 0.5:
                result["weight_trend"] = "stable"
            elif diff > 0:
                result["weight_trend"] = "up"
            else:
                result["weight_trend"] = "down"

    # Body fat
    bf_records = sorted(records.get("HKQuantityTypeIdentifierBodyFatPercentage", []))
    if bf_records:
        result["body_fat_pct"] = round(bf_records[-1][1], 1)

    # Lean mass
    lm_records = sorted(records.get("HKQuantityTypeIdentifierLeanBodyMass", []))
    if lm_records:
        result["lean_mass_lbs"] = round(lm_records[-1][1], 1)

    if not any(k in result for k in ("weight_lbs", "body_fat_pct", "lean_mass_lbs")):
        result["error"] = "No body composition data found in export (last 30 days)."

    return result
