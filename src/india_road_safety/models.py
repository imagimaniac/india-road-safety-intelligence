"""Domain models.

One central rule, adapted from ``~/Projects/investment-research``:

    An unavailable value is ``None`` (NULL), never ``0`` and never a stale copy.

Models are separated by *evidence type*. Accident counts, official statistics,
news claims and crash-test assessments are different observations and are
represented by different models. They are never merged into one "observation".

Pydantic validates at the boundaries (collectors, registry, fixtures). The
storage layer serialises these to SQLite (see :mod:`india_road_safety.store`).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class SourceStatus(str, Enum):
    VERIFIED = "verified"
    PENDING = "pending_verification"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class AccessMethod(str, Enum):
    OFFICIAL_API = "official_api"
    BULK_DOWNLOAD = "bulk_download"
    PDF_REPORT = "pdf_report"
    STRUCTURED_HTML = "structured_html"
    PERMITTED_SCRAPING = "permitted_scraping"
    MANUAL_ONLY = "manual_only"


class DataType(str, Enum):
    ACCIDENT_STATS = "accident_stats"
    CRASH_TEST = "crash_test"
    RECALL = "recall"
    REGISTRATION = "registration"
    RESEARCH = "research"
    NEWS = "news"
    OTHER = "other"


class Jurisdiction(str, Enum):
    IN = "IN"
    GLOBAL = "GLOBAL"
    OTHER = "OTHER"


class GeoLevel(str, Enum):
    NATIONAL = "national"
    STATE = "state"
    DISTRICT = "district"
    CITY = "city"


class Severity(str, Enum):
    FATAL = "fatal"
    SERIOUS = "serious"
    MINOR = "minor"
    DAMAGE_ONLY = "damage_only"
    UNKNOWN = "unknown"


class EvidenceClass(str, Enum):
    """Distinguishes what kind of statement a record represents."""

    OBSERVED_FACT = "observed_fact"          # directly from a primary document
    EXTRACTED_CLAIM = "extracted_claim"      # a claim extracted from a text source
    ANALYST_INTERPRETATION = "analyst_interpretation"


class ConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


# --------------------------------------------------------------------------- #
# Sources, documents, provenance
# --------------------------------------------------------------------------- #
class Source(_Base):
    """A registered data source (mirrors an entry in ``config/sources.yaml``)."""

    slug: str
    organization: str
    url: Optional[str] = None
    access_method: AccessMethod
    data_type: DataType
    jurisdiction: Jurisdiction = Jurisdiction.OTHER
    status: SourceStatus = SourceStatus.PENDING
    coverage: Optional[dict[str, Any]] = None
    licence: Optional[str] = None
    permitted_use: Optional[str] = None
    terms_url: Optional[str] = None
    attribution: Optional[str] = None
    verified_on: Optional[date] = None
    notes: Optional[str] = None

    @property
    def is_usable(self) -> bool:
        """Collection is allowed only for verified sources."""
        return self.status == SourceStatus.VERIFIED.value


class Provenance(_Base):
    """Where a record came from. Attached to anything reported."""

    source_slug: str
    source_url: Optional[str] = None
    document_id: Optional[int] = None
    retrieved_at: datetime
    method: str
    http_status: Optional[int] = None
    content_sha256: Optional[str] = None
    note: Optional[str] = None


class Document(_Base):
    """A retrieved artefact (PDF, CSV, HTML page) with a stable content hash."""

    source_slug: str
    url: str
    title: Optional[str] = None
    doc_type: Optional[str] = None
    published_on: Optional[date] = None
    retrieved_at: datetime
    content_sha256: Optional[str] = None
    raw_path: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


# --------------------------------------------------------------------------- #
# Accident statistics (aggregate observations)
# --------------------------------------------------------------------------- #
class AccidentRecord(_Base):
    """One aggregate observation from an official/institutional statistic.

    This is intentionally *aggregate* — it is not an individual crash linked to a
    person or a specific car. Individual records are only added if a lawful,
    de-identified dataset becomes available.
    """

    geography: str
    geo_level: GeoLevel = GeoLevel.NATIONAL
    year: int
    month: Optional[int] = None
    road_type: Optional[str] = None
    road_user: Optional[str] = None
    label: Optional[str] = None         # dimension value (collision type, time interval, ...)
    severity: Severity = Severity.UNKNOWN
    metric: str                       # e.g. "accidents", "fatalities", "injuries"
    value: Optional[float] = None     # None = not reported (never 0 by default)
    unit: str = "count"               # "count" | "percent" | "per_lakh" | ...
    source_slug: str
    document_id: Optional[int] = None
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED_FACT
    confidence: ConfidenceBand = ConfidenceBand.UNVERIFIED

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 12):
            raise ValueError("month must be 1..12")
        return v


# --------------------------------------------------------------------------- #
# Vehicle catalogue (normalized, auditable)
# --------------------------------------------------------------------------- #
class VehicleMake(_Base):
    name: str
    slug: str
    parent: Optional[str] = None
    country: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)


class VehicleModel(_Base):
    make_slug: str
    name: str
    slug: str
    body_style: Optional[str] = None
    segment: Optional[str] = None
    launch_year: Optional[int] = None
    notes: Optional[str] = None


class VehicleGeneration(_Base):
    model_slug: str
    name: str
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    platform: Optional[str] = None
    structural_notes: Optional[str] = None


class VehicleVariant(_Base):
    generation_ref: str               # slug identifying the generation
    name: str
    model_year: Optional[int] = None
    fuel: Optional[str] = None
    transmission: Optional[str] = None
    safety_equipment: Optional[dict[str, Any]] = None


# --------------------------------------------------------------------------- #
# Crash tests, recalls, exposure
# --------------------------------------------------------------------------- #
class CrashTestAssessment(_Base):
    """A single model-level crash-test result.

    ``program``, ``protocol_version``, ``market`` and the tested equipment are
    first-class because star ratings are only comparable within a matched
    protocol/market/spec. ``is_comparable`` defaults to False and must be set
    deliberately.
    """

    variant_ref: Optional[str] = None
    make_slug: Optional[str] = None
    model_slug: Optional[str] = None
    program: str
    protocol_version: Optional[str] = None
    test_date: Optional[date] = None
    market: Optional[str] = None
    adult_stars: Optional[int] = None
    child_stars: Optional[int] = None
    overall_stars: Optional[int] = None
    adult_occupant_protection: Optional[float] = None   # 0..100 where reported
    child_occupant_protection: Optional[float] = None
    safety_assist: Optional[float] = None
    equipment_tested: Optional[str] = None
    bodyshell: Optional[str] = None
    source_slug: str
    document_id: Optional[int] = None
    is_comparable: bool = False
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED_FACT
    confidence: ConfidenceBand = ConfidenceBand.UNVERIFIED

    @field_validator("adult_stars", "child_stars", "overall_stars")
    @classmethod
    def _check_stars(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 5):
            raise ValueError("star rating must be 0..5")
        return v

    @field_validator(
        "adult_occupant_protection", "child_occupant_protection", "safety_assist"
    )
    @classmethod
    def _check_pct(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("percentage score must be 0..100")
        return v


class Recall(_Base):
    make_slug: str
    model_slug: Optional[str] = None
    year_range: Optional[str] = None
    defect: str
    remedy: Optional[str] = None
    announced_on: Optional[date] = None
    source_slug: Optional[str] = None
    document_id: Optional[int] = None
    confidence: ConfidenceBand = ConfidenceBand.UNVERIFIED


class RegistrationExposure(_Base):
    """An exposure denominator (registrations, fleet size) — never an outcome."""

    geography: str
    geo_level: GeoLevel = GeoLevel.NATIONAL
    year: int
    vehicle_category: str
    metric: str                       # e.g. "registrations", "fleet"
    value: Optional[int] = None
    unit: str = "count"
    source_slug: str
    document_id: Optional[int] = None
    confidence: ConfidenceBand = ConfidenceBand.UNVERIFIED


# --------------------------------------------------------------------------- #
# Evidence grading
# --------------------------------------------------------------------------- #
DEFAULT_EVIDENCE_DIMENSIONS = (
    "primary_source",
    "corroboration",
    "recency",
    "completeness",
    "identification_confidence",
)


class EvidenceGrade(_Base):
    """How defensible a claim is. Deliberately separate from any judgement of
    "quality" or "importance".

    Each dimension is 0..100. ``None`` means the dimension was not assessed.
    The composite is a weighted mean over *assessed* dimensions only; if no
    dimension is assessed, the composite is ``None`` (not 0).
    """

    dimensions: dict[str, Optional[float]] = Field(default_factory=dict)
    weights: Optional[dict[str, float]] = None
    method: str = "weighted_mean_of_assessed_dimensions"

    @field_validator("dimensions")
    @classmethod
    def _check_dims(cls, v: dict[str, Optional[float]]) -> dict[str, Optional[float]]:
        for k, val in v.items():
            if val is not None and not (0.0 <= val <= 100.0):
                raise ValueError(f"dimension {k!r} must be 0..100 or None")
        return v

    def composite(self) -> Optional[float]:
        items = [(k, v) for k, v in self.dimensions.items() if v is not None]
        if not items:
            return None
        if not self.weights:
            return sum(v for _, v in items) / len(items)
        num = 0.0
        den = 0.0
        for k, v in items:
            w = self.weights.get(k, 1.0)
            num += v * w
            den += w
        return num / den if den else None
