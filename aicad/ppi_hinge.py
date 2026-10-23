"""Captive print-in-place (PPI) hinge that splits any solid into two linked parts.

One print, no inserted pin, axis parallel to the bed, no supports.

Local frame (geometry is built here, then placed in the world):
    X = hinge axis (horizontal), Y = "forward" (from link A to link B), Z = up.
    Axis centre at the origin. The hinge band is `width` wide (X) and
    `thickness` tall (Z, centred on the axis): for a flat-bottomed body put the
    axis thickness/2 above the bed.

Side view (Y right, Z up), 2D "territories" split the body:
    * link A keeps the wedge behind the axis (angles 90+s/2 .. 270-s/2,
      s = swing_deg);
    * link B keeps the wedge ahead (angles -(90-s/2) .. 90-s/2), minus a
      clearance disk and minus the swept path of A's prong nose;
    * the V-notches between them close at +-s: that is the swing stop (flank
      on flank);
    * hood: in the middle band, above the band, A stops at a 45 deg roof so A
      never leaves a flat unsupported lip over the knuckle;
    * on_bed=False (hinge in mid-air): B keeps a 45 deg underside tangent to
      the knuckle, A owns a shelf under it that B's lowest layer prints on.
      The body must have material under the knuckle.

Across the width (X):
    * middle band (loop_frac * width): link B's LOOP = round knuckle (radius
      R = thickness/2) with a 45 deg foot, bored for the axle;
    * side bands: link A's PRONGS = rounded noses (45 deg feet) holding the
      AXLE;
    * the axle flares into 45 deg cone bosses at the prong faces; the loop has
      matching countersinks, so the axle is captured and self-supporting;
    * the bore is an ellipse (xy_gap sideways, z_gap_bottom below the axle)
      with a 45 deg teardrop roof. The top clearance (layer direction) is
      z_gap_top when given; otherwise the legacy 45 deg apex, which is larger
      than it looks (see legacy_top_gap). clearances(p) reports the true
      top / bottom / side values.

Built with manifold3d. Circles use 128 segments (chord error < 0.001 mm at
these radii).

Usage:
    link_a, link_b, hg = split_with_hinge(body, pivot, axis, forward, HingeParams())
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, OpType

SEG = 128     # circular segments
BIG = 400.0   # minimum "infinite" extent for territories (mm); grown to fit the body


@dataclass
class HingeParams:
    xy_gap: float = 0.4       # clearance between vertical faces / sideways at the axle
    z_gap: float = 0.4        # bottom gap when z_gap_bottom is None (+ legacy top)
    z_gap_top: float | None = None     # axle top -> bore roof apex; None = legacy 45 deg apex
    z_gap_bottom: float | None = None  # axle bottom -> bore floor (+ on_bed=False shelf gap)
    axle_d: float = 2.4       # axle diameter
    width: float = 12.0       # hinge band width along the axis
    thickness: float = 8.0    # hinge band thickness (Z); axis at thickness/2 above bed
    loop_frac: float = 0.5    # loop width as a fraction of width
    cone: float = 0.5         # cone boss radial step (45 deg) at each axle end
    nose_wall: float = 0.9    # prong wall around the cone boss root
    swing_deg: float = 60.0   # swing stop, +- degrees from flat
    min_wall: float = 0.8     # min loop wall above the bore roof
    on_bed: bool = True       # False: hinge in mid-air (see module doc)
    flank_gap: float | None = None  # axial gap loop face <-> prong face; None = xy_gap


@dataclass
class HingeGeometry:
    """Pieces for joining two halves of a body at one pivot (world coords).

    link_a = ((body ^ a_keep) - male_cut) + male_add
    link_b = ((body ^ b_keep) + female_add) - female_cut
    """
    a_keep: Manifold
    b_keep: Manifold
    male_add: Manifold
    male_cut: Manifold
    female_add: Manifold
    female_cut: Manifold
    frame: np.ndarray        # 3x4 local -> world
    info: dict = field(default_factory=dict)


# ---------------------------------------------------------------- 2D helpers (Y, Z)
def _poly(pts) -> CrossSection:
    return CrossSection([[tuple(map(float, p)) for p in pts]])


def _wedge(a0: float, a1: float, r: float = BIG) -> CrossSection:
    """Pie slice from angle a0 to a1 (deg, CCW from +Y)."""
    n = max(4, int(abs(a1 - a0) / 3))
    pts = [(0.0, 0.0)] + [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
                          for a in np.linspace(a0, a1, n + 1)]
    return _poly(pts)


def _hull(cs: CrossSection, pts) -> CrossSection:
    allp = [tuple(map(float, v)) for pl in cs.to_polygons() for v in pl]
    return CrossSection.hull_points(allp + [tuple(map(float, p)) for p in pts])


def _rect(y0, y1, z0, z1) -> CrossSection:
    return _poly([(y0, z0), (y1, z0), (y1, z1), (y0, z1)])


def _prism(cs: CrossSection, x0: float, x1: float) -> Manifold:
    """Extrude a (Y, Z) cross-section along X from x0 to x1."""
    return cs.extrude(x1 - x0).transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])


def _revolve_x(profile_xr) -> Manifold:
    """Solid of revolution about X from an (x, r) outline."""
    cs = CrossSection([[(float(r), float(x)) for x, r in profile_xr]])
    return Manifold.revolve(cs, SEG).transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])


def _union(items):
    return CrossSection.batch_boolean(items, OpType.Add)


# ---------------------------------------------------------------- derived sizes
def z_bottom(p: HingeParams) -> float:
    return p.z_gap if p.z_gap_bottom is None else p.z_gap_bottom


def legacy_top_gap(xy_gap: float, z_gap_bottom: float, axle_d: float = 2.4,
                   thickness: float = 8.0, min_wall: float = 0.8) -> float:
    """Top clearance a legacy (z_gap only) bore really has: 45 deg teardrop apex
    at sqrt(a^2 + b^2) above the axis, capped at R - min_wall, minus the axle
    radius. At axle 2.4, xy 0.5, z 0.4 that is about 1.13 mm, not 0.4."""
    ra = axle_d / 2
    return min(math.hypot(ra + xy_gap, ra + z_gap_bottom), thickness / 2 - min_wall) - ra


def flank(p: HingeParams) -> float:
    return p.xy_gap if p.flank_gap is None else p.flank_gap


def clearances(p: HingeParams) -> dict:
    """Design clearances at the axle, mm: top (to the bore roof apex), bottom,
    side (+ flank, the axial loop-to-prong gap, when flank_gap is set)."""
    d = derived(p)
    out = dict(top=round(d["roof"] - d["ra"], 4), bottom=round(d["bore_b"] - d["ra"], 4),
               side=round(d["bore_a"] - d["ra"], 4),
               top_mode="explicit" if p.z_gap_top is not None else "legacy 45 deg apex")
    if p.flank_gap is not None:
        out["flank"] = round(p.flank_gap, 4)
    return out


def validate(p: HingeParams) -> None:
    """Raise ValueError for non-finite, zero or negative dimensions and clearances."""
    def num(name, v, positive=True):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise ValueError(f"{name} must be a finite number, got {v!r}")
        if positive and v <= 0:
            raise ValueError(f"{name} must be > 0, got {v}")
    for name in ("xy_gap", "z_gap", "axle_d", "width", "thickness", "nose_wall", "min_wall"):
        num(name, getattr(p, name))
    for name in ("z_gap_top", "z_gap_bottom", "flank_gap"):
        if getattr(p, name) is not None:
            num(name, getattr(p, name))
    num("cone", p.cone, positive=False)
    if p.cone < 0:
        raise ValueError(f"cone must be >= 0, got {p.cone}")
    num("swing_deg", p.swing_deg)
    num("loop_frac", p.loop_frac)
    if not 0 < p.loop_frac < 1:
        raise ValueError(f"loop_frac must be between 0 and 1 (exclusive), got {p.loop_frac}")


def derived(p: HingeParams) -> dict:
    """Derived sizes; raises ValueError when the parameters cannot be built."""
    validate(p)
    R = p.thickness / 2
    g = p.xy_gap
    ra = p.axle_d / 2
    s = p.swing_deg
    wm = p.width * p.loop_frac
    f = flank(p)
    xp = wm / 2 + f                                   # prong inner face
    r_core = ra + p.cone + p.nose_wall                # prong nose radius
    y_foot = r_core * math.sqrt(2) - R                # nose 45 deg foot on the bed
    rho = math.hypot((math.sqrt(2) - 1) * R, R) + g   # web face distance (knuckle foot + g)
    bore_a, bore_b = ra + p.xy_gap, ra + z_bottom(p)
    if p.z_gap_top is None:
        roof = min(math.hypot(bore_a, bore_b), R - p.min_wall)
    else:
        roof = ra + p.z_gap_top
        if roof > R - p.min_wall + 1e-9:
            raise ValueError(f"z_gap_top {p.z_gap_top} leaves < min_wall {p.min_wall} over the bore")
        if p.z_gap_top <= 0 or z_bottom(p) <= 0:
            raise ValueError("z gaps must be > 0")
    csk_face = ra + g * math.sqrt(2) + p.cone - f     # countersink radius at the loop face
    d = dict(R=R, g=g, f=f, ra=ra, wm=wm, xp=xp, r_core=r_core, y_foot=y_foot, rho=rho,
             bore_a=bore_a, bore_b=bore_b, roof=roof, csk_face=csk_face,
             flank_top_y=R * math.tan(math.radians(s / 2)))
    if not 20 <= s <= 80:
        raise ValueError("swing_deg must be 20..80 (V-notch stops)")
    if r_core + g > R - 0.4:
        raise ValueError("thickness too small for axle + cone + nose_wall")
    if p.z_gap_top is None and roof < bore_b:
        raise ValueError("thickness too small for axle + z_gap + min_wall")
    if R - bore_b < p.min_wall:
        raise ValueError("thickness too small for axle + z_gap_bottom + min_wall (bore floor)")
    if R - csk_face < 0.6:
        raise ValueError(f"loop side wall {R - csk_face:.2f} mm too thin")
    if f <= 0:
        raise ValueError("flank_gap must be > 0")
    if (p.width - wm) / 2 - f < 1.2:
        raise ValueError("prongs thinner than 1.2 mm; raise width or lower loop_frac")
    return d


# ---------------------------------------------------------------- local parts
_CACHE: dict = {}


def local_parts(p: HingeParams, big: float = BIG) -> dict:
    key = (tuple(sorted(p.__dict__.items())), big)
    if key not in _CACHE:
        _CACHE[key] = _local_parts(p, big)
    return _CACHE[key]


def territory_extent(body: Manifold, pivot) -> float:
    """Half-size of the "infinite" territories that covers body from pivot:
    BIG, or the next power of two above 1.1x the farthest bbox corner."""
    x0, y0, z0, x1, y1, z1 = body.bounding_box()
    pv = np.asarray(pivot, float)
    far = max(float(np.linalg.norm(np.array([x, y, z]) - pv))
              for x in (x0, x1) for y in (y0, y1) for z in (z0, z1))
    need = 1.1 * far + 10.0
    return BIG if need <= BIG else float(2 ** math.ceil(math.log2(need)))


def _local_parts(p: HingeParams, big: float = BIG) -> dict:
    d = derived(p)
    R, g, ra, wm, xp, rc = d["R"], d["g"], d["ra"], d["wm"], d["xp"], d["r_core"]
    s = p.swing_deg
    W2 = p.width / 2
    c = p.cone
    arm = d["flank_top_y"] + R + 2.0   # how far add-geometry reaches into each body

    # territories (unbounded in Z and X)
    a_terr = _wedge(90 + s / 2, 270 - s / 2, big)
    nose = _hull(CrossSection.circle(rc, SEG), [(d["y_foot"], -R), (-d["flank_top_y"], -R)])
    nose_g = nose.offset(g, JoinType.Round, 2.0, SEG)
    carve = _union([nose_g.rotate(float(t)) for t in np.linspace(-s, s, int(2 * s) + 1)])
    b_terr = _wedge(-(90 - s / 2), 90 - s / 2, big) - carve
    # 45 deg chop of the concave clearance arc above 45 deg (else it overhangs)
    phi_top = 90 - s / 2
    if phi_top > 45:
        r1 = rc + g + 0.02
        u45 = (math.cos(math.radians(45)), math.sin(math.radians(45)))
        r2 = r1 / math.cos(math.radians(phi_top - 45)) + 0.02
        ut = (math.cos(math.radians(phi_top)), math.sin(math.radians(phi_top)))
        b_terr = b_terr - _poly([(0, 0), (r1 * u45[0], r1 * u45[1]), (r2 * ut[0], r2 * ut[1])])

    a_keep = _prism(a_terr, -big, big)
    b_keep = _prism(b_terr, -big, big)
    # hood over the loop (middle band, above the band): 45 deg line through (-rho, R)
    rho = d["rho"]
    hood = _poly([(-rho - 0.01, R - 0.01), (big, R - 0.01), (big, R + rho + big)])
    a_keep = a_keep - _prism(hood, -xp, xp)
    trim_b = None
    if not p.on_bed:
        s2 = math.sqrt(2)
        trim_b = _prism(_poly([(-big, -R), ((s2 - 1) * R, -R), (big, big - s2 * R),
                               (big, big), (-big, big)]), -big, big)
        b_keep = b_keep ^ trim_b
        zb = z_bottom(p)
        under = _prism(_rect(-rho, big, -R - zb, -R + 0.001), -big, big)
        shelf = _prism(_rect(-big, big, -big, -R - zb), -big, big)
        a_keep = (a_keep - under) + shelf

    # male (A): prong noses (side bands), web (middle), axle with cone bosses
    noses = _prism(nose, xp, W2) + _prism(nose, -W2, -xp)
    web = _prism(_rect(-arm, -d["rho"], -R, R), -xp, xp)
    axle = _revolve_x([(-xp - 0.3, 0), (-xp - 0.3, ra + c), (-xp, ra + c), (-xp + c, ra),
                       (xp - c, ra), (xp, ra + c), (xp + 0.3, ra + c), (xp + 0.3, 0)])
    male_add = noses + web + axle
    male_cut = _prism(_rect(-d["rho"], big, -R, R), -xp, xp)

    # female (B): knuckle (circle R + 45 deg foot) + neck
    knuckle = _hull(CrossSection.circle(R, SEG), [((1 - math.sqrt(2)) * R, -R)])
    loop = _prism(knuckle + _rect(0, arm, -R, R), -wm / 2, wm / 2)
    female_add = loop if trim_b is None else loop ^ trim_b

    # bore: ellipse + 45 deg teardrop roof, cut flat at `roof`. A roof above the
    # 45 deg apex gets a steeper teardrop so the apex still reaches it.
    ell = CrossSection.circle(1.0, SEG).scale([d["bore_a"], d["bore_b"]])
    pk = math.hypot(d["bore_a"], d["bore_b"])
    if p.z_gap_top is not None and d["roof"] > pk:
        pk = d["roof"]
    tear = _hull(ell, [(0, pk)])
    tear = tear ^ _rect(-big, big, -big, d["roof"])
    bore = _prism(tear, -wm / 2 - 0.5, wm / 2 + 0.5)
    s2 = g * math.sqrt(2)
    x0 = xp - c - s2
    rf = ra + s2 + c
    csk = _revolve_x([(-xp, 0), (-xp, rf), (-x0, ra), (x0, ra), (xp, rf), (xp, 0)])
    female_cut = bore + csk

    return dict(a_keep=a_keep, b_keep=b_keep, male_add=male_add, male_cut=male_cut,
                female_add=female_add, female_cut=female_cut, d=d, arm=arm)


# ---------------------------------------------------------------- world placement
def frame_matrix(pivot, axis, forward) -> np.ndarray:
    """3x4 local -> world. axis and forward must be horizontal (bed = XY plane)."""
    ax = np.asarray(axis, float).copy()
    fw = np.asarray(forward, float).copy()
    pv = np.asarray(pivot, float)
    if ax.shape != (3,) or fw.shape != (3,) or pv.shape != (3,):
        raise ValueError("pivot, axis and forward must each have 3 components")
    if not (np.isfinite(ax).all() and np.isfinite(fw).all() and np.isfinite(pv).all()):
        raise ValueError("pivot, axis and forward must be finite")
    if np.linalg.norm(ax) < 1e-9:
        raise ValueError("axis is the zero vector")
    if np.linalg.norm(fw) < 1e-9:
        raise ValueError("forward is the zero vector")
    if np.linalg.norm(np.cross(ax, fw)) < 1e-6 * np.linalg.norm(ax) * np.linalg.norm(fw):
        raise ValueError("axis and forward are parallel: they must span the bed plane")
    if abs(ax[2]) > 1e-6 or abs(fw[2]) > 1e-6:
        raise ValueError("axis and forward must be parallel to the bed (z component 0)")
    ax /= np.linalg.norm(ax)
    fw = fw - ax * np.dot(fw, ax)
    fw /= np.linalg.norm(fw)
    up = np.cross(ax, fw)
    if up[2] < 0:            # keep Z up: flip the axis direction
        ax = -ax
        up = -up
    return np.column_stack([ax, fw, up, np.asarray(pivot, float)])


def hinge_geometry(pivot, axis, forward, p: HingeParams | None = None,
                   extent: float = BIG) -> HingeGeometry:
    """Cutters + add-geometry for one hinge (world coords).

    pivot   : (x, y, z) axis centre; z = bed + thickness/2 for a flat-bottomed body
    axis    : hinge axis direction, horizontal
    forward : direction from link A to link B, horizontal
    extent  : half-size of the territories (mm from the pivot); split_with_hinge
              derives it from the body (territory_extent) so nothing is clipped
    """
    p = p or HingeParams()
    lp = local_parts(p, extent)
    M = frame_matrix(pivot, axis, forward)
    T = M.tolist()
    return HingeGeometry(
        a_keep=lp["a_keep"].transform(T), b_keep=lp["b_keep"].transform(T),
        male_add=lp["male_add"].transform(T), male_cut=lp["male_cut"].transform(T),
        female_add=lp["female_add"].transform(T), female_cut=lp["female_cut"].transform(T),
        frame=M, info=dict(lp["d"], arm=lp["arm"], swing_deg=p.swing_deg, on_bed=p.on_bed,
                           clearances=clearances(p), axle_d=p.axle_d))


def split_with_hinge(body: Manifold, pivot, axis, forward,
                     p: HingeParams | None = None) -> tuple[Manifold, Manifold, HingeGeometry]:
    """Split `body` at the pivot into link A (behind) and link B (ahead), joined
    by a captive hinge. Returns (link_a, link_b, geometry). Call again on either
    link for the next joint.

    The body must enclose the hinge band: a box `width` along the axis, one
    `thickness` either side of the pivot along forward, `thickness` tall and
    centred on the axis. If less than 99.9% of that box lies inside the body
    a ValueError says how much is missing (the hinge would hang off the edge
    of the part). This checks the band only, not that the result suits your
    part's shape elsewhere."""
    hg = hinge_geometry(pivot, axis, forward, p, territory_extent(body, pivot))
    p = p or HingeParams()
    band = _prism(_rect(-p.thickness, p.thickness, -p.thickness / 2, p.thickness / 2),
                  -p.width / 2, p.width / 2).transform(hg.frame.tolist())
    inside = (band ^ body).volume() / band.volume()
    if inside < 0.999:
        raise ValueError(f"body does not enclose the hinge band at the pivot: only {inside:.1%} of the "
                         f"{p.width} x {2 * p.thickness} x {p.thickness} mm band is inside the solid "
                         f"(needs 100%); move the pivot inward or enlarge the body")
    link_a = ((body ^ hg.a_keep) - hg.male_cut) + hg.male_add
    link_b = ((body ^ hg.b_keep) + hg.female_add) - hg.female_cut
    return link_a, link_b, hg


def rotate_about_axis(m: Manifold, hg: HingeGeometry, deg: float) -> Manifold:
    """Rotate a manifold about the hinge axis (positive = link B tip goes up)."""
    M = np.vstack([hg.frame, [0, 0, 0, 1]])
    t = math.radians(deg)
    Rx = np.array([[1, 0, 0, 0], [0, math.cos(t), -math.sin(t), 0],
                   [0, math.sin(t), math.cos(t), 0], [0, 0, 0, 1]])
    return m.transform((M @ Rx @ np.linalg.inv(M))[:3].tolist())
