"""Tests for integrations/apple_health.py (body composition only)"""

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

from integrations.apple_health import get_summary, _parse_body_comp, _summarize


def _make_export_xml(records: list[dict]) -> str:
    """Generate minimal Apple Health XML with given records."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<HealthData>"]
    for r in records:
        attrs = " ".join(f'{k}="{v}"' for k, v in r.items())
        lines.append(f"  <Record {attrs}/>")
    lines.append("</HealthData>")
    return "\n".join(lines)


class TestGetSummary:
    def test_returns_cached_data(self):
        cached = {"source": "apple_health", "weight_lbs": 180.0, "body_fat_pct": 18.5}
        with patch("integrations.apple_health.cache.load", return_value=cached):
            result = get_summary()
        assert result["weight_lbs"] == 180.0

    def test_returns_error_when_export_missing(self, tmp_path):
        missing = tmp_path / "nonexistent.xml"
        with patch("integrations.apple_health.cache.load", return_value=None), \
             patch.dict(os.environ, {"APPLE_HEALTH_EXPORT_PATH": str(missing)}):
            result = get_summary()
        assert "error" in result
        assert "No Apple Health export found" in result["error"]

    def test_parses_export_and_caches(self, tmp_path):
        xml = _make_export_xml([
            {
                "type": "HKQuantityTypeIdentifierBodyMass",
                "startDate": "2026-03-28 07:30:00 -0500",
                "value": "81.6",
                "unit": "kg",
            },
            {
                "type": "HKQuantityTypeIdentifierBodyFatPercentage",
                "startDate": "2026-03-28 07:30:00 -0500",
                "value": "18.5",
                "unit": "%",
            },
        ])
        export_file = tmp_path / "export.xml"
        export_file.write_text(xml)

        with patch("integrations.apple_health.cache.load", return_value=None), \
             patch("integrations.apple_health.cache.save") as mock_save, \
             patch.dict(os.environ, {"APPLE_HEALTH_EXPORT_PATH": str(export_file)}):
            result = get_summary()

        assert result["source"] == "apple_health"
        assert result["weight_lbs"] == 179.9  # 81.6 kg * 2.20462
        assert result["body_fat_pct"] == 18.5
        mock_save.assert_called_once()


class TestParseBodyComp:
    def test_extracts_weight_in_kg(self, tmp_path):
        xml = _make_export_xml([{
            "type": "HKQuantityTypeIdentifierBodyMass",
            "startDate": "2026-03-28 07:30:00 -0500",
            "value": "80.0",
            "unit": "kg",
        }])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert result["weight_lbs"] == 176.4  # 80 * 2.20462 rounded

    def test_extracts_body_fat_percentage(self, tmp_path):
        xml = _make_export_xml([{
            "type": "HKQuantityTypeIdentifierBodyFatPercentage",
            "startDate": "2026-03-28 07:30:00 -0500",
            "value": "22.3",
            "unit": "%",
        }])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert result["body_fat_pct"] == 22.3

    def test_extracts_lean_body_mass(self, tmp_path):
        xml = _make_export_xml([{
            "type": "HKQuantityTypeIdentifierLeanBodyMass",
            "startDate": "2026-03-28 07:30:00 -0500",
            "value": "65.0",
            "unit": "kg",
        }])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert result["lean_mass_lbs"] == 143.3  # 65 * 2.20462 rounded

    def test_skips_old_records(self, tmp_path):
        xml = _make_export_xml([{
            "type": "HKQuantityTypeIdentifierBodyMass",
            "startDate": "2024-01-01 07:30:00 -0500",  # >30 days ago
            "value": "80.0",
            "unit": "kg",
        }])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert "weight_lbs" not in result
        assert "error" in result  # no data found

    def test_skips_non_bodycomp_records(self, tmp_path):
        xml = _make_export_xml([
            {
                "type": "HKQuantityTypeIdentifierStepCount",
                "startDate": "2026-03-28 07:30:00 -0500",
                "value": "8500",
                "unit": "count",
            },
            {
                "type": "HKQuantityTypeIdentifierBodyMass",
                "startDate": "2026-03-28 07:30:00 -0500",
                "value": "80.0",
                "unit": "kg",
            },
        ])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert "weight_lbs" in result
        # StepCount should be ignored — only body comp types extracted

    def test_weight_trend_calculation(self, tmp_path):
        xml = _make_export_xml([
            {
                "type": "HKQuantityTypeIdentifierBodyMass",
                "startDate": "2026-03-20 07:30:00 -0500",
                "value": "82.0",
                "unit": "kg",
            },
            {
                "type": "HKQuantityTypeIdentifierBodyMass",
                "startDate": "2026-03-28 07:30:00 -0500",
                "value": "80.0",
                "unit": "kg",
            },
        ])
        f = tmp_path / "export.xml"
        f.write_text(xml)
        result = _parse_body_comp(f)
        assert result["weight_trend"] == "down"

    def test_handles_empty_xml(self, tmp_path):
        f = tmp_path / "export.xml"
        f.write_text('<?xml version="1.0"?><HealthData></HealthData>')
        result = _parse_body_comp(f)
        assert result["source"] == "apple_health"
        assert "error" in result
