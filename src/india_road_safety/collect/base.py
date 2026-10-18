"""Collection infrastructure.

Collectors produce a ``Collection`` of parsed records. The ``ingest`` helper
writes those records to the store, validates against JSON schemas, and records
run outcomes. Network access is expected to be injected (via ``http.HttpFetcher``)
and all parsing must remain deterministic and testable on fixtures.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .. import models, schema
from ..normalize import content_hash
from ..store import Store


class CollectionError(Exception):
    """Raised when a collector produces an invalid collection."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_document(
    source_slug: str,
    url: str,
    data: bytes | str,
    title: Optional[str] = None,
    doc_type: Optional[str] = None,
    raw_path: Optional[str] = None,
) -> models.Document:
    """Build a :class:`Document` with a stable content hash for provenance."""
    body = data.encode("utf-8") if isinstance(data, str) else data
    return models.Document(
        source_slug=source_slug,
        url=url,
        title=title,
        doc_type=doc_type,
        retrieved_at=_now(),
        content_sha256=hashlib.sha256(body).hexdigest(),
        raw_path=raw_path,
    )


def _coerce_doc(doc: models.Document) -> dict[str, Any]:
    d = doc.model_dump()
    # ensure datetime serialised
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _safe(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool, bytes)):
        return v
    if hasattr(v, "model_dump"):
        return v.model_dump()
    if hasattr(v, "value"):  # enum
        return v.value
    if hasattr(v, "isoformat"):  # datetime/date
        return v.isoformat()
    return str(v)


@dataclass
class Collection:
    """Container of parsed records produced by a collector."""

    source_slug: str
    documents: list[models.Document] = field(default_factory=list)
    accident_records: list[models.AccidentRecord] = field(default_factory=list)
    crash_tests: list[models.CrashTestAssessment] = field(default_factory=list)
    exposures: list[models.RegistrationExposure] = field(default_factory=list)
    recalls: list[models.Recall] = field(default_factory=list)
    provenance: list[models.Provenance] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def has_fatal_error(self) -> bool:
        return len(self.errors) > 10  # heuristic; caller can override

    def record_summary(self) -> dict[str, int]:
        return {
            "documents": len(self.documents),
            "accident_records": len(self.accident_records),
            "crash_tests": len(self.crash_tests),
            "exposures": len(self.exposures),
            "recalls": len(self.recalls),
            "provenance": len(self.provenance),
            "errors": len(self.errors),
        }


def _accident_content_hash(r: models.AccidentRecord) -> str:
    return content_hash(
        r.geography,
        r.geo_level,
        r.year,
        r.month,
        r.road_type,
        r.road_user,
        r.label,
        r.severity,
        r.metric,
        r.value,
        r.unit,
        r.source_slug,
    )


def _crash_content_hash(r: models.CrashTestAssessment) -> str:
    return content_hash(
        r.program,
        r.protocol_version,
        r.test_date,
        r.market,
        r.variant_ref,
        r.make_slug,
        r.model_slug,
        r.adult_occupant_protection,
        r.child_occupant_protection,
        r.bodyshell,
        r.source_slug,
    )


def _exposure_content_hash(r: models.RegistrationExposure) -> str:
    return content_hash(
        r.geography,
        r.geo_level,
        r.year,
        r.vehicle_category,
        r.metric,
        r.value,
        r.unit,
        r.source_slug,
    )


def _recall_content_hash(r: models.Recall) -> str:
    return content_hash(
        r.make_slug,
        r.model_slug,
        r.year_range,
        r.defect,
        r.remedy,
        r.announced_on,
        r.source_slug,
    )


def ingest(collection: Collection, store: Store) -> int:
    """Ingest a collection into the store.

    Returns the number of new records written (counting primary fact rows
    that were not skipped by content-hash).
    """

    new_total = 0
    with store.connect() as conn:
        pass  # ensure schema up to date via store; caller can call migrate

    # Documents
    for d in collection.documents:
        try:
            schema.validate_record_like("document", d)
        except Exception as exc:  # pragma: no cover
            collection.add_error(f"document validation: {exc}")
            continue
        if d.content_sha256 and store.query(
            "SELECT 1 FROM documents WHERE content_sha256 = ? LIMIT 1", (d.content_sha256,)
        ):
            continue
        row = _coerce_doc(d)
        store.insert("documents", row)

    # Accident records
    for r in collection.accident_records:
        try:
            schema.validate_record_like("accident_record", r)
        except Exception as exc:
            collection.add_error(f"accident_record validation: {exc}")
            continue
        h = _accident_content_hash(r)
        if store.exists_by_hash("accident_records", h):
            continue
        row = r.model_dump()
        row["content_hash"] = h
        store.insert("accident_records", row)
        new_total += 1

    # Crash tests
    for r in collection.crash_tests:
        try:
            schema.validate_record_like("crash_test", r)
        except Exception as exc:
            collection.add_error(f"crash_test validation: {exc}")
            continue
        h = _crash_content_hash(r)
        if store.exists_by_hash("crash_tests", h):
            continue
        row = r.model_dump()
        row["content_hash"] = h
        store.insert("crash_tests", row)
        new_total += 1

    # Exposures
    for r in collection.exposures:
        try:
            schema.validate_record_like("exposure", r)
        except Exception as exc:
            collection.add_error(f"exposure validation: {exc}")
            continue
        h = _exposure_content_hash(r)
        if store.exists_by_hash("exposures", h):
            continue
        row = r.model_dump()
        row["content_hash"] = h
        store.insert("exposures", row)
        new_total += 1

    # Recalls
    for r in collection.recalls:
        try:
            schema.validate_record_like("recall", r)
        except Exception as exc:
            collection.add_error(f"recall validation: {exc}")
            continue
        h = _recall_content_hash(r)
        if store.exists_by_hash("recalls", h):
            continue
        row = r.model_dump()
        row["content_hash"] = h
        store.insert("recalls", row)
        new_total += 1

    # Provenance
    for p in collection.provenance:
        try:
            schema.validate_record_like("provenance", p)
        except Exception as exc:  # pragma: no cover
            collection.add_error(f"provenance validation: {exc}")
            continue
        store.insert("provenance", p.model_dump())

    return new_total
