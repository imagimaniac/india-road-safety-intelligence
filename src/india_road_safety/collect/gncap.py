"""Global NCAP collector and parsers."""

from __future__ import annotations

import re
from html import unescape
from typing import Any, Optional

from .. import models, normalize
from ..config import Settings, load_settings
from ..http import HttpFetcher
from ..pdf import extract_text
from .base import Collection, make_document


_RESULTS_ROW = re.compile(
    r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>',
    re.DOTALL | re.I,
)

# The live results page is Squarespace: one block per model, e.g.
#   <h2 ...><strong>Tata Nexon (*)</strong></h2><p ...>Tested model: Tata Nexon<br>
#   Body type: 5 Door SUV<br>Year of publication: 2024</p><p ...>
#   <a href="/s/Tata-Nexon-fact-sheet-2024-xeag.pdf" ...>Download full fact sheet</a>
_ENTRY_BLOCK = re.compile(
    r"<h2[^>]*>(?P<heading>.*?)</h2>(?P<rest>.*?)(?=<h2[^>]*>|</body>|$)",
    re.DOTALL | re.I,
)
_TAG = re.compile(r"<[^>]+>")
_STRONG = re.compile(r"<strong[^>]*>(.*?)</strong>", re.DOTALL | re.I)
_TESTED_MODEL = re.compile(r"Tested\s+model\s*:\s*(.*?)(?:<br|</p|$)", re.I | re.S)
_BODY_TYPE = re.compile(r"Body\s+type\s*:\s*(.*?)(?:<br|</p|$)", re.I | re.S)
_PUB_YEAR = re.compile(r"[Yy]ear\s+of\s+publication\s*:\s*(\d{4})", re.I)
_PDF_LINK = re.compile(r'href=["\']([^"\']+\.pdf)["\']', re.I)


def _plain(html_fragment: str) -> str:
    return normalize.clean_text(unescape(_TAG.sub(" ", html_fragment)))


def parse_gncap_results_html(html: str) -> list[dict[str, Any]]:
    """Parse the Global NCAP India results page.

    Handles the live Squarespace layout (an ``<h2>`` per model followed by a
    metadata paragraph and a fact-sheet PDF link). Falls back to a simple table
    row parser for the older/alternative markup.

    Extracts: model, tested_model, body_type, year, vin, fact_sheet_url.
    """

    out: list[dict[str, Any]] = []
    for m in _ENTRY_BLOCK.finditer(html):
        heading = m.group("heading")
        rest = m.group("rest")
        strong = _STRONG.search(heading)
        model = _plain(strong.group(1) if strong else heading)
        if not model:
            continue

        tm = _TESTED_MODEL.search(rest)
        bt = _BODY_TYPE.search(rest)
        ym = _PUB_YEAR.search(rest)
        pdfm = _PDF_LINK.search(rest)

        tested = _plain(tm.group(1)) if tm else model
        body = _plain(bt.group(1)) if bt else None
        year = ym.group(1) if ym else None
        fs_url = pdfm.group(1) if pdfm else None
        if not (tested != model or body or year or fs_url):
            # Not a model entry (e.g. a stray heading with no metadata).
            continue
        if fs_url and fs_url.startswith("/"):
            fs_url = "https://www.globalncap.org" + fs_url

        out.append(
            {
                "model": model,
                "tested_model": tested,
                "body_type": body,
                "year": year,
                "vin": None,
                "fact_sheet_url": fs_url,
            }
        )

    if out:
        return out

    # Fallback: simple table markup.
    for m in _RESULTS_ROW.finditer(html):
        cells = [normalize.clean_text(_TAG.sub(" ", m.group(i))) for i in (1, 2, 3, 4, 5, 6)]
        if not any(cells):
            continue
        fs_url = None
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(6))
        if href:
            fs_url = href.group(1)
            if fs_url.startswith("/"):
                fs_url = "https://www.globalncap.org" + fs_url
        out.append(
            {
                "model": cells[0] or cells[1],
                "tested_model": cells[1],
                "body_type": cells[2],
                "year": cells[3],
                "vin": cells[4],
                "fact_sheet_url": fs_url,
            }
        )
    return out


