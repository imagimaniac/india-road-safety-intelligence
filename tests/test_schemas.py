"""Tests for JSON schemas and validation."""

from __future__ import annotations

import datetime

import pytest

from india_road_safety import models, schema


def test_validate_accident_record_minimal():
    rec = models.AccidentRecord(
        geography="India",
        geo_level="national",
        year=2022,
        severity="unknown",
        metric="accidents",
        source_slug="morth-road-accidents-in-india",
        evidence_class="observed_fact",
        confidence="medium",
    )
    schema.validate_record_like("accident_record", rec)


def test_validate_crash_test_minimal():
    ct = models.CrashTestAssessment(
        program="Global NCAP",
        source_slug="global-ncap",
        is_comparable=False,
        evidence_class="observed_fact",
        confidence="medium",
    )
    schema.validate_record_like("crash_test", ct)


def test_validate_rejects_bad_stars():
    bad = {
        "program": "GN",
        "source_slug": "global-ncap",
        "is_comparable": False,
        "evidence_class": "observed_fact",
        "confidence": "low",
        "adult_stars": 10,
    }
    with pytest.raises(schema.SchemaValidationError):
        schema.validate("crash_test", bad)


def test_validate_source_schema():
    s = models.Source(
        slug="test",
        organization="Test",
        access_method="structured_html",
        data_type="accident_stats",
        status="verified",
    )
    schema.validate_record_like("source", s)


def test_validate_exposure_and_recall():
    exp = models.RegistrationExposure(
        geography="India",
        geo_level="national",
        year=2022,
        vehicle_category="cars",
        metric="registrations",
        source_slug="morth-road-accidents-in-india",
        confidence="medium",
    )
    schema.validate_record_like("exposure", exp)
    rec = models.Recall(
        make_slug="tata",
        defect="test",
        source_slug="morth-road-accidents-in-india",
        confidence="medium",
    )
    schema.validate_record_like("recall", rec)
