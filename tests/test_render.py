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
    root = ET.fromstring(svg)
    assert root.get("width") == "495"
    shown = texts(svg)
    assert "Package downloads" in shown
    assert "1.2M" in shown  # 1,200,000 all time
    assert "+46K" in shown  # 31K + 6K + 9K known; Docker and NuGet unknown
    assert "updated 11 Oct" in shown


def test_card_has_no_scripts_external_resources_or_em_dashes():
    svg = render_card(STATS, date(2026, 10, 11), "dark")
    assert "<script" not in svg
    assert "href" not in svg
    assert "@import" not in svg
    assert "\u2014" not in svg


def test_legend_keeps_the_given_order_column_by_column():
    svg = render_card(STATS, date(2026, 10, 11), "light")
    labels = [t for t in texts(svg) if t in {"PyPI", "crates.io", "Docker", "NuGet", "npm"}]
    assert labels == ["PyPI", "crates.io", "Docker", "NuGet", "npm"]
    root = ET.fromstring(svg)
    positions = {t.text: (float(t.get("x")), float(t.get("y"))) for t in root.iter(f"{SVG}text") if t.text in labels}
    assert positions["PyPI"][0] == positions["Docker"][0] < positions["NuGet"][0]  # 3 rows left, 2 right
    assert positions["PyPI"][1] == positions["NuGet"][1]


def test_unknown_30_day_shows_n_a_in_the_legend():
    shown = texts(render_card(STATS, date(2026, 10, 11), "light"))
    assert shown.count("n/a") == 2


def test_bar_segments_are_proportional_and_use_theme_colours():
    svg = render_card(STATS, date(2026, 10, 11), "dark")
    rects = re.findall(r'<rect x="([\d.]+)" y="118" width="([\d.]+)" height="8" fill="(#[0-9a-f]{6})"/>', svg)
    assert [fill for _, _, fill in rects] == [COLORS["dark"][s.key] for s in STATS]
    widths = [float(w) for _, w, _ in rects]
    assert sum(widths) == pytest.approx(445 - 2 * 4, abs=0.05)
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
