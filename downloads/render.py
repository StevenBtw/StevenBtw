"""Render the downloads card as a static SVG: no scripts and no external fonts, as GitHub's image proxy requires."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

# Drawn at the width of GitHub's profile README column; the README scales it to 100% of the column.
WIDTH = 800
PAD = 24
FOOT_Y = 30
HEADLINE_Y = 48
CAPTION_Y = 68
BAR_Y = 90
BAR_HEIGHT = 8
BAR_GAP = 2
LABEL_Y = 126
VALUE_Y = 148
HEIGHT = 172
DELTA_OFFSET = 56  # from a legend value's start to its 30-day number
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# GitHub's code-block surface and text colours, so the card sits in the README like the projects box.
THEMES = {
    "light": {"bg": "#f6f8fa", "text": "#1f2328", "muted": "#59636e"},
    "dark": {"bg": "#151b23", "text": "#f0f6fc", "muted": "#9198a1"},
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
    column = _column_width(stats)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(_describe(stats, total, last30))}</title>',
            "<style>",
            "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, "
            f"sans-serif; fill: {palette['text']}; }}",
            ".big { font-size: 32px; font-weight: 700; }",
            ".mid { font-size: 24px; font-weight: 600; }",
            ".label, .value { font-size: 13px; }",
            ".value { font-weight: 600; }",
            ".caption, .delta, .foot { font-size: 12px; }",
            f".caption, .delta, .foot {{ fill: {palette['muted']}; }}",
            "</style>",
            f'<rect width="{WIDTH}" height="{HEIGHT}" rx="6" fill="{palette["bg"]}"/>',
            f'<text x="{PAD}" y="{HEADLINE_Y}" class="big">{format_count(total)}</text>',
            f'<text x="{PAD}" y="{CAPTION_Y}" class="caption">all time</text>',
            # The 30-day headline lines up with the second legend column.
            f'<text x="{PAD + column:.2f}" y="{HEADLINE_Y}" class="mid">{format_delta(last30)}</text>',
            f'<text x="{PAD + column:.2f}" y="{CAPTION_Y}" class="caption">last 30 days</text>',
            f'<text x="{WIDTH - PAD}" y="{FOOT_Y}" class="foot" text-anchor="end">'
            f"updated {updated.day} {MONTHS[updated.month - 1]}</text>",
            _bar(stats, colors),
            _legend(stats, colors, column),
            "</svg>",
            "",
        ]
    )


def _column_width(stats: list[RegistryStat]) -> float:
    return (WIDTH - 2 * PAD) / max(1, len(stats))


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


def _legend(stats: list[RegistryStat], colors: dict[str, str], column: float) -> str:
    """One row, one evenly spaced column per registry: a dot and label, then the total and 30-day number."""
    items = []
    for i, s in enumerate(stats):
        x = PAD + i * column
        items.append(
            f'<circle cx="{x + 5:.2f}" cy="{LABEL_Y - 4}" r="5" fill="{colors[s.key]}"/>'
            f'<text x="{x + 16:.2f}" y="{LABEL_Y}" class="label">{escape(s.label)}</text>'
            f'<text x="{x + 16:.2f}" y="{VALUE_Y}" class="value">{format_count(s.total)}</text>'
            f'<text x="{x + 16 + DELTA_OFFSET:.2f}" y="{VALUE_Y}" class="delta">{format_delta(s.last30)}</text>'
        )
    return "".join(items)
