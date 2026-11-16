"""Render the downloads box and its registry chips as static SVGs in the profile identity (outlined text).

The box follows a project banner's layout without a mark: eyebrow, the 30-day total in the name slot, a tagline
and a thin stacked bar. The legend sits outside the box as chips, one per registry, like the repo chips under a
banner: each chip is labelled with its name and value, so no registry is told apart by colour alone.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from visuals import document, frame, px, tokens
from visuals.projects import CHIP_GAP, CHIP_HEIGHT
from visuals.type import Typesetter, measure, wrap

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
NUMBERS = ("tnum",)  # tabular figures, so numbers keep their width from week to week
EYEBROW = "PACKAGE DOWNLOADS · LAST 30 DAYS"
NOTE = "PyPI counted without mirrors, from pypistats.org."
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}

# Drawn width per variant, as the project banners: the README picks one by column width.
VARIANTS = {"": 800, "-narrow": 400}
BAR_HEIGHT = 8
BAR_GAP = 2  # unfilled: GitHub's page shows through, since the box has no fill
MIN_SEGMENT = 2.0

# Each registry keeps one slot of the profile's data palette (grond.st data-1 to data-7). The bar and the chips
# always draw in this order, so colour and position follow a registry from week to week and the adjacent pairs
# drawn are exactly the ones the palette was validated for.
SLOTS = {"pypi": 1, "crates": 2, "npm": 3, "docker": 4, "nuget": 5, "github": 6, "pubdev": 7}


def palette(theme: str) -> dict[str, str]:
    """Text, rule and registry colours for one theme, from the grond.st tokens."""
    t = tokens("grond-st")[theme]
    return {
        "text": t["foreground"],
        "muted": t["muted-foreground"],
        "rule": t["border-strong"],
        "radius": t["radius-box"],
        "control-radius": t["radius-control"],
    } | {key: t[f"data-{slot}"] for key, slot in SLOTS.items()}


@dataclass(frozen=True)
class RegistryStat:
    key: str
    label: str
    total: int | None  # all time; kept in the history, not drawn
    last30: int | None  # None while a snapshot-based registry has no 30-day number yet


def format_count(n: int) -> str:
    """One rule for every value: whole numbers under 1,000, then one decimal with K, M or B (a trailing .0 is
    dropped): 773, 1K, 1.2K, 8.8K, 46.5K, 812K, 1.2M. A value that rounds up to 1,000 moves to the next unit."""
    if n < 1000:
        return str(n)
    for suffix, scale in (("K", 1e3), ("M", 1e6), ("B", 1e9)):
        rounded = round(n / scale, 1)
        if rounded < 1000 or suffix == "B":
            return f"{rounded:.1f}".removesuffix(".0") + suffix
    raise AssertionError("unreachable")


def box_alt(stats: list[RegistryStat]) -> str:
    """The box's alt text, from the same numbers as the image."""
    entries = in_slot_order(stats)
    first, note = tagline(entries)
    across = first.removesuffix(".").replace("Across", "across", 1)
    return f"Package downloads in the last 30 days: {format_value(_known_sum(s.last30 for s in entries))} {across}. {note}".strip()


def chip_alt(stat: RegistryStat) -> str:
    if stat.last30 is None:
        return f"{stat.label}: no 30-day number yet"
    return f"{stat.label}: {format_count(stat.last30)} downloads in the last 30 days"


def format_value(n: int | None) -> str:
    return "n/a" if n is None else format_count(n)


def in_slot_order(stats: Iterable[RegistryStat]) -> list[RegistryStat]:
    return sorted(stats, key=lambda s: SLOTS[s.key])


def tagline(stats: list[RegistryStat]) -> tuple[str, str]:
    count = len(stats)
    first = f"Across {WORDS.get(count, str(count))} registr{'y' if count == 1 else 'ies'}."
    return first, NOTE if any(s.key == "pypi" for s in stats) else ""


