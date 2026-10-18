"""Dependency-free inline SVG chart primitives.

Every function returns a complete ``<svg>`` element string with inline styling,
so the final report is a single, self-contained HTML file (no JS, no CSS files,
no network requests).
"""

from __future__ import annotations

import math
from html import escape as _escape
from typing import Optional, Sequence

# Okabe-Ito colorblind-safe palette (adapted for light backgrounds).
PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00",
    "#56B4E9", "#8C6BB1", "#999999",
]

_AXIS = "#4a4a4a"
_GRID = "#e6e6e6"
_FONT = "font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif"


def esc(text: object) -> str:
    return _escape(str(text), quote=True)


def _fmt(v: Optional[float], fmt: str = "{:,.0f}") -> str:
    if v is None:
        return "n/a"
    try:
        return fmt.format(v)
    except (ValueError, TypeError):
        return str(v)


def _empty(message: str, width: int = 720, height: int = 120) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">'
        f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#888" font-size="14">'
        f"{esc(message)}</text></svg>"
    )


def line_chart(
    series: Sequence[tuple[object, Optional[float]]],
    width: int = 720,
    height: int = 320,
    color: str = PALETTE[0],
    x_label: str = "",
    y_label: str = "",
    fmt: str = "{:,.0f}",
) -> str:
    pts = [(str(x), v) for x, v in series if v is not None]
    if len(pts) < 2:
        return _empty("Not enough data for a line chart", width, height)

    pad_l, pad_r, pad_t, pad_b = 64, 24, 24, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    ys = [v for _, v in pts]
    ymin, ymax = min(ys), max(ys)
    if ymin == ymax:
        ymin, ymax = ymin - 1, ymax + 1
    span = ymax - ymin
    ymin -= span * 0.05
    ymax += span * 0.05

    def sx(i: int) -> float:
        return pad_l + (plot_w * i / (len(pts) - 1)) if len(pts) > 1 else pad_l + plot_w / 2

    def sy(v: float) -> float:
        return pad_t + plot_h * (1 - (v - ymin) / (ymax - ymin))

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">']
    # gridlines + y labels
    for k in range(5):
        yv = ymin + (ymax - ymin) * k / 4
        y = sy(yv)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="{_GRID}"/>')
        parts.append(
            f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="{_AXIS}">{esc(_fmt(yv, fmt))}</text>'
        )
    # x labels (thin out if crowded)
    step = max(1, len(pts) // 12)
    for i, (label, _) in enumerate(pts):
        if i % step == 0 or i == len(pts) - 1:
            parts.append(
                f'<text x="{sx(i):.1f}" y="{height-pad_b+20}" text-anchor="middle" font-size="11" fill="{_AXIS}">{esc(label)}</text>'
            )
    # line + points
    d = " ".join(f"{'M' if i == 0 else 'L'}{sx(i):.1f},{sy(v):.1f}" for i, (_, v) in enumerate(pts))
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    for i, (label, v) in enumerate(pts):
        parts.append(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="3" fill="{color}"><title>{esc(label)}: {esc(_fmt(v, fmt))}</title></circle>')
    if x_label:
        parts.append(f'<text x="{width/2}" y="{height-8}" text-anchor="middle" font-size="12" fill="{_AXIS}">{esc(x_label)}</text>')
    if y_label:
        parts.append(f'<text x="14" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="12" fill="{_AXIS}" transform="rotate(-90 14 {pad_t+plot_h/2})">{esc(y_label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(
    categories: Sequence[str],
    values: Sequence[Optional[float]],
    width: int = 720,
    height: int = 320,
    color: str = PALETTE[0],
    fmt: str = "{:,.0f}",
    y_label: str = "",
) -> str:
    pairs = [(c, v) for c, v in zip(categories, values) if v is not None]
    if not pairs:
        return _empty("No data for a bar chart", width, height)
    pad_l, pad_r, pad_t, pad_b = 64, 24, 24, 56
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vmax = max(v for _, v in pairs) or 1
    n = len(pairs)
    bw = plot_w / n * 0.62
    gap = plot_w / n

    def sy(v: float) -> float:
        return pad_t + plot_h * (1 - v / vmax)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">']
    for k in range(5):
        yv = vmax * k / 4
        y = sy(yv)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="{_GRID}"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="{_AXIS}">{esc(_fmt(yv, fmt))}</text>')
    for i, (cat, v) in enumerate(pairs):
        x = pad_l + gap * i + (gap - bw) / 2
        y = sy(v)
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{pad_t+plot_h-y:.1f}" fill="{color}" rx="2"><title>{esc(cat)}: {esc(_fmt(v, fmt))}</title></rect>')
        parts.append(f'<text x="{x+bw/2:.1f}" y="{height-pad_b+18}" text-anchor="middle" font-size="11" fill="{_AXIS}">{esc(cat)}</text>')
    if y_label:
        parts.append(f'<text x="14" y="{pad_t+plot_h/2}" text-anchor="middle" font-size="12" fill="{_AXIS}" transform="rotate(-90 14 {pad_t+plot_h/2})">{esc(y_label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def grouped_bar_chart(
    categories: Sequence[str],
    series: dict[str, Sequence[Optional[float]]],
    width: int = 720,
    height: int = 340,
    fmt: str = "{:,.0f}",
) -> str:
    names = list(series)
    if not names or not categories:
        return _empty("No data for a grouped bar chart", width, height)
    pad_l, pad_r, pad_t, pad_b = 64, 120, 24, 56
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    allvals = [v for vals in series.values() for v in vals if v is not None]
    vmax = max(allvals) if allvals else 1
    n = len(categories)
    gcount = len(names)
    group_w = plot_w / n
    bw = group_w * 0.8 / gcount

    def sy(v: float) -> float:
        return pad_t + plot_h * (1 - v / vmax)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">']
    for k in range(5):
        yv = vmax * k / 4
        y = sy(yv)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="{_GRID}"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="{_AXIS}">{esc(_fmt(yv, fmt))}</text>')
    for i, cat in enumerate(categories):
        base_x = pad_l + group_w * i + group_w * 0.1
        for j, name in enumerate(names):
            v = series[name][i] if i < len(series[name]) else None
            if v is None:
                continue
            x = base_x + bw * j
            y = sy(v)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{pad_t+plot_h-y:.1f}" fill="{PALETTE[j%len(PALETTE)]}" rx="2"><title>{esc(name)} — {esc(cat)}: {esc(_fmt(v, fmt))}</title></rect>')
        parts.append(f'<text x="{base_x+group_w*0.4:.1f}" y="{height-pad_b+18}" text-anchor="middle" font-size="11" fill="{_AXIS}">{esc(cat)}</text>')
    # legend
    for j, name in enumerate(names):
        ly = pad_t + j * 20
        parts.append(f'<rect x="{width-pad_r+8}" y="{ly}" width="12" height="12" fill="{PALETTE[j%len(PALETTE)]}"/>')
        parts.append(f'<text x="{width-pad_r+26}" y="{ly+11}" font-size="11" fill="{_AXIS}">{esc(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbar_chart(
    categories: Sequence[str],
    values: Sequence[Optional[float]],
    width: int = 720,
    row_h: int = 26,
    fmt: str = "{:,.0f}",
    color: str = PALETTE[0],
) -> str:
    pairs = [(c, v) for c, v in zip(categories, values) if v is not None]
    if not pairs:
        return _empty("No data for a bar chart", width, 120)
    pad_l, pad_r, pad_t, pad_b = 180, 70, 12, 12
    height = pad_t + pad_b + row_h * len(pairs)
    plot_w = width - pad_l - pad_r
    vmax = max(v for _, v in pairs) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">']
    for i, (cat, v) in enumerate(pairs):
        y = pad_t + i * row_h
        w = plot_w * v / vmax
        parts.append(f'<text x="{pad_l-10}" y="{y+row_h*0.65:.1f}" text-anchor="end" font-size="12" fill="{_AXIS}">{esc(cat)}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y+4}" width="{w:.1f}" height="{row_h-10}" fill="{color}" rx="2"><title>{esc(cat)}: {esc(_fmt(v, fmt))}</title></rect>')
        parts.append(f'<text x="{pad_l+w+6:.1f}" y="{y+row_h*0.65:.1f}" font-size="12" fill="{_AXIS}">{esc(_fmt(v, fmt))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def donut_chart(
    segments: Sequence[tuple[str, Optional[float]]],
    width: int = 360,
    height: int = 280,
    fmt: str = "{:.1f}%",
) -> str:
    segs = [(label, v) for label, v in segments if v is not None]
    total = sum(v for _, v in segs)
    if not segs or total <= 0:
        return _empty("No data for a donut chart", width, height)
    cx, cy, r, rin = width * 0.36, height / 2, min(width, height) * 0.34, min(width, height) * 0.19
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" style="{_FONT}">']
    angle = -math.pi / 2
    for i, (label, v) in enumerate(segs):
        frac = v / total
        end = angle + frac * 2 * math.pi
        large = 1 if frac > 0.5 else 0
        x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        xi2, yi2 = cx + rin * math.cos(end), cy + rin * math.sin(end)
        xi1, yi1 = cx + rin * math.cos(angle), cy + rin * math.sin(angle)
        d = (
            f"M{x1:.1f},{y1:.1f} A{r:.1f},{r:.1f} 0 {large} 1 {x2:.1f},{y2:.1f} "
            f"L{xi2:.1f},{yi2:.1f} A{rin:.1f},{rin:.1f} 0 {large} 0 {xi1:.1f},{yi1:.1f} Z"
        )
        parts.append(f'<path d="{d}" fill="{PALETTE[i%len(PALETTE)]}"><title>{esc(label)}: {esc(_fmt(v, fmt))}</title></path>')
        angle = end
    # legend
    for i, (label, v) in enumerate(segs):
        ly = 30 + i * 22
        parts.append(f'<rect x="{width*0.7:.0f}" y="{ly}" width="12" height="12" fill="{PALETTE[i%len(PALETTE)]}"/>')
        parts.append(f'<text x="{width*0.7+18:.0f}" y="{ly+11}" font-size="12" fill="{_AXIS}">{esc(label)} ({esc(_fmt(v, fmt))})</text>')
    parts.append("</svg>")
    return "".join(parts)
