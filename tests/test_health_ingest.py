"""Tests for the /health/ingest endpoint in main.py"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestHealthIngest:
    def test_accepts_weight_lbs(self):
        with patch("integrations.cache.save") as mock_save:
            resp = client.post("/health/ingest", json={"weight_lbs": 185.5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["saved"]["weight_lbs"] == 185.5
        mock_save.assert_called_once()

    def test_converts_kg_to_lbs(self):
        with patch("integrations.cache.save") as mock_save:
            resp = client.post("/health/ingest", json={"weight_kg": 84.0})
        saved = resp.json()["saved"]
        assert saved["weight_lbs"] == round(84.0 * 2.20462, 1)

    def test_accepts_body_fat(self):
        with patch("integrations.cache.save"):
            resp = client.post("/health/ingest", json={"body_fat_pct": 18.2})
        assert resp.json()["saved"]["body_fat_pct"] == 18.2

    def test_accepts_lean_mass_kg(self):
        with patch("integrations.cache.save"):
            resp = client.post("/health/ingest", json={"lean_mass_kg": 68.0})
        saved = resp.json()["saved"]
        assert saved["lean_mass_lbs"] == round(68.0 * 2.20462, 1)

    def test_empty_body_rejected(self):
        """Empty POST doesn't overwrite good cached data."""
        with patch("integrations.cache.save") as mock_save:
            resp = client.post("/health/ingest", json={})
        assert resp.json()["status"] == "error"
        mock_save.assert_not_called()

    def test_out_of_range_rejected(self):
        """Values outside sanity ranges are rejected by Pydantic."""
        resp = client.post("/health/ingest", json={"weight_lbs": -10})
        assert resp.status_code == 422

    def test_lbs_preferred_over_kg(self):
        """When both weight_lbs and weight_kg are provided, lbs wins."""
        with patch("integrations.cache.save"):
            resp = client.post("/health/ingest", json={"weight_lbs": 185.0, "weight_kg": 84.0})
        assert resp.json()["saved"]["weight_lbs"] == 185.0

    def test_get_not_allowed(self):
        resp = client.get("/health/ingest")
        assert resp.status_code == 405
