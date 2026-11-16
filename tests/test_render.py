import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from downloads.render import (
    BAR_GAP,
    box_alt,
    chip_alt,
    BAR_HEIGHT,
    EYEBROW,
    MIN_SEGMENT,
    NOTE,
    SLOTS,
    VARIANTS,
    RegistryStat,
    describe,
    format_count,
    format_value,
    palette,
    render_card,
    render_chip,
    segment_widths,
)
from visuals import tokens
from visuals.projects import CHIP_GAP, CHIP_HEIGHT

SVG = "{http://www.w3.org/2000/svg}"
DAY = date(2026, 11, 16)

STATS = [  # in fetch order, the way collect() returns them
    RegistryStat("pypi", "PyPI", 737_301, 46_451),
    RegistryStat("crates", "crates.io", 99_123, 25_761),
    RegistryStat("docker", "Docker", 10_980, 2_700),
    RegistryStat("nuget", "NuGet", 3_549, 773),
    RegistryStat("npm", "npm", 59_771, 8_793),
    RegistryStat("github", "GitHub", 1_285, 507),
    RegistryStat("pubdev", "pub.dev", None, 1_155),
]
SLOT_ORDER = ["pypi", "crates", "npm", "docker", "nuget", "github", "pubdev"]
SEGMENT = r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="\d+" fill="(#[0-9a-f]{6})"/>'


def runs(svg, role=None):
    return [
        g
        for g in ET.fromstring(svg).iter(f"{SVG}g")
        if g.get("data-text") is not None and role in (None, g.get("class"))
    ]


def texts(svg, role=None):
    return [g.get("data-text") for g in runs(svg, role)]


def bar(svg):
    return re.findall(SEGMENT, svg)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0"),
        (773, "773"),
        (999, "999"),  # under 1,000: a whole number
        (1_000, "1K"),  # from 1,000: thousands with one decimal, a trailing .0 dropped
        (1_160, "1.2K"),
        (8_790, "8.8K"),
        (46_451, "46.5K"),
        (99_999, "100K"),
        (812_000, "812K"),
        (999_499, "999.5K"),
        (999_950, "1M"),  # rounds up to 1,000K, so it moves to the next unit
        (1_240_000, "1.2M"),  # millions with one decimal
        (12_345_678, "12.3M"),
        (2_500_000_000, "2.5B"),
    ],
)
def test_format_count_uses_one_rule_for_every_value(n, expected):
    assert format_count(n) == expected


def test_format_value():
    assert format_value(46_451) == "46.5K"
    assert format_value(None) == "n/a"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", VARIANTS.values())
def test_box_leads_with_the_30_day_total(theme, width):
    svg = render_card(STATS, DAY, theme, width)
    assert ET.fromstring(svg).get("width") == str(width)
    assert texts(svg, "title") == [EYEBROW]
    assert texts(svg, "big") == ["86.1K"]  # 86,140: every registry has a 30-day number
    assert texts(svg, "foot") == ["UPDATED 16 NOV"]
    assert "n/a" not in texts(svg)  # no all-time column, so no hole in it


def test_box_never_shows_all_time_numbers():
    shown = texts(render_card(STATS, DAY, "light"))
    for all_time in ("737K", "99.1K", "11K", "3.55K", "59.8K", "1.29K"):
        assert all_time not in shown


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_box_is_a_hairline_frame_in_the_profile_tokens(theme):
    t = tokens("grond-st")[theme]
    outline = ET.fromstring(render_card(STATS, DAY, theme)).find(f"{SVG}rect")
    assert outline.get("fill") == "none"
    assert outline.get("stroke") == t["border-strong"] and outline.get("stroke-width") == "1"
    assert outline.get("rx") == t["radius-box"].removesuffix("px")


def test_wide_tagline_names_the_registries_and_the_pypi_source_on_one_line():
    assert texts(render_card(STATS, DAY, "light", 800), "tagline") == [f"Across seven registries. {NOTE}"]


def test_narrow_tagline_wraps_after_its_first_sentence():
    lines = texts(render_card(STATS, DAY, "light", 400), "tagline")
    assert lines[0] == "Across seven registries."
    assert " ".join(lines[1:]) == NOTE


def test_wide_stamp_shares_the_eyebrow_line_narrow_stamp_sits_under_the_bar():
    for width, same_line in ((800, True), (400, False)):
        svg = render_card(STATS, DAY, "light", width)
        title, foot = runs(svg, "title")[0], runs(svg, "foot")[0]
        assert (title.get("data-y") == foot.get("data-y")) == same_line
        if not same_line:
            bar_y = float(re.search(r'clipPath id="bar"><rect x="[\d.]+" y="([\d.]+)"', svg).group(1))
            assert float(foot.get("data-y")) > bar_y + BAR_HEIGHT


