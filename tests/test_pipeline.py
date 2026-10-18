"""End-to-end pipeline test with a fake HTTP fetcher (no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest

from india_road_safety import pipeline
from india_road_safety.collect import gncap, morth
from india_road_safety.config import Settings
from india_road_safety.registry import Registry
from india_road_safety.store import Store

from .fixtures import morth_samples as fx


class FakeFetcher:
    """Returns fixture payloads keyed by substring of the URL."""

    def __init__(self, pdf_text: str):
        self.pdf_text = pdf_text
        self.calls: list[str] = []

    def fetch_bytes(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> bytes:
        self.calls.append(url)
        if url.endswith(".pdf") and "fact" in url.lower():
            return fx.GNCAP_FACT_SHEET_SAMPLE.encode("utf-8")
        if url.endswith(".pdf"):
            return b"%PDF-1.4 fake-bytes"
        return fx.GNCAP_FACT_SHEET_SAMPLE.encode("utf-8")

    def fetch_text(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> str:
        self.calls.append(url)
        if "road-accidents" in url and url.endswith(".csv"):
            return fx.STATE_CSV_SAMPLE
        if url.endswith("/results"):
            return fx.GNCAP_RESULTS_SAMPLE
        if "fact" in url or "assessment" in url:
            return fx.GNCAP_FACT_SHEET_SAMPLE
        return fx.STATE_CSV_SAMPLE


def _settings(root: Path) -> Settings:
    (root / "config").mkdir(parents=True, exist_ok=True)
    raw = {
        "app": {"db_path": "data/interim/irsi.db"},
        "study": {"cutoff_policy": "latest_available_at_build"},
        "http": {"min_seconds_between_requests": 0, "max_attempts": 1},
        "analysis": {"min_sample_size": 30, "allow_cross_protocol_comparison": False},
        "report": {"output": "reports/india-road-safety-report.html", "charts": "inline_svg"},
    }
    return Settings(root=root, raw=raw)


def _registry() -> Registry:
    return Registry.from_mapping(
        {
            "version": 1,
            "sources": [
                {
                    "slug": "morth-road-accidents-in-india",
                    "organization": "MoRTH",
                    "url": "https://morth.gov.in/",
                    "access_method": "pdf_report",
                    "data_type": "accident_stats",
                    "status": "verified",
                },
                {
                    "slug": "morth-state-wise-accidents",
                    "organization": "MoRTH via data.opencity.in",
                    "url": "https://data.opencity.in/",
                    "access_method": "bulk_download",
                    "data_type": "accident_stats",
                    "status": "verified",
                },
                {
                    "slug": "global-ncap",
                    "organization": "Global NCAP",
                    "url": "https://www.globalncap.org/results",
                    "access_method": "structured_html",
                    "data_type": "crash_test",
                    "status": "verified",
                },
                {
                    "slug": "bharat-ncap",
                    "organization": "Bharat NCAP",
                    "url": "https://bharatncap.org/",
                    "access_method": "structured_html",
                    "data_type": "crash_test",
                    "status": "blocked",
                },
            ],
        }
    )


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return _settings(tmp_path)


def test_full_pipeline_offline(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(morth, "_extract_pdf_text", lambda b: fx.MO_NATIONAL_SERIES_SAMPLE + "\n" + fx.MO_PREFACE_SAMPLE)
    monkeypatch.setattr(gncap, "extract_text", lambda b: b.decode("utf-8"))
    store = pipeline.open_store(settings)
    registry = _registry()
    fetcher = FakeFetcher(fx.MO_NATIONAL_SERIES_SAMPLE)

    summary = pipeline.collect(store, registry, settings, fetcher=fetcher)
    assert summary["new_records"] > 0
    assert not summary["errors"], summary["errors"]
    assert store.count("accident_records") > 0
    assert store.count("crash_tests") == 2

    ctx = pipeline.build_context(store, registry, settings)
    assert ctx["national_summary"]["year"] == 2022
    assert ctx["national_summary"]["fatalities"] == 168491
    assert ctx["crash_test_table"]
    assert ctx["source_count"] == 4

    out = pipeline.write_report(ctx, settings)
    html = out.read_text(encoding="utf-8")
    assert "India Road Safety" in html
    assert "168,491" in html
    assert "<script" not in html


def test_collect_blocks_unverified(settings: Settings):
    store = pipeline.open_store(settings)
    registry = _registry()
    # bharat-ncap is registered but blocked -> require_verified must raise.
    from india_road_safety.registry import SourceNotVerified

    with pytest.raises(SourceNotVerified):
        pipeline.collect(store, registry, settings, fetcher=FakeFetcher(""), only=["bharat-ncap"])


def test_ingest_is_idempotent(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(morth, "_extract_pdf_text", lambda b: fx.MO_NATIONAL_SERIES_SAMPLE + "\n" + fx.MO_PREFACE_SAMPLE)
    monkeypatch.setattr(gncap, "extract_text", lambda b: b.decode("utf-8"))
    store = pipeline.open_store(settings)
    registry = _registry()
    fetcher = FakeFetcher(fx.MO_NATIONAL_SERIES_SAMPLE)
    pipeline.collect(store, registry, settings, fetcher=fetcher)
    first = store.count("accident_records")
    pipeline.collect(store, registry, settings, fetcher=fetcher)
    assert store.count("accident_records") == first
