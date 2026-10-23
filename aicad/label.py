"""Embossed text labels for coupons (which cell is which, printed on the part).

Uses matplotlib's TextPath with DejaVu Sans Bold (ships with matplotlib), so
no font file is needed.
"""
from __future__ import annotations

import numpy as np
from manifold3d import CrossSection, FillRule, Manifold, OpType


def text_cs(s: str, height: float) -> CrossSection:
    """Text outline as a manifold3d CrossSection, cap height about `height` mm."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    tp = TextPath((0, 0), s, size=height, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    polys = [np.asarray(pl) for pl in tp.to_polygons() if len(pl) > 2]
    return CrossSection([[tuple(map(float, v)) for v in pl] for pl in polys], FillRule.EvenOdd)


def emboss(lines: list[str], center_xy, top_z: float, text_h: float = 3.5, depth: float = 0.6,
           line_gap: float = 1.0, along: str = "x") -> Manifold:
    """Raised text sitting on the plane z = top_z, centred on center_xy.

    along = "x": text reads along +X, lines stacked downward in -Y.
    along = "y": text reads along +Y, lines stacked in -X.
    Union the result with the part. Keep text_h >= 3 mm and depth >= 2 layers
    for a 0.4 nozzle.
    """
    out = []
    n = len(lines)
    for i, s in enumerate(lines):
        cs = text_cs(s, text_h)
        x0, y0, x1, y1 = cs.bounds()
        cs = cs.translate([-(x0 + x1) / 2, -(y0 + y1) / 2])
        off = (i - (n - 1) / 2) * (text_h + line_gap)
        if along == "y":
            cs = cs.rotate(90)
            t = [center_xy[0] - off, center_xy[1], top_z]
        else:
            t = [center_xy[0], center_xy[1] - off, top_z]
        out.append(cs.extrude(depth).translate(t))
    return Manifold.batch_boolean(out, OpType.Add)


def engrave(part: Manifold, lines: list[str], center_xy, top_z: float, text_h: float = 3.5,
            depth: float = 0.4, line_gap: float = 1.0, along: str = "x") -> Manifold:
    """Cut text `depth` mm into the face z = top_z of `part`."""
    txt = emboss(lines, center_xy, top_z - depth, text_h, depth + 0.01, line_gap, along)
    return part - txt