def test_bar_draws_in_fixed_slot_order_not_by_size():
    colors = palette("dark")
    assert [fill for _, _, fill in bar(render_card(STATS, DAY, "dark"))] == [colors[k] for k in SLOT_ORDER]


def test_bar_keeps_2px_unfilled_gaps_and_a_thin_height():
    segments = [(float(x), float(w)) for x, w, _ in bar(render_card(STATS, DAY, "light"))]
    for (x1, w1), (x2, _) in zip(segments, segments[1:]):
        assert x2 - (x1 + w1) == pytest.approx(BAR_GAP, abs=0.02)
    assert 8 <= BAR_HEIGHT <= 10


def test_bar_rounds_only_its_outer_ends():
    svg = render_card(STATS, DAY, "light")
    clip = re.search(r'<clipPath id="bar"><rect [^>]*rx="([\d.]+)"', svg)
    assert clip and clip.group(1) == tokens("grond-st")["light"]["radius-box"].removesuffix("px")
    assert len(bar(svg)) == 7  # the segment pattern has no rx: inner ends stay square


def test_segments_use_true_proportions():
    widths = [float(w) for _, w, _ in bar(render_card(STATS, DAY, "light"))]
    assert widths[0] / widths[1] == pytest.approx(46_451 / 25_761, rel=0.01)  # PyPI, then crates.io
    assert sum(widths) == pytest.approx(800 - 2 * 24 - 6 * BAR_GAP, abs=0.05)


def test_tiny_segments_are_drawn_at_the_minimum_width():
    widths = segment_widths([100_000, 10], 500)
    assert widths[1] == MIN_SEGMENT
    assert sum(widths) == pytest.approx(500)


def test_registry_without_a_30_day_number_gets_no_segment():
    stats = [RegistryStat("pypi", "PyPI", 1, 100), RegistryStat("nuget", "NuGet", 5, None)]
    assert len(bar(render_card(stats, DAY, "light"))) == 1


def test_box_has_no_scripts_external_resources_live_text_or_em_dashes():
    svg = render_card(STATS, DAY, "dark")
    assert "<script" not in svg and "<text" not in svg and "—" not in svg
    assert all(ref.startswith("#") for ref in re.findall(r'href="([^"]*)"', svg))


def test_title_spells_out_every_number_for_screen_readers():
    title = ET.fromstring(render_card(STATS, DAY, "light")).find(f"{SVG}title").text
    assert title.startswith("Package downloads in the last 30 days: 86,140.")
    assert "PyPI 46,451 (without mirrors)" in title and "pub.dev 1,155" in title
    assert title.index("crates.io") < title.index("npm") < title.index("Docker")  # slot order
    assert describe([RegistryStat("nuget", "NuGet", 1, None)], None).startswith(
        "Package downloads in the last 30 days: unknown."
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_chip_is_a_labelled_legend_key(theme):
    t = tokens("grond-st")[theme]
    colors = palette(theme)
    for stat in STATS:
        svg = render_chip(stat, theme)
        root = ET.fromstring(svg)
        outline = root.find(f"{SVG}rect")
        assert outline.get("fill") == "none" and outline.get("stroke") == t["border-strong"]
        assert outline.get("rx") == t["radius-control"].removesuffix("px")
        dot = root.find(f"{SVG}circle")  # the only coloured part, about 8px
        assert dot.get("fill") == colors[stat.key] and float(dot.get("r")) * 2 == pytest.approx(8)
        assert texts(svg, "label") == [stat.label] and texts(svg, "value") == [format_value(stat.last30)]
        assert all(g.get("fill") == t["foreground"] for g in runs(svg))  # text colours, never the slot colour
        assert root.get("height") == str(CHIP_HEIGHT + CHIP_GAP)
        assert "<script" not in svg and "<text" not in svg


def test_total_and_chips_round_the_same_way():
    assert texts(render_card(STATS, DAY, "light"), "big") == [format_count(sum(s.last30 for s in STATS))]
    assert [texts(render_chip(s, "light"), "value")[0] for s in STATS] == [format_count(s.last30) for s in STATS]


def test_registry_slots_are_the_profile_data_palette_in_order():
    assert list(SLOTS) == SLOT_ORDER and list(SLOTS.values()) == list(range(1, 8))
    for theme in ("light", "dark"):
        t, colors = tokens("grond-st")[theme], palette(theme)
        assert all(colors[key] == t[f"data-{slot}"] for key, slot in SLOTS.items())


def test_alt_texts_carry_the_numbers():
    assert box_alt(STATS) == (
        "Package downloads in the last 30 days: 86.1K across seven registries. "
        "PyPI counted without mirrors, from pypistats.org."
    )
    assert [chip_alt(s) for s in STATS][:2] == [
        "PyPI: 46.5K downloads in the last 30 days",
        "crates.io: 25.8K downloads in the last 30 days",
    ]
    assert chip_alt(RegistryStat("nuget", "NuGet", 1, None)) == "NuGet: no 30-day number yet"