# Fact sheet points extraction
_POINTS = re.compile(
    r"([\d.]+)\s*max\.\s*(49\.00|17\.00|34\.00)\s*(Child|Adult)",
    re.I,
)
_BODYSHELL = re.compile(
    r"bodyshell(?:\s+integrity)?[\s\S]{0,90}?\b(unstable|stable|collapsed|not\s+ratingable|not\s+assessed)\b",
    re.I,
)
_EQUIP = re.compile(r"(airbag|esc|abs|ebd|isofix|crash avoidance|autonomous emergency)", re.I)


def parse_gncap_fact_sheet(text: str) -> dict[str, Any]:
    """Parse Global NCAP fact sheet text for points, bodyshell, equipment."""
    out: dict[str, Any] = {}
    for m in _POINTS.finditer(text):
        score = normalize.parse_float(m.group(1))
        maxv = normalize.parse_float(m.group(2))
        typ = m.group(3).lower()  # adult/child
        if score is not None:
            if typ == "adult":
                out["adult_occupant_protection"] = score
                out["adult_max"] = maxv
            else:
                out["child_occupant_protection"] = score
                out["child_max"] = maxv
    m2 = _BODYSHELL.search(text)
    if m2:
        out["bodyshell"] = m2.group(1).lower()
    equip = set()
    for m3 in _EQUIP.finditer(text):
        equip.add(m3.group(1).lower())
    if equip:
        out["equipment_tested"] = ",".join(sorted(equip))
    return out


def collect_gncap(
    fetcher: HttpFetcher,
    settings: Optional[Settings] = None,
    max_fact_sheets: Optional[int] = None,
) -> Collection:
    settings = settings or load_settings()
    coll = Collection(source_slug="global-ncap")
    results_url = "https://www.globalncap.org/results"
    try:
        html = fetcher.fetch_text(results_url)
    except Exception as exc:  # pragma: no cover
        coll.add_error(str(exc))
        return coll

    entries = parse_gncap_results_html(html)
    coll.documents.append(
        make_document("global-ncap", results_url, html, title="Global NCAP results", doc_type="html")
    )
    fetched = 0
    for e in entries:
        fs = e.get("fact_sheet_url")
        if not fs:
            continue
        if max_fact_sheets is not None and fetched >= max_fact_sheets:
            break
        try:
            pdf_bytes = fetcher.fetch_bytes(fs)
            txt = extract_text(pdf_bytes)
        except Exception:  # pragma: no cover
            coll.add_error(f"fact sheet fetch failed: {fs}")
            continue
        fetched += 1
        parsed = parse_gncap_fact_sheet(txt)

        amax = parsed.get("adult_max")
        cmax = parsed.get("child_max")
        proto_bits = []
        if amax is not None:
            proto_bits.append(f"adult_max={amax:g}")
        if cmax is not None:
            proto_bits.append(f"child_max={cmax:g}")
        protocol_version = ";".join(proto_bits) if proto_bits else None

        model_name = e.get("tested_model") or e.get("model") or ""
        ct = models.CrashTestAssessment(
            program="Global NCAP",
            protocol_version=protocol_version,
            test_date=None,
            market="India",
            make_slug=None,
            model_slug=normalize.slugify(model_name),
            variant_ref=e.get("model") if e.get("model") != e.get("tested_model") else None,
            adult_occupant_protection=parsed.get("adult_occupant_protection"),
            child_occupant_protection=parsed.get("child_occupant_protection"),
            bodyshell=parsed.get("bodyshell"),
            equipment_tested=parsed.get("equipment_tested"),
            source_slug="global-ncap",
            document_id=None,
            is_comparable=False,  # never compare star ratings across protocol eras
            evidence_class="observed_fact",
            confidence="medium",
        )
        coll.crash_tests.append(ct)
    return coll
