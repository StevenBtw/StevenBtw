"""The project marks and the single-repo README headers."""

from __future__ import annotations

import re

from visuals import THEMES, marks, tokens
from visuals.projects import GROUPS
from visuals.repo_headers import BY_KEY, HEADERS, render_repo_header
from dataclasses import replace


def test_hairlines_keep_one_pixel_when_a_mark_is_drawn_smaller():
    t = tokens("anywidgets")["dark"]
    small = marks.trio(t, 0, 0, 64)  # each widget at 0.48 of the slot
    hairlines = re.findall(r'<path [^>]*stroke-width="1"[^>]*>', small)
    assert hairlines, "the trio draws hairlines"
    assert all('vector-effect="non-scaling-stroke"' in h for h in hairlines)


def test_full_size_marks_draw_plain_hairlines():
    t = tokens("anywidgets")["light"]
    for draw in (marks.graph, marks.vector, marks.archimate):
        assert "vector-effect" not in draw(t, 0, 0, 64)


def test_every_repo_header_renders_in_both_themes():
    for repo, key, eyebrow, name, tagline in HEADERS:
        group = replace(BY_KEY[key], eyebrow=eyebrow, name=name, tagline=tagline)
        for theme in THEMES:
            svg = render_repo_header(repo, group, theme)
            assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>"), repo
            assert f"{name}: {tagline}" in svg, repo  # the title, for screen readers
            # Only the anywidgets set live text (the host's UI font, by design); the others are outlined glyphs
            assert ("<text" in svg) == (key == "anywidgets"), repo


def test_each_widget_header_has_its_own_mark():
    by_repo = {}
    for repo, key, eyebrow, name, tagline in HEADERS:
        if key == "anywidgets":
            group = replace(BY_KEY[key], eyebrow=eyebrow, name=name, tagline=tagline)
            by_repo[repo] = render_repo_header(repo, group, "light")
    marks_only = [re.sub(r"<text.*?</text>|<title>.*?</title>", "", svg, flags=re.S) for svg in by_repo.values()]
    assert len(set(marks_only)) == 3


def test_every_group_still_has_a_header_or_banner_key():
    assert {key for _, key, *_ in HEADERS} <= {g.key for g in GROUPS}


def test_every_header_has_a_narrow_version():
    for repo, key, eyebrow, name, tagline in HEADERS:
        group = replace(BY_KEY[key], eyebrow=eyebrow, name=name, tagline=tagline)
        svg = render_repo_header(repo, group, "dark", width=400)
        assert re.search(r'<svg[^>]*\bwidth="400"', svg), repo


def test_the_readme_snippet_switches_on_width_and_theme():
    from visuals.repo_headers import snippet

    html = snippet("anywidget-archimate")
    base = "https://raw.githubusercontent.com/StevenBtw/anywidget-archimate/main/.github/readme"
    for variant in ("header-narrow-dark", "header-narrow-light", "header-dark", "header-light"):
        assert f"{base}/{variant}.svg" in html
    assert html.index("narrow-dark") < html.index("narrow-light") < html.index('"' + base + "/header-dark")
    assert 'alt="anywidget-archimate: Interactive ArchiMate model viewer for Python notebooks."' in html
