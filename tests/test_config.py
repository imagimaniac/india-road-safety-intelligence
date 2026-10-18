"""Tests for configuration loading and path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from india_road_safety.config import ConfigError, load_settings, project_root


def test_project_root_contains_settings():
    root = project_root()
    assert (root / "config" / "settings.yaml").is_file()


def test_load_settings_paths_are_absolute_and_under_root():
    s = load_settings()
    assert s.root.is_absolute()
    for p in (s.data_dir, s.raw_dir, s.interim_dir, s.processed_dir, s.reports_dir, s.schemas_dir):
        assert p.is_absolute()
        assert str(p).startswith(str(s.root))


def test_load_settings_reads_guardrails():
    s = load_settings()
    assert s.min_sample_size == 30
    assert s.allow_cross_protocol_comparison is False
    assert s.study.get("primary_question") == "passenger_car_safety"
    assert s.study.get("cutoff_policy") == "latest_available_at_build"


def test_missing_config_raises():
    with pytest.raises(ConfigError):
        load_settings(Path("/nonexistent/settings.yaml"))
