"""Pure, deterministic normalisation helpers.

Everything here is side-effect free and dependency-free so it can be unit-tested
without any network access. Adapted from the normalisation approach in
``~/Projects/unified-job-portal-automation/discovery/normalize.py``.

Guiding rule: a value that cannot be parsed confidently becomes ``None`` — never
``0`` and never a guessed date.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import date, datetime
from typing import Iterable, Optional

# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")

# Corporate / market noise stripped for a stable comparison key. Kept small and
# explicit so it is auditable; real make/model mapping lives in the alias table.
_MAKE_NOISE = {
    "ltd", "limited", "pvt", "private", "india", "motors", "motor", "auto",
    "automobiles", "automotive", "company", "co", "inc", "corp", "corporation",
}


def collapse_ws(text: str) -> str:
    """Collapse all runs of whitespace to single spaces and strip the ends."""
    return _WS_RE.sub(" ", text).strip()


def clean_text(text: Optional[str]) -> str:
    """Unescape HTML entities and collapse whitespace. ``None`` -> ``""``."""
    if not text:
        return ""
    return collapse_ws(html.unescape(str(text)))


def strip_accents(text: str) -> str:
    """Remove combining marks (defensive for mixed-script source text)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def slugify(text: str) -> str:
    """Lowercase, accent-stripped, hyphenated slug. ``""`` in -> ``""`` out."""
    if not text:
        return ""
    t = strip_accents(str(text)).lower()
    t = _NON_WORD_RE.sub("-", t)
    return t.strip("-")


def normalize_key(text: Optional[str]) -> str:
    """A tight comparison key: lowercase alphanumerics separated by single spaces."""
    if not text:
        return ""
    t = strip_accents(str(text)).lower()
    t = _NON_WORD_RE.sub(" ", t)
    return collapse_ws(t)


def normalize_manufacturer(name: Optional[str]) -> str:
    """Comparison key for a manufacturer, stripping common corporate noise."""
    key = normalize_key(name)
    if not key:
        return ""
    tokens = [tok for tok in key.split() if tok not in _MAKE_NOISE]
    return " ".join(tokens) if tokens else key


def normalize_vehicle_name(name: Optional[str]) -> str:
    """Comparison key for a model name (see the alias table for real mapping)."""
    return normalize_key(name)


# --------------------------------------------------------------------------- #
# Hashing / stable identifiers
# --------------------------------------------------------------------------- #
def content_hash(*parts: object) -> str:
    """Deterministic SHA-256 over normalised parts.

    Used to detect unchanged vs changed source records (dedupe by content, not
    by position). ``None`` and ``""`` normalise to the empty string so that a
    missing field does not manufacture spurious distinctions.
    """
    norm = []
    for p in parts:
        if p is None:
            norm.append("")
        else:
            norm.append(collapse_ws(str(p)).lower())
    return hashlib.sha256("\x1f".join(norm).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 16) -> str:
    """A short, stable identifier derived from content (e.g. ``src-1a2b3c...``)."""
    digest = content_hash(*parts)[:length]
    return f"{prefix}-{digest}" if prefix else digest


# --------------------------------------------------------------------------- #
# Numbers
# --------------------------------------------------------------------------- #
_MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nil", "none", "null", "unknown", "not reported"}
_CURRENCY_RE = re.compile(r"[₹$€£]|(?:\brs\.?\b)|(?:\binr\b)", re.I)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    s = str(value).strip().lower()
    return s in _MISSING_TOKENS


def parse_int(value: object) -> Optional[int]:
    """Parse an integer from messy source text, else ``None``.

    Handles Indian digit grouping ("1,23,456"), surrounding spaces and currency
    marks. Non-numeric leftovers make the whole value ``None`` (no guessing).
    """
    if _is_missing(value):
        return None
    s = str(value).strip()
    s = _CURRENCY_RE.sub("", s)
    s = s.replace(",", "").replace(" ", "").replace("\u00a0", "")
    if s in ("", "-", "+"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return int(round(f))


def parse_float(value: object) -> Optional[float]:
    """Parse a float from messy source text, else ``None``."""
    if _is_missing(value):
        return None
    s = str(value).strip()
    s = _CURRENCY_RE.sub("", s)
    s = s.replace(",", "").replace(" ", "").replace("\u00a0", "").rstrip("%")
    if s in ("", "-", "+"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d-%b-%Y",
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_YM_RE = re.compile(r"(\d{4})\s*[-/ ]\s*(\d{1,2})(?!\d)")
_Y_MONTHNAME_RE = re.compile(r"([A-Za-z]{3,9})\s+(\d{4})")


def parse_date(value: object) -> Optional[date]:
    """Parse a calendar date, else ``None``. Never invents a missing day."""
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = collapse_ws(str(value))
    if not s:
        return None
    s_iso = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s_iso).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_year_month(value: object) -> Optional[tuple[int, int]]:
    """Parse a year + month from text, else ``None``.

    Returns ``(year, month)`` for inputs like "2024-01", "01/2024", "Jan 2024".
    A year alone is *not* a year-month and yields ``None`` (no invented month).
    """
    if _is_missing(value):
        return None
    s = collapse_ws(str(value))
    m = _YM_RE.search(s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return year, month
    m2 = _Y_MONTHNAME_RE.search(s)
    if m2:
        name, year = m2.group(1).lower(), int(m2.group(2))
        key = name[:4] if name.startswith("sept") else name[:3]
        if key in _MONTHS:
            return year, _MONTHS[key]
    return None


def parse_year(value: object) -> Optional[int]:
    """Parse a 4-digit year, else ``None``."""
    if _is_missing(value):
        return None
    m = re.search(r"(?<!\d)(1[89]\d{2}|20\d{2}|21\d{2})(?!\d)", str(value))
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
def canonical_category(value: object, mapping: dict[str, str]) -> Optional[str]:
    """Map raw category text to a canonical value via ``mapping`` (keyed by
    :func:`normalize_key`). Returns ``None`` when the mapping has no match —
    unknown categories are never silently force-fitted.
    """
    key = normalize_key(str(value) if value is not None else "")
    if not key:
        return None
    for raw, canon in mapping.items():
        if normalize_key(raw) == key:
            return canon
    return None


def first_present(values: Iterable[object]) -> Optional[object]:
    """Return the first value that is not missing, else ``None``."""
    for v in values:
        if not _is_missing(v):
            return v
    return None
