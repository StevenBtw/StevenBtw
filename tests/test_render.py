import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from downloads.render import COLORS, OTHERS, VARIANTS, RegistryStat, format_count, format_delta, render_card

SVG = "{http://www.w3.org/2000/svg}"
DAY = date(2026, 10, 11)

STATS = [  # in fetch order, the way collect() returns them
    RegistryStat("pypi", "PyPI", 812_000, 31_000),
    RegistryStat("crates", "crates.io", 150_000, 6_000),
    RegistryStat("docker", "Docker", 15_000, None),
    RegistryStat("nuget", "NuGet", 22_000, None),
    RegistryStat("npm", "npm", 201_000, 9_000),
    RegistryStat("github", "GitHub", 750, None),
    RegistryStat("pubdev", "pub.dev", None, 408),
]
LARGEST_FIRST = ["PyPI", "npm", "crates.io", "NuGet", "Docker", "GitHub", "pub.dev"]


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1_000, "1K"),
        (1_234, "1.23K"),
        (9_999, "10K"),
        (48_300, "48.3K"),
        (99_999, "100K"),
        (812_000, "812K"),
        (999_499, "999K"),
        (999_950, "1M"),
        (1_240_000, "1.24M"),
        (12_345_678, "12.3M"),
        (2_500_000_000, "2.5B"),
    ],
)
def test_format_count(n, expected):
    assert format_count(n) == expected


def test_format_delta():
    assert format_delta(31_000) == "+31K"
    assert format_delta(0) == "+0"
    assert format_delta(None) == "n/a"


def texts(svg):
    return [t.text for t in ET.fromstring(svg).iter(f"{SVG}text")]


def labels(svg):
    return [t for t in ET.fromstring(svg).iter(f"{SVG}text") if t.get("class") == "label"]


def bar(svg):
    return re.findall(r'<rect x="([\d.]+)" y="\d+" width="([\d.]+)" height="8" fill="(#[0-9a-f]{6})"/>', svg)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_card_is_valid_svg_with_headline_numbers(theme):
    shown = texts(render_card(STATS, DAY, theme))
    assert "1.2M" in shown  # 1,200,750 all time; pub.dev has no all-time number
    assert "+46.4K" in shown  # 31K + 6K + 9K + 408; Docker, NuGet and GitHub unknown
    assert "updated 11 Oct" in shown


def test_card_is_drawn_at_the_readme_column_width():
    # GitHub's profile README column is 800px on desktop; the README scales the image to 100% of it.
    root = ET.fromstring(render_card(STATS, DAY, "light"))
    assert root.get("width") == "800"
    assert root.get("viewBox").startswith("0 0 800 ")


def test_card_leaves_the_title_to_the_readme_heading():
    assert "Package downloads" not in texts(render_card(STATS, DAY, "light"))


@pytest.mark.parametrize(("theme", "surface"), [("light", "#f6f8fa"), ("dark", "#151b23")])
def test_card_uses_the_readme_code_block_surface_without_a_border(theme, surface):
    background = ET.fromstring(render_card(STATS, DAY, theme)).find(f"{SVG}rect")
    assert background.get("fill") == surface
    assert background.get("stroke") is None
    assert background.get("rx") == "6"


def test_card_has_no_scripts_external_resources_or_em_dashes():
    svg = render_card(STATS, DAY, "dark")
    assert "<script" not in svg
    assert "href" not in svg
    assert "@import" not in svg
    assert "\u2014" not in svg


def test_wide_card_lists_every_registry_largest_first_in_one_row():
    found = labels(render_card(STATS, DAY, "light"))
    assert [t.text for t in found] == LARGEST_FIRST  # unknown totals (pub.dev) go last
    assert len({t.get("y") for t in found}) == 1
    xs = [float(t.get("x")) for t in found]
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert min(steps) > 0 and max(steps) - min(steps) < 0.02  # evenly spaced, left to right (2-decimal rounding)


def test_equal_totals_keep_the_given_order():
    stats = [RegistryStat("nuget", "NuGet", 10, None), RegistryStat("docker", "Docker", 10, None)]
    assert [t.text for t in labels(render_card(stats, DAY, "light"))] == ["NuGet", "Docker"]


def test_unknown_total_shows_n_a_and_gets_no_bar_segment():
    svg = render_card(STATS, DAY, "light")
    assert "n/a" in texts(svg) and "+408" in texts(svg)
    assert COLORS["light"]["pubdev"] not in [fill for _, _, fill in bar(svg)]


