"""Smoke tests for the command-line interface."""

from __future__ import annotations

from india_road_safety import cli


def test_parser_has_expected_commands():
    parser = cli.build_parser()
    for cmd in ("sources", "collect", "report", "all"):
        assert cmd in parser.format_help()


def test_sources_command_runs(capsys):
    rc = cli.main(["sources"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "morth-road-accidents-in-india" in out
    assert "global-ncap" in out
