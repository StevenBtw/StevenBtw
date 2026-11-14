"""Marks for the three anywidgets, in the anywidgets ink style: a 2px ring in a data colour over a 38% fill of
the same colour on an opaque surface base, hairline connections; and solvOR's search mark. Each draws on a
64x64 grid at (x, y), scaled to `size`."""

from __future__ import annotations


def _ink(t: dict[str, str], color: str, shape: str) -> str:
    """The shape twice: an opaque surface base, then the colour's 38% fill with a 2px ring."""
    return shape.format(fill=t["surface"], extra="") + shape.format(
        fill=color, extra=f' fill-opacity="0.38" stroke="{color}" stroke-width="2"'
    )


def _hair(size: float) -> str:
    """A hairline's width: 1 unit on the 64-grid, kept at 1px when the mark is drawn smaller (as in the trio)."""
    return 'stroke-width="1"' + ("" if size == 64 else ' vector-effect="non-scaling-stroke"')


def _group(x: float, y: float, size: float, body: str) -> str:
    s = size / 64
    return f'<g transform="translate({x:g} {y:g}) scale({s:g})">{body}</g>'


def graph(t: dict[str, str], x: float, y: float, size: float) -> str:
    """anywidget-graph: nodes in the category colours joined by hairline edges."""
    nodes = [(14, 18, 1), (46, 12, 2), (32, 36, 3), (12, 50, 4), (52, 46, 5)]
    edges = [(0, 2), (1, 2), (2, 3), (2, 4), (0, 1), (3, 4)]
    out = [f'<path d="M{nodes[a][0]} {nodes[a][1]}L{nodes[b][0]} {nodes[b][1]}" stroke="{t["edge"]}" {_hair(size)}/>' for a, b in edges]
    for cx, cy, slot in nodes:
        out.append(_ink(t, t[f"data-{slot}"], f'<circle cx="{cx}" cy="{cy}" r="6" fill="{{fill}}"{{extra}}/>'))
    return _group(x, y, size, "".join(out))


def vector(t: dict[str, str], x: float, y: float, size: float) -> str:
    """anywidget-vector: a 3D point cloud, two clusters over three hairline axes; nearer points are larger."""
    ox, oy = 14, 48  # the axes' origin
    axes = [(ox, oy, 62, oy), (ox, oy, ox, 2), (ox, oy, 2, 62)]
    out = [f'<path d="M{a} {b}L{c} {d}" stroke="{t["edge"]}" {_hair(size)}/>' for a, b, c, d in axes]
    # (cx, cy, r, slot): the far cluster first, so nearer points draw over it
    points = [
        (44, 10, 4, 1), (55, 18, 4.5, 1), (40, 22, 5, 1),
        (26, 30, 5.5, 3), (40, 40, 6, 3), (24, 46, 6.5, 3),
    ]
    for cx, cy, r, slot in points:
        out.append(_ink(t, t[f"data-{slot}"], f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{{fill}}"{{extra}}/>'))
    return _group(x, y, size, "".join(out))


def archimate(t: dict[str, str], x: float, y: float, size: float) -> str:
    """anywidget-archimate: a layered view, three faint layer bands (business, application, technology) with an
    element box in each and a relationship line running down through them."""
    bands = [(4, 4, 4), (4, 24, 1), (4, 44, 3)]  # (x, y, data slot): business amber, application blue, technology green
    out = []
    for bx, by, slot in bands:
        out.append(f'<rect x="{bx}" y="{by}" width="56" height="16" rx="2" fill="{t[f"data-{slot}"]}" fill-opacity="0.10"/>')
    out.append(f'<path d="M24 12V52M42 32V52" stroke="{t["edge"]}" {_hair(size)}/>')
    boxes = [(12, 7, 22, 10, 4), (30, 27, 22, 10, 1), (14, 47, 20, 10, 3), (36, 47, 16, 10, 3)]
    for bx, by, w, h, slot in boxes:
        out.append(_ink(t, t[f"data-{slot}"], f'<rect x="{bx}" y="{by}" width="{w}" height="{h}" rx="2" fill="{{fill}}"{{extra}}/>'))
    return _group(x, y, size, "".join(out))


def trio(t: dict[str, str], x: float, y: float, size: float) -> str:
    """All three in one mark slot, smaller: graph and vector side by side, ArchiMate centred under them."""
    small = size * 0.48
    gap = size - 2 * small
    return (
        graph(t, x, y, small)
        + vector(t, x + small + gap, y, small)
        + archimate(t, x + (size - small) / 2, y + small + gap, small)
    )


BY_NAME = {"anywidget-graph": graph, "anywidget-vector": vector, "anywidget-archimate": archimate}


def solvor(t: dict[str, str], x: float, y: float, size: float) -> str:
    """solvOR: level sets of an objective as hairline ellipses, a dotted search stepping in, the optimum in gold
    (the motif of solvor.ai's link preview)."""
    out = ['<g transform="translate(36 36) rotate(-18)">']
    for rx, ry in [(30, 20), (21, 14), (12, 8)]:
        out.append(f'<ellipse rx="{rx}" ry="{ry}" fill="none" stroke="{t["border-strong"]}" stroke-width="1.6"/>')
    out.append("</g>")
    steps = [(4, 6), (15, 18), (24, 15), (30, 26), (36, 36)]
    path = "M" + "L".join(f"{a} {b}" for a, b in steps)
    out.append(f'<path d="{path}" fill="none" stroke="{t["muted-foreground"]}" stroke-width="1.6" stroke-dasharray="2 3" stroke-linecap="round"/>')
    for a, b in steps[:-1]:
        out.append(f'<circle cx="{a}" cy="{b}" r="3.2" fill="{t["surface"]}" stroke="{t["muted-foreground"]}" stroke-width="1.6"/>')
    out.append(f'<circle cx="36" cy="36" r="9" fill="none" stroke="{t["primary"]}" stroke-width="1.6" opacity="0.55"/>')
    out.append(f'<circle cx="36" cy="36" r="5.5" fill="{t["primary"]}"/>')
    return _group(x, y, size, "".join(out))
