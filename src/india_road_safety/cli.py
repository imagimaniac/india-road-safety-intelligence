"""Command-line interface: ``irsi <command>``.

Commands
--------
sources    show the source register and verification status
collect    fetch verified sources into the local store
report     render the self-contained HTML report from stored records
all        collect, then render
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import pipeline
from .config import ConfigError, load_settings
from .registry import Registry


def _cmd_sources(args: argparse.Namespace) -> int:
    registry = Registry.load()
    print(f"{'slug':42} {'status':22} {'data_type':20} organization")
    for s in registry.all():
        print(f"{s.slug:42} {s.status.value if hasattr(s.status,'value') else s.status:22} "
              f"{getattr(s,'data_type',''):20} {s.organization}")
    print(f"\n{len(registry)} sources registered; "
          f"{len(registry.verified()) if hasattr(registry,'verified') else 'n/a'} verified.")
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = pipeline.open_store(settings)
    registry = Registry.load(settings=settings)
    only = [args.source] if args.source else None
    summary = pipeline.collect(
        store, registry, settings, only=only, max_fact_sheets=args.limit
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0 if not summary["errors"] else 1


def _cmd_report(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = pipeline.open_store(settings)
    registry = Registry.load(settings=settings)
    ctx = pipeline.build_context(store, registry, settings)
    out = pipeline.write_report(ctx, settings)
    print(f"report written: {out}")
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    settings = load_settings()
    result = pipeline.run_all(settings, max_fact_sheets=args.limit)
    print(json.dumps(result["collect"], indent=2, default=str))
    print(f"\nreport written: {result['report']}")
    return 0 if not result["collect"]["errors"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="irsi",
        description="India road-safety intelligence: collect public data and build an evidence report.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("sources", help="show the source register")
    sp.set_defaults(func=_cmd_sources)

    cp = sub.add_parser("collect", help="fetch verified sources into the local store")
    cp.add_argument("--source", help="collect a single source slug")
    cp.add_argument("--limit", type=int, default=None, help="max Global NCAP fact sheets to fetch")
    cp.set_defaults(func=_cmd_collect)

    rp = sub.add_parser("report", help="render the HTML report from stored records")
    rp.set_defaults(func=_cmd_report)

    ap = sub.add_parser("all", help="collect then render the report")
    ap.add_argument("--limit", type=int, default=None, help="max Global NCAP fact sheets to fetch")
    ap.set_defaults(func=_cmd_all)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