def render_card(stats: list[RegistryStat], updated: date, theme: str, width: int = 800) -> str:
    """The downloads box for one theme ("light" or "dark") at one drawn width. See VARIANTS."""
    colors = palette(theme)
    ink, muted = colors["text"], colors["muted"]
    ts = Typesetter()
    wide = width >= 600
    pad = 24 if wide else 20
    body_size = 16 if wide else 15
    entries = in_slot_order(stats)
    last30 = _known_sum(s.last30 for s in entries)
    stamp = f"UPDATED {updated.day} {MONTHS[updated.month - 1].upper()}"

    eyebrow_y = pad + 12
    name_y = eyebrow_y + 12 + 32
    parts = [ts.text("plex-mono", EYEBROW, pad, eyebrow_y, 11, muted, tracking=1.4, role="title")]
    stamp_on_top = measure("plex-mono", EYEBROW, 11, 1.4) + 24 + measure("plex-mono", stamp, 11, 1.4) <= width - 2 * pad
    if stamp_on_top:
        parts.append(ts.text("plex-mono", stamp, width - pad, eyebrow_y, 11, muted, "end", 1.4, role="foot"))
    parts.append(ts.text("hanken-600", format_value(last30), pad, name_y, 32, ink, features=NUMBERS, role="big"))

    # The tagline wraps after its first sentence when it does not fit on one line.
    first, note = tagline(entries)
    whole = f"{first} {note}".strip()
    avail = width - 2 * pad
    if measure("hanken", whole, body_size) <= avail:
        lines = [whole]
    else:
        lines = wrap("hanken", first, body_size, avail) + (wrap("hanken", note, body_size, avail) if note else [])
    y = name_y + 28
    for line in lines:
        parts.append(ts.text("hanken", line, pad, y, body_size, muted, role="tagline"))
        y += body_size * 1.5
    bar_y = y - body_size * 1.5 + 18
    parts.append(_bar(entries, colors, pad, bar_y, width - 2 * pad))
    height = bar_y + BAR_HEIGHT + pad
    if not stamp_on_top:  # narrow: the date moves under the bar
        parts.append(ts.text("plex-mono", stamp, pad, height + 2, 11, muted, tracking=1.4, role="foot"))
        height += 2 + pad - 6
    height = round(height)
    parts.insert(0, frame(width, height, colors["rule"], px(colors["radius"])))
    return document(width, height, describe(entries, last30), "".join(parts), ts.defs())


def render_chip(stat: RegistryStat, theme: str) -> str:
    """A registry's legend chip: a dot in its data slot (the only coloured part), its name and 30-day value in
    text colours with tabular figures, inside the profile's control outline."""
    colors = palette(theme)
    ts = Typesetter()
    size, inset, dot = 12.5, 11, 4
    value = format_value(stat.last30)
    label_x = inset + 2 * dot + 7
    value_x = label_x + measure("hanken", stat.label, size) + 7
    box = round(value_x + measure("hanken-600", value, size, features=NUMBERS) + inset)
    body = (
        f'<rect x="0.5" y="0.5" width="{box - 1}" height="{CHIP_HEIGHT - 1}" rx="{px(colors["control-radius"]):g}" '
        f'fill="none" stroke="{colors["rule"]}" stroke-width="1"/>'
        f'<circle cx="{inset + dot}" cy="{CHIP_HEIGHT / 2:g}" r="{dot}" fill="{colors[stat.key]}"/>'
        + ts.text("hanken", stat.label, label_x, 18.5, size, colors["text"], role="label")
        + ts.text("hanken-600", value, value_x, 18.5, size, colors["text"], features=NUMBERS, role="value")
    )
    title = f"{stat.label}: {_words(stat.last30)} downloads in the last 30 days"
    return document(box + CHIP_GAP, CHIP_HEIGHT + CHIP_GAP, title, body, ts.defs())


def describe(stats: list[RegistryStat], last30: int | None) -> str:
    parts = [
        f"{s.label} {_words(s.last30)}{' (without mirrors)' if s.key == 'pypi' else ''}" for s in in_slot_order(stats)
    ]
    return f"Package downloads in the last 30 days: {_words(last30)}. " + "; ".join(parts) + "."


def _words(n: int | None) -> str:
    return "unknown" if n is None else f"{n:,}"


def _known_sum(values: Iterable[int | None]) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def segment_widths(values: list[int], usable: float) -> list[float]:
    """True proportions of `usable`, except that no segment is drawn narrower than MIN_SEGMENT; the others
    shrink in proportion to make room."""
    total = sum(values)
    widths = [usable * v / total for v in values]
    small = [w < MIN_SEGMENT for w in widths]
    if any(small):
        rest = usable - MIN_SEGMENT * sum(small)
        large_total = sum(v for v, s in zip(values, small) if not s)
        widths = [MIN_SEGMENT if s else rest * v / large_total for v, s in zip(values, small)]
    return widths


def _bar(entries: list[RegistryStat], colors: dict[str, str], x0: float, y: float, width: float) -> str:
    """Segments in slot order with unfilled gaps; only the bar's two outer ends are rounded."""
    shown = [s for s in entries if s.last30]
    if not shown:
        return ""
    usable = width - BAR_GAP * (len(shown) - 1)
    segments, x = [], x0
    for s, w in zip(shown, segment_widths([s.last30 for s in shown], usable)):
        segments.append(
            f'<rect x="{x:.2f}" y="{y:g}" width="{w:.2f}" height="{BAR_HEIGHT}" fill="{colors[s.key]}"/>'
        )
        x += w + BAR_GAP
    return (
        f'<clipPath id="bar"><rect x="{x0:g}" y="{y:g}" width="{width:g}" height="{BAR_HEIGHT}" '
        f'rx="{px(colors["radius"]):g}"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )
