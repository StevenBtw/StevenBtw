import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from downloads.render import COLORS, RegistryStat, format_count, format_delta, render_card

SVG = "{http://www.w3.org/2000/svg}"

STATS = [
    RegistryStat("pypi", "PyPI", 812_000, 31_000),
    RegistryStat("crates", "crates.io", 150_000, 6_000),
    RegistryStat("docker", "Docker", 15_000, None),
    RegistryStat("nuget", "NuGet", 22_000, None),
    RegistryStat("npm", "npm", 201_000, 9_000),
]


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


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_card_is_valid_svg_with_headline_numbers(theme):
    svg = render_card(STATS, date(2026, 10, 11), theme)
    shown = texts(svg)
    assert "1.2M" in shown  # 1,200,000 all time
    assert "+46K" in shown  # 31K + 6K + 9K known; Docker and NuGet unknown
    assert "updated 11 Oct" in shown


def test_card_is_drawn_at_the_readme_column_width():
    # GitHub's profile README column is 800px on desktop; the README scales the image to 100% of it.
    root = ET.fromstring(render_card(STATS, date(2026, 10, 11), "light"))
    assert root.get("width") == "800"
    assert root.get("viewBox").startswith("0 0 800 ")


def test_card_leaves_the_title_to_the_readme_heading():
    assert "Package downloads" not in texts(render_card(STATS, date(2026, 10, 11), "light"))


@pytest.mark.parametrize(("theme", "surface"), [("light", "#f6f8fa"), ("dark", "#151b23")])
def test_card_uses_the_readme_code_block_surface_without_a_border(theme, surface):
    background = ET.fromstring(render_card(STATS, date(2026, 10, 11), theme)).find(f"{SVG}rect")
    assert background.get("fill") == surface
    assert background.get("stroke") is None
    assert background.get("rx") == "6"


def test_card_has_no_scripts_external_resources_or_em_dashes():
    svg = render_card(STATS, date(2026, 10, 11), "dark")
    assert "<script" not in svg
    assert "href" not in svg
    assert "@import" not in svg
    assert "\u2014" not in svg


def test_legend_is_one_row_in_the_given_order():
    svg = render_card(STATS, date(2026, 10, 11), "light")
    order = ["PyPI", "crates.io", "Docker", "NuGet", "npm"]
    root = ET.fromstring(svg)
    labels = [t for t in root.iter(f"{SVG}text") if t.text in order]
    assert [t.text for t in labels] == order
    assert len({t.get("y") for t in labels}) == 1
    xs = [float(t.get("x")) for t in labels]
    steps = {round(b - a, 2) for a, b in zip(xs, xs[1:])}
    assert len(steps) == 1 and steps.pop() > 0  # evenly spaced, left to right


def test_legend_shows_each_registrys_total_and_30_days():
    shown = texts(render_card(STATS, date(2026, 10, 11), "light"))
    for value in ("812K", "+31K", "150K", "+6K", "201K", "+9K"):
        assert value in shown


def test_unknown_30_day_shows_n_a_in_the_legend():
    shown = texts(render_card(STATS, date(2026, 10, 11), "light"))
    assert shown.count("n/a") == 2


def test_bar_segments_are_proportional_and_use_theme_colours():
    svg = render_card(STATS, date(2026, 10, 11), "dark")
    rects = re.findall(r'<rect x="([\d.]+)" y="\d+" width="([\d.]+)" height="8" fill="(#[0-9a-f]{6})"/>', svg)
    assert [fill for _, _, fill in rects] == [COLORS["dark"][s.key] for s in STATS]
    widths = [float(w) for _, w, _ in rects]
    assert sum(widths) == pytest.approx(800 - 2 * 24 - 4 * 2, abs=0.05)  # full width less padding and 4 gaps
    assert widths[0] / widths[1] == pytest.approx(812 / 150, rel=0.01)


def test_zero_total_registry_gets_no_bar_segment_but_stays_in_the_legend():
    stats = [RegistryStat("pypi", "PyPI", 100, 10), RegistryStat("nuget", "NuGet", 0, None)]
    svg = render_card(stats, date(2026, 10, 11), "light")
    assert len(re.findall(r'height="8" fill=', svg)) == 1
    assert "NuGet" in texts(svg)


def test_all_zero_draws_no_bar_and_unknown_30_days():
    stats = [RegistryStat("docker", "Docker", 0, None), RegistryStat("nuget", "NuGet", 0, None)]
    svg = render_card(stats, date(2026, 10, 11), "light")
    ET.fromstring(svg)
    assert 'height="8" fill=' not in svg
    shown = texts(svg)
    assert "0" in shown and "n/a" in shown


def test_title_describes_full_numbers_for_screen_readers():
    root = ET.fromstring(render_card(STATS, date(2026, 10, 11), "light"))
    title = root.find(f"{SVG}title").text
    assert title.startswith("Package downloads: 1,200,000 all time, 46,000 in the last 30 days.")
    assert "Docker 15,000 all time, unknown in the last 30 days" in title
