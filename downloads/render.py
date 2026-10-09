"""Render the downloads card as a static SVG: no scripts and no external fonts, as GitHub's image proxy requires."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

PAD = 24
FOOT_Y = 30
HEADLINE_Y = 48
CAPTION_Y = 68
BAR_Y = 90
BAR_HEIGHT = 8
BAR_GAP = 2
LEGEND_Y = 126  # label baseline of the first legend row
VALUE_DY = 20  # from a legend label to its all-time number
DELTA_DY = 38  # from a legend label to its 30-day number
ROW_STEP = 62  # from one legend row to the next
BOTTOM = 20
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Card variants, picked by the README's <picture> from the width of GitHub's README column. Each is drawn
# close to the width it is shown at, so the text stays readable: file suffix -> (registries shown on their
# own, legend columns, drawn width). The rest fold into Others; None columns means one row.
VARIANTS = {
    "": (None, None, 800),  # column 760px and wider: every registry in one row
    "-md": (5, None, 640),  # column 600 to 759px: top 5 and Others
    "-sm": (4, None, 540),  # column 460 to 599px (up to 670px on some screens): top 4 and Others
    "-xs": (4, 3, 340),  # column under 460px: top 4 and Others in two rows
}

# GitHub's code-block surface and text colours, so the card sits in the README like the projects box.
THEMES = {
    "light": {"bg": "#f6f8fa", "text": "#1f2328", "muted": "#59636e"},
    "dark": {"bg": "#151b23", "text": "#f0f6fc", "muted": "#9198a1"},
}

# Validated categorical palette slots per registry. Registries are sorted by size, so the colours were checked
# for every pair that can realistically end up side by side: PyPI first, crates.io and npm in either order,
# then Docker, then NuGet and GitHub in either order. pub.dev has no all-time number and never gets a bar
# segment. Others is a neutral grey, checked against every registry that can come before it.
COLORS = {
    "light": {
        "pypi": "#2a78d6", "crates": "#eda100", "npm": "#e87ba4", "docker": "#008300",
        "nuget": "#4a3aa7", "github": "#e34948", "pubdev": "#1baf7a",
    },
    "dark": {
        "pypi": "#3987e5", "crates": "#c98500", "npm": "#d55181", "docker": "#008300",
        "nuget": "#9085e9", "github": "#e66767", "pubdev": "#199e70",
    },
}
OTHERS = {"light": "#6e7781", "dark": "#adb5bf"}


@dataclass(frozen=True)
class RegistryStat:
    key: str
    label: str
    total: int | None  # None when the registry has no all-time number (pub.dev)
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


def format_total(n: int | None) -> str:
    return "n/a" if n is None else format_count(n)


def format_delta(n: int | None) -> str:
    return "n/a" if n is None else f"+{format_count(n)}"


def largest_first(stats: list[RegistryStat]) -> list[RegistryStat]:
    """Sorted by all-time downloads; unknown totals go last and ties keep the given order."""
    return sorted(stats, key=lambda s: (s.total is None, -(s.total or 0)))


def fold_others(stats: list[RegistryStat], shown: int | None) -> list[RegistryStat]:
    """The `shown` largest registries, then one Others entry for the rest (only when two or more are left)."""
    ordered = largest_first(stats)
    if shown is None or len(ordered) - shown < 2:
        return ordered
    rest = ordered[shown:]
    others = RegistryStat("others", "Others", _known_sum(s.total for s in rest), _known_sum(s.last30 for s in rest))
    return ordered[:shown] + [others]


def render_card(
    stats: list[RegistryStat],
    updated: date,
    theme: str,
    shown: int | None = None,
    columns: int | None = None,
    width: int = 800,
) -> str:
    """One card variant for one theme ("light" or "dark"), registries largest first. See VARIANTS."""
    palette = THEMES[theme]
    colors = COLORS[theme] | {"others": OTHERS[theme]}
    entries = fold_others(stats, shown)
    total = _known_sum(s.total for s in stats)
    last30 = _known_sum(s.last30 for s in stats)
    columns = columns or max(1, len(entries))
    rows = max(1, math.ceil(len(entries) / columns))
    column = (width - 2 * PAD) / columns
    height = LEGEND_Y + (rows - 1) * ROW_STEP + DELTA_DY + BOTTOM
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
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
            f'<rect width="{width}" height="{height}" rx="6" fill="{palette["bg"]}"/>',
            f'<text x="{PAD}" y="{HEADLINE_Y}" class="big">{format_total(total)}</text>',
            f'<text x="{PAD}" y="{CAPTION_Y}" class="caption">all time</text>',
            # The 30-day headline lines up with the second legend column.
            f'<text x="{PAD + column:.2f}" y="{HEADLINE_Y}" class="mid">{format_delta(last30)}</text>',
            f'<text x="{PAD + column:.2f}" y="{CAPTION_Y}" class="caption">last 30 days</text>',
            f'<text x="{width - PAD}" y="{FOOT_Y}" class="foot" text-anchor="end">'
            f"updated {updated.day} {MONTHS[updated.month - 1]}</text>",
            _bar(entries, colors, width),
            _legend(entries, colors, columns, column),
            "</svg>",
            "",
        ]
    )


def _known_sum(values: Iterable[int | None]) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _describe(stats: list[RegistryStat], total: int | None, last30: int | None) -> str:
    def words(n: int | None) -> str:
        return "unknown" if n is None else f"{n:,}"

    parts = [
        f"{s.label} {words(s.total)} all time, {words(s.last30)} in the last 30 days" for s in largest_first(stats)
    ]
    return f"Package downloads: {words(total)} all time, {words(last30)} in the last 30 days. " + "; ".join(parts) + "."


def _bar(entries: list[RegistryStat], colors: dict[str, str], width: int) -> str:
    shown = [s for s in entries if s.total]
    total = sum(s.total for s in shown)
    if not total:
        return ""
    bar_width = width - 2 * PAD
    usable = bar_width - BAR_GAP * (len(shown) - 1)
    segments, x = [], float(PAD)
    for s in shown:
        w = usable * s.total / total
        segments.append(
            f'<rect x="{x:.2f}" y="{BAR_Y}" width="{w:.2f}" height="{BAR_HEIGHT}" fill="{colors[s.key]}"/>'
        )
        x += w + BAR_GAP
    return (
        f'<clipPath id="bar"><rect x="{PAD}" y="{BAR_Y}" width="{bar_width}" height="{BAR_HEIGHT}" rx="4"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )


def _legend(entries: list[RegistryStat], colors: dict[str, str], columns: int, column: float) -> str:
    """Rows of evenly spaced columns, filled left to right: a dot and label, the total, then the 30-day number."""
    items = []
    for i, s in enumerate(entries):
        row, col = divmod(i, columns)
        x, y = PAD + col * column, LEGEND_Y + row * ROW_STEP
        items.append(
            f'<circle cx="{x + 5:.2f}" cy="{y - 4}" r="5" fill="{colors[s.key]}"/>'
            f'<text x="{x + 16:.2f}" y="{y}" class="label">{escape(s.label)}</text>'
            f'<text x="{x + 16:.2f}" y="{y + VALUE_DY}" class="value">{format_total(s.total)}</text>'
            f'<text x="{x + 16:.2f}" y="{y + DELTA_DY}" class="delta">{format_delta(s.last30)}</text>'
        )
    return "".join(items)
