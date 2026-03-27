"""Tests for integrations/weather.py"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations import weather


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(weather, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(weather, "CACHE_PATH", tmp_path / "weather.json")


OWM_RESPONSE = {
    "name": "Austin",
    "main": {"temp": 72.5, "feels_like": 70.0, "humidity": 55},
    "weather": [{"description": "partly cloudy"}],
    "wind": {"speed": 8.3},
}


class TestGetWeather:
    def test_fetches_from_api_when_no_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        monkeypatch.setenv("USER_LOCATION", "Austin,TX,US")
        mock_resp = MagicMock()
        mock_resp.json.return_value = OWM_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.weather.httpx.get", return_value=mock_resp) as mock_get:
            result = weather.get_weather()

        mock_get.assert_called_once()
        assert result["location"] == "Austin"
        assert result["temp_f"] == round(72.5)
        assert result["description"] == "Partly cloudy"
        assert result["humidity_pct"] == 55
        assert result["wind_mph"] == 8

    def test_returns_cached_result_within_ttl(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        cached = {"location": "Austin", "temp_f": 68, "description": "Sunny",
                  "feels_like_f": 66, "humidity_pct": 40, "wind_mph": 5}
        (tmp_path / "weather.json").write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "weather": cached,
        }))

        with patch("integrations.weather.httpx.get") as mock_get:
            result = weather.get_weather()

        mock_get.assert_not_called()
        assert result["temp_f"] == 68

    def test_refetches_when_cache_expired(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        monkeypatch.setenv("USER_LOCATION", "Austin,TX,US")
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        (tmp_path / "weather.json").write_text(json.dumps({
            "fetched_at": old_time,
            "weather": {"location": "Austin", "temp_f": 60},
        }))
        mock_resp = MagicMock()
        mock_resp.json.return_value = OWM_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("integrations.weather.httpx.get", return_value=mock_resp) as mock_get:
            result = weather.get_weather()

        mock_get.assert_called_once()
        assert result["temp_f"] == round(72.5)

    def test_raises_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OPENWEATHER_API_KEY"):
            weather.get_weather()

    def test_raises_on_api_error(self, monkeypatch):
        import httpx as _httpx
        monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
        monkeypatch.setenv("USER_LOCATION", "Austin,TX,US")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        with patch("integrations.weather.httpx.get", return_value=mock_resp):
            with pytest.raises(_httpx.HTTPStatusError):
                weather.get_weather()
