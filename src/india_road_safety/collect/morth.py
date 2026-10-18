"""MoRTH collector (national series + state-wise CSV + preface narrative).

Parsers are pure functions operating on extracted text/CSV so they can be unit
tested on fixtures without network access. Values that cannot be parsed become
``None`` — never ``0`` and never a guessed value.
"""

from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Optional

from .. import models, normalize
from ..config import Settings, load_settings
from ..http import HttpFetcher
from .base import Collection, make_document

_NATIONAL_PDF_URL = (
    "https://morth.gov.in/backend/documents/uploaded/1755600426_RA_2022_30_Oct.pdf"
)
_STATE_CSV_URL = (
    "https://data.opencity.in/dataset/33d29ab0-f9e8-4fc7-b404-c93c1ed8e1b8/"
    "resource/115647dd-4e46-4a22-8638-bd230edbcca4/download/road-accidents-2024-states-road-accidents.csv"
)

# --------------------------------------------------------------------------- #
# National series (Annexure 1) parsing
# --------------------------------------------------------------------------- #
_ROW_YEAR = re.compile(r"^\s*(1[89]\d{2}|20\d{2})\s+\S")

# The report contains several tables whose rows also begin with a calendar year
# (decadal charts, population series). To avoid reading, say, a population value
# as an accident count we bound Annexure 1 ("Road Accidents, Persons Killed and
# Injured: 1970 ...") by its heading and the next heading.
_ANNEX1_START = re.compile(r"Road Accidents,\s*Persons Killed and Injured:\s*19\d{2}", re.I)
_ANNEX1_END = re.compile(r"Total Number of Road Accidents in India|Annexure\s*[- ]?\s*2\b", re.I)


def _annex1_region(text: str) -> str:
    matches = list(_ANNEX1_START.finditer(text))
    if not matches:
        return text
    region = text[matches[-1].end():]
    end = _ANNEX1_END.search(region)
    if end:
        region = region[: end.start()]
    return region


