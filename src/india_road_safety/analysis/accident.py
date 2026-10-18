"""Analysis of aggregate accident statistics.

All functions are pure: they take already-collected rows (dicts as stored) and
return plain data structures. Nothing here fetches data or invents values.

Key institutional facts used:
* population is stored in **thousands** (MoRTH table unit);
* ``fatalities_per_lakh = fatalities / population_thousand * 100``;
* a recorded factor (e.g. 'over speeding') is a *recorded* factor, not proof of
  causation (see docs/limitations.md).
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _national(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("geo_level") == "national" and r.get("road_type") is None and r.get("road_user") is None]


def series_by_year(
    rows: Iterable[dict[str, Any]],
    metric: str,
    geo_level: str = "national",
) -> dict[int, float]:
    """Map year -> value for a given metric (national, all-road-type).

    Only *annual* national rows count here: a monthly row (``month`` set) is a
    finer cut of the same metric and must not overwrite the annual total.
    """
    out: dict[int, float] = {}
    for r in rows:
        if r.get("metric") != metric or r.get("geo_level") != geo_level:
            continue
        if r.get("road_type") is not None or r.get("road_user") is not None:
            continue
        if r.get("month") is not None:
            continue
        v = _num(r.get("value"))
        if v is not None:
            out[int(r["year"])] = v
    return out


def national_trend(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-year national accidents/fatalities/injuries, ascending by year."""
    acc = series_by_year(rows, "accidents")
    fat = series_by_year(rows, "fatalities")
    inj = series_by_year(rows, "injuries")
    years = sorted(set(acc) | set(fat) | set(inj))
    return [
        {
            "year": y,
            "accidents": acc.get(y),
            "fatalities": fat.get(y),
            "injuries": inj.get(y),
        }
        for y in years
    ]