def test_bar_segments_follow_the_legend_and_use_theme_colours():
    segments = bar(render_card(STATS, DAY, "dark"))
    keys = ["pypi", "npm", "crates", "nuget", "docker", "github"]
    assert [fill for _, _, fill in segments] == [COLORS["dark"][k] for k in keys]
    widths = [float(w) for _, w, _ in segments]
    assert sum(widths) == pytest.approx(800 - 2 * 24 - 5 * 2, abs=0.05)  # full width less padding and 5 gaps
    assert widths[0] / widths[1] == pytest.approx(812 / 201, rel=0.01)  # PyPI, then npm


def test_top_four_and_others():
    svg = render_card(STATS, DAY, "light", shown=4, width=540)
    assert [t.text for t in labels(svg)] == ["PyPI", "npm", "crates.io", "NuGet", "Others"]
    shown = texts(svg)
    assert "15.8K" in shown  # Docker 15,000 + GitHub 750; pub.dev has no all-time number
    assert shown.count("+408") == 1  # Others' 30 days: pub.dev is the only one of the three with a number
    keys = ["pypi", "npm", "crates", "nuget"]
    assert [fill for _, _, fill in bar(svg)] == [COLORS["light"][k] for k in keys] + [OTHERS["light"]]


def test_others_only_appears_when_two_or_more_registries_are_left():
    five = STATS[:5]
    assert "Others" not in [t.text for t in labels(render_card(five, DAY, "light", shown=4, width=540))]


def test_others_with_nothing_known_shows_n_a():
    stats = STATS[:4] + [RegistryStat("github", "GitHub", None, None), RegistryStat("pubdev", "pub.dev", None, None)]
    svg = render_card(stats, DAY, "light", shown=4, width=540)
    assert [t.text for t in labels(svg)][-1] == "Others"
    assert texts(svg)[-2:] == ["n/a", "n/a"]  # Others: all time and 30 days


def test_two_row_legend_fills_rows_left_to_right():
    found = labels(render_card(STATS, DAY, "light", shown=4, columns=3, width=340))
    assert [t.text for t in found] == ["PyPI", "npm", "crates.io", "NuGet", "Others"]
    ys = [float(t.get("y")) for t in found]
    assert ys[0] == ys[1] == ys[2] < ys[3] == ys[4]
    assert found[3].get("x") == found[0].get("x")


@pytest.mark.parametrize("suffix", list(VARIANTS))
def test_every_variant_leaves_room_for_its_legend(suffix):
    shown, columns, width = VARIANTS[suffix]
    root = ET.fromstring(render_card(STATS, DAY, "light", shown, columns, width))
    assert root.get("width") == str(width)
    entries = len([t for t in root.iter(f"{SVG}text") if t.get("class") == "label"])
    assert (width - 2 * 24) / (columns or entries) >= 95  # px per legend column at the drawn size


def test_registry_colours_are_the_validated_palette_slots():
    # Checked with the dataviz validator for every pair that can end up side by side once sorted by size.
    assert COLORS["light"] == {
        "pypi": "#2a78d6", "crates": "#eda100", "npm": "#e87ba4", "docker": "#008300",
        "nuget": "#4a3aa7", "github": "#e34948", "pubdev": "#1baf7a",
    }
    assert COLORS["dark"] == {
        "pypi": "#3987e5", "crates": "#c98500", "npm": "#d55181", "docker": "#008300",
        "nuget": "#9085e9", "github": "#e66767", "pubdev": "#199e70",
    }
    assert OTHERS == {"light": "#6e7781", "dark": "#adb5bf"}


def test_legend_shows_each_registrys_total_and_30_days():
    shown = texts(render_card(STATS, DAY, "light"))
    for value in ("812K", "+31K", "150K", "+6K", "201K", "+9K", "750", "+408"):
        assert value in shown


def test_zero_total_registry_gets_no_bar_segment_but_stays_in_the_legend():
    stats = [RegistryStat("pypi", "PyPI", 100, 10), RegistryStat("nuget", "NuGet", 0, None)]
    svg = render_card(stats, DAY, "light")
    assert len(bar(svg)) == 1
    assert "NuGet" in texts(svg)


def test_all_zero_draws_no_bar_and_unknown_30_days():
    stats = [RegistryStat("docker", "Docker", 0, None), RegistryStat("nuget", "NuGet", 0, None)]
    svg = render_card(stats, DAY, "light")
    ET.fromstring(svg)
    assert bar(svg) == []
    shown = texts(svg)
    assert "0" in shown and "n/a" in shown


def test_title_describes_full_numbers_for_screen_readers():
    root = ET.fromstring(render_card(STATS, DAY, "light", shown=4, width=540))
    title = root.find(f"{SVG}title").text
    assert title.startswith("Package downloads: 1,200,750 all time, 46,408 in the last 30 days.")
    assert "Docker 15,000 all time, unknown in the last 30 days" in title  # folded entries are still named
    assert "pub.dev unknown all time, 408 in the last 30 days" in title
