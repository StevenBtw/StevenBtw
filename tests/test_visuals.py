import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from visuals import THEMES, tokens
from visuals.header import NOW, render_header
from visuals.header import VARIANTS as HEADER_VARIANTS
from visuals.projects import CHIP_GAP, CHIP_HEIGHT, GROUPS, eyebrow_style, render_banner, render_chip
from visuals.readme import END, NARROW_DARK, START, section
from visuals.projects import VARIANTS as BANNER_VARIANTS
from visuals.type import Typesetter, measure, wrap

SVG = "{http://www.w3.org/2000/svg}"
ROOT = Path(__file__).resolve().parent.parent


def runs(svg, role=None):
    return [
        g.get("data-text")
        for g in ET.fromstring(svg).iter(f"{SVG}g")
        if g.get("data-text") is not None and (role is None or g.get("class") == role)
    ]


def assert_self_contained(svg):
    assert "<script" not in svg and "@import" not in svg and "—" not in svg
    assert all(ref.startswith("#") for ref in re.findall(r'href="([^"]*)"', svg))


def test_runs_are_shaped_and_measured():
    assert measure("newsreader", "Hi there!", 46) > measure("newsreader", "Hi", 46) > 0
    # Tabular figures give every digit the same advance.
    assert measure("hanken-600", "111", 20, features=("tnum",)) == pytest.approx(
        measure("hanken-600", "888", 20, features=("tnum",))
    )


def test_wrap_keeps_lines_inside_the_width():
    lines = wrap("hanken", NOW, 16, 300)
    assert " ".join(lines) == NOW
    assert all(measure("hanken", line, 16) <= 300 for line in lines)


def test_glyphs_are_drawn_once_per_document():
    ts = Typesetter()
    ts.text("plex-mono", "AAAA", 0, 10, 11, "#000")
    assert ts.defs().count("<path") == 1


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width", HEADER_VARIANTS.values())
def test_header_sets_the_greeting_and_now_line(theme, width):
    svg = render_header(theme, width)
    root = ET.fromstring(svg)
    assert root.get("width") == str(width)
    assert root.find(f"{SVG}title").text == "Hi there! I’m Steven, by the way."
    greeting = "".join(runs(svg, "greeting")).replace(" ", "")
    assert greeting == "Hithere!I’mSteven,bytheway."
    assert " ".join(runs(svg, "now")) == NOW
    assert "<text" not in svg
    assert_self_contained(svg)


def test_header_takes_its_colours_from_the_profile_tokens():
    t = tokens("grond-st")["dark"]
    svg = render_header("dark")
    assert f'fill="{t["foreground"]}"' in svg and f'stroke="{t["border-strong"]}"' in svg


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width", BANNER_VARIANTS.values())
@pytest.mark.parametrize("group", GROUPS, ids=lambda g: g.key)
def test_banner_wears_its_projects_identity(group, theme, width):
    svg = render_banner(group, theme, width)
    root = ET.fromstring(svg)
    t = tokens(group.project)[theme]
    outline = root.find(f"{SVG}rect")
    assert outline.get("fill") == "none" and outline.get("stroke") == t["border-strong"]
    assert outline.get("rx") == t["radius-box"].removesuffix("px")
    assert root.find(f"{SVG}title").text == f"{group.name}: {group.tagline}"
    assert_self_contained(svg)
    # Only the anywidgets use live text: they take the host's system font by design.
    assert ("<text" in svg) == (group.key == "anywidgets")


def test_banners_are_static():
    for group in GROUPS:
        svg = render_banner(group, "dark")
        assert "@keyframes" not in svg and "<animate" not in svg  # the bonsai is the page's one moving element


@pytest.mark.parametrize("theme", THEMES)
def test_every_repo_has_a_chip_in_its_projects_mono_face(theme):
    for group in GROUPS:
        t = tokens(group.project)[theme]
        for repo in group.repos:
            svg = render_chip(group, repo, theme)
            root = ET.fromstring(svg)
            box = root.find(f"{SVG}rect")
            assert box.get("stroke") == t["border-strong"] and box.get("fill") == "none"
            assert box.get("rx") == t["radius-control"].removesuffix("px")  # a control: the softer radius
            assert root.get("height") == str(CHIP_HEIGHT + CHIP_GAP)
            assert runs(svg, "repo") == [repo.name]
            assert f'<g class="repo" data-text="{repo.name}"' in svg and group.mono in svg
            assert_self_contained(svg)


def test_readme_projects_section_is_generated_from_the_groups():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.split(START, 1)[1].split(END, 1)[0].strip() == section().strip()


def test_banners_link_to_websites_and_chips_to_repos():
    block = section()
    for group in GROUPS:
        banner_start = f'<picture>\n  <source media="{NARROW_DARK}" srcset="assets/project-{group.key}-'
        if group.url:
            assert f'<a href="{group.url}">\n{banner_start}' in block
        else:  # no website: the banner is no link, only its chips are
            assert banner_start in block and f'">\n{banner_start}' not in block
        assert f"project-{group.key}-light.svg" in block
        for repo in group.repos:
            assert f'<a href="https://github.com/{repo.path}"><picture>' in block
            assert f"repo-{repo.key}-light.svg" in block
    assert {g.url for g in GROUPS} >= {"https://grafeo.dev", "https://grafeo.ai", "https://deriva.dev", "https://solvor.ai"}


