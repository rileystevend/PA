"""Tests for integrations/daft.py (gateway API approach)"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations import daft


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_response(listings: list[dict], total: int | None = None) -> dict:
    """Build a Daft.ie gateway API response."""
    return {
        "listings": listings,
        "paging": {"totalResults": total if total is not None else len(listings)},
    }


def _raw_listing(
    title="2 Bed Apartment, Bray",
    price="€2,100 per month",
    beds="2 Bed",
    baths="1 Bath",
    path="/for-rent/apartment-bray-123",
    img_url="https://media.daft.ie/img/123.jpg",
):
    return {
        "listing": {
            "title": title,
            "price": price,
            "numBedrooms": beds,
            "numBathrooms": baths,
            "seoFriendlyPath": path,
            "media": {"images": [{"size720x480": img_url}]},
        }
    }


def _mock_resp(data: dict):
    resp = MagicMock()
    resp.json.return_value = data
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

    def test_from_prefix(self):
        assert daft._parse_price("From €2,150 per month") == 2150


# ---------------------------------------------------------------------------
# _parse_listing
# ---------------------------------------------------------------------------

class TestParseListing:
    def test_parses_standard_listing(self):
        item = _raw_listing()
        result = daft._parse_listing(item, "Bray")
        assert result["title"] == "2 Bed Apartment, Bray"
        assert result["price_per_month"] == 2100
        assert result["beds"] == "2 Bed"
        assert result["baths"] == "1 Bath"
        assert result["url"] == "https://www.daft.ie/for-rent/apartment-bray-123"
        assert result["area"] == "Bray"
        assert "media.daft.ie" in result["img"]

    def test_missing_title_returns_none(self):
        assert daft._parse_listing({"listing": {}}, "Bray") is None

    def test_url_with_full_href(self):
        item = _raw_listing(path="https://www.daft.ie/already-full")
        result = daft._parse_listing(item, "Bray")
        assert result["url"] == "https://www.daft.ie/already-full"

    def test_no_images(self):
        item = {"listing": {"title": "Test", "price": "€1,000", "media": {}}}
        result = daft._parse_listing(item, "Bray")
        assert result["img"] == ""


# ---------------------------------------------------------------------------
# search_rentals (integration, mocked HTTP)
# ---------------------------------------------------------------------------

class TestSearchRentals:
    def setup_method(self):
        daft._cache.clear()

    def test_returns_listings_from_all_areas(self):
        api_data = _api_response([_raw_listing()])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_resp(api_data)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert len(results) >= 1
        assert results[0]["area"] in ("Bray", "Greystones", "Dún Laoghaire", "Sandyford")

    def test_caches_results(self):
        api_data = _api_response([_raw_listing()])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_resp(api_data)
            mock_client_cls.return_value = mock_client

            daft.search_rentals()
            daft.search_rentals()
            assert mock_client_cls.call_count == 1

    def test_partial_failure_returns_other_areas(self):
        good_data = _api_response([_raw_listing(title="Good Listing", path="/for-rent/good")])
        call_count = [0]

        def post_side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Network error")
            return _mock_resp(good_data)

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = post_side_effect
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert any(r["title"] == "Good Listing" for r in results)

    def test_deduplicates_by_url(self):
        api_data = _api_response([_raw_listing(path="/for-rent/same-url")])

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_resp(api_data)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls))

    def test_cache_expires_after_ttl(self):
        api_data = _api_response([_raw_listing()])

        daft._cache["Bray,Greystones,Dún Laoghaire,Sandyford-2-2800"] = {
            "data": [{"title": "Stale", "url": "/stale"}],
            "fetched_at": datetime.now(timezone.utc) - timedelta(minutes=60),
        }

        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_resp(api_data)
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert not any(r.get("title") == "Stale" for r in results)

    def test_all_areas_fail_returns_fallback_note(self):
        with patch("integrations.daft.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = Exception("Network error")
            mock_client_cls.return_value = mock_client

            results = daft.search_rentals()

        assert len(results) == 1
        assert "fallback_note" in results[0]
