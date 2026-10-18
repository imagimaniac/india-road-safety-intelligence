"""Evidence grading for registered sources.

Each source is scored 0-100 on the five independent dimensions declared in
``config/settings.yaml`` (``evidence.dimensions``). The dimensions are kept
**separate** — they are not a single quality judgement — and any summary is an
explicit mean of the parts, shown alongside them in the report.

Scoring is deliberately transparent and rule-based (no black box): every
dimension's rule is stated so a reader can disagree with it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Optional

_DIMENSIONS = (
    "primary_source",
    "corroboration",
    "recency",
    "completeness",
    "identification_confidence",
)

_OFFICIAL_METHODS = {"official_api", "bulk_download", "pdf_report"}


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, float(x)))


def _mean(dims: dict[str, float]) -> float:
    return round(sum(dims.values()) / len(dims), 1) if dims else 0.0


def score_source(
    source: dict[str, Any],
    *,
    record_count: int = 0,
    same_type_verified: int = 1,
    latest_year: Optional[int] = None,
    build_year: Optional[int] = None,
) -> dict[str, Any]:
    """Score one source on the five evidence dimensions (0-100 each)."""
    status = (source.get("status") or "").lower()
    method = (source.get("access_method") or "").lower()
    dtype = (source.get("data_type") or "").lower()

    dims: dict[str, float] = {}
    # primary_source — is this straight from the publishing body?
    if status == "verified" and method in _OFFICIAL_METHODS:
        dims["primary_source"] = 90.0
    elif status == "verified" and method == "structured_html":
        dims["primary_source"] = 75.0
    elif status == "verified":
        dims["primary_source"] = 60.0
    else:
        dims["primary_source"] = 20.0
    # corroboration — is the same data_type independently verified elsewhere?
    dims["corroboration"] = 80.0 if same_type_verified >= 2 else 45.0
    # recency — age of the latest data year relative to the build year.
    if latest_year and build_year:
        dims["recency"] = _clamp(100.0 - max(0, build_year - latest_year) * 25.0)
    else:
        dims["recency"] = 50.0
    # completeness — did this source actually yield stored records?
    dims["completeness"] = 100.0 if record_count > 0 else 10.0
    # identification_confidence — how sure are we what entity a record describes?
    if any(k in dtype for k in ("accident", "crash", "stat", "exposure")):
        dims["identification_confidence"] = 85.0
    elif "news" in dtype:
        dims["identification_confidence"] = 35.0
    else:
        dims["identification_confidence"] = 60.0

    return {
        "slug": source.get("slug"),
        "status": status,
        "record_count": record_count,
        "dimensions": dims,
        "mean_score": _mean(dims),
    }


def grade_sources(
    sources: Iterable[dict[str, Any]],
    counts: dict[str, int],
    *,
    latest_year: Optional[int] = None,
    build_year: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Grade every source. ``counts`` maps slug -> stored record count."""
    srcs = list(sources)
    type_counts = Counter(
        (s.get("data_type") or "").lower()
        for s in srcs
        if (s.get("status") or "").lower() == "verified"
    )
    out = []
    for s in srcs:
        dtype = (s.get("data_type") or "").lower()
        out.append(
            score_source(
                s,
                record_count=counts.get(s.get("slug"), 0),
                same_type_verified=type_counts.get(dtype, 1),
                latest_year=latest_year,
                build_year=build_year,
            )
        )
    return out


DIMENSIONS = _DIMENSIONS
