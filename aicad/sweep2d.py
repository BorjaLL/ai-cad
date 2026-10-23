"""2D mechanism sweep: rotate side-view polygons through their motion and
report the smallest gap between parts that must not touch.

Use it before any 3D CAD to place pivots and stops: draw each part as a
shapely polygon in a side view, say how it moves as a function of one
parameter t (an angle, usually), and let the sweep find the first collision.

    parts = {"lid": lambda t: rotate_about(lid, t, pivot), "box": lambda t: box}
    rep = sweep(parts, [("lid", "box")], ts=range(0, 181, 5), min_gap=0.5)

Results are sampled at the spacing of ts (5 deg here) and refined to 0.01 deg
around local gap minima and the first violation.
"""
from __future__ import annotations

from shapely import affinity
from shapely.geometry.base import BaseGeometry


def rotate_about(geom: BaseGeometry, deg: float, origin) -> BaseGeometry:
    """Rotate a shapely geometry by deg (CCW) about origin (x, y)."""
    return affinity.rotate(geom, deg, origin=tuple(origin), use_radians=False)


def gap(a: BaseGeometry, b: BaseGeometry) -> float:
    """Signed gap: distance when apart, minus the overlap area's equivalent
    depth (-sqrt(area)) when they intersect with area, 0.0 when touching."""
    inter = a.intersection(b)
    if not inter.is_empty and inter.area > 1e-9:
        return -inter.area ** 0.5
    return a.distance(b)


def _refine_min(f, lo: float, hi: float, tol: float) -> tuple:
    """Golden-section search for the minimum of f on [lo, hi] -> (t, f(t))."""
    r = 0.6180339887498949
    c, d = hi - r * (hi - lo), lo + r * (hi - lo)
    fc, fd = f(c), f(d)
    while hi - lo > tol:
        if fc <= fd:
            hi, d, fd = d, c, fc
            c = hi - r * (hi - lo)
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + r * (hi - lo)
            fd = f(d)
    return (c, fc) if fc <= fd else (d, fd)


def sweep(parts: dict, pairs: list, ts, min_gap: float = 0.0, refine_tol: float = 0.01) -> dict:
    """Evaluate every pair at every t, then refine.

    parts  : name -> callable(t) returning a shapely geometry at state t
    pairs  : [(name_a, name_b), ...] that must stay at least min_gap apart
    ts     : states (angles in deg, usually), numeric, sorted ascending
    Sampled at the spacing of ts (reported as step), then refined: golden
    section around every local minimum of the gap (minimum found to refine_tol)
    and bisection between the last passing and the first failing t (first
    violation found to refine_tol). Contact narrower than one step that is not
    next to a local minimum of the samples is not seen.
    Returns per pair: the refined minimum gap, where it occurs, the first t
    that breaks min_gap, the sampled series, the step and ok.
    """
    ts = list(ts)
    if len(ts) < 2:
        raise ValueError("sweep needs at least two states in ts")
    step = max(b - a for a, b in zip(ts, ts[1:]))
    out = {}
    for a, b in pairs:
        def g(t, a=a, b=b):
            return gap(parts[a](t), parts[b](t))
        series = [(t, g(t)) for t in ts]
        t_min, g_min = min(series, key=lambda s: s[1])
        cands = []      # refined local minima: (t, gap)
        for i, (t, v) in enumerate(series):
            lo_v = series[i - 1][1] if i else float("inf")
            hi_v = series[i + 1][1] if i + 1 < len(series) else float("inf")
            if v < lo_v and v <= hi_v:
                lo_t = series[i - 1][0] if i else t
                hi_t = series[i + 1][0] if i + 1 < len(series) else t
                cands.append(_refine_min(g, lo_t, hi_t, refine_tol) if hi_t > lo_t else (t, v))
        t_ref, g_ref = min(cands + [(t_min, g_min)], key=lambda s: s[1])
        bad = [t for t, v in series if v < min_gap - 1e-9]
        bad += [t for t, v in cands if v < min_gap - 1e-9]
        first_bad = min(bad) if bad else None
        if first_bad is not None:
            prior = [t for t, v in series if t < first_bad and v >= min_gap - 1e-9]
            if prior:
                lo, hi = max(prior), first_bad
                while hi - lo > refine_tol:
                    mid = (lo + hi) / 2
                    lo, hi = (lo, mid) if g(mid) < min_gap - 1e-9 else (mid, hi)
                first_bad = round(hi, 4)
        out[f"{a}|{b}"] = dict(min_gap=round(g_ref, 3), at_t=round(t_ref, 3), first_violation_t=first_bad,
                               step=step, refine_tol=refine_tol,
                               series=[(t, round(v, 3)) for t, v in series], ok=first_bad is None)
    return dict(min_gap_required=min_gap, step=step, refine_tol=refine_tol, pairs=out,
                ok=all(v["ok"] for v in out.values()))


def free_range(parts: dict, pair: tuple, ts, min_gap: float = 0.0) -> tuple | None:
    """Longest run of consecutive sampled t values where the pair keeps min_gap
    (sampled at the spacing of ts, not refined; the true range can extend up to
    one step further at each end, or be broken by contact between samples)."""
    best, cur = None, []
    for t in ts:
        if gap(parts[pair[0]](t), parts[pair[1]](t)) >= min_gap - 1e-9:
            cur.append(t)
            if best is None or len(cur) > len(best):
                best = list(cur)
        else:
            cur = []
    return (best[0], best[-1]) if best else None


def draw_states(ax, parts: dict, ts, colours=None, alpha_min=0.15):
    """Overlay a few states on one matplotlib axis (earliest faint, last solid)."""
    from matplotlib.patches import Polygon as MplPolygon
    colours = colours or ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
    ts = list(ts)
    for k, t in enumerate(ts):
        a = alpha_min + (1 - alpha_min) * (k + 1) / len(ts)
        for i, (name, f) in enumerate(parts.items()):
            g = f(t)
            geoms = list(g.geoms) if hasattr(g, "geoms") else [g]
            for p in geoms:
                ax.add_patch(MplPolygon(list(p.exterior.coords), closed=True,
                                        fc=colours[i % len(colours)], ec="k", lw=0.4, alpha=a))
    ax.set_aspect("equal")
    ax.autoscale_view()
