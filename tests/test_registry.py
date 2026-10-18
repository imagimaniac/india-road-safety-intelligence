"""Tests for the source registry (provenance root)."""

from __future__ import annotations

import textwrap

import pytest

from india_road_safety import models, registry


def test_from_mapping_roundtrips_id_to_slug():
    data = {
        "version": 1,
        "sources": [
            {
                "id": "example-src",
                "organization": "Example Org",
                "url": "https://example.org",
                "access_method": "structured_html",
                "data_type": "accident_stats",
                "jurisdiction": "IN",
                "status": "verified",
                "notes": "test",
            }
        ],
    }
    r = registry.Registry.from_mapping(data)
    src = r.get("example-src")
    assert src.organization == "Example Org"
    assert src.status == "verified"
    assert r.verified() == [src]


def test_duplicate_slug_raises():
    data = {
        "version": 1,
        "sources": [
            {
                "id": "x",
                "organization": "A",
                "url": "https://a",
                "access_method": "structured_html",
                "data_type": "accident_stats",
                "jurisdiction": "IN",
                "status": "verified",
            },
            {
                "id": "x",
                "organization": "B",
                "url": "https://b",
                "access_method": "structured_html",
                "data_type": "accident_stats",
                "jurisdiction": "IN",
                "status": "pending_verification",
            },
        ],
    }
    with pytest.raises(registry.RegistryError):
        registry.Registry.from_mapping(data)


def test_unknown_source_errors():
    r = registry.Registry.from_mapping({"version": 1, "sources": []})
    with pytest.raises(registry.RegistryError):
        r.get("missing")


def test_require_verified_blocks_pending():
    r = registry.Registry.from_mapping({
        "version": 1,
        "sources": [
            {
                "id": "pending",
                "organization": "Org",
                "url": "https://p",
                "access_method": "structured_html",
                "data_type": "accident_stats",
                "jurisdiction": "IN",
                "status": "pending_verification",
            }
        ],
    })
    with pytest.raises(registry.SourceNotVerified):
        r.require_verified("pending")


def test_require_verified_allows_verified():
    r = registry.Registry.from_mapping({
        "version": 1,
        "sources": [
            {
                "id": "ok",
                "organization": "Org",
                "url": "https://p",
                "access_method": "structured_html",
                "data_type": "accident_stats",
                "jurisdiction": "IN",
                "status": "verified",
            }
        ],
    })
    src = r.require_verified("ok")
    assert src.slug == "ok"
    assert src.is_usable


def test_load_real_registry_has_expected_statuses():
    r = registry.Registry.load()
    # Newly verified sources exist and are usable
    assert "morth-road-accidents-in-india" in r
    assert "morth-state-wise-accidents" in r
    assert "global-ncap" in r
    # Bharat NCAP blocked in recon
    assert r.get("bharat-ncap").status == models.SourceStatus.BLOCKED.value
    # At least some are verified
    assert len(r.verified()) >= 3
    # Sanity check: blocked is not usable
    assert not r.get("bharat-ncap").is_usable
    # The two new morth/global-ncap are usable
    assert r.get("morth-road-accidents-in-india").is_usable
    assert r.get("morth-state-wise-accidents").is_usable
    assert r.get("global-ncap").is_usable
