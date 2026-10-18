"""Tests for Global NCAP parsers."""

from __future__ import annotations

from india_road_safety.collect import gncap
from tests.fixtures.morth_samples import GNCAP_FACT_SHEET_SAMPLE, GNCAP_RESULTS_SAMPLE


def test_parse_results_html_extracts_entries():
    entries = gncap.parse_gncap_results_html(GNCAP_RESULTS_SAMPLE)
    assert len(entries) == 2
    nexon = next(e for e in entries if "Nexon" in e["model"])
    assert nexon["body_type"] == "5 Door SUV"
    assert nexon["year"] == "2018"
    assert nexon["fact_sheet_url"].startswith("https://www.globalncap.org/")


def test_parse_fact_sheet_points_and_bodyshell():
    parsed = gncap.parse_gncap_fact_sheet(GNCAP_FACT_SHEET_SAMPLE)
    assert parsed["adult_occupant_protection"] == 16.06
    assert parsed["child_occupant_protection"] == 25.00
    assert parsed["bodyshell"] == "stable"
    assert "airbag" in parsed["equipment_tested"]


def test_points_are_not_confused_between_adult_child():
    # The regex must attribute 17.00-max to adult and 49.00-max to child,
    # regardless of order in the text.
    text = "25.00 max. 49.00 Child then 16.06 max. 17.00 Adult"
    parsed = gncap.parse_gncap_fact_sheet(text)
    assert parsed["child_occupant_protection"] == 25.00
    assert parsed["adult_occupant_protection"] == 16.06