def exposure_adjusted(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fatalities per lakh population by year (uses the population column)."""
    fat = series_by_year(rows, "fatalities")
    pop = series_by_year(rows, "population")  # thousands
    out = []
    for y in sorted(set(fat) & set(pop)):
        f, p = fat[y], pop[y]
        if p and p > 0 and f is not None:
            out.append(
                {
                    "year": y,
                    "fatalities": f,
                    "population_thousand": p,
                    "fatalities_per_lakh_population": round(f / p * 100.0, 2),
                }
            )
    return out


def latest_year(rows: Iterable[dict[str, Any]], metric: str = "accidents") -> Optional[int]:
    s = series_by_year(rows, metric)
    return max(s) if s else None


def national_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Latest-year national accidents/fatalities/injuries plus prior-year deltas."""

    trend = national_trend(rows)
    if not trend:
        return {}
    latest = trend[-1]
    prev = trend[-2] if len(trend) > 1 else None
    summary: dict[str, Any] = {"year": latest["year"], **{k: latest[k] for k in ("accidents", "fatalities", "injuries")}}
    if prev:
        summary["prev_year"] = prev["year"]
        for k in ("accidents", "fatalities", "injuries"):
            a, b = latest[k], prev[k]
            if a is not None and b:
                summary[f"{k}_yoy_pct"] = round((a - b) / b * 100.0, 1)
    return summary


def road_type_breakdown(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    """Accidents and fatalities split by road type for a given year."""
    result: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("year") != year or r.get("road_type") is None:
            continue
        metric = r.get("metric")
        if metric not in ("accidents", "fatalities"):
            continue
        rt = r["road_type"]
        entry = result.setdefault(rt, {"road_type": rt, "accidents": None, "fatalities": None})
        entry[metric] = _num(r.get("value"))
    total_acc = sum(e["accidents"] or 0 for e in result.values())
    total_fat = sum(e["fatalities"] or 0 for e in result.values())
    out = []
    for rt in sorted(result):
        e = result[rt]
        e = dict(e)
        if total_acc and e["accidents"] is not None:
            e["accidents_share_pct"] = round(e["accidents"] / total_acc * 100.0, 1)
        if total_fat and e["fatalities"] is not None:
            e["fatalities_share_pct"] = round(e["fatalities"] / total_fat * 100.0, 1)
        out.append(e)
    return out


_ROAD_USER_LABELS = {
    "road_user_two_wheeler_share_of_deaths": "Two-wheeler riders",
    "road_user_pedestrian_share_of_deaths": "Pedestrians",
    "road_user_car_occupant_share_of_deaths": "Car / taxi / van / LMV occupants",
}


def road_user_shares(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    """Share of road deaths by road-user category (percent)."""
    by_metric = {r.get("metric"): _num(r.get("value")) for r in rows if r.get("year") == year}
    out = []
    for metric, label in _ROAD_USER_LABELS.items():
        if by_metric.get(metric) is not None:
            out.append({"category": label, "share_pct": by_metric[metric]})
    return out


def road_user_deaths(rows: Iterable[dict[str, Any]], year: int) -> dict[str, float]:
    """Absolute road-user death counts where the publisher states them."""
    by_metric = {r.get("metric"): _num(r.get("value")) for r in rows if r.get("year") == year}
    return {
        "two_wheeler": by_metric.get("road_user_two_wheeler_deaths"),
        "car_occupant": by_metric.get("road_user_car_occupant_deaths"),
    }


def risk_factors(rows: Iterable[dict[str, Any]], year: int) -> dict[str, Any]:
    """Recorded contributing factors (percent), as stated by the publisher."""
    by_metric = {r.get("metric"): _num(r.get("value")) for r in rows if r.get("year") == year}
    return {
        "overspeeding_share_of_accidents_pct": by_metric.get("overspeeding_share_of_accidents"),
        "overspeeding_share_of_deaths_pct": by_metric.get("overspeeding_share_of_deaths"),
        "wrong_side_share_of_accidents_pct": by_metric.get("wrong_side_share_of_accidents"),
    }


def state_table(rows: Iterable[dict[str, Any]], metric: str = "accidents", top: Optional[int] = None) -> dict[str, Any]:
    """Latest-year state/UT table with year-on-year change, sorted descending."""

    states: dict[str, dict[int, float]] = {}
    for r in rows:
        if r.get("geo_level") != "state" or r.get("metric") != metric:
            continue
        v = _num(r.get("value"))
        if v is None:
            continue
        states.setdefault(r["geography"], {})[int(r["year"])] = v
    if not states:
        return {"year": None, "rows": []}
    years = sorted({y for s in states.values() for y in s})
    latest = years[-1]
    prev = years[-2] if len(years) > 1 else None
    table = []
    for state, series in states.items():
        cur = series.get(latest)
        row = {"state": state, "year": latest, "value": cur}
        if prev is not None and series.get(prev) is not None and cur is not None:
            pv = series[prev]
            row["prev_value"] = pv
            row["change"] = cur - pv
            if pv:
                row["change_pct"] = round((cur - pv) / pv * 100.0, 1)
        table.append(row)
    table.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0)))
    if top is not None:
        table = table[:top]
    return {"year": latest, "prev_year": prev, "rows": table}


def _labeled(rows: Iterable[dict[str, Any]], metric: str, year: int) -> dict[str, float]:
    """label -> value for national records carrying a ``label``."""
    out: dict[str, float] = {}
    for r in rows:
        if r.get("metric") != metric or r.get("geo_level") != "national":
            continue
        if r.get("year") != year or r.get("label") is None:
            continue
        v = _num(r.get("value"))
        if v is not None:
            out[str(r["label"])] = v
    return out