def test_downloads_box_closes_the_page_with_a_linked_chip_per_registry():
    from downloads.registries import PAGES
    from downloads.render import SLOTS
    from visuals.readme import DOWNLOADS_END, DOWNLOADS_START

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = readme.split(DOWNLOADS_START, 1)[1].split(DOWNLOADS_END, 1)[0]
    assert readme.index("assets/bonsai-light.svg") < readme.index(DOWNLOADS_START)  # under the bonsai, last
    assert readme.rstrip().endswith(DOWNLOADS_END)
    hrefs = re.findall(r'<a href="([^"]+)"><picture><source [^>]*srcset="assets/registry-', block)
    assert hrefs == [PAGES[key] for key in SLOTS]  # chips in slot order, each to its registry page
    assert "<a href" not in block.split("<p>", 1)[0]  # the box itself is no link
    assert re.search(r'alt="Package downloads in the last 30 days: [\d.]+[KMB]? across seven registries\.', block)
    assert len(re.findall(r'alt="[^"]+: [\d.]+[KMB]? downloads in the last 30 days"', block)) == len(SLOTS)


def test_visuals_leaves_the_downloads_block_to_the_weekly_run(tmp_path):
    from visuals.readme import DOWNLOADS_END, DOWNLOADS_START, update

    readme = tmp_path / "README.md"
    original = (ROOT / "README.md").read_text(encoding="utf-8")
    readme.write_text(original, encoding="utf-8")
    update(readme)
    after = readme.read_text(encoding="utf-8")
    assert after.split(DOWNLOADS_START, 1)[1] == original.split(DOWNLOADS_START, 1)[1]
    assert DOWNLOADS_END in after


def test_readme_only_references_existing_assets():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = set(re.findall(r'(?:src|srcset)="(assets/[^"]+)"', readme))
    assert refs, "no images found"
    assert [r for r in sorted(refs) if not (ROOT / r).is_file()] == []


def test_marks_keep_the_paint_set_on_their_root():
    # The Grafeo marks set fill="none" on their root <svg>; without it the G's outline would fill black.
    from visuals import mark

    nested = mark("grafeo-mark-64-light.svg", 0, 0, 64, 64)
    assert nested.startswith("<svg ") and 'fill="none"' in nested.split(">", 1)[0]


@pytest.mark.parametrize("width", BANNER_VARIANTS.values())
@pytest.mark.parametrize("group", GROUPS, ids=lambda g: g.key)
def test_eyebrow_fits_inside_the_banner(group, width):
    root = ET.fromstring(render_banner(group, "light", width))
    eyebrow = next(g for g in root.iter(f"{SVG}g") if g.get("class") == "eyebrow")
    face, size, tracking = eyebrow_style(group)
    right = float(eyebrow.get("data-x")) + measure(face, eyebrow.get("data-text"), size, tracking)
    assert right <= width - 20
    assert eyebrow.get("data-text").upper().startswith(group.eyebrow.upper())


@pytest.mark.parametrize("theme", THEMES)
def test_only_grafeo_ai_carries_the_beam_in_its_effect_colours(theme):
    for group in GROUPS:
        svg = render_banner(group, theme)
        assert ('stroke="url(#beam)"' in svg) == (group.key == "grafeo-ai")
    t = tokens("grafeo-ai")[theme]
    svg = render_banner(next(g for g in GROUPS if g.key == "grafeo-ai"), theme)
    assert all(t[f"effect-{i}"] in svg for i in (1, 2, 3))



@pytest.mark.parametrize("width", BANNER_VARIANTS.values())
def test_every_banner_eyebrow_is_mono_uppercase(width):
    # The eyebrow is profile chrome: one style on all five banners, Grafeo AI included (design ruling 2026-11-16).
    for group in GROUPS:
        eyebrow = next(g for g in ET.fromstring(render_banner(group, "light", width)).iter(f"{SVG}g") if g.get("class") == "eyebrow")
        assert eyebrow.get("data-text") == eyebrow.get("data-text").upper()
        assert eyebrow_style(group) == (group.mono, 11, 1.3)


def test_bonsai_links_to_gitbonsai_without_a_caption():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bonsai = readme[readme.index('<p align="center">') :]
    bonsai = bonsai[: bonsai.index("</p>")]
    assert '<a href="https://github.com/StevenBtw/gitbonsai">' in bonsai and "assets/bonsai-light.svg" in bonsai
    assert "<sub>" not in bonsai


@pytest.mark.parametrize("width", HEADER_VARIANTS.values())
def test_header_carries_the_subtitle_between_greeting_and_rule(width):
    from visuals.header import SUBTITLE

    svg = render_header("light", width)
    assert " ".join(runs(svg, "subtitle")) == SUBTITLE
    root = ET.fromstring(svg)
    sub_y = max(float(g.get("data-y")) for g in root.iter(f"{SVG}g") if g.get("class") == "subtitle")
    greet_y = max(float(g.get("data-y")) for g in root.iter(f"{SVG}g") if g.get("class") == "greeting")
    rule_y = float(re.search(r'<path d="M0 ([\d.]+)H', svg).group(1))
    assert greet_y < sub_y < rule_y
