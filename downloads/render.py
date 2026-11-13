"""Render the downloads card as a static SVG in the profile identity: outlined text, no scripts, no external fonts."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from visuals import document, frame, px, tokens
from visuals.type import Typesetter

# A thin strip at the foot of the profile, in the profile identity (grond.st field notes): a hairline frame
# on GitHub's canvas, a mono eyebrow for the title and the date, Hanken Grotesk with tabular figures for numbers.
PAD = 16
TITLE_Y = 26  # the title and "updated" share this baseline
HEADLINE_Y = 60
CAPTION_Y = 77
BAR_Y = 90
BAR_HEIGHT = 6
BAR_GAP = 2
LEGEND_Y = 118  # label baseline of the first legend row
VALUE_DY = 18  # from a legend label to its total and 30-day number, side by side
DELTA_DX = 44  # from a legend total to its 30-day number
ROW_STEP = 44  # from one legend row to the next
BOTTOM = 14
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
NUMBERS = ("tnum",)  # tabular figures, so the columns of numbers line up

# Card variants, picked by the README's <picture> from the width of GitHub's README column. Each is drawn
# close to the width it is shown at, so the text stays readable: file suffix -> (registries shown on their
# own, legend columns, drawn width). The rest fold into Others; None columns means one row.
VARIANTS = {
    "": (None, None, 800),  # column 760px and wider: every registry in one row
    "-md": (5, None, 640),  # column 600 to 759px: top 5 and Others
    "-sm": (4, None, 540),  # column 460 to 599px (up to 670px on some screens): top 4 and Others
    "-xs": (4, 3, 360),  # column under 460px: top 4 and Others in two rows
}

# Each registry keeps one slot of the profile's data palette (grond.st data-1 to data-7), in the order the
# registries usually sort by size, so neighbours in the bar are neighbouring slots of the validated palette.
SLOTS = {"pypi": 1, "crates": 2, "npm": 3, "docker": 4, "nuget": 5, "github": 6, "pubdev": 7}


def palette(theme: str) -> dict[str, str]:
    """Text, rule and registry colours for one theme, from the grond.st tokens. Others is the muted text grey."""
    t = tokens("grond-st")[theme]
    return {
        "text": t["foreground"],
        "muted": t["muted-foreground"],
        "rule": t["border-strong"],
        "radius": t["radius-box"],
        "others": t["muted-foreground"],
    } | {key: t[f"data-{slot}"] for key, slot in SLOTS.items()}


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
    colors = palette(theme)
    ts = Typesetter()
    entries = fold_others(stats, shown)
    total = _known_sum(s.total for s in stats)
    last30 = _known_sum(s.last30 for s in stats)
    columns = columns or max(1, len(entries))
    rows = max(1, math.ceil(len(entries) / columns))
    column = (width - 2 * PAD) / columns
    height = LEGEND_Y + (rows - 1) * ROW_STEP + VALUE_DY + BOTTOM
    ink, muted = colors["text"], colors["muted"]
    stamp = f"updated {updated.day} {MONTHS[updated.month - 1]}"
    body = "".join(
        [
            frame(width, height, colors["rule"], px(colors["radius"])),
            ts.text("plex-mono", "PACKAGE DOWNLOADS", PAD, TITLE_Y, 11, muted, tracking=1.4, role="title"),
            ts.text("plex-mono", stamp.upper(), width - PAD, TITLE_Y, 11, muted, "end", 1.4, role="foot"),
            ts.text("hanken-600", format_total(total), PAD, HEADLINE_Y, 26, ink, features=NUMBERS, role="big"),
            ts.text("hanken", "all time", PAD, CAPTION_Y, 12, muted, role="caption"),
            # The 30-day headline lines up with the second legend column.
            ts.text("hanken-600", format_delta(last30), PAD + column, HEADLINE_Y, 20, ink, features=NUMBERS, role="mid"),
            ts.text("hanken", "last 30 days", PAD + column, CAPTION_Y, 12, muted, role="caption"),
            _bar(entries, colors, width),
            _legend(entries, colors, columns, column, ts),
        ]
    )
    return document(width, height, _describe(stats, total, last30), body, ts.defs())


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
        f'<clipPath id="bar"><rect x="{PAD}" y="{BAR_Y}" width="{bar_width}" height="{BAR_HEIGHT}" '
        f'rx="{px(colors["radius"]):g}"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )


def _legend(entries: list[RegistryStat], colors: dict[str, str], columns: int, column: float, ts: Typesetter) -> str:
    """Rows of evenly spaced columns, filled left to right: a dot and label, then the total and 30-day number."""
    items = []
    for i, s in enumerate(entries):
        row, col = divmod(i, columns)
        x, y = PAD + col * column, LEGEND_Y + row * ROW_STEP
        items.append(
            f'<circle cx="{x + 4:.2f}" cy="{y - 4}" r="4" fill="{colors[s.key]}"/>'
            + ts.text("hanken", s.label, x + 14, y, 12, colors["muted"], role="label")
            + ts.text("hanken-600", format_total(s.total), x + 14, y + VALUE_DY, 13, colors["text"], features=NUMBERS, role="value")
            + ts.text("hanken", format_delta(s.last30), x + 14 + DELTA_DX, y + VALUE_DY, 12, colors["muted"], features=NUMBERS, role="delta")
        )
    return "".join(items)
