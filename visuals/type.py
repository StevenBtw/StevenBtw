"""Set text as outlined glyphs, so the profile's SVGs carry their typefaces without loading any font.

GitHub shows README images as <img>, which cannot fetch web fonts. Each glyph is shaped with HarfBuzz (kerning,
ligatures, tabular figures when asked), drawn once into the SVG's <defs> in font units and placed with <use>.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from xml.sax.saxutils import quoteattr

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

FONT_DIR = Path(__file__).resolve().parent / "fonts"

# Short name -> file in visuals/fonts. Fontsource latin subsets (OFL, licences beside them).
FONTS = {
    "newsreader": "newsreader-latin-400-normal.woff2",
    "newsreader-italic": "newsreader-latin-400-italic.woff2",
    "newsreader-500": "newsreader-latin-500-normal.woff2",
    "hanken": "hanken-grotesk-latin-400-normal.woff2",
    "hanken-500": "hanken-grotesk-latin-500-normal.woff2",
    "hanken-600": "hanken-grotesk-latin-600-normal.woff2",
    "plex-mono": "ibm-plex-mono-latin-400-normal.woff2",
    "plex-mono-500": "ibm-plex-mono-latin-500-normal.woff2",
    "instrument": "instrument-sans-latin-400-normal.woff2",
    "instrument-500": "instrument-sans-latin-500-normal.woff2",
    "jetbrains-mono": "jetbrains-mono-latin-400-normal.woff2",
    "stix": "stix-two-text-latin-400-normal.woff2",
    "stix-500": "stix-two-text-latin-500-normal.woff2",
    "redhat-display-500": "red-hat-display-latin-500-normal.woff2",
    "redhat-display-700": "red-hat-display-latin-700-normal.woff2",
    "redhat-text": "red-hat-text-latin-400-normal.woff2",
    "redhat-mono": "red-hat-mono-latin-400-normal.woff2",
}


@dataclass(frozen=True)
class Face:
    name: str
    font: hb.Font
    upem: int


@cache
def face(name: str) -> Face:
    ttf = TTFont(FONT_DIR / FONTS[name])
    ttf.flavor = None  # woff2 -> plain sfnt bytes, which HarfBuzz reads
    data = io.BytesIO()
    ttf.save(data)
    hb_face = hb.Face(hb.Blob(data.getvalue()))
    return Face(name, hb.Font(hb_face), hb_face.upem)


@cache
def _shape(name: str, text: str, features: tuple[str, ...]) -> tuple[tuple[int, int, int], ...]:
    """(glyph id, x, y) in font units for each glyph of the run, plus the run's advance as a last (-1, x, 0)."""
    f = face(name)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(f.font, buf, {"kern": True, "liga": True} | {feat: True for feat in features})
    glyphs, x = [], 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((info.codepoint, x + pos.x_offset, pos.y_offset))
        x += pos.x_advance
    glyphs.append((-1, x, 0))
    return tuple(glyphs)


def measure(name: str, text: str, size: float, tracking: float = 0, features: tuple[str, ...] = ()) -> float:
    """Advance width in px; tracking is extra px after every glyph but the last."""
    glyphs = _shape(name, text, features)
    return glyphs[-1][1] * size / face(name).upem + tracking * max(0, len(glyphs) - 2)


def wrap(name: str, text: str, size: float, width: float, features: tuple[str, ...] = ()) -> list[str]:
    """Greedy word wrap into lines no wider than width px (a single long word gets its own line)."""
    lines: list[str] = []
    for word in text.split():
        if lines and measure(name, f"{lines[-1]} {word}", size, features=features) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


@dataclass
class Typesetter:
    """Collects glyph outlines for one SVG document; text() returns the placed run, defs() the outlines."""

    _glyphs: dict[str, str] = field(default_factory=dict)

    def text(
        self,
        name: str,
        text: str,
        x: float,
        y: float,
        size: float,
        fill: str,
        anchor: str = "start",
        tracking: float = 0,
        features: tuple[str, ...] = (),
        role: str | None = None,
    ) -> str:
        """One run on baseline y. role becomes the group's class; data-text keeps the string for tests and diffs."""
        f = face(name)
        glyphs = _shape(name, text, features)
        width = measure(name, text, size, tracking, features)
        x0 = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        scale = size / f.upem
        uses = []
        for i, (gid, gx, gy) in enumerate(glyphs[:-1]):
            ref = self._glyph(f, gid)
            if ref is None:  # spaces and other blank glyphs only advance
                continue
            ux = gx + i * tracking / scale
            uses.append(f'<use href="#{ref}" x="{round(ux)}" y="{round(gy)}"/>')  # font units, y up
        attrs = f' class="{role}"' if role else ""
        return (
            f"<g{attrs} data-text={quoteattr(text)} data-x=\"{_fmt(x)}\" data-y=\"{_fmt(y)}\" fill=\"{fill}\" "
            f'transform="translate({_fmt(x0)} {_fmt(y)}) scale({scale:.6f} {-scale:.6f})">{"".join(uses)}</g>'
        )

    def _glyph(self, f: Face, gid: int) -> str | None:
        ref = f"{f.name}-{gid}"
        if ref not in self._glyphs:
            self._glyphs[ref] = _outline(f.name, gid)
        return ref if self._glyphs[ref] else None

    def defs(self) -> str:
        return "".join(f'<path id="{ref}" d="{d}"/>' for ref, d in self._glyphs.items() if d)


@cache
def _outline(name: str, gid: int) -> str:
    pen = SVGPathPen(None, ntos=lambda v: str(round(v)))
    face(name).font.draw_glyph_with_pen(gid, pen)
    return pen.getCommands()
