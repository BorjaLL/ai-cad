"""Geometry checks a generator runs on itself before anything is printed.

- ray_clearance(): distance from a point along a direction to a mesh wall.
- hinge_measured_clearances(): ray-measured top / bottom / side gaps round a
  ppi_hinge axle (compare with ppi_hinge.clearances()).
- swing_sweep(): overlap volume of a moving part vs a fixed part sampled over
  the whole claimed range at step_deg, plus the first contact past the limit
  (the stop), bisected.
- pose_chain() / pose_report(): pose a serial chain of hinged links and
  report every colliding pair and anything below the bed.
- pairwise_overlaps(): overlap volume of every pair of parts in an assembly.
- thin_walls(), z_thickness(), min_wall_in_zones(), named_zones(), for_printer(), gated(): re-exported
  from thickness.py (in-layer width and Z thickness, per-piece findings).
"""
from __future__ import annotations

import math

import numpy as np
from manifold3d import Manifold

from .mesh import to_trimesh


# ---------------------------------------------------------------- clearances
def ray_clearance(mesh_or_manifold, origin, direction) -> float | None:
    """Distance from origin along direction to the first mesh hit (None = no hit)."""
    import trimesh
    tm = to_trimesh(mesh_or_manifold) if isinstance(mesh_or_manifold, Manifold) else mesh_or_manifold
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    locs, _, _ = trimesh.ray.ray_triangle.RayMeshIntersector(tm).intersects_location(
        [origin], [d], multiple_hits=False)
    if len(locs) == 0:
        return None
    return float(np.linalg.norm(locs[0] - np.asarray(origin, float)))


def hinge_measured_clearances(loop_link: Manifold, hg) -> dict:
    """Rays from a ppi_hinge axis centre (middle band) to the loop link's bore
    wall, minus the axle radius: top (+Z), bottom (-Z), side ahead / behind."""
    M = hg.frame
    piv, fw, up = M[:, 3], M[:, 1], M[:, 2]
    ra = hg.info["ra"]
    tm = to_trimesh(loop_link)
    out = {}
    for k, v in (("top", up), ("bottom", -up), ("side_fwd", fw), ("side_back", -fw)):
        d = ray_clearance(tm, piv, v)
        out[k] = None if d is None else round(d - ra, 4)
    return out


# ---------------------------------------------------------------- motion
def swing_sweep(fixed: Manifold, moving: Manifold, rotate, angles=None, limit_deg: float | None = None,
                tol_mm3: float = 0.01, search_to: float = 100.0, step_deg: float = 1.0,
                refine_deg: float = 0.05) -> dict:
    """Overlap volume between `fixed` and `rotate(moving, deg)`, sampled.

    rotate     : callable (manifold, deg) -> manifold, e.g.
                 lambda m, a: ppi_hinge.rotate_about_axis(m, hg, a)
    limit_deg  : the claimed swing. Every angle in -limit..+limit is tested at
                 step_deg, plus any explicit `angles`; then the search continues
                 past +-limit at step_deg up to search_to for the first contact
                 (> tol_mm3), and that step is bisected down to refine_deg:
                 stops_deg are the mechanical stops to about refine_deg.
    angles     : extra angles to record. Without limit_deg only these angles are
                 tested: the range is then NOT verified, so ok is False.
    Sampling: contact that starts and ends between two samples (narrower than
    step_deg) is not seen. The resolution is returned as step_deg / refine_deg.
    ok         : limit_deg given and no overlap at any sampled angle within +-limit.
    """
    def ov(a):
        return round((fixed ^ rotate(moving, a)).volume(), 4)

    if step_deg <= 0:
        raise ValueError("step_deg must be > 0")
    grid = set(float(a) for a in (angles or ()))
    if limit_deg is not None:
        n = int(math.floor(limit_deg / step_deg + 1e-9))
        grid.update(k * step_deg for k in range(-n, n + 1))
        grid.update((-float(limit_deg), float(limit_deg)))
    overlaps = {a: ov(a) for a in sorted(grid)}
    out = dict(overlap_mm3_at_deg=overlaps, step_deg=step_deg, sampled=True,
               explicit_angles_only=limit_deg is None, n_angles=len(overlaps))
    if limit_deg is None:
        lim = max((abs(a) for a in overlaps), default=0.0)
        out.update(limit_deg=None, tested_up_to_deg=lim, free_within_limit=None,
                   ok=False, note="only the supplied angles were tested; give limit_deg to verify a range")
        return out
    free = all(v <= tol_mm3 for v in overlaps.values())
    out.update(limit_deg=limit_deg, refine_deg=refine_deg, free_within_limit=free)

    def stop(sign):
        prev = float(limit_deg)
        a = prev
        while a < search_to:
            a = min(a + step_deg, search_to)
            if ov(sign * a) > tol_mm3:
                lo, hi = prev, a
                while hi - lo > refine_deg:
                    mid = (lo + hi) / 2
                    lo, hi = (lo, mid) if ov(sign * mid) > tol_mm3 else (mid, hi)
                return round(sign * hi, 3)
            prev = a
        return None
    out["stops_deg"] = [stop(-1), stop(1)]
    out["ok"] = bool(free)
    return out


def pose_chain(links: list, hinges: list, degs, rotate) -> list:
    """Pose a serial chain: link i sits after joints 0..i-1. Each link is turned
    about its nearest joint first, then outward, so every angle is relative to
    the parent link. rotate = callable (manifold, hinge, deg) -> manifold."""
    out = [links[0]]
    for i in range(1, len(links)):
        m = links[i]
        for j in range(i - 1, -1, -1):
            if degs[j]:
                m = rotate(m, hinges[j], degs[j])
        out.append(m)
    return out


def pairwise_overlaps(parts: list, names: list, tol_mm3: float = 0.05) -> list:
    """[name_a, name_b, volume] for every pair of parts overlapping by > tol_mm3."""
    hits = []
    for i in range(len(parts)):
        for k in range(i + 1, len(parts)):
            v = (parts[i] ^ parts[k]).volume()
            if v > tol_mm3:
                hits.append([names[i], names[k], round(v, 3)])
    return hits


def pose_report(posed: list, names: list, tol_mm3: float = 0.05, bed: bool = True) -> dict:
    """Collisions between posed parts plus the lowest point vs the bed (z >= 0,
    0.05 mm tolerance). ok = no part-part collision; bed_ok is reported apart."""
    hits = pairwise_overlaps(posed, names, tol_mm3)
    zs = [m.bounding_box()[2] for m in posed]
    low = {names[i]: round(z, 3) for i, z in enumerate(zs) if z < -0.05}
    return dict(ok=not hits, collisions=hits, z_min=round(min(zs), 3),
                bed_ok=(not low) if bed else None, below_bed=low)


# ---------------------------------------------------------------- walls
# thin_walls, z_thickness, min_wall_in_zones live in thickness.py
from .thickness import for_printer, gated, min_wall_in_zones, named_zones, thin_walls, z_thickness  # noqa: E402,F401
