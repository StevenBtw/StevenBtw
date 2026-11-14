"""README headers for single repos: the project banner's layout (frame, mark, eyebrow, name, one line) in that
project's identity, without the repo count, in light and dark, wide and narrow.

    uv run python -m visuals.repo_headers OUT_DIR      writes OUT_DIR/<repo>[-narrow]-{light,dark}.svg

Each repo keeps its four files in .github/readme/ as header[-narrow]-{light,dark}.svg; snippet(repo) is the
<picture> that opens its README (absolute raw URLs on main, so PyPI and crates.io show it too).
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from visuals import THEMES, document, frame, marks, px, tokens
from visuals.projects import GROUPS, Group, _beam_gradient, _body, _case, _mark, _name, _wrap, eyebrow_style
from visuals.readme import DARK, NARROW, NARROW_DARK
from visuals.type import Typesetter

BY_KEY = {g.key: g for g in GROUPS}

# (repo, project group, eyebrow, name, tagline)
HEADERS = [
    ("grafeo", "grafeo", "Graph (and vector) database", "Grafeo", "The embeddable graph database, written in Rust."),
    (
        "grafeodb", "grafeo", "GitHub organisation", "GrafeoDB",
        "The embeddable graph database, and everything built around it.",
    ),
    (
        "grafeo-memory", "grafeo-ai", "Grafeo AI", "grafeo-memory",
        "Memory for agents, in one file: a graph with vectors and history, with any LLM.",
    ),
    (
        "grafeo-mcp", "grafeo-ai", "Grafeo AI", "grafeo-mcp",
        "An MCP server that gives agents a Grafeo database: queries, search and graph algorithms.",
    ),
    (
        "grafeo-langchain", "grafeo-ai", "Grafeo AI", "grafeo-langchain",
        "LangChain graph and vector stores backed by Grafeo, in one file.",
    ),
    (
        "grafeo-llamaindex", "grafeo-ai", "Grafeo AI", "grafeo-llamaindex",
        "A LlamaIndex property graph store backed by Grafeo, in one file.",
    ),
    (
        "anywidget-graph", "anywidgets", "Notebook widgets", "anywidget-graph",
        "Interactive graph visualization for Python notebooks.",
    ),
    (
        "anywidget-vector", "anywidgets", "Notebook widgets", "anywidget-vector",
        "Interactive 3D vector visualization for Python notebooks.",
    ),
    (
        "anywidget-archimate", "anywidgets", "Notebook widgets", "anywidget-archimate",
        "Interactive ArchiMate model viewer for Python notebooks.",
    ),
    ("solvor", "solvor", "Optimization", "solvOR", "Pure Python optimization solvers, each in one readable file."),
]

# Where each repo lives on GitHub (owner/name), for the README snippet's URLs.
REPO_PATHS = {
    "grafeo": "GrafeoDB/grafeo",
    "grafeodb": "GrafeoDB/.github",
    "grafeo-memory": "GrafeoDB/grafeo-memory",
    "grafeo-mcp": "GrafeoDB/grafeo-mcp",
    "grafeo-langchain": "GrafeoDB/grafeo-langchain",
    "grafeo-llamaindex": "GrafeoDB/grafeo-llamaindex",
    "anywidget-graph": "GrafeoDB/anywidget-graph",
    "anywidget-vector": "GrafeoDB/anywidget-vector",
    "anywidget-archimate": "StevenBtw/anywidget-archimate",
    "solvor": "StevenBtw/solvOR",
}

VARIANTS = {"": 800, "-narrow": 400}

# Each widget has its own mark in its README; the profile shows all three in one slot.
WIDGET_MARKS = {"anywidget-graph": marks.graph, "anywidget-vector": marks.vector, "anywidget-archimate": marks.archimate}


def render_repo_header(repo: str, group: Group, theme: str, width: int = 800) -> str:
    t = tokens(group.project)[theme]
    ink, muted = t["foreground"], t["muted-foreground"]
    ts = Typesetter()
    wide = width >= 600
    pad = 24 if wide else 20
    mark_size = 64 if wide else 48
    name_size, body_size = (32, 16) if wide else (28, 15)
    text_x = pad + mark_size + 24
    face, size, tracking = eyebrow_style(group)
    eyebrow_y = pad + 12
    name_y = eyebrow_y + 12 + name_size
    parts = [ts.text(face, _case(group, group.eyebrow), text_x, eyebrow_y, size, muted, tracking=tracking, role="eyebrow")]
    parts.append(_name(group, ts, t, theme, text_x, name_y, name_size, ink))
    if wide:
        lines_x, line_y, avail = text_x, name_y + 28, width - text_x - pad
    else:  # as the profile's narrow banner: the tagline runs under the mark at full width
        lines_x, line_y, avail = pad, max(name_y, pad + mark_size) + 30, width - 2 * pad
    lines = _wrap(group, body_size, avail)
    for i, line in enumerate(lines):
        parts.append(_body(group, ts, line, lines_x, line_y + i * body_size * 1.5, body_size, muted))
    height = round(line_y + (len(lines) - 1) * body_size * 1.5 + pad)
    mark_y = (height - mark_size) / 2 if wide else pad
    if repo in WIDGET_MARKS:
        parts.insert(0, WIDGET_MARKS[repo](t, pad, mark_y, mark_size))
    else:
        parts.insert(0, _mark(group, theme, t, pad, mark_y, mark_size))
    parts.insert(0, frame(width, height, t["border-strong"], px(t["radius-box"])))
    defs = ts.defs()
    if group.beam:
        defs += _beam_gradient(t, width)
        r = px(t["radius-box"])
        parts.insert(1, f'<path d="M{r:g} 0.75H{width - r:g}" stroke="url(#beam)" stroke-width="1.5"/>')
    return document(width, height, f"{group.name}: {group.tagline}", "".join(parts), defs)


def snippet(repo: str) -> str:
    """The <picture> that opens the repo's README: narrow below a 460px column, dark or light by the viewer."""
    _, _, _, name, tagline = next(h for h in HEADERS if h[0] == repo)
    base = f"https://raw.githubusercontent.com/{REPO_PATHS[repo]}/main/.github/readme"
    return (
        "<picture>\n"
        f'  <source media="{NARROW_DARK}" srcset="{base}/header-narrow-dark.svg">\n'
        f'  <source media="{NARROW}" srcset="{base}/header-narrow-light.svg">\n'
        f'  <source media="{DARK}" srcset="{base}/header-dark.svg">\n'
        f'  <img alt="{name}: {tagline}" src="{base}/header-light.svg" width="100%">\n'
        "</picture>"
    )


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for repo, key, eyebrow, name, tagline in HEADERS:
        group = replace(BY_KEY[key], eyebrow=eyebrow, name=name, tagline=tagline)
        for theme in THEMES:
            for suffix, width in VARIANTS.items():
                path = out / f"{repo}{suffix}-{theme}.svg"
                path.write_text(render_repo_header(repo, group, theme, width), encoding="utf-8", newline="\n")
                print("wrote", path)
        (out / f"{repo}.snippet.html").write_text(snippet(repo) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