def collision_breakdown(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    """Accidents & deaths by collision type (Table 1.5), sorted by accidents."""
    acc = _labeled(rows, "collision_accidents", year)
    fat = _labeled(rows, "collision_fatalities", year)
    cats = sorted(set(acc) | set(fat))
    if not cats:
        return []
    tacc, tfat = sum(acc.values()), sum(fat.values())
    out = []
    for c in cats:
        e = {"category": c, "accidents": acc.get(c), "fatalities": fat.get(c)}
        if tacc and e["accidents"] is not None:
            e["accidents_share_pct"] = round(e["accidents"] / tacc * 100.0, 1)
        if tfat and e["fatalities"] is not None:
            e["fatalities_share_pct"] = round(e["fatalities"] / tfat * 100.0, 1)
        out.append(e)
    out.sort(key=lambda e: -(e["accidents"] or 0))
    return out


def time_of_day_breakdown(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    """Accidents by time interval of day (Table 7.3), in clock order."""
    counts = _labeled(rows, "time_interval_accidents", year)
    if not counts:
        return []
    total = sum(counts.values())
    order = [
        "00.00 to 3.00 hrs (Night)", "03.00 to 6.00 hrs (Night)",
        "06.00 to 9.00 hrs (Day)", "09.00 to 12.00 hrs (Day)",
        "12.00 to 15.00 hrs (Day)", "15.00 to 18.00 hrs (Day)",
        "18.00 to 21.00 hrs (Night)", "21.00 to 24.00 hrs (Night)",
        "Un-known Time",
    ]
    out = []
    for label in order:
        if label not in counts:
            continue
        period = "Night" if "(Night)" in label else "Day" if "(Day)" in label else "Unknown"
        e = {"interval": label, "period": period, "accidents": counts[label]}
        if total:
            e["share_pct"] = round(counts[label] / total * 100.0, 1)
        out.append(e)
    return out


def safety_device_deaths(rows: Iterable[dict[str, Any]], year: int) -> dict[str, Any]:
    """Deaths from non-use of helmet / seat belt (Table 3.3)."""
    d = _labeled(rows, "safety_device_fatalities", year)
    return {
        "helmet_total": d.get("non_use_helmet"),
        "helmet_driver": d.get("non_use_helmet_driver"),
        "helmet_passenger": d.get("non_use_helmet_passenger"),
        "seatbelt_total": d.get("non_use_seatbelt"),
        "seatbelt_driver": d.get("non_use_seatbelt_driver"),
        "seatbelt_passenger": d.get("non_use_seatbelt_passenger"),
    }


def monthly_series(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    """National accidents & deaths by month (Table 7.2), Jan..Dec."""
    acc: dict[int, float] = {}
    fat: dict[int, float] = {}
    for r in rows:
        if r.get("geo_level") != "national" or r.get("year") != year or r.get("month") is None:
            continue
        v = _num(r.get("value"))
        if v is None:
            continue
        m = int(r["month"])
        if r.get("metric") == "accidents":
            acc[m] = v
        elif r.get("metric") == "fatalities":
            fat[m] = v
    if not acc and not fat:
        return []
    return [
        {"month": m, "accidents": acc.get(m), "fatalities": fat.get(m)}
        for m in range(1, 13)
    ]


def _cagr(start: float, end: float, years: int) -> Optional[float]:
    if not start or not end or years <= 0 or start <= 0 or end <= 0:
        return None
    return round(((end / start) ** (1.0 / years) - 1.0) * 100.0, 2)


def trend_stats(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Long-run trend: CAGR and 5-year change for accidents, deaths, and the
    exposure-adjusted death rate."""
    ea = {r["year"]: r["fatalities_per_lakh_population"] for r in exposure_adjusted(rows)}
    series = {
        "accidents": series_by_year(rows, "accidents"),
        "fatalities": series_by_year(rows, "fatalities"),
        "fatalities_per_lakh_population": ea,
    }
    out: dict[str, Any] = {}
    for name, s in series.items():
        if not s:
            continue
        years = sorted(s)
        latest, first = years[-1], years[0]
        entry: dict[str, Any] = {
            "latest_year": latest, "latest": s[latest],
            "first_year": first, "first": s[first],
            "cagr_pct": _cagr(s[first], s[latest], latest - first),
        }
        base_year = max((y for y in years if y <= latest - 5), default=None)
        if base_year is not None and s[base_year]:
            entry["five_year_base"] = base_year
            entry["five_year_change_pct"] = round((s[latest] - s[base_year]) / s[base_year] * 100.0, 1)
        out[name] = entry
    return out
