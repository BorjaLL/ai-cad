"""Test-piece (coupon) builders: small prints that answer one fit question.

- hole_gauge_strip(): a strip of vertical holes stepping through a size range,
  each labelled, for "which hole grips / turns this pin on MY printer".
- hinge_chain(): a plain bar split twice with ppi_hinge.split_with_hinge,
  giving a 3-link chain: the smallest print that tests a hinge setting.

Build coupons from the same functions as the real part, so a passing coupon
means the real joint has the same geometry.
"""
from __future__ import annotations

from manifold3d import Manifold, OpType

from .label import emboss, engrave
from .ppi_hinge import HingeParams, split_with_hinge


def _fmt(v: float) -> str:
    """0.25 -> '.25', 2.10 -> '2.1' (short labels fit small cells)."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s[1:] if s.startswith("0.") else s


def hole_gauge_strip(diameters, thickness: float = 4.0, pitch: float | None = None,
                     margin: float = 3.0, chamfer: float = 0.0, label_h: float = 3.0,
                     label_depth: float = 0.4, segments: int = 64) -> tuple[Manifold, list]:
    """A flat strip with one vertical (Z axis) through-hole per diameter.

    Each hole gets its size engraved below it. chamfer > 0 adds a 45 deg entry
    chamfer on the top face. Returns (strip, holes) where holes is a list of
    dicts {d, x, y} in strip coordinates (bottom-left corner at the origin).
    """
    diameters = list(diameters)
    dmax = max(diameters)
    pitch = pitch or max(dmax + 3.0, label_h * 2.2)
    length = margin * 2 + pitch * (len(diameters) - 1) + dmax
    depth = margin + dmax + 1.5 + label_h + margin
    strip = Manifold.cube([length, depth, thickness])
    y_hole = depth - margin - dmax / 2
    holes, cuts = [], []
    for i, d in enumerate(diameters):
        x = margin + dmax / 2 + i * pitch
        cyl = Manifold.cylinder(thickness + 2, d / 2, d / 2, segments).translate([x, y_hole, -1])
        cuts.append(cyl)
        if chamfer > 0:
            r0 = d / 2
            cone = Manifold.cylinder(chamfer + 0.01, r0, r0 + chamfer + 0.01, segments)
            cuts.append(cone.translate([x, y_hole, thickness - chamfer]))
        holes.append(dict(d=d, x=round(x, 3), y=round(y_hole, 3)))
    strip = strip - Manifold.batch_boolean(cuts, OpType.Add)
    for h in holes:
        strip = engrave(strip, [_fmt(h["d"])], (h["x"], margin + label_h / 2), thickness,
                        text_h=label_h, depth=label_depth)
    return strip, holes


def hinge_chain(p: HingeParams, x0: float = 0.0, lead: float = 26.0, pitch: float = 18.0,
                tail: float = 14.0, label_lines: list[str] | None = None, label_h: float = 3.2):
    """Three links joined by two captive hinges, axis along X, links along Y.

    lead  : length of link 1 behind hinge 1
    pitch : hinge 1 to hinge 2
    tail  : length of link 3 past hinge 2
    Returns (links, hinges): links = [l1, l2, l3], hinges = [HingeGeometry] * 2.
    """
    W, T = p.width, p.thickness
    bar = Manifold.cube([W, lead + pitch + tail, T]).translate([x0 - W / 2, -lead, 0])
    l1, rest, h1 = split_with_hinge(bar, (x0, 0, T / 2), (1, 0, 0), (0, 1, 0), p)
    l2, l3, h2 = split_with_hinge(rest, (x0, pitch, T / 2), (1, 0, 0), (0, 1, 0), p)
    if label_lines:
        l1 = l1 + emboss(label_lines, (x0, -lead / 2 - 4), T, text_h=label_h,
                         line_gap=0.7, along="y")
    # drop near-collinear vertices from the swept carve (5 micron; checks run after)
    return [m.simplify(0.005) for m in (l1, l2, l3)], [h1, h2]
