"""Static SVG visuals for the profile README, in the profile identity (grond.st field notes) and the projects' own.

Every visual is a light and a dark file with a transparent background: it sits on GitHub's own canvas, and
structure comes from hairlines and tinted text taken from the design tokens in visuals/tokens/.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
THEMES = ("light", "dark")


@cache
def tokens(project: str) -> dict[str, dict[str, str]]:
    """Design tokens per theme, copied from the design knowledge base's tokens/dist/<project>/tokens.json."""
    return json.loads((HERE / "tokens" / f"{project}.json").read_text(encoding="utf-8"))


def px(value: str) -> float:
    return float(value.removesuffix("px"))


def document(width: float, height: float, title: str, body: str, defs: str = "", desc: str = "") -> str:
    """A self-contained SVG: no scripts, no external references, as GitHub's image proxy requires."""
    described = f'<desc id="d">{escape(desc)}</desc>' if desc else ""
    labelled = "t d" if desc else "t"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" role="img" aria-labelledby="{labelled}">'
        f'<title id="t">{escape(title)}</title>{described}'
        f"<defs>{defs}</defs>{body}</svg>\n"
    )


def hairline(x1: float, y: float, x2: float, color: str) -> str:
    """A 1px horizontal rule, centred on the pixel row so it stays crisp at the drawn size."""
    return f'<path d="M{x1:g} {y + 0.5:g}H{x2:g}" stroke="{color}" stroke-width="1" fill="none"/>'


def frame(width: float, height: float, color: str, radius: float) -> str:
    """The container outline: a 1px hairline inside the drawn area, no fill, crisp corners from the tokens."""
    return (
        f'<rect x="0.5" y="0.5" width="{width - 1:g}" height="{height - 1:g}" rx="{radius:g}" '
        f'fill="none" stroke="{color}" stroke-width="1"/>'
    )


def mark(file: str, x: float, y: float, width: float, height: float) -> str:
    """An SVG file from visuals/marks/, placed as a nested <svg> at the given box (its viewBox keeps the shape)."""
    source = (HERE / "marks" / file).read_text(encoding="utf-8")
    source = re.sub(r"<\?xml[^>]*\?>\s*", "", source).strip()
    opening = re.match(r"<svg\b[^>]*>", source).group(0)
    view_box = re.search(r'viewBox="([^"]+)"', opening).group(1)
    # Paint set on the mark's root (the Grafeo marks set fill="none") is inherited by its shapes, so it moves
    # along; dropping it would fill every unfilled outline black.
    paint = "".join(
        f' {m.group(0)}' for m in re.finditer(r'\b(?:fill|stroke|stroke-width|stroke-linecap|stroke-linejoin)="[^"]*"', opening)
    )
    inner = source[len(opening) : source.rindex("</svg>")]
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
    return (
        f'<svg x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" viewBox="{view_box}"{paint} '
        f'aria-hidden="true">{inner}</svg>'
    )
