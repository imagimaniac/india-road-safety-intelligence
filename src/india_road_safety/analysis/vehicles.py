"""Analysis of crash-test assessments.

Discipline (from AGENTS.md): star ratings are never compared across protocols.
We work with the **raw protection points** the publisher states, and we
normalise only by the *stated maximum of the same protocol era*, clearly
labelled. Points from a 17-point adult protocol are not comparable to a
34-point adult protocol except through this explicit normalisation.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_maxima(protocol_version: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Parse 'adult_max=17;child_max=49' -> (17.0, 49.0)."""
    if not protocol_version:
        return None, None
    a = re.search(r"adult_max=([\d.]+)", protocol_version)
    c = re.search(r"child_max=([\d.]+)", protocol_version)
    return (_num(a.group(1)) if a else None, _num(c.group(1)) if c else None)


def crash_test_table(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-model crash-test figures with normalised protection where possible."""
    out = []
    for r in rows:
        amax, cmax = parse_maxima(r.get("protocol_version"))
        adult = _num(r.get("adult_occupant_protection"))
        child = _num(r.get("child_occupant_protection"))
        entry = {
            "model_slug": r.get("model_slug"),
            "program": r.get("program"),
            "protocol_version": r.get("protocol_version"),
            "adult_points": adult,
            "adult_max": amax,
            "child_points": child,
            "child_max": cmax,
            "adult_pct_of_max": round(adult / amax * 100.0, 1) if (adult is not None and amax) else None,
            "child_pct_of_max": round(child / cmax * 100.0, 1) if (child is not None and cmax) else None,
            "bodyshell": r.get("bodyshell"),
            "equipment_tested": r.get("equipment_tested"),
        }
        out.append(entry)
    out.sort(key=lambda e: (e["adult_pct_of_max"] is None, -(e["adult_pct_of_max"] or 0)))
    return out


def bodyshell_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        key = (r.get("bodyshell") or "unknown").lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def equipment_summary(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """How many tests explicitly list each safety equipment item."""
    counts: dict[str, int] = {}
    for r in rows:
        raw = r.get("equipment_tested") or ""
        for item in {x.strip() for x in raw.split(",") if x.strip()}:
            counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def protocol_era_split(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count tests by stated adult maximum (protocol era proxy)."""
    eras: dict[str, int] = {}
    for r in rows:
        amax, _ = parse_maxima(r.get("protocol_version"))
        key = f"adult_max={amax:g}" if amax else "unknown"
        eras[key] = eras.get(key, 0) + 1
    return eras


def _adult_pct(r: dict[str, Any]) -> Optional[float]:
    amax, _ = parse_maxima(r.get("protocol_version"))
    adult = _num(r.get("adult_occupant_protection"))
    if adult is None or not amax:
        return None
    return round(adult / amax * 100.0, 1)


def equipment_contrast(rows: Iterable[dict[str, Any]], min_n: int = 30) -> dict[str, Any]:
    """Compare protection for tests *with* vs *without* each equipment item,
    strictly **within** a protocol era (never across eras).

    A comparison is only flagged ``comparable`` when **both** groups reach
    ``min_n``. In the current Global NCAP India corpus the equipment tags are
    near-constant inside each era (e.g. every 34-point-era test lists ESC), so
    most items have no valid contrast. That is reported honestly rather than
    forcing a misleading with-vs-without claim.
    """
    eras: dict[str, list[tuple[set[str], Optional[float]]]] = {}
    for r in rows:
        amax, _ = parse_maxima(r.get("protocol_version"))
        if amax is None:
            continue
        items = {x.strip() for x in (r.get("equipment_tested") or "").split(",") if x.strip()}
        eras.setdefault(f"adult_max={amax:g}", []).append((items, _adult_pct(r)))

    comparisons: list[dict[str, Any]] = []
    for era, tests in sorted(eras.items()):
        all_items = sorted({i for its, _ in tests for i in its})
        for item in all_items:
            present = [p for its, p in tests if item in its and p is not None]
            absent = [p for its, p in tests if item not in its and p is not None]
            entry: dict[str, Any] = {
                "era": era,
                "item": item,
                "present_n": len(present),
                "absent_n": len(absent),
                "present_mean_pct": round(sum(present) / len(present), 1) if present else None,
                "absent_mean_pct": round(sum(absent) / len(absent), 1) if absent else None,
            }
            entry["comparable"] = len(present) >= min_n and len(absent) >= min_n
            if entry["comparable"] and entry["present_mean_pct"] is not None and entry["absent_mean_pct"] is not None:
                entry["difference_pct_points"] = round(entry["present_mean_pct"] - entry["absent_mean_pct"], 1)
            comparisons.append(entry)
    return {
        "min_n": min_n,
        "has_comparable_contrast": any(c["comparable"] for c in comparisons),
        "comparisons": comparisons,
    }
