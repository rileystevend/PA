"""
Daft.ie rental search integration.

Uses Daft.ie's internal gateway API (gateway.daft.ie) to fetch listings.
The public site is behind Cloudflare bot protection, but the API accepts
direct JSON requests with text-based location search.

Results are cached in memory for 30 minutes.

Default search: Bray, Greystones, Dún Laoghaire, Sandyford
                2+ bedrooms, max €2,800/month
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_MINUTES = 30
_cache: dict = {}

DEFAULT_AREAS = [
    ("Bray", "Bray, Co. Wicklow"),
    ("Greystones", "Greystones, Co. Wicklow"),
    ("Dún Laoghaire", "Dún Laoghaire, Co. Dublin"),
    ("Sandyford", "Sandyford, Dublin 18"),
]

_API_URL = "https://gateway.daft.ie/old/v1/listings"

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "brand": "daft",
    "platform": "web",
}

MAX_PER_AREA = 10


def search_rentals(
    areas: list[tuple[str, str]] | None = None,
    min_beds: int = 2,
    max_price: int = 2800,
) -> list[dict]:
    """
    Search Daft.ie for rentals across the given areas.
    Returns list of {title, price_per_month, beds, baths, url, img, area} dicts.
    """
    if areas is None:
        areas = DEFAULT_AREAS

    cache_key = f"{','.join(label for label, _ in areas)}-{min_beds}-{max_price}"
    cached = _cache.get(cache_key)
    if cached:
        if datetime.now(timezone.utc) - cached["fetched_at"] < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info("Daft.ie cache hit")
            return cached["data"]

    all_listings: list[dict] = []
    seen_urls: set[str] = set()

    with httpx.Client(headers=_HEADERS, timeout=15) as client:
        for area_label, search_term in areas:
            try:
                listings = _fetch_area(client, area_label, search_term, min_beds, max_price)
                for listing in listings:
                    if listing["url"] not in seen_urls:
                        seen_urls.add(listing["url"])
                        all_listings.append(listing)
            except Exception as e:
                logger.warning("Daft.ie fetch failed for %s: %s", area_label, e)

    if not all_listings:
        return [
            {
                "fallback_note": (
                    "Daft.ie returned no results. The API may be temporarily "
                    "unavailable, or there are genuinely no listings matching "
                    "your criteria. Try adjusting the budget or bedrooms, or "
                    "run /ireland-rental-search in Claude Code for a browser-based search."
                )
            }
        ]

    _cache[cache_key] = {"data": all_listings, "fetched_at": datetime.now(timezone.utc)}
    return all_listings


def _fetch_area(
    client: httpx.Client,
    area_label: str,
    search_term: str,
    min_beds: int,
    max_price: int,
) -> list[dict]:
    payload = {
        "section": "residential-to-rent",
        "filters": [
            {"name": "adState", "values": ["published"]},
        ],
        "ranges": [
            {"name": "rentalPrice", "from": "0", "to": str(max_price)},
            {"name": "numBeds", "from": str(min_beds), "to": ""},
        ],
        "terms": search_term,
        "paging": {"from": "0", "pageSize": str(MAX_PER_AREA)},
        "sort": "publishDateDesc",
    }
    resp = client.post(_API_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("listings", []):
        parsed = _parse_listing(item, area_label)
        if parsed:
            results.append(parsed)
    return results


def _parse_listing(item: dict, area_label: str) -> dict | None:
    listing = item.get("listing", item)

    title = listing.get("title") or listing.get("seoTitle") or ""
    if not title:
        return None

    price = _parse_price(str(listing.get("price") or listing.get("abbreviatedPrice") or ""))
    beds = listing.get("numBedrooms") or 0
    baths = listing.get("numBathrooms") or 0

    path = listing.get("seoFriendlyPath") or listing.get("daftShortcode") or ""
    listing_url = f"https://www.daft.ie{path}" if path.startswith("/") else path

    img_url = ""
    media = listing.get("media") or {}
    images = media.get("images") or []
    if images and isinstance(images[0], dict):
        img_url = (
            images[0].get("size720x480")
            or images[0].get("size600x600")
            or images[0].get("size400x300")
            or ""
        )

    return {
        "title": title,
        "price_per_month": price,
        "beds": beds,
        "baths": baths,
        "url": listing_url,
        "img": img_url,
        "area": area_label,
    }


def _parse_price(raw: str) -> int:
    """Extract integer from strings like '€2,150 per month' or '2150'."""
    cleaned = raw.replace("€", "").replace(",", "").replace(" ", "")
    match = re.search(r"\d+", cleaned)
    return int(match.group()) if match else 0
