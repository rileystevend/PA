"""
Daft.ie rental search integration.

Fetches rental listings from Daft.ie's server-rendered Next.js pages.
Extracts listing data from __NEXT_DATA__ JSON embedded in each search page.
Results are cached in memory for 30 minutes.

Default search: Bray, Greystones, Dún Laoghaire, Sandyford
                2+ bedrooms, max €2,800/month
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_MINUTES = 30
_cache: dict = {}

DEFAULT_AREAS = [
    ("Bray", "bray-wicklow"),
    ("Greystones", "greystones-wicklow"),
    ("Dún Laoghaire", "dun-laoghaire-dublin"),
    ("Sandyford", "sandyford-dublin"),
]

_SEARCH_URL = "https://www.daft.ie/property-for-rent/{slug}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IE,en;q=0.9",
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

    cache_key = f"{','.join(s for _, s in areas)}-{min_beds}-{max_price}"
    cached = _cache.get(cache_key)
    if cached:
        if datetime.now(timezone.utc) - cached["fetched_at"] < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info("Daft.ie cache hit")
            return cached["data"]

    all_listings: list[dict] = []
    seen_urls: set[str] = set()

    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
        for area_label, slug in areas:
            try:
                listings = _fetch_area(client, area_label, slug, min_beds, max_price)
                for listing in listings:
                    if listing["url"] not in seen_urls:
                        seen_urls.add(listing["url"])
                        all_listings.append(listing)
            except Exception as e:
                logger.warning("Daft.ie fetch failed for %s: %s", area_label, e)

    if not all_listings:
        # Daft.ie may have changed their page structure or blocked the request.
        # Return a sentinel so Claude can surface a helpful message.
        return [
            {
                "fallback_note": (
                    "Daft.ie results could not be fetched — the site may have "
                    "updated its page structure or blocked the request. "
                    "For reliable results, run the /ireland-rental-search skill "
                    "in Claude Code, which uses a real browser."
                )
            }
        ]

    _cache[cache_key] = {"data": all_listings, "fetched_at": datetime.now(timezone.utc)}
    return all_listings


def _fetch_area(
    client: httpx.Client,
    area_label: str,
    slug: str,
    min_beds: int,
    max_price: int,
) -> list[dict]:
    url = _SEARCH_URL.format(slug=slug)
    resp = client.get(url, params={
        "numBeds_from": min_beds,
        "maxPrice": max_price,
        "sort": "publishDateDesc",
    })
    resp.raise_for_status()
    return _extract_listings(resp.text, area_label)[:MAX_PER_AREA]


def _extract_listings(html: str, area_label: str) -> list[dict]:
    """Parse listings from the __NEXT_DATA__ JSON block embedded by Next.js."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        logger.warning("No __NEXT_DATA__ found for %s", area_label)
        return []

    try:
        page_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse __NEXT_DATA__ for %s", area_label)
        return []

    raw = _find_listings_array(page_data)
    if not raw:
        logger.warning("No listings array found in __NEXT_DATA__ for %s", area_label)
        return []

    results = []
    for item in raw:
        parsed = _parse_listing(item, area_label)
        if parsed:
            results.append(parsed)
    return results


def _find_listings_array(data: Any) -> list | None:
    """
    Recursively walk the Next.js page tree to find a listings array.
    Daft.ie nests results under various keys depending on the page version.
    """
    if isinstance(data, list) and data and isinstance(data[0], dict):
        first = data[0]
        if any(k in first for k in ("listing", "title", "price", "seoTitle", "daftShortcode")):
            return data

    if isinstance(data, dict):
        # Walk known high-value keys first for speed
        for key in ("listings", "results", "searchResults", "props", "pageProps", "data"):
            if key in data:
                found = _find_listings_array(data[key])
                if found:
                    return found
        # Fall back to exhaustive search
        for value in data.values():
            if isinstance(value, (dict, list)):
                found = _find_listings_array(value)
                if found:
                    return found

    return None


def _parse_listing(item: dict, area_label: str) -> dict | None:
    # Daft.ie wraps each result under a "listing" key in some API versions
    listing = item.get("listing", item)

    title = (
        listing.get("title")
        or listing.get("seoTitle")
        or listing.get("header")
        or ""
    )
    if not title:
        return None

    price = _parse_price(str(listing.get("price") or listing.get("rent") or ""))
    beds = listing.get("numBedrooms") or listing.get("bedrooms") or 0
    baths = listing.get("numBathrooms") or listing.get("bathrooms") or 0

    path = listing.get("seoFriendlyPath") or listing.get("daftShortcode") or ""
    listing_url = f"https://www.daft.ie{path}" if path.startswith("/") else path

    # Photo: try nested media.images first, then top-level images array
    img_url = ""
    media = listing.get("media") or {}
    images = media.get("images") or listing.get("images") or []
    if images:
        first = images[0]
        if isinstance(first, str):
            img_url = first
        elif isinstance(first, dict):
            img_url = (
                first.get("size720x480")
                or first.get("size612x459")
                or first.get("src")
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
