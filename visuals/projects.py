"""One banner per project group, each in that project's own identity: its typefaces, tokens and mark.

The banners are static (the bonsai is the page's one moving element). A README image can only be one link, so
the banner links to the project's website and each repo gets its own chip under it, linking to the repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from visuals import document, frame, mark, marks, px, tokens
from visuals.type import Typesetter, measure, wrap


GITHUB = "https://github.com"


@dataclass(frozen=True)
class Repo:
    name: str
    path: str  # owner/repo on GitHub

    @property
    def url(self) -> str:
        return f"{GITHUB}/{self.path}"

    @property
    def key(self) -> str:
        return self.name.lower()


def repos(owner: str, *names: str) -> tuple[Repo, ...]:
    return tuple(Repo(name, f"{owner}/{name}") for name in names)


@dataclass(frozen=True)
class Group:
    key: str
    project: str  # tokens file in visuals/tokens/
    eyebrow: str
    name: str
    tagline: str
    repos: tuple[Repo, ...]
    url: str | None  # the project's website, where the README links the banner; None = no link
    heading: str | None  # outlined face for the name; None = the project's live system font
    body: str | None  # outlined face for the tagline; None = live system font
    mono: str
    label: str | None = None  # face for the eyebrow in sentence case; None = the mono face in uppercase
    beam: bool = False  # a static gradient rule on the top edge, in the identity's effect colours


GROUPS = (
    Group(
        "deriva", "deriva", "Architecture", "Deriva",
        "ArchiMate model derivation. A research project.",
        repos("StevenBtw", "deriva"), "https://deriva.dev", "stix-500", "stix", "plex-mono",
    ),
    Group(
        "grafeo", "grafeo", "Embedded · server · browser", "Grafeo",
        "A graph & vector database in Rust, built for speed and low memory use, with bindings for Python, Node.js, Go, C, C# and Dart.",
        repos("GrafeoDB", "grafeo", "grafeo-web", "grafeo-server", "graph-bench", "boltr")
        + (Repo("gwp", "GrafeoDB/gql-wire-protocol"),),
        "https://grafeo.dev", "instrument-500", "instrument", "jetbrains-mono",
    ),
    Group(
        "grafeo-ai", "grafeo-ai", "Hybrid memory for AI", "Grafeo AI",
        "A memory layer for AI agents, an MCP server and integrations for LangChain and LlamaIndex.",
        repos("GrafeoDB", "grafeo-memory", "grafeo-mcp", "grafeo-langchain", "grafeo-llamaindex"),
        "https://grafeo.ai", "instrument-500", "instrument", "jetbrains-mono", beam=True,
    ),
    Group(
        "anywidgets", "anywidgets", "Notebook widgets", "anywidgets",
        "Graph, 3D vector and ArchiMate viewers for Python notebooks.",
        repos("GrafeoDB", "anywidget-graph", "anywidget-vector") + repos("StevenBtw", "anywidget-archimate"),
        None, None, None, "jetbrains-mono",  # no website yet: the banner links nowhere, the chips do
    ),
    Group(
        "solvor", "solvor", "Optimization", "solvOR",
        "Pure Python optimization solvers, plus OR solver benchmarking.",
        repos("StevenBtw", "solvOR", "benchmORk"), "https://solvor.ai", None, "redhat-text", "redhat-mono",
    ),
)

VARIANTS = {"": 800, "-narrow": 400}


def render_banner(group: Group, theme: str, width: int = 800) -> str:
    t = tokens(group.project)[theme]
    ink, muted = t["foreground"], t["muted-foreground"]
    ts = Typesetter()
    wide = width >= 600
    pad = 24 if wide else 20
    mark_size = 64 if wide else 48
    name_size, body_size = (32, 16) if wide else (28, 15)
    has_mark = True  # every project has a mark; solvOR's sits before its wordmark
    text_x = pad + mark_size + 24
    face, size, tracking = eyebrow_style(group)
    # Just the project's kind: the chips under the banner already show its repos
    eyebrow = _case(group, group.eyebrow)

    eyebrow_y = pad + 12
    name_y = eyebrow_y + 12 + name_size
    parts = [ts.text(face, eyebrow, text_x, eyebrow_y, size, muted, tracking=tracking, role="eyebrow")]
    parts.append(_name(group, ts, t, theme, text_x, name_y, name_size, ink))

    if wide:
        lines_x, line_y = text_x, name_y + 28
        avail = width - text_x - pad
    else:  # the tagline runs under the mark at full width
        lines_x, line_y = pad, max(name_y, pad + mark_size) + 30
        avail = width - 2 * pad
    lines = _wrap(group, body_size, avail)
    for i, line in enumerate(lines):
        parts.append(_body(group, ts, line, lines_x, line_y + i * body_size * 1.5, body_size, muted))
    height = round(line_y + (len(lines) - 1) * body_size * 1.5 + pad)
    if has_mark:
        mark_y = (height - mark_size) / 2 if wide else pad
        parts.insert(0, _mark(group, theme, t, pad, mark_y, mark_size))
    parts.insert(0, frame(width, height, t["border-strong"], px(t["radius-box"])))
    defs = ts.defs()
    if group.beam:
        defs += _beam_gradient(t, width)
        parts.insert(1, f'<path d="M{px(t["radius-box"]):g} 0.75H{width - px(t["radius-box"]):g}" stroke="url(#beam)" stroke-width="1.5"/>')
    title = f"{group.name}: {group.tagline}"
    return document(width, height, title, "".join(parts), defs)


def eyebrow_style(group: Group) -> tuple[str, float, float]:
    """(face, size, tracking) of the banner's eyebrow."""
    return (group.label, 13, 0) if group.label else (group.mono, 11, 1.3)


