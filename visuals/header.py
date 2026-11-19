"""The profile header: the greeting in Newsreader, a hairline, and the Now line, as on grond.st."""

from __future__ import annotations

from visuals import document, hairline, tokens
from visuals.type import Typesetter, measure, wrap

EYEBROW = "Side projects, research and experiments"
GREETING = ("Hi there! I’m Steven, ", "by the way.")
NOW = (
    "Tinkering with architecture model derivation, the occasional ethical hacking "
    "and maintaining a graph database ecosystem."
)
SUBTITLE = "Recreational programmer. I code to learn, build and have fun."
TITLE = "Hi there! I’m Steven, by the way."
DESC = f"{SUBTITLE} My personal GitHub for side projects, research and experiments. Now: {NOW}"

# Drawn width -> layout. Wide sets the greeting on one line; narrow splits it after "Hi there!".
VARIANTS = {"": 800, "-narrow": 400}


def render_header(theme: str, width: int = 800) -> str:
    t = tokens("grond-st")[theme]
    ink, muted, rule = t["foreground"], t["muted-foreground"], t["border-strong"]
    ts = Typesetter()
    parts = [ts.text("plex-mono", EYEBROW.upper(), 0, 14, 11, muted, tracking=1.4, role="eyebrow")]
    wide = width >= 600
    size = 46 if wide else 38
    if wide:
        lines = [GREETING]
    else:
        lines = [("Hi there!", ""), ("I’m Steven, ", "by the way.")]
    y = 14 + size * 1.25
    for roman, italic in lines:
        parts.append(ts.text("newsreader", roman, 0, y, size, ink, role="greeting"))
        if italic:
            x = measure("newsreader", roman, size)
            parts.append(ts.text("newsreader-italic", italic, x, y, size, ink, role="greeting"))
        y += size * 1.12
    y -= size * 1.12  # back to the greeting's last baseline
    sub_size, sub_leading = (17, 25) if wide else (15, 22)
    y += sub_size + 14
    # Too long for one line: break after the first sentence, not before a lone last word.
    fits = measure("hanken", SUBTITLE, sub_size) <= width
    first, _, rest = SUBTITLE.partition(". ")
    sub_lines = [SUBTITLE] if fits else wrap("hanken", first + ".", sub_size, width) + wrap("hanken", rest, sub_size, width)
    for line in sub_lines:
        parts.append(ts.text("hanken", line, 0, y, sub_size, muted, role="subtitle"))
        y += sub_leading
    y += 22 - sub_leading
    parts.append(hairline(0, y, width, rule))
    label_w = 56 if wide else 0
    text_size, leading = (16, 25) if wide else (15, 23)
    y += 32
    parts.append(ts.text("plex-mono", "NOW", 0, y, 11, muted, tracking=1.4, role="eyebrow"))
    if not wide:
        y += 24
    for line in wrap("hanken", NOW, text_size, width - label_w):
        parts.append(ts.text("hanken", line, label_w, y, text_size, ink, role="now"))
        y += leading
    height = round(y - leading + 10)
    return document(width, height, TITLE, "".join(parts), ts.defs(), DESC)
