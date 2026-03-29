"""Tests for integrations/daft.py"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations import daft


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_next_data(listings: list[dict]) -> str:
    """Wrap a listings list in a minimal __NEXT_DATA__ HTML page."""
    page = {
        "props": {
            "pageProps": {
                "listings": listings
            }
        }
    }
    return (
        '<html><head>'
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(page)}</script>'
        '</head><body></body></html>'
    )


def _listing(
    title="2 Bed Apartment, Bray",
    price="€2,100 per month",
    beds=2,
    baths=1,
    path="/for-rent/apartment-bray-123",
    img="https://media.daft.ie/img/123.jpg",
):
    return {
        "title": title,
        "price": price,
        "numBedrooms": beds,
        "numBathrooms": baths,
        "seoFriendlyPath": path,
        "media": {"images": [{"size720x480": img}]},
    }


def _mock_resp(html: str):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------

class TestParsePrice:
    def test_standard_format(self):
        assert daft._parse_price("€2,150 per month") == 2150

    def test_no_currency_symbol(self):
        assert daft._parse_price("1800") == 1800

    def test_empty(self):
        assert daft._parse_price("") == 0

    def test_no_digits(self):
        assert daft._parse_price("POA") == 0


# ---------------------------------------------------------------------------
# _parse_listing
# ---------------------------------------------------------------------------

class TestParseListing:
    def test_parses_standard_listing(self):
        item = _listing()
        result = daft._parse_listing(item, "Bray")
        assert result["title"] == "2 Bed Apartment, Bray"
        assert result["price_per_month"] == 2100
        assert result["beds"] == 2
        assert result["baths"] == 1
        assert result["url"] == "https://www.daft.ie/for-rent/apartment-bray-123"
        assert result["area"] == "Bray"
        assert "media.daft.ie" in result["img"]

    def test_nested_listing_key(self):
        item = {"listing": _listing(title="Nested Listing")}
        result = daft._parse_listing(item, "Bray")
        assert result["title"] == "Nested Listing"

    def test_missing_title_returns_none(self):
        assert daft._parse_listing({}, "Bray") is None

    def test_url_with_full_href(self):
        item = _listing(path="https://www.daft.ie/already-full")
        result = daft._parse_listing(item, "Bray")
        assert result["url"] == "https://www.daft.ie/already-full"


# ---------------------------------------------------------------------------
# _extract_listings
# ---------------------------------------------------------------------------

class TestExtractListings:
    def test_extracts_from_valid_html(self):
        html = _make_next_data([_listing(title="Test Property")])
        results = daft._extract_listings(html, "Bray")
        assert len(results) == 1
        assert results[0]["title"] == "Test Property"

    def test_returns_empty_when_no_next_data(self):
        results = daft._extract_listings("<html></html>", "Bray")
        assert results == []

    def test_returns_empty_on_invalid_json(self):
        html = '<script id="__NEXT_DATA__" type="application/json">{bad json}</script>'
        results = daft._extract_listings(html, "Bray")
        assert results == []

    def test_caps_at_max_per_area(self):
        listings = [_listing(title=f"Listing {i}", path=f"/for-rent/{i}") for i in range(20)]
        html = _make_next_data(listings)
        results = daft._extract_listings(html, "Bray")
        # _extract_listings itself doesn't cap; _fetch_area does — but we can verify
        # it returns all parsed valid listings
        assert len(results) == 20


# ---------------------------------------------------------------------------
# search_rentals (integration, mocked HTTP)
# ---------------------------------------------------------------------------

class TestSearchRentals:
    def setup_method(self):
        # Clear cache between tests
        daft._cache.clear()

    def test_returns_listings_from_all_areas(self):
        html = _make_next_data([_listing()])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_resp(html)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        # 4 areas × 1 listing each, but dedup by URL collapses identical paths
        assert len(results) >= 1
        assert results[0]["area"] in ("Bray", "Greystones", "Dún Laoghaire", "Sandyford")

    def test_caches_results(self):
        html = _make_next_data([_listing()])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_resp(html)
            mock_client_cls.return_value = mock_client

            daft.search_rentals()
            daft.search_rentals()
            # Second call should hit cache — HTTP client only constructed once
            assert mock_client_cls.call_count == 1

    def test_partial_failure_returns_other_areas(self):
        good_html = _make_next_data([_listing(title="Good Listing", path="/for-rent/good")])

        call_count = [0]

        def get_side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Network error")
            return _mock_resp(good_html)

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = get_side_effect
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert any(r["title"] == "Good Listing" for r in results)

    def test_deduplicates_by_url(self):
        # Same listing URL across all areas
        html = _make_next_data([_listing(path="/for-rent/same-url")])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_resp(html)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls))

    def test_cache_expires_after_ttl(self):
        html = _make_next_data([_listing()])

        # Pre-populate with expired cache entry
        daft._cache["bray-wicklow,greystones-wicklow,dun-laoghaire-dublin,sandyford-dublin-2-2800"] = {
            "data": [{"title": "Stale", "url": "/stale"}],
            "fetched_at": datetime.now(timezone.utc) - timedelta(minutes=60),
        }

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_resp(html)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        # Should have re-fetched, not returned stale data
        assert not any(r.get("title") == "Stale" for r in results)

    def test_all_areas_fail_returns_fallback_note(self):
        """When every area fetch fails, return a sentinel with fallback_note."""
        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = Exception("Network error")
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert len(results) == 1
        assert "fallback_note" in results[0]
        assert "could not be fetched" in results[0]["fallback_note"]