def _case(group: Group, text: str) -> str:
    return text if group.label else text.upper()


def _beam_gradient(t: dict[str, str], width: float) -> str:
    """Navy to aubergine to orange (effect-1 to effect-3), fading out at both ends: a Border Beam, held still.
    In user space: a gradient sized to a straight line's own box (zero height) would not paint."""
    stops = [(0, 1, 0), (0.18, 1, 1), (0.5, 2, 1), (0.82, 3, 1), (1, 3, 0)]
    return (
        f'<linearGradient id="beam" gradientUnits="userSpaceOnUse" x1="0" x2="{width:g}" y1="0" y2="0">'
        + "".join(f'<stop offset="{o:g}" stop-color="{t[f"effect-{e}"]}" stop-opacity="{a:g}"/>' for o, e, a in stops)
        + "</linearGradient>"
    )


CHIP_HEIGHT = 28
CHIP_GAP = 6  # transparent margin right and below, so chips keep apart when the README flows them into rows


def render_chip(group: Group, repo: Repo, theme: str) -> str:
    """A repo's link chip, in its project's mono face: a control, so the softer control radius."""
    t = tokens(group.project)[theme]
    ts = Typesetter()
    size, inset = 12.5, 11
    box = round(measure(group.mono, repo.name, size) + 2 * inset)
    width, height = box + CHIP_GAP, CHIP_HEIGHT + CHIP_GAP
    body = (
        f'<rect x="0.5" y="0.5" width="{box - 1}" height="{CHIP_HEIGHT - 1}" rx="{px(t["radius-control"]):g}" '
        f'fill="none" stroke="{t["border-strong"]}" stroke-width="1"/>'
        + ts.text(group.mono, repo.name, inset, 18.5, size, t["foreground"], role="repo")
    )
    return document(width, height, f"{repo.name} on GitHub", body, ts.defs())


def _name(group: Group, ts: Typesetter, t: dict[str, str], theme: str, x: float, y: float, size: float, ink: str) -> str:
    if group.key == "solvor":  # the wordmark, already outlined: viewBox -40 -740 3338 800, baseline at 0
        height = size * 1.1
        return mark(f"solvor-{theme}.svg", x - height * 40 / 800, y - height * 740 / 800, height * 3338 / 800, height)
    if group.heading is None:
        return _live(group.name, x, y, size, ink, t["font-heading"], weight=600)
    return ts.text(group.heading, group.name, x, y, size, ink, role="name")


def _body(group: Group, ts: Typesetter, line: str, x: float, y: float, size: float, color: str) -> str:
    if group.body is None:
        return _live(line, x, y, size, color, tokens(group.project)["light"]["font-body"])
    return ts.text(group.body, line, x, y, size, color, role="tagline")


def _wrap(group: Group, size: float, width: float) -> list[str]:
    if group.body is not None:
        return wrap(group.body, group.tagline, size, width)
    # Live system text cannot be measured here; assume a wide sans (0.56em a character) to be safe.
    per_line = int(width / (size * 0.56))
    lines: list[str] = []
    for word in group.tagline.split():
        if lines and len(lines[-1]) + 1 + len(word) <= per_line:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def _live(text: str, x: float, y: float, size: float, fill: str, family: str, weight: int = 400) -> str:
    """Text in the viewer's system font: the anywidgets take the host's UI font by design."""
    return (
        f'<text x="{x:g}" y="{y:g}" font-family={quoteattr(family)} font-size="{size:g}" '
        f'font-weight="{weight}" fill="{fill}">{escape(text)}</text>'
    )


def _mark(group: Group, theme: str, t: dict[str, str], x: float, y: float, size: float) -> str:
    if group.key == "grafeo-ai":  # its own mark: the G in a navy, aubergine and orange gradient
        return mark(f"grafeo-ai-mark-64-{theme}.svg", x, y, size, size)
    if group.project == "grafeo":
        return mark(f"grafeo-mark-64-{theme}.svg", x, y, size, size)
    if group.project == "deriva":
        return mark(f"deriva-{theme}.svg", x, y, size, size)
    if group.key == "solvor":  # level sets, a search stepping in, the optimum in gold
        return marks.solvor(t, x, y, size)
    return marks.trio(t, x, y, size)  # the anywidgets: graph, vector and ArchiMate in one slot
