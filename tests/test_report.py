"""Tests for inline SVG primitives and the HTML report builder."""

from __future__ import annotations

from india_road_safety.report import html as report_html
from india_road_safety.report import svg


def test_line_chart_returns_svg():
    out = svg.line_chart([("2020", 1), ("2021", 2), ("2022", 3)], y_label="Deaths")
    assert out.startswith("<svg") and out.endswith("</svg>")
    assert "2022" in out


def test_line_chart_handles_insufficient_data():
    out = svg.line_chart([("2022", 3)])
    assert "Not enough data" in out


def test_donut_and_hbar_and_grouped():
    d = svg.donut_chart([("A", 44.5), ("B", 19.5), ("C", 12.5)])
    assert d.startswith("<svg")
    h = svg.hbar_chart(["X", "Y"], [10, 20])
    assert h.startswith("<svg")
    g = svg.grouped_bar_chart(["m1", "m2"], {"adult": [90, 50], "child": [40, 60]})
    assert g.startswith("<svg")


def test_no_external_resources_in_svg():
    out = svg.line_chart([("2020", 1), ("2021", 2)])
    assert "http://" not in out and "https://" not in out
    assert "<script" not in out


def _ctx():
    return {
        "title": "Test Report",
        "generated_at": "2026-10-17T00:00:00Z",
        "latest_data_year": 2024,
        "source_count": 7,
        "national_summary": {"year": 2022, "accidents": 461312, "fatalities": 168491, "injuries": 443366, "accidents_yoy_pct": 11.9, "prev_year": 2021},
        "national_trend": [
            {"year": 2020, "accidents": 372181, "fatalities": 138383, "injuries": 346747},
            {"year": 2021, "accidents": 412432, "fatalities": 153972, "injuries": 384448},
            {"year": 2022, "accidents": 461312, "fatalities": 168491, "injuries": 443366},
        ],
        "exposure_adjusted": [
            {"year": 2021, "fatalities_per_lakh_population": 11.3},
            {"year": 2022, "fatalities_per_lakh_population": 12.25},
        ],
        "road_type": [
            {"road_type": "national_highway", "accidents": 151997, "accidents_share_pct": 32.9, "fatalities": 61038, "fatalities_share_pct": 36.2},
            {"road_type": "state_highway", "accidents": 106682, "accidents_share_pct": 23.1, "fatalities": 41012, "fatalities_share_pct": 24.3},
            {"road_type": "other_road", "accidents": 202633, "accidents_share_pct": 43.9, "fatalities": 66441, "fatalities_share_pct": 39.4},
        ],
        "road_user": [
            {"category": "Two-wheeler riders", "share_pct": 44.5},
            {"category": "Pedestrians", "share_pct": 19.5},
            {"category": "Car / taxi / van / LMV occupants", "share_pct": 12.5},
        ],
        "risk_factors": {"overspeeding_share_of_accidents_pct": 72.3, "overspeeding_share_of_deaths_pct": 71.2, "wrong_side_share_of_accidents_pct": 4.9},
        "state_table": {"year": 2024, "prev_year": 2023, "rows": [
            {"state": "Tamil Nadu", "value": 66160, "prev_value": 67238, "change": -1078, "change_pct": -1.6},
        ]},
        "crash_test_table": [
            {"model_slug": "tata-nexon", "adult_points": 16.06, "adult_max": 17.0, "adult_pct_of_max": 94.5, "child_points": 25.0, "child_max": 49.0, "child_pct_of_max": 51.0, "bodyshell": "stable"},
        ],
        "bodyshell_counts": {"stable": 10, "unstable": 3},
        "equipment_summary": {"airbag": 20, "esc": 8},
        "protocol_eras": {"adult_max=17": 5, "adult_max=34": 12},
        "sources": [
            {"slug": "morth-road-accidents-in-india", "organization": "MoRTH", "url": "https://morth.gov.in/", "data_type": "accident_stats", "status": "verified", "licence": "GoI publication", "attribution": "MoRTH"},
        ],
    }


def test_build_report_is_self_contained_and_has_sections():
    out = report_html.build_report(_ctx())
    assert out.startswith("<!doctype html>")
    assert "</html>" in out
    # no external resources
    assert "http://" not in out.replace("https://morth.gov.in/", "")  # only the known source link
    assert "<script" not in out
    for section in ["Executive summary", "Scope", "National accident context", "Passenger-car safety", "What this data does NOT support", "Source register"]:
        assert section in out
    # values rendered
    assert "461,312" in out
    assert "44.5" in out


def test_build_report_renders_na_for_missing():
    ctx = _ctx()
    ctx["national_summary"]["accidents"] = None
    out = report_html.build_report(ctx)
    assert "n/a" in out
