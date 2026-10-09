"""Render the downloads card as a static SVG: no scripts and no external fonts, as GitHub's image proxy requires."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

WIDTH = 495
PAD = 25
BAR_Y = 118
BAR_HEIGHT = 8
BAR_GAP = 2
LEGEND_Y = 154
ROW_HEIGHT = 22
COLUMN_X = (25, 260)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# github-readme-stats' default and github_dark themes; muted text is GitHub's own fg.muted.
THEMES = {
    "light": {"bg": "#ffffff", "border": "#e4e2e2", "title": "#2f80ed", "text": "#434d58", "muted": "#656d76"},
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#58a6ff", "text": "#c9d1d9", "muted": "#8b949e"},
}

# Validated categorical palette slots per registry (see the spec's "Registry colours").
COLORS = {
    "light": {"pypi": "#2a78d6", "crates": "#eda100", "docker": "#1baf7a", "nuget": "#4a3aa7", "npm": "#e34948"},
    "dark": {"pypi": "#3987e5", "crates": "#c98500", "docker": "#199e70", "nuget": "#9085e9", "npm": "#e66767"},
}


@dataclass(frozen=True)
class RegistryStat:
    key: str
    label: str
    total: int
    last30: int | None


def format_count(n: int) -> str:
    """Three significant digits with a K/M/B suffix: 999, 1K, 1.23K, 48.3K, 812K, 1.24M."""
    if n < 1000:
        return str(n)
    for suffix, scale in (("K", 1e3), ("M", 1e6), ("B", 1e9)):
        value = n / scale
        decimals = 2 if value < 10 else 1 if value < 100 else 0
        rounded = round(value, decimals)
        if rounded < 1000 or suffix == "B":
            text = f"{rounded:.{decimals}f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return text + suffix


def format_delta(n: int | None) -> str:
    return "n/a" if n is None else f"+{format_count(n)}"


def render_card(stats: list[RegistryStat], updated: date, theme: str) -> str:
    """The card for one theme ("light" or "dark"). Registries are drawn in the order given."""
    palette, colors = THEMES[theme], COLORS[theme]
    total = sum(s.total for s in stats)
    known = [s.last30 for s in stats if s.last30 is not None]
    last30 = sum(known) if known else None
    rows = max(1, math.ceil(len(stats) / 2))
    footer_y = LEGEND_Y + (rows - 1) * ROW_HEIGHT + 28
    height = footer_y + 14
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(_describe(stats, total, last30))}</title>',
            "<style>",
            f"text {{ font-family: 'Segoe UI', Ubuntu, sans-serif; fill: {palette['text']}; }}",
            f".title {{ font-size: 18px; font-weight: 600; fill: {palette['title']}; }}",
            ".big { font-size: 32px; font-weight: 700; }",
            ".mid { font-size: 24px; font-weight: 600; }",
            ".caption, .label, .value, .delta { font-size: 12px; }",
            ".value { font-weight: 600; }",
            ".foot { font-size: 10px; }",
            f".caption, .delta, .foot {{ fill: {palette['muted']}; }}",
            "</style>",
            f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="4.5" '
            f'fill="{palette["bg"]}" stroke="{palette["border"]}"/>',
            f'<text x="{PAD}" y="35" class="title">Package downloads</text>',
            f'<text x="{PAD}" y="80" class="big">{format_count(total)}</text>',
            f'<text x="{PAD}" y="99" class="caption">all time</text>',
            f'<text x="250" y="80" class="mid">{format_delta(last30)}</text>',
            '<text x="250" y="99" class="caption">last 30 days</text>',
            _bar(stats, colors),
            _legend(stats, colors, rows),
            f'<text x="{WIDTH - PAD}" y="{footer_y}" class="foot" text-anchor="end">'
            f"updated {updated.day} {MONTHS[updated.month - 1]}</text>",
            "</svg>",
            "",
        ]
    )


def _describe(stats: list[RegistryStat], total: int, last30: int | None) -> str:
    def words(n: int | None) -> str:
        return "unknown" if n is None else f"{n:,}"

    parts = [f"{s.label} {s.total:,} all time, {words(s.last30)} in the last 30 days" for s in stats]
    return f"Package downloads: {total:,} all time, {words(last30)} in the last 30 days. " + "; ".join(parts) + "."


def _bar(stats: list[RegistryStat], colors: dict[str, str]) -> str:
    shown = [s for s in stats if s.total > 0]
    total = sum(s.total for s in shown)
    if not total:
        return ""
    width = WIDTH - 2 * PAD
    usable = width - BAR_GAP * (len(shown) - 1)
    segments, x = [], float(PAD)
    for s in shown:
        w = usable * s.total / total
        segments.append(
            f'<rect x="{x:.2f}" y="{BAR_Y}" width="{w:.2f}" height="{BAR_HEIGHT}" fill="{colors[s.key]}"/>'
        )
        x += w + BAR_GAP
    return (
        f'<clipPath id="bar"><rect x="{PAD}" y="{BAR_Y}" width="{width}" height="{BAR_HEIGHT}" rx="4"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )


def _legend(stats: list[RegistryStat], colors: dict[str, str], rows: int) -> str:
    items = []
    for i, s in enumerate(stats):
        column, row = divmod(i, rows)
        x, y = COLUMN_X[column], LEGEND_Y + row * ROW_HEIGHT
        items.append(
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{colors[s.key]}"/>'
            f'<text x="{x + 16}" y="{y}" class="label">{escape(s.label)}</text>'
            f'<text x="{x + 150}" y="{y}" class="value" text-anchor="end">{format_count(s.total)}</text>'
            f'<text x="{x + 205}" y="{y}" class="delta" text-anchor="end">{format_delta(s.last30)}</text>'
        )
    return "".join(items)
