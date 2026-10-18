from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from india_road_safety.models import (
    AccidentRecord,
    CrashTestAssessment,
    EvidenceGrade,
    Provenance,
    Source,
    SourceStatus,
)


def test_source_usable_only_when_verified():
    pending = Source(
        slug="morth", organization="MoRTH", access_method="pdf_report",
        data_type="accident_stats", status=SourceStatus.PENDING,
    )
    verified = Source(
        slug="morth", organization="MoRTH", access_method="pdf_report",
        data_type="accident_stats", status=SourceStatus.VERIFIED,
    )
    assert pending.is_usable is False
    assert verified.is_usable is True


def test_accident_record_allows_none_value():
    rec = AccidentRecord(
        geography="India", year=2023, severity="fatal", metric="fatalities",
        value=None, source_slug="morth",
    )
    assert rec.value is None       # not reported != 0
    assert rec.geo_level == "national"


def test_accident_record_month_validation():
    with pytest.raises(ValidationError):
        AccidentRecord(
            geography="India", year=2023, month=13, severity="fatal",
            metric="fatalities", source_slug="morth",
        )


def test_crash_test_stars_and_pct_validation_and_comparability_default():
    ct = CrashTestAssessment(
        program="Bharat NCAP", adult_stars=5, child_stars=4,
        adult_occupant_protection=100.0, market="India", source_slug="bncap",
    )
    assert ct.is_comparable is False  # must be set deliberately

    with pytest.raises(ValidationError):
        CrashTestAssessment(program="X", adult_stars=6, source_slug="s")
    with pytest.raises(ValidationError):
        CrashTestAssessment(program="X", adult_occupant_protection=150.0, source_slug="s")


def test_evidence_grade_composite_none_when_unassessed():
    g = EvidenceGrade(dimensions={"primary_source": None, "recency": None})
    assert g.composite() is None


def test_evidence_grade_unweighted_mean_of_assessed():
    g = EvidenceGrade(dimensions={"primary_source": 80.0, "recency": 60.0, "corroboration": None})
    assert g.composite() == 70.0


def test_evidence_grade_weighted_mean():
    g = EvidenceGrade(
        dimensions={"primary_source": 100.0, "recency": 0.0},
        weights={"primary_source": 3.0, "recency": 1.0},
    )
    assert g.composite() == 75.0


def test_evidence_grade_rejects_out_of_range():
    with pytest.raises(ValidationError):
        EvidenceGrade(dimensions={"primary_source": 150.0})


def test_provenance_requires_retrieved_at():
    p = Provenance(
        source_slug="morth", method="pdf_report",
        retrieved_at=datetime.now(timezone.utc),
    )
    assert p.source_slug == "morth"
    with pytest.raises(ValidationError):
        Provenance(source_slug="morth", method="pdf_report")  # missing retrieved_at