def parse_national_series(text: str) -> list[models.AccidentRecord | models.RegistrationExposure]:
    """Parse Annexure 1 (Road Accidents, Persons Killed and Injured: 1970-2022).

    Column order for modern years (as observed):
    Year, Accidents, Killed, Injured, Population(thousand), Vehicles(thousand),
    [Road length], [Rates...]. Older years have more trailing columns; we only
    read the columns we can identify confidently. Missing values stay ``None``.
    """

    out: list[models.AccidentRecord | models.RegistrationExposure] = []
    text = _annex1_region(text)

    def _rec(metric: str, value: Optional[int], unit: str = "count") -> models.AccidentRecord:
        return models.AccidentRecord(
            geography="India",
            geo_level="national",
            year=year,
            severity="unknown",
            metric=metric,
            value=value,
            unit=unit,
            source_slug="morth-road-accidents-in-india",
            evidence_class="observed_fact",
            confidence="medium",
        )

    for line in text.splitlines():
        line_clean = normalize.collapse_ws(line)
        if not line_clean:
            continue
        m = _ROW_YEAR.match(line_clean)
        if not m:
            continue
        year = int(m.group(1))
        tokens = re.split(r"\s+", line_clean)
        if tokens and tokens[0].isdigit() and int(tokens[0]) == year:
            tokens = tokens[1:]
        nums: list[Optional[float]] = []
        for t in tokens:
            t2 = t.rstrip("#$*")
            if not t2:
                continue
            nums.append(normalize.parse_float(t2))

        if len(nums) > 0 and nums[0] is not None:
            out.append(_rec("accidents", int(round(nums[0]))))
        if len(nums) > 1 and nums[1] is not None:
            out.append(_rec("fatalities", int(round(nums[1]))))
        if len(nums) > 2 and nums[2] is not None:
            out.append(_rec("injuries", int(round(nums[2]))))
        if len(nums) > 3 and nums[3] is not None:
            out.append(_rec("population", int(round(nums[3])), unit="thousand"))
        # Registered vehicles (thousands) only present in rows that carry the
        # full column set (e.g. 1970-2019). It is a large integer, not a rate.
        if len(nums) > 4 and nums[4] is not None and nums[4] >= 10000:
            out.append(
                models.RegistrationExposure(
                    geography="India",
                    geo_level="national",
                    year=year,
                    vehicle_category="all",
                    metric="registrations",
                    value=int(round(nums[4])),
                    unit="thousand",
                    source_slug="morth-road-accidents-in-india",
                    confidence="medium",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Preface/narrative extraction (road-type, risk factors)
# --------------------------------------------------------------------------- #
_ROAD_ACCIDENTS = re.compile(
    r"accidents were recorded[\s\S]*?(\d[\d,]+)\s*\([^)]*%\)[\s\S]*?"
    r"on\s+(?:the\s+)?National\s+Highways[\s\S]*?"
    r"(\d[\d,]+)\s*\([^)]*%\)[\s\S]*?on\s+State\s+Highways[\s\S]*?"
    r"(\d[\d,]+)\s*\([^)]*%\)[\s\S]*?on\s+Other\s+Roads",
    re.DOTALL | re.I,
)
_ROAD_FATALITIES = re.compile(
    r"fatalities[\s\S]{0,200}?(\d[\d,]+)\s*\([^)]*%\)\s*were\s+on\s+(?:the\s+)?National\s+Highways[\s\S]*?"
    r"(\d[\d,]+)\s*\([^)]*%\)\s*were\s+on\s+State\s+Highways[\s\S]*?"
    r"(\d[\d,]+)\s*\([^)]*%\)\s*were\s+on\s+Other\s+Roads",
    re.DOTALL | re.I,
)
_OVERSPEED_DEATH = re.compile(
    r"(\d{2}\.?\d?)\s*percent\s+of\s+total\s+deaths", re.I
)
_OVERSPEED_ACC = re.compile(
    r"accounting\s+for\s+(\d{2}\.?\d?)\s*percent\s+of\s+the\s+total\s+road\s+accidents", re.I
)
_WRONG_SIDE = re.compile(
    r"wrong\s+side[\s\S]{0,160}?accounting\s+for\s+(\d{1,2}\.?\d?)\s*percent", re.I
)
_TWO_WHEELER = re.compile(
    r"two-?wheelers\s+with\s+a\s+share\s+of\s+(\d{2}\.?\d?)\s*(?:percent|%)", re.I
)
_PEDESTRIAN = re.compile(
    r"pedestrians\s+are\s+the\s+next[\s\S]{0,120}?share\s+of\s+(\d{2}\.?\d?)\s*(?:percent|%)", re.I
)
_CAR_OCCUPANT = re.compile(
    r"as\s+many\s+as\s+(\d[\d,]+)\s+occupants\s+of\s+cars[\s\S]{0,120}?\((\d{1,2}\.?\d?)\s*(?:percent|%)\)", re.I
)
_TWO_WHEELER_FATAL = re.compile(
    r"victims\s+on\s+two\s+wheelers\s+killed\s+were\s+(\d[\d,]+)\s+which\s+is\s+around\s+(\d{2}\.?\d?)\s*(?:percent|%)",
    re.I,
)


def parse_preface_narrative(text: str) -> list[models.AccidentRecord]:
    """Extract citable aggregate figures from the report's narrative/preface.

    Only values the publisher states are recorded. Percentages are kept as
    percentages (unit='percent') with value=None for the numeric count when not
    given in the same sentence.
    """

    out: list[models.AccidentRecord] = []
    base = dict(
        geography="India",
        geo_level="national",
        year=2022,
        source_slug="morth-road-accidents-in-india",
        evidence_class="extracted_claim",
        confidence="medium",
        severity="unknown",
    )

    m = _ROAD_ACCIDENTS.search(text)
    if m:
        nh_acc = normalize.parse_int(m.group(1))
        sh_acc = normalize.parse_int(m.group(2))
        or_acc = normalize.parse_int(m.group(3))
        for road_type, value in [
            ("national_highway", nh_acc),
            ("state_highway", sh_acc),
            ("other_road", or_acc),
        ]:
            if value is not None:
                out.append(models.AccidentRecord(metric="accidents", road_type=road_type, value=value, **base))  # type: ignore

    m1f = _ROAD_FATALITIES.search(text)
    if m1f:
        nh_fat = normalize.parse_int(m1f.group(1))
        sh_fat = normalize.parse_int(m1f.group(2))
        or_fat = normalize.parse_int(m1f.group(3))
        for road_type, value in [
            ("national_highway", nh_fat),
            ("state_highway", sh_fat),
            ("other_road", or_fat),
        ]:
            if value is not None:
                out.append(models.AccidentRecord(metric="fatalities", road_type=road_type, value=value, **base))  # type: ignore

    m2 = _OVERSPEED_DEATH.search(text)
    if m2:
        out.append(models.AccidentRecord(metric="overspeeding_share_of_deaths", unit="percent", value=normalize.parse_float(m2.group(1)), **base))
    m3 = _OVERSPEED_ACC.search(text)
    if m3:
        out.append(models.AccidentRecord(metric="overspeeding_share_of_accidents", unit="percent", value=normalize.parse_float(m3.group(1)), **base))
    m4 = _WRONG_SIDE.search(text)
    if m4:
        out.append(models.AccidentRecord(metric="wrong_side_share_of_accidents", unit="percent", value=normalize.parse_float(m4.group(1)), **base))

    m5 = _TWO_WHEELER.search(text)
    if m5:
        out.append(models.AccidentRecord(metric="road_user_two_wheeler_share_of_deaths", unit="percent", value=normalize.parse_float(m5.group(1)), **base))
    m6 = _PEDESTRIAN.search(text)
    if m6:
        out.append(models.AccidentRecord(metric="road_user_pedestrian_share_of_deaths", unit="percent", value=normalize.parse_float(m6.group(1)), **base))
    m7 = _CAR_OCCUPANT.search(text)
    if m7:
        out.append(models.AccidentRecord(metric="road_user_car_occupant_deaths", unit="count", value=normalize.parse_int(m7.group(1)), **base))
        out.append(models.AccidentRecord(metric="road_user_car_occupant_share_of_deaths", unit="percent", value=normalize.parse_float(m7.group(2)), **base))
    m8 = _TWO_WHEELER_FATAL.search(text)
    if m8:
        out.append(models.AccidentRecord(metric="road_user_two_wheeler_deaths", unit="count", value=normalize.parse_int(m8.group(1)), **base))
        out.append(models.AccidentRecord(metric="road_user_two_wheeler_share_of_deaths", unit="percent", value=normalize.parse_float(m8.group(2)), **base))

    return out


# --------------------------------------------------------------------------- #
# State-wise CSV parsing (2020-2024 accidents)
# --------------------------------------------------------------------------- #
_STATE_YEARS = (2020, 2021, 2022, 2023, 2024)


def parse_state_accidents_csv(text: str) -> list[models.AccidentRecord]:
    """Parse the state-wise accidents CSV (columns: Sl No,State,2020 Accidents,...)."""

    out: list[models.AccidentRecord] = []
    reader = csv.DictReader(StringIO(text))
    aggregates = {"all india", "india", "total", "grand total"}
    for row in reader:
        state = normalize.clean_text(row.get("State") or row.get("state") or "")
        if not state or state.strip().lower() in aggregates:
            continue
        for year in _STATE_YEARS:
            raw = row.get(f"{year} Accidents") or row.get(f"{year} accidents") or row.get(f"{year}")
            val = normalize.parse_int(raw)
            if val is not None:
                out.append(
                    models.AccidentRecord(
                        geography=state,
                        geo_level="state",
                        year=year,
                        severity="unknown",
                        metric="accidents",
                        value=val,
                        unit="count",
                        source_slug="morth-state-wise-accidents",
                        evidence_class="observed_fact",
                        confidence="medium",
                    )
                )
    return out


# --------------------------------------------------------------------------- #
# Deeper annexure parsing (collision type, time-of-day, safety devices, month)
#
# Each parser is guarded: it only emits records if the table's own Total row
# reconciles with the sum of its parts. A parse that cannot be reconciled
# returns [] rather than guessing — unavailable stays None, never a fabricated
# number.
# --------------------------------------------------------------------------- #
_NUM = r"[\d,]+(?:\.\d+)?"
_NUM10 = r"\s+".join("(" + _NUM + ")" for _ in range(10))


def _reconciles(parts: list[Optional[float]], total: Optional[float]) -> bool:
    """True when the parts sum to the published total (small tolerance)."""
    if total is None or any(p is None for p in parts):
        return False
    s = float(sum(p for p in parts if p is not None))
    return abs(s - float(total)) <= max(1.0, float(total) * 0.001)


def parse_collision_types(text: str) -> list[models.AccidentRecord]:
    """Table 1.5 — accidents & deaths by type of collision (2022).

    Each data row is ``Name  acc21 killed21 inj21 acc22 killed22 inj22 %x3``.
    The scan is bounded to the Table 1.5 section so other tables (road type,
    factors, junctions …) that share the same row shape are not mixed in.
    Validated against the section's own Total row.
    """
    anchor = re.search(r"Hit and Run\s+" + _NUM + r"\s+" + _NUM, text)
    if not anchor:
        return []
    start = text.rfind("Table 1.5", 0, anchor.start())
    end = text.find("Table 1.4", anchor.end())
    lo = start if start != -1 else max(0, anchor.start() - 2000)
    hi = end if end != -1 else anchor.end() + 2000
    region = text[lo:hi]

    rows: list[tuple[str, float, float]] = []
    total_acc = total_kill = None
    for line in region.splitlines():
        line = normalize.collapse_ws(line)
        if not line or "Table 1." in line:
            continue
        tokens = re.split(r"\s+", line)
        i = 0
        while i < len(tokens) and normalize.parse_float(tokens[i]) is None:
            i += 1
        name, nums = " ".join(tokens[:i]), tokens[i:]
        if not name or name.startswith("%"):
            continue
        if len(nums) != 9 or any(normalize.parse_float(t) is None for t in nums):
            continue
        n = [normalize.parse_float(t) for t in nums]
        acc22, kill22 = n[3], n[4]
        if name.lower() == "total":
            total_acc, total_kill = acc22, kill22
            continue
        if acc22 is not None and kill22 is not None:
            rows.append((name, acc22, kill22))
    if not rows or not _reconciles([r[1] for r in rows], total_acc):
        return []
    base = dict(
        geography="India", geo_level="national", year=2022, severity="unknown",
        source_slug="morth-road-accidents-in-india", evidence_class="observed_fact",
        confidence="medium",
    )
    out: list[models.AccidentRecord] = []
    for name, acc, kill in rows:
        out.append(models.AccidentRecord(metric="collision_accidents", label=name, value=int(acc), **base))  # type: ignore
        out.append(models.AccidentRecord(metric="collision_fatalities", label=name, value=int(kill), **base))  # type: ignore
    return out


_TIME_INTERVALS: tuple[tuple[str, str], ...] = (
    ("00.00 to 3.00 hrs (Night)", r"00\.00\s*to\s*3\.00\s*hrs\s*\(Night\)"),
    ("03.00 to 6.00 hrs (Night)", r"03\.00\s*to\s*6\.00\s*hrs\s*\(Night\)"),
    ("06.00 to 9.00 hrs (Day)", r"06\.00\s*to\s*9\.00\s*hrs\s*\(Day\)"),
    ("09.00 to 12.00 hrs (Day)", r"09\.00\s*to\s*12\.00\s*hrs\s*\(Day\)"),
    ("12.00 to 15.00 hrs (Day)", r"12\.00\s*to\s*15\.00\s*hrs\s*\(Day\)"),
    ("15.00 to 18.00 hrs (Day)", r"15\.00\s*to\s*18\.00\s*hrs\s*\(Day\)"),
    ("18.00 to 21.00 hrs (Night)", r"18\.00\s*to\s*21\.00\s*hrs\s*\(Night\)"),
    ("21.00 to 24.00 hrs (Night)", r"21\.00\s*to\s*24\.00\s*hrs\s*\(Night\)"),
    ("Un-known Time", r"Un-?\s*known\s*Time"),
)


def parse_time_of_day(text: str) -> list[models.AccidentRecord]:
    """Table 7.3 — accidents by time interval of day (2022).

    Each row carries five (count, share) pairs for 2018-2022; we keep the 2022
    count. Validated against the table's own ``Total 24 hrs`` row.
    """
    counts: list[float] = []
    total: Optional[float] = None
    for label, pat in _TIME_INTERVALS:
        m = re.search(pat + r"[\s\S]{0,60}?" + _NUM10, text)
        if m:
            nums = [normalize.parse_float(t) for t in m.groups()]
            if len(nums) == 10 and nums[8] is not None:
                counts.append(nums[8])
    mt = re.search(r"Total\s*24\s*hrs[\s\S]{0,20}?" + _NUM10, text)
    if mt:
        tn = [normalize.parse_float(t) for t in mt.groups()]
        if len(tn) == 10:
            total = tn[8]
    if len(counts) != len(_TIME_INTERVALS) or not _reconciles(counts, total):
        return []
    base = dict(
        geography="India", geo_level="national", year=2022, severity="unknown",
        metric="time_interval_accidents", source_slug="morth-road-accidents-in-india",
        evidence_class="observed_fact", confidence="medium",
    )
    return [
        models.AccidentRecord(label=_TIME_INTERVALS[i][0], value=int(counts[i]), **base)  # type: ignore
        for i in range(len(counts))
    ]


def parse_safety_devices(text: str) -> list[models.AccidentRecord]:
    """Table 3.3 — deaths from non-use of helmet / seat belt (2022).

    Values come from the narrative summary; each device's driver + passenger
    split is validated against its own total.
    """
    base = dict(
        geography="India", geo_level="national", year=2022, severity="unknown",
        metric="safety_device_fatalities", source_slug="morth-road-accidents-in-india",
        evidence_class="extracted_claim", confidence="medium",
    )
    out: list[models.AccidentRecord] = []

    mh = re.search(
        r"total of ([\d,]+)\s+persons\s+were\s+killed\s+who\s+were\s+not\s+wearing\s+helmet[\s\S]{0,160}?"
        r"of which\s+([\d,]+)\s*\([\d.]+%\)\s*persons\s+were\s+drivers\s+and\s+([\d,]+)",
        text, re.I,
    )
    if mh:
        total, driver, passenger = (normalize.parse_int(mh.group(i)) for i in (1, 2, 3))
        if None not in (total, driver, passenger) and _reconciles([driver, passenger], total):
            out.append(models.AccidentRecord(label="non_use_helmet", value=total, **base))  # type: ignore
            out.append(models.AccidentRecord(label="non_use_helmet_driver", value=driver, **base))  # type: ignore
            out.append(models.AccidentRecord(label="non_use_helmet_passenger", value=passenger, **base))  # type: ignore

    ms = re.search(
        r"([\d,]+)\s+persons\s+were\s+killed\s+who\s+were\s+not\s+wearing\s+seat\s+belt[\s\S]{0,80}?"
        r"Out of\s+[\d,]+,\s*([\d,]+)\s*\([\d.]+%\)\s*were\s+drivers\s+and\s+remaining\s+([\d,]+)",
        text, re.I,
    )
    if ms:
        total, driver, passenger = (normalize.parse_int(ms.group(i)) for i in (1, 2, 3))
        if None not in (total, driver, passenger) and _reconciles([driver, passenger], total):
            out.append(models.AccidentRecord(label="non_use_seatbelt", value=total, **base))  # type: ignore
            out.append(models.AccidentRecord(label="non_use_seatbelt_driver", value=driver, **base))  # type: ignore
            out.append(models.AccidentRecord(label="non_use_seatbelt_passenger", value=passenger, **base))  # type: ignore
    return out


_MONTHS: dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUG": 8, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_monthly(text: str) -> list[models.AccidentRecord]:
    """Table 7.2 — accidents & deaths by month (2022). Validated on Total."""
    num10 = r"\s+".join([_NUM] * 10)
    counts: list[float] = []
    kills: list[float] = []
    months: list[int] = []
    for name, num in _MONTHS.items():
        m = re.search(rf"(?<![A-Z]){name}\s+{_NUM10}", text)
        if m:
            n = [normalize.parse_float(t) for t in m.groups()]
            if len(n) == 10 and n[8] is not None and n[9] is not None:
                months.append(num)
                counts.append(n[8])
                kills.append(n[9])
    total_acc = total_kill = None
    target = sum(counts) if counts else None
    if target is not None:
        for mt in re.finditer(r"Total\s+" + _NUM10, text):
            tn = [normalize.parse_float(t) for t in mt.groups()]
            if len(tn) == 10 and tn[8] is not None and abs(tn[8] - target) <= max(1.0, target * 0.001):
                total_acc, total_kill = tn[8], tn[9]
                break
    if len(counts) != 12 or not _reconciles(counts, total_acc):
        return []
    base = dict(
        geography="India", geo_level="national", year=2022, severity="unknown",
        source_slug="morth-road-accidents-in-india", evidence_class="observed_fact",
        confidence="medium",
    )
    out: list[models.AccidentRecord] = []
    for i in range(12):
        out.append(models.AccidentRecord(month=months[i], metric="accidents", value=int(counts[i]), **base))  # type: ignore
        out.append(models.AccidentRecord(month=months[i], metric="fatalities", value=int(kills[i]), **base))  # type: ignore
    return out



def _extract_pdf_text(pdf_bytes: bytes) -> str:
    from ..pdf import extract_text

    return extract_text(pdf_bytes)


def collect_morth(fetcher: HttpFetcher, settings: Optional[Settings] = None) -> Collection:
    """Collect MoRTH national series and state-wise accidents."""

    settings = settings or load_settings()
    coll = Collection(source_slug="morth-road-accidents-in-india")

    try:
        pdf_bytes = fetcher.fetch_bytes(_NATIONAL_PDF_URL)
        text = _extract_pdf_text(pdf_bytes)
        coll.documents.append(
            make_document(
                "morth-road-accidents-in-india",
                _NATIONAL_PDF_URL,
                pdf_bytes,
                title="Road Accidents in India 2022",
                doc_type="pdf",
            )
        )
    except Exception as exc:
        coll.add_error(f"national PDF fetch failed: {exc}")
        text = ""
    try:
        csv_text = fetcher.fetch_text(_STATE_CSV_URL)
    except Exception as exc:
        coll.add_error(f"state CSV fetch failed: {exc}")
        csv_text = ""
    if csv_text:
        coll.documents.append(
            make_document(
                "morth-state-wise-accidents",
                _STATE_CSV_URL,
                csv_text,
                title="State-wise road accidents 2020-2024",
                doc_type="csv",
            )
        )

    for rec in parse_national_series(text):
        if isinstance(rec, models.RegistrationExposure):
            coll.exposures.append(rec)
        else:
            coll.accident_records.append(rec)
    coll.accident_records.extend(parse_preface_narrative(text))
    coll.accident_records.extend(parse_collision_types(text))
    coll.accident_records.extend(parse_time_of_day(text))
    coll.accident_records.extend(parse_safety_devices(text))
    coll.accident_records.extend(parse_monthly(text))
    coll.accident_records.extend(parse_state_accidents_csv(csv_text))
    return coll
