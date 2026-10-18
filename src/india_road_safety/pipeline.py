"""Pipeline orchestration: collect -> ingest -> analyse -> report.

This is the single place that wires configuration, the registry gate, the
politeness-bounded HTTP fetcher, the store and the report together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .analysis import accident as accident_analysis
from .analysis import evidence as evidence_analysis
from .analysis import vehicles as vehicle_analysis
from .collect import gncap as gncap_collector
from .collect import morth as morth_collector
from .collect.base import Collection, ingest
from .config import Settings, load_settings
from .http import HttpFetcher, RateLimiter
from .registry import Registry
from .store import Store

GLOBAL_NCAP = "global-ncap"
MORTH = "morth-road-accidents-in-india"

# slug -> collector callable(fetcher, settings) -> Collection
COLLECTORS: dict[str, Callable[..., Collection]] = {
    MORTH: morth_collector.collect_morth,
    GLOBAL_NCAP: gncap_collector.collect_gncap,
}


def make_fetcher(settings: Settings) -> HttpFetcher:
    h = settings.http
    return HttpFetcher(
        user_agent=h.get("user_agent", "india-road-safety-intelligence/0.1"),
        timeout=float(h.get("timeout_seconds", 30)),
        max_attempts=int(h.get("max_attempts", 3)),
        base_delay=float(h.get("base_delay_seconds", 1.0)),
        max_delay=float(h.get("max_delay_seconds", 15.0)),
        rate_limiter=RateLimiter(float(h.get("min_seconds_between_requests", 1.0))),
    )


def open_store(settings: Optional[Settings] = None) -> Store:
    settings = settings or load_settings()
    store = Store(settings.db_path)
    store.migrate()
    return store


def register_sources(store: Store, registry: Registry) -> None:
    for source in registry.all():
        store.upsert_source(source.model_dump())


def collect(
    store: Store,
    registry: Registry,
    settings: Settings,
    fetcher: Optional[HttpFetcher] = None,
    only: Optional[list[str]] = None,
    max_fact_sheets: Optional[int] = None,
) -> dict[str, Any]:
    """Run collectors for verified sources and ingest their records."""

    fetcher = fetcher or make_fetcher(settings)
    register_sources(store, registry)
    summary: dict[str, Any] = {"sources": {}, "new_records": 0, "errors": []}

    targets = only or list(COLLECTORS)
    for slug in targets:
        registry.require_verified(slug)  # blocks non-verified sources
        collector = COLLECTORS.get(slug)
        if collector is None:
            summary["errors"].append(f"no collector for {slug}")
            continue
        try:
            if slug == GLOBAL_NCAP and max_fact_sheets is not None:
                collection = collector(fetcher, settings, max_fact_sheets=max_fact_sheets)
            else:
                collection = collector(fetcher, settings)
        except Exception as exc:  # pragma: no cover - network dependent
            summary["errors"].append(f"{slug}: {exc}")
            store.record_run(slug, "failed", error_count=1, message=str(exc))
            continue

        new = ingest(collection, store)
        summary["new_records"] += new
        summary["sources"][slug] = collection.record_summary()
        status = "ok" if not collection.errors else "partial"
        store.record_run(
            slug,
            status,
            new_count=new,
            error_count=len(collection.errors),
            message="; ".join(collection.errors[:3]) or None,
        )
        if collection.errors:
            summary["errors"].extend(collection.errors)
    return summary


# --------------------------------------------------------------------------- #
# Analysis context
# --------------------------------------------------------------------------- #
def _records(store: Store, table: str) -> list[dict[str, Any]]:
    return store.query(f"SELECT * FROM {table}")


def build_context(store: Store, registry: Registry, settings: Settings) -> dict[str, Any]:
    """Assemble the report context from stored records."""

    accident_rows = _records(store, "accident_records")
    crash_rows = _records(store, "crash_tests")

    summary = accident_analysis.national_summary(accident_rows)
    latest_year = summary.get("year") if summary else accident_analysis.latest_year(accident_rows)
    # road-type / risk factors are for 2022 in the sourced report
    context_year = 2022 if latest_year != 2022 else latest_year
    if not any(r.get("road_type") for r in accident_rows):
        context_year = latest_year

    state = accident_analysis.state_table(accident_rows)
    latest_data_year = max([latest_year or 0, state.get("year") or 0]) or None

    min_n = int(settings.analysis.get("min_sample_size", 30)) if settings.analysis else 30
    build_year = datetime.now(timezone.utc).year
    counts: dict[str, int] = {}
    for table in ("crash_tests", "accident_records", "documents", "exposures"):
        for r in store.query(f"SELECT source_slug, COUNT(*) AS c FROM {table} GROUP BY source_slug"):
            counts[r["source_slug"]] = counts.get(r["source_slug"], 0) + int(r["c"])
    sources = [s.model_dump(mode="json") for s in registry.all()]

    ctx: dict[str, Any] = {
        "title": "India Road Safety & Passenger-Car Safety — Evidence Report",
        "generated_at": datetime.now(timezone.utc),
        "cutoff_policy": settings.study.get("cutoff_policy"),
        "latest_data_year": latest_data_year,
        "source_count": len(registry),
        "national_summary": summary,
        "national_trend": accident_analysis.national_trend(accident_rows),
        "exposure_adjusted": accident_analysis.exposure_adjusted(accident_rows),
        "road_type": accident_analysis.road_type_breakdown(accident_rows, context_year),
        "road_user": accident_analysis.road_user_shares(accident_rows, context_year),
        "risk_factors": accident_analysis.risk_factors(accident_rows, context_year),
        "trend_stats": accident_analysis.trend_stats(accident_rows),
        "collision_breakdown": accident_analysis.collision_breakdown(accident_rows, context_year),
        "time_of_day": accident_analysis.time_of_day_breakdown(accident_rows, context_year),
        "monthly": accident_analysis.monthly_series(accident_rows, context_year),
        "safety_devices": accident_analysis.safety_device_deaths(accident_rows, context_year),
        "state_table": state,
        "crash_test_table": vehicle_analysis.crash_test_table(crash_rows),
        "bodyshell_counts": vehicle_analysis.bodyshell_counts(crash_rows),
        "equipment_summary": vehicle_analysis.equipment_summary(crash_rows),
        "protocol_eras": vehicle_analysis.protocol_era_split(crash_rows),
        "equipment_contrast": vehicle_analysis.equipment_contrast(crash_rows, min_n=min_n),
        "evidence_grading": evidence_analysis.grade_sources(
            sources, counts, latest_year=latest_data_year, build_year=build_year
        ),
        "sources": sources,
    }
    return ctx


def write_report(ctx: dict[str, Any], settings: Optional[Settings] = None) -> Path:
    from .report import html as report_html

    settings = settings or load_settings()
    out = settings.path(settings.report.get("output", "reports/india-road-safety-report.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_html.build_report(ctx), encoding="utf-8")
    return out


def run_all(settings: Optional[Settings] = None, max_fact_sheets: Optional[int] = None) -> dict[str, Any]:
    """Full pipeline: collect (verified sources) and generate the report."""

    settings = settings or load_settings()
    store = open_store(settings)
    registry = Registry.load(settings=settings)
    collect_summary = collect(store, registry, settings, max_fact_sheets=max_fact_sheets)
    ctx = build_context(store, registry, settings)
    report_path = write_report(ctx, settings)
    return {"collect": collect_summary, "report": str(report_path), "context_keys": sorted(ctx)}
