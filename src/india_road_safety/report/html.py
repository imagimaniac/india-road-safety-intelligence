"""Self-contained HTML report builder.

Produces a single HTML document with an embedded stylesheet and inline SVG
charts. No external JS, CSS or network requests — the file can be opened
offline and emailed as-is.

The builder never invents facts: every figure it renders comes from the
analysis context passed in by the pipeline, which in turn comes from collected
records with provenance.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime, timezone
from html import escape
from typing import Any, Optional

from . import svg


def _e(v: Any) -> str:
    return escape(str(v), quote=True)


def _h2(anchor: str, text: str) -> str:
    return f"<h2 id='{_e(anchor)}'>{_e(text)}</h2>"


def _fmt(v: Optional[float], fmt: str = "{:,.0f}") -> str:
    if v is None:
        return '<span class="na">n/a</span>'
    try:
        return _e(fmt.format(v))
    except (ValueError, TypeError):
        return _e(v)


def _pct(v: Optional[float]) -> str:
    if v is None:
        return '<span class="na">n/a</span>'
    return _e(f"{v:+.1f}%" if isinstance(v, (int, float)) else str(v))


_CSS = """
:root { --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; --accent:#0072B2; --bg:#ffffff; --panel:#f7f9fb; --card:#f7f9fb; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif; line-height:1.5; }
.wrap { max-width:960px; margin:0 auto; padding:32px 24px 80px; }
header.hero { border-bottom:3px solid var(--accent); padding-bottom:16px; margin-bottom:8px; }
h1 { font-size:28px; margin:0 0 6px; }
h2 { font-size:20px; margin:34px 0 10px; border-left:4px solid var(--accent); padding-left:10px; }
h3 { font-size:16px; margin:22px 0 8px; color:#333; }
.sub { color:var(--muted); font-size:14px; }
.meta { color:var(--muted); font-size:12.5px; margin-top:10px; }
nav.toc { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin:16px 0; }
nav.toc .t { font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:6px; }
nav.toc ol { margin:0; padding-left:20px; }
nav.toc li { margin:2px 0; }
nav.toc a { color:var(--accent); text-decoration:none; }
nav.toc a:hover { text-decoration:underline; }
.cards { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }
.card { flex:1 1 180px; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 16px; }
.card .k { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.card .v { font-size:24px; font-weight:600; margin-top:2px; }
.card .d { font-size:12px; color:var(--muted); }
table { border-collapse:collapse; width:100%; margin:10px 0 6px; font-size:13.5px; }
th,td { border-bottom:1px solid var(--line); padding:7px 9px; text-align:left; }
th { background:var(--panel); font-weight:600; }
td.num,th.num { text-align:right; font-variant-numeric:tabular-nums; }
.figure { background:#fff; border:1px solid var(--line); border-radius:8px; padding:12px; margin:14px 0; }
.figure svg { width:100%; height:auto; display:block; }
.figcap { font-size:12.5px; color:var(--muted); margin-top:6px; }
.note { background:var(--panel); border-left:4px solid var(--accent); padding:10px 14px; margin:14px 0; font-size:13.5px; }
.warn { border-left-color:#E69F00; }
.danger { border-left-color:#D55E00; }
.na { color:#999; font-style:italic; }
ul.tight { margin:8px 0; padding-left:22px; }
ul.tight li { margin:4px 0; }
.badge { display:inline-block; font-size:11px; padding:1px 7px; border-radius:10px; background:#eef3f7; color:#005b8f; border:1px solid #cfe0ec; }
.badge.verified { background:#eaf6ee; color:#1d7a3a; border-color:#c5e6cf; }
.badge.blocked { background:#fdecec; color:#a12b2b; border-color:#f3c9c9; }
.badge.pending_verification { background:#fdf6e6; color:#8a6d1a; border-color:#efe0b0; }
.exports { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; }
.exports a { display:inline-block; font-size:12.5px; padding:5px 11px; border:1px solid var(--line); border-radius:16px; background:var(--panel); color:var(--accent); text-decoration:none; }
.exports a:hover { border-color:var(--accent); }
footer { margin-top:40px; border-top:1px solid var(--line); padding-top:14px; color:var(--muted); font-size:12.5px; }
.small { font-size:12px; color:var(--muted); }
.two { display:flex; gap:18px; flex-wrap:wrap; }
.two > div { flex:1 1 320px; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --muted:#a0a0a0; --line:#333; --accent:#56B4E9; --bg:#15181c; --panel:#1e2227; --card:#1e2227; }
  h3 { color:#ddd; }
  .badge { background:#123; color:#7cc4ee; border-color:#245; }
  .badge.verified { background:#0d2917; color:#6fd48c; border-color:#1d4; }
  .badge.blocked { background:#2d0d0d; color:#f08a8a; border-color:#a33; }
  .badge.pending_verification { background:#2d260d; color:#e0c060; border-color:#a83; }
  .exports a, nav.toc { background:var(--panel); }
  /* charts keep a light card so inline-SVG stays legible in dark mode */
  .figure { background:#fff; border-color:#444; }
  .figcap { color:#666; }
}
@media print {
  nav.toc, .exports { display:none; }
  body { background:#fff; color:#000; }
  h2 { page-break-after:avoid; }
  .figure, table { page-break-inside:avoid; }
  a { color:#000; text-decoration:none; }
}
"""


def _stat_cards(cards: list[tuple[str, str, str]]) -> str:
    out = ['<div class="cards">']
    for k, v, d in cards:
        out.append(f'<div class="card"><div class="k">{_e(k)}</div><div class="v">{v}</div><div class="d">{d}</div></div>')
    out.append("</div>")
    return "".join(out)


def build_report(ctx: dict[str, Any]) -> str:
    """Render the full HTML report from an analysis context dict."""

    title = ctx.get("title", "India Road Safety & Passenger-Car Safety — Evidence Report")
    generated = ctx.get("generated_at") or datetime.now(timezone.utc)
    if isinstance(generated, datetime):
        generated_s = generated.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        generated_s = str(generated)

    parts: list[str] = []
    parts.append(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_e(title)}</title><style>{_CSS}</style></head><body><div class='wrap'>"
    )

    # -- header ----------------------------------------------------------- #
    parts.append("<header class='hero'>")
    parts.append(f"<h1>{_e(title)}</h1>")
    parts.append(
        "<div class='sub'>Aggregate road-accident statistics (national &amp; state) with an "
        "objective, protocol-aware look at passenger-car crash-test results. Built from a "
        "source registry with mandatory provenance.</div>"
    )
    parts.append(
        "<div class='meta'>"
        f"Generated {_e(generated_s)} &middot; Cutoff policy: {_e(ctx.get('cutoff_policy','latest_available_at_build'))} &middot; "
        f"Latest data year: {_e(ctx.get('latest_data_year','n/a'))} &middot; Sources registered: {_e(ctx.get('source_count','n/a'))}"
        "</div>"
    )
    parts.append("</header>")

    parts.append(_toc())

    parts.append(_executive_summary(ctx))
    parts.append(_scope_and_method(ctx))
    parts.append(_national_context(ctx))
    parts.append(_vehicle_safety(ctx))
    parts.append(_evidence_section(ctx))
    parts.append(_limitations(ctx))
    parts.append(_sources_section(ctx))
    parts.append(_data_export(ctx))
    parts.append(_methodology_appendix(ctx))

    parts.append(
        "<footer>This report is generated from public data with recorded provenance. "
        "Costs, counts and shares are reported as published; unavailable values are shown as "
        "&lsquo;n/a&rsquo; and never replaced with zero. See the source register for licences and attribution.</footer>"
    )
    parts.append("</div></body></html>")
    return "".join(parts)


def _executive_summary(ctx: dict[str, Any]) -> str:
    s = ctx.get("national_summary", {})
    parts = [_h2("exec-summary", "Executive summary"), "<ul class='tight'>"]
    if s.get("accidents") is not None:
        yoy = s.get("accidents_yoy_pct")
        yoystr = f" ({yoy:+.1f}% vs {s.get('prev_year')})" if yoy is not None else ""
        parts.append(f"<li><b>{_fmt(s['accidents'])}</b> road accidents were reported in India in {_e(s.get('year'))}{yoystr}.</li>")
    if s.get("fatalities") is not None:
        yoy = s.get("fatalities_yoy_pct")
        yoystr = f" ({yoy:+.1f}% vs {s.get('prev_year')})" if yoy is not None else ""
        parts.append(f"<li><b>{_fmt(s['fatalities'])}</b> people were killed{yoystr}.</li>")
    ru = ctx.get("road_user") or []
    if ru:
        top = ru[0]
        parts.append(f"<li>Road deaths are dominated by <b>{_e(top['category'])}</b> ({_e(top['share_pct'])}% of deaths).</li>")
    rf = ctx.get("risk_factors") or {}
    if rf.get("overspeeding_share_of_deaths_pct") is not None:
        parts.append(f"<li>&lsquo;Over speeding&rsquo; was the recorded factor in <b>{_e(rf['overspeeding_share_of_deaths_pct'])}%</b> of deaths (recorded factor, not proven cause).</li>")
    ct = ctx.get("crash_test_table") or []
    if ct:
        parts.append(f"<li>{len(ct)} passenger-car crash tests are catalogued; results are shown as <b>protection points normalised within each protocol era</b> — star ratings are deliberately not compared across protocols.</li>")
    parts.append("</ul>")
    return "".join(parts)


def _scope_and_method(ctx: dict[str, Any]) -> str:
    return "".join([
        _h2("scope", "Scope & method"),
        "<p>Primary question: <b>what does the evidence say about passenger-car safety in India?</b> "
        "National and state accident statistics provide the context; crash-test results provide the "
        "model-level, testable evidence. We keep three evidence types strictly separate: "
        "<span class='badge'>official statistics</span> "
        "<span class='badge'>crash-test assessments</span> "
        "<span class='badge'>derived indicators</span>.</p>",
        "<div class='note'>A police-recorded factor (e.g. &lsquo;over speeding&rsquo;) is a <b>recorded</b> "
        "factor, not proof of causation. Observational correlation is not treated as causation anywhere in this report.</div>",
    ])


def _national_context(ctx: dict[str, Any]) -> str:
    parts = [_h2("national", "National accident context")]
    s = ctx.get("national_summary", {})
    cards = []
    if s.get("accidents") is not None:
        cards.append(("Road accidents", _fmt(s["accidents"]), f"year {s.get('year')}"))
    if s.get("fatalities") is not None:
        cards.append(("Deaths", _fmt(s["fatalities"]), f"year {s.get('year')}"))
    if s.get("injuries") is not None:
        cards.append(("Injuries", _fmt(s["injuries"]), f"year {s.get('year')}"))
    if cards:
        parts.append(_stat_cards(cards))

    trend = ctx.get("national_trend") or []
    if trend:
        cats = [str(r["year"]) for r in trend]
        parts.append("<div class='figure'>")
        parts.append(svg.line_chart([(str(r["year"]), r["accidents"]) for r in trend], color=svg.PALETTE[0], y_label="Accidents", x_label="Year"))
        parts.append("<div class='figcap'>Reported road accidents per year (national). Source: MoRTH.</div></div>")
        parts.append("<div class='figure'>")
        parts.append(svg.line_chart([(str(r["year"]), r["fatalities"]) for r in trend], color=svg.PALETTE[4], y_label="Deaths", x_label="Year"))
        parts.append("<div class='figcap'>Reported road deaths per year (national). Source: MoRTH.</div></div>")

    ea = ctx.get("exposure_adjusted") or []
    if ea:
        parts.append("<div class='figure'>")
        parts.append(svg.line_chart([(str(r["year"]), r["fatalities_per_lakh_population"]) for r in ea], color=svg.PALETTE[1], y_label="Deaths per lakh population", x_label="Year", fmt="{:,.1f}"))
        parts.append("<div class='figcap'>Deaths per 100,000 population (exposure-adjusted). This distinguishes a rising count from a rising <em>rate</em>.</div></div>")

    rt = ctx.get("road_type") or []
    if rt:
        parts.append("<h3>Where accidents happen (road type, latest year)</h3>")
        segs = [(b["road_type"].replace("_", " ").title(), b.get("accidents_share_pct")) for b in rt if b.get("accidents_share_pct") is not None]
        if segs:
            parts.append("<div class='figure'>" + svg.donut_chart(segs) + "<div class='figcap'>Share of accidents by road type. Source: MoRTH.</div></div>")
        rows = []
        for b in rt:
            rows.append(
                f"<tr><td>{_e(b['road_type'].replace('_',' ').title())}</td>"
                f"<td class='num'>{_fmt(b.get('accidents'))}</td>"
                f"<td class='num'>{_fmt(b.get('accidents_share_pct'), '{:.1f}%')}</td>"
                f"<td class='num'>{_fmt(b.get('fatalities'))}</td>"
                f"<td class='num'>{_fmt(b.get('fatalities_share_pct'), '{:.1f}%')}</td></tr>"
            )
        parts.append("<table><thead><tr><th>Road type</th><th class='num'>Accidents</th><th class='num'>Share</th><th class='num'>Deaths</th><th class='num'>Share</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")

    ru = ctx.get("road_user") or []
    if ru:
        parts.append("<h3>Who dies (road-user category)</h3>")
        segs = [(r["category"], r["share_pct"]) for r in ru if r.get("share_pct") is not None]
        parts.append("<div class='figure'>" + svg.donut_chart(segs) + "<div class='figcap'>Share of road deaths by road-user category. Source: MoRTH.</div></div>")

    rf = ctx.get("risk_factors") or {}
    rf_items = [
        ("Over speeding — share of accidents", rf.get("overspeeding_share_of_accidents_pct")),
        ("Over speeding — share of deaths", rf.get("overspeeding_share_of_deaths_pct")),
        ("Wrong-side driving — share of accidents", rf.get("wrong_side_share_of_accidents_pct")),
    ]
    if any(v is not None for _, v in rf_items):
        parts.append("<h3>Recorded contributing factors</h3>")
        parts.append("<div class='figure'>" + svg.hbar_chart([k for k, _ in rf_items], [v for _, v in rf_items], fmt="{:.1f}%", color=svg.PALETTE[1]) + "<div class='figcap'>Recorded factors, as a share of accidents/deaths. Source: MoRTH.</div></div>")

    ts = ctx.get("trend_stats") or {}
    if ts:
        parts.append("<h3>Long-run trend</h3>")
        cards = []
        for key, label in (
            ("accidents", "Accidents"),
            ("fatalities", "Deaths"),
            ("fatalities_per_lakh_population", "Deaths / lakh"),
        ):
            e = ts.get(key) or {}
            if e.get("cagr_pct") is not None:
                cards.append((f"{label} CAGR", f"{e['cagr_pct']:+.2f}%", f"{e['first_year']}–{e['latest_year']}"))
            elif e.get("five_year_change_pct") is not None:
                cards.append((f"{label} 5-yr", f"{e['five_year_change_pct']:+.1f}%", f"vs {e['five_year_base']}"))
        if cards:
            parts.append(_stat_cards(cards))

    coll = ctx.get("collision_breakdown") or []
    if coll:
        parts.append("<h3>By collision type (latest year)</h3>")
        parts.append("<div class='figure'>" + svg.hbar_chart([c["category"] for c in coll], [c.get("accidents") for c in coll], color=svg.PALETTE[0], fmt="{:,.0f}") + "<div class='figcap'>Accidents by collision type. Source: MoRTH Table 1.5.</div></div>")
        body = []
        for c in coll:
            body.append(
                f"<tr><td>{_e(c['category'])}</td>"
                f"<td class='num'>{_fmt(c.get('accidents'))}</td>"
                f"<td class='num'>{_fmt(c.get('accidents_share_pct'), '{:.1f}%')}</td>"
                f"<td class='num'>{_fmt(c.get('fatalities'))}</td>"
                f"<td class='num'>{_fmt(c.get('fatalities_share_pct'), '{:.1f}%')}</td></tr>"
            )
        parts.append("<table><thead><tr><th>Collision type</th><th class='num'>Accidents</th><th class='num'>Share</th><th class='num'>Deaths</th><th class='num'>Share</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")

    tod = ctx.get("time_of_day") or []
    if tod:
        parts.append("<h3>By time of day</h3>")
        parts.append("<div class='figure'>" + svg.bar_chart([t["interval"] for t in tod], [t.get("accidents") for t in tod], color=svg.PALETTE[1], y_label="Accidents") + "<div class='figcap'>Accidents by time interval. Source: MoRTH Table 7.3.</div></div>")
        body = []
        for t in tod:
            body.append(
                f"<tr><td>{_e(t['interval'])}</td><td>{_e(t['period'])}</td>"
                f"<td class='num'>{_fmt(t.get('accidents'))}</td>"
                f"<td class='num'>{_fmt(t.get('share_pct'), '{:.1f}%')}</td></tr>"
            )
        parts.append("<table><thead><tr><th>Interval</th><th>Period</th><th class='num'>Accidents</th><th class='num'>Share</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")

    mon = ctx.get("monthly") or []
    if mon:
        parts.append("<h3>Month-to-month seasonality</h3>")
        pts = [(str(m["month"]), m["accidents"]) for m in mon if m.get("accidents") is not None]
        if pts:
            parts.append("<div class='figure'>" + svg.line_chart(pts, color=svg.PALETTE[2], y_label="Accidents", x_label="Month (1=Jan)") + "<div class='figcap'>National accidents by month. Source: MoRTH Table 7.2.</div></div>")

    sd = ctx.get("safety_devices") or {}
    if any(v is not None for v in sd.values()):
        parts.append("<h3>Deaths from non-use of protective equipment</h3>")
        cards = []
        if sd.get("helmet_total") is not None:
            cards.append(("Helmet (non-use)", _fmt(sd["helmet_total"]), f"driver {_fmt(sd.get('helmet_driver'))} · pax {_fmt(sd.get('helmet_passenger'))}"))
        if sd.get("seatbelt_total") is not None:
            cards.append(("Seat belt (non-use)", _fmt(sd["seatbelt_total"]), f"driver {_fmt(sd.get('seatbelt_driver'))} · pax {_fmt(sd.get('seatbelt_passenger'))}"))
        if cards:
            parts.append(_stat_cards(cards))
        parts.append("<div class='note'>Deaths where the investigating officer recorded non-use of a helmet or seat belt. Source: MoRTH Table 3.3.</div>")

    st = ctx.get("state_table") or {}
    if st.get("rows"):
        parts.append(f"<h3>States/UTs by accidents ({_e(st.get('year'))})</h3>")
        rows = st["rows"][:15]
        top = [(r["state"], r.get("value")) for r in rows if r.get("value") is not None][:10]
        if top:
            parts.append("<div class='figure'>" + svg.hbar_chart([t[0] for t in top], [t[1] for t in top], color=svg.PALETTE[2]) + "<div class='figcap'>Top states by reported accidents. Source: MoRTH via data.opencity.in.</div></div>")
        body = []
        for r in rows:
            body.append(
                f"<tr><td>{_e(r['state'])}</td><td class='num'>{_fmt(r.get('value'))}</td>"
                f"<td class='num'>{_fmt(r.get('prev_value'))}</td>"
                f"<td class='num'>{_e(str(r.get('change')) if r.get('change') is not None else 'n/a')}</td>"
                f"<td class='num'>{_fmt(r.get('change_pct'), '{:+.1f}%')}</td></tr>"
            )
        parts.append(f"<table><thead><tr><th>State/UT</th><th class='num'>Accidents {_e(st.get('year'))}</th><th class='num'>{_e(st.get('prev_year'))}</th><th class='num'>Change</th><th class='num'>Change %</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    return "".join(parts)


def _vehicle_safety(ctx: dict[str, Any]) -> str:
    parts = [_h2("vehicles", "Passenger-car safety (crash tests)")]
    eras = ctx.get("protocol_eras") or {}
    if eras:
        parts.append("<p>" + " &middot; ".join(f"<span class='badge'>{_e(k)}: {_e(v)} tests</span>" for k, v in eras.items()) + "</p>")
    parts.append(
        "<div class='note warn'><b>Comparability rule.</b> Crash-test scores are only comparable within the "
        "same protocol era, variant and equipment. Global NCAP's adult-score maximum changed over time "
        "(17 points to 34 points per the fact sheets we parsed). We therefore show raw protection points, "
        "the protocol maximum they are out of, and a normalised percentage — never a cross-protocol star ranking.</div>"
    )
    ct = ctx.get("crash_test_table") or []
    if ct:
        top = ct[:20]
        cats = [e["model_slug"] for e in top]
        adult = [e.get("adult_pct_of_max") for e in top]
        child = [e.get("child_pct_of_max") for e in top]
        parts.append("<div class='figure'>" + svg.grouped_bar_chart(cats, {"Adult protection (% of max)": adult, "Child protection (% of max)": child}, fmt="{:,.0f}%") + "<div class='figcap'>Normalised occupant protection by tested model (top 20 by adult protection). Bars are comparable only within the same protocol era. Source: Global NCAP fact sheets.</div></div>")

        body = []
        for e in ct:
            body.append(
                f"<tr><td>{_e(e['model_slug'])}</td>"
                f"<td class='num'>{_fmt(e.get('adult_points'), '{:.2f}')} / {_fmt(e.get('adult_max'), '{:.0f}')}</td>"
                f"<td class='num'>{_fmt(e.get('adult_pct_of_max'), '{:.0f}%')}</td>"
                f"<td class='num'>{_fmt(e.get('child_points'), '{:.2f}')} / {_fmt(e.get('child_max'), '{:.0f}')}</td>"
                f"<td>{_e(e.get('bodyshell') or 'n/a')}</td></tr>"
            )
        parts.append("<table><thead><tr><th>Model (slug)</th><th class='num'>Adult pts/max</th><th class='num'>Adult %</th><th class='num'>Child pts/max</th><th>Bodyshell</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")

    bs = ctx.get("bodyshell_counts") or {}
    if bs:
        parts.append("<h3>Bodyshell integrity (as stated)</h3>")
        parts.append("<div class='figure'>" + svg.bar_chart(list(bs.keys()), list(bs.values()), color=svg.PALETTE[2], y_label="Tests") + "<div class='figcap'>Count of tests by stated bodyshell outcome.</div></div>")

    eq = ctx.get("equipment_summary") or {}
    if eq:
        items = list(eq.items())[:8]
        parts.append("<h3>Safety equipment explicitly listed in fact sheets</h3>")
        parts.append("<div class='figure'>" + svg.hbar_chart([k.upper() for k, _ in items], [v for _, v in items], color=svg.PALETTE[3]) + "<div class='figcap'>Number of fact sheets mentioning each item. Presence in the tested variant is not proof of standard fitment across all variants.</div></div>")

    ec = ctx.get("equipment_contrast") or {}
    if ec:
        parts.append("<h3>Equipment vs protection (within protocol era)</h3>")
        if not ec.get("has_comparable_contrast"):
            parts.append(
                "<div class='note warn'><b>No valid contrast in this corpus.</b> Testing whether a safety "
                "item (ESC, ISOFIX…) is associated with higher protection would require tests that differ "
                "only in that item. In the catalogued Global NCAP India results the equipment tags are "
                "near-constant inside each protocol era, so the &lsquo;without&rsquo; group is empty or below "
                f"the minimum group size of {_e(ec.get('min_n'))}. We therefore do <em>not</em> report a "
                "with-vs-without protection difference, because it would be statistically unsupported.</div>"
            )
        body = []
        for c in ec.get("comparisons") or []:
            body.append(
                f"<tr><td>{_e(c['era'])}</td><td>{_e(str(c['item']).upper())}</td>"
                f"<td class='num'>{_e(c['present_n'])}</td>"
                f"<td class='num'>{_e(c['absent_n'])}</td>"
                f"<td class='num'>{_fmt(c.get('present_mean_pct'), '{:.1f}%')}</td>"
                f"<td class='num'>{_fmt(c.get('absent_mean_pct'), '{:.1f}%')}</td>"
                f"<td>{'yes' if c.get('comparable') else 'no'}</td></tr>"
            )
        parts.append("<table><thead><tr><th>Protocol era</th><th>Item</th><th class='num'>With (n)</th><th class='num'>Without (n)</th><th class='num'>Mean % with</th><th class='num'>Mean % without</th><th>Comparable?</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    return "".join(parts)


def _limitations(ctx: dict[str, Any]) -> str:
    items = ctx.get("limitations") or [
        "Crash-test results describe a specific tested variant; other variants/trim levels may differ.",
        "Star ratings are not compared across protocols, years or markets (different maxima and test routines).",
        "National accident totals are police-recorded and subject to under-reporting and definitional differences.",
        "A recorded contributing factor is not proof of causation.",
        "Model-level real-world risk cannot be computed without per-model exposure (registrations/kilometres), which is not available here.",
    ]
    return _h2("limitations", "What this data does NOT support") + "<ul class='tight'>" + "".join(f"<li>{_e(x)}</li>" for x in items) + "</ul>"


def _sources_section(ctx: dict[str, Any]) -> str:
    sources = ctx.get("sources") or []
    parts = [_h2("sources", "Source register")]
    if not sources:
        parts.append("<p class='small'>No sources registered.</p>")
        return "".join(parts)
    body = []
    for s in sources:
        status = s.get("status", "unknown")
        if s.get("url"):
            name = f"<a href='{_e(s['url'])}'>{_e(s.get('organization') or s.get('slug'))}</a>"
        else:
            name = _e(s.get("organization") or s.get("slug"))
        body.append(
            f"<tr><td>{_e(s.get('slug'))}</td><td>{name}</td>"
            f"<td>{_e(s.get('data_type'))}</td>"
            f"<td><span class='badge {_e(status)}'>{_e(status)}</span></td>"
            f"<td class='small'>{_e(s.get('licence') or 'n/a')}</td></tr>"
        )
    parts.append("<table><thead><tr><th>Slug</th><th>Organization</th><th>Type</th><th>Status</th><th>Licence / basis</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")
    atts = [(s.get("slug"), s.get("attribution")) for s in sources if s.get("attribution")]
    if atts:
        parts.append("<h3>Attribution</h3><ul class='tight'>")
        for slug, att in atts:
            parts.append(f"<li>{_e(att)}</li>")
        parts.append("</ul>")
    return "".join(parts)


def _methodology_appendix(ctx: dict[str, Any]) -> str:
    return "".join([
        _h2("methodology", "Methodology appendix"),
        "<ul class='tight'>",
        "<li>Collection is gated by a source registry: a source must be <span class='badge verified'>verified</span> before it is fetched.</li>",
        "<li>Every record carries provenance (source slug, retrieval time, method, content hash) and is stored append-only.</li>",
        "<li>Missing values are stored as NULL and rendered as &lsquo;n/a&rsquo; — never as zero.</li>",
        "<li>Rates are computed from published numerators and denominators (e.g. deaths per lakh population from the MoRTH population column).</li>",
        "<li>Crash-test protection is normalised only within the same stated protocol maximum.</li>",
        "</ul>",
    ])


_SECTIONS = [
    ("exec-summary", "Executive summary"),
    ("scope", "Scope & method"),
    ("national", "National accident context"),
    ("vehicles", "Passenger-car safety"),
    ("evidence", "Evidence grading"),
    ("limitations", "What this data does NOT support"),
    ("sources", "Source register"),
    ("data-export", "Download the data"),
    ("methodology", "Methodology appendix"),
]


def _toc() -> str:
    items = "".join(f"<li><a href='#{_e(i)}'>{_e(t)}</a></li>" for i, t in _SECTIONS)
    return f"<nav class='toc'><div class='t'>Contents</div><ol>{items}</ol></nav>"


def _csv(headers: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue()


def _data_uri(content: str, mime: str = "text/csv") -> str:
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _data_export(ctx: dict[str, Any]) -> str:
    parts = [_h2("data-export", "Download the data")]
    parts.append(
        "<p class='small'>Every table in this report is embedded below as a downloadable file "
        "(data URI &mdash; works fully offline; nothing is fetched from a network when you click these).</p>"
    )
    links: list[tuple[str, str]] = []

    trend = ctx.get("national_trend") or []
    if trend:
        c = _csv(
            ["year", "accidents", "fatalities", "injuries"],
            [[r.get("year"), r.get("accidents"), r.get("fatalities"), r.get("injuries")] for r in trend],
        )
        links.append(("national_trend.csv", _data_uri(c)))

    coll = ctx.get("collision_breakdown") or []
    if coll:
        c = _csv(
            ["category", "accidents", "accidents_share_pct", "fatalities", "fatalities_share_pct"],
            [[r.get("category"), r.get("accidents"), r.get("accidents_share_pct"), r.get("fatalities"), r.get("fatalities_share_pct")] for r in coll],
        )
        links.append(("collision_by_type.csv", _data_uri(c)))

    tod = ctx.get("time_of_day") or []
    if tod:
        c = _csv(
            ["interval", "period", "accidents", "share_pct"],
            [[r.get("interval"), r.get("period"), r.get("accidents"), r.get("share_pct")] for r in tod],
        )
        links.append(("time_of_day.csv", _data_uri(c)))

    mon = ctx.get("monthly") or []
    if mon:
        c = _csv(["month", "accidents", "fatalities"], [[r.get("month"), r.get("accidents"), r.get("fatalities")] for r in mon])
        links.append(("monthly.csv", _data_uri(c)))

    ct = ctx.get("crash_test_table") or []
    if ct:
        c = _csv(
            ["model_slug", "adult_points", "adult_max", "adult_pct_of_max", "child_points", "child_max", "child_pct_of_max", "bodyshell", "equipment_tested"],
            [[e.get("model_slug"), e.get("adult_points"), e.get("adult_max"), e.get("adult_pct_of_max"), e.get("child_points"), e.get("child_max"), e.get("child_pct_of_max"), e.get("bodyshell"), e.get("equipment_tested")] for e in ct],
        )
        links.append(("crash_tests.csv", _data_uri(c)))

    st = ctx.get("state_table") or {}
    if st.get("rows"):
        c = _csv(
            ["state", "value", "prev_value", "change", "change_pct"],
            [[r.get("state"), r.get("value"), r.get("prev_value"), r.get("change"), r.get("change_pct")] for r in st["rows"]],
        )
        links.append((f"states_{st.get('year')}.csv", _data_uri(c)))

    try:
        blob = json.dumps(ctx, default=str, sort_keys=True)
        links.append(("report_context.json", _data_uri(blob, "application/json")))
    except (TypeError, ValueError):
        pass

    if links:
        parts.append("<div class='exports'>")
        for name, uri in links:
            parts.append(f"<a href='{_e(uri)}' download='{_e(name)}'>{_e(name)}</a>")
        parts.append("</div>")
    return "".join(parts)


def _evidence_section(ctx: dict[str, Any]) -> str:
    grading = ctx.get("evidence_grading") or []
    parts = [
        _h2("evidence", "Evidence grading"),
        "<p>Each registered source is scored 0&ndash;100 on five independent evidence dimensions "
        "(<em>primary source, corroboration, recency, completeness, identification confidence</em>). "
        "The dimensions are deliberately kept separate &mdash; they are not collapsed into a single "
        "quality judgement; the mean is shown only as a convenience, never as a verdict on the publisher.</p>",
    ]
    if not grading:
        parts.append("<p class='small'>No evidence grading computed.</p>")
        return "".join(parts)
    body = []
    for g in grading:
        d = g.get("dimensions") or {}
        body.append(
            f"<tr><td>{_e(g.get('slug'))}</td>"
            f"<td class='num'>{_fmt(d.get('primary_source'), '{:.0f}')}</td>"
            f"<td class='num'>{_fmt(d.get('corroboration'), '{:.0f}')}</td>"
            f"<td class='num'>{_fmt(d.get('recency'), '{:.0f}')}</td>"
            f"<td class='num'>{_fmt(d.get('completeness'), '{:.0f}')}</td>"
            f"<td class='num'>{_fmt(d.get('identification_confidence'), '{:.0f}')}</td>"
            f"<td class='num'><b>{_fmt(g.get('mean_score'), '{:.1f}')}</b></td>"
            f"<td class='num'>{_fmt(g.get('record_count'))}</td></tr>"
        )
    parts.append(
        "<table><thead><tr><th>Source</th><th class='num'>Primary</th><th class='num'>Corroboration</th>"
        "<th class='num'>Recency</th><th class='num'>Completeness</th><th class='num'>ID confidence</th>"
        "<th class='num'>Mean</th><th class='num'>Records</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"
    )
    parts.append(
        "<div class='note'>Scoring rules are documented in <code>analysis/evidence.py</code>. A low mean does "
        "not judge the publisher &mdash; it flags how well <em>this</em> snapshot supports a specific claim.</div>"
    )
    return "".join(parts)
