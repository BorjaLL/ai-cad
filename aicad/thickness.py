"""Wall and roof thickness checks with per-piece findings.

- thin_walls(): in-layer (XY) feature width, layer by layer (2D opening).
- z_thickness(): material thinner than a minimum along Z (roofs, floors,
  bridges), by solid geometry on local tiles.
- min_wall_in_zones(): thinnest in-layer wall inside zones (bisection).

Both main checks return a dict with `ok`, a capped, sorted list of
`findings` (what is thin and where), what was `ignored` as a numerical
sliver and why (thresholds in `params`), and what each named zone
`excused`. Run heavy checks at low process priority (see docs/checks.md).

Zones: boxes (x0, x1, y0, y1, z0, z1) where thin material is intended (the
inside of a joint, a sacrificial roof over a pin hole). Pass a dict
{name: box} or a list of boxes (named zone0, zone1, ...).
"""
from __future__ import annotations

import math
import time

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, OpType

# Defaults for a 0.4 mm nozzle and 0.2 mm layers; for another setup pass
# for_printer(nozzle_mm, layer_mm) to both checks.
NOZZLE_MM = 0.4
LAYER_MM = 0.2


def for_printer(nozzle_mm: float = NOZZLE_MM, layer_mm: float = LAYER_MM) -> dict:
    """Keyword arguments that tie both checks to one nozzle (line width) and
    layer height: sections and Z steps every layer, hard floors of one line
    in XY and two layers in Z, footprint filter of one line.
        kw = for_printer(0.6, 0.3)
        thin_walls(m, 1.2, **kw["thin_walls"]); z_thickness(m, 0.9, **kw["z_thickness"])"""
    if nozzle_mm <= 0 or layer_mm <= 0:
        raise ValueError("nozzle_mm and layer_mm must be > 0")
    return dict(thin_walls=dict(layer=layer_mm, hard_min_mm=nozzle_mm),
                z_thickness=dict(step=layer_mm, min_footprint=nozzle_mm, hard_min_mm=2 * layer_mm))
SHEET_TOL_MM = 1e-4
HAIRLINE_MM = 0.01


def gated(result: dict, gate: str = "ok_hard") -> dict:
    """A thickness result for verification.json with the gate chosen
    explicitly: ok = result[gate] (the stop), and the findings behind the
    advisory `ok` kept under "review" (a list to read, not a stop).
    write_verification ANDs every "ok" key, so the raw result would make the
    advisory ok a stop; this copy carries only the gate's ok.
        checks = dict(walls=gated(thin_walls(m, 0.8)), roofs=gated(z_thickness(m, 0.6)))"""
    if gate not in ("ok_hard", "ok", "ok_strict") or gate not in result:
        raise ValueError(f"gated: gate must be a flag of this result (ok_hard, ok, ok_strict), got {gate!r}")
    review = {k: result[k] for k in ("n_findings", "groups", "findings", "ignored", "excused_by_zone",
                                     "params", "n_hard", "verified") if k in result}
    return dict(check=result.get("check"), gate=gate, ok=bool(result[gate]),
                advisory_ok=bool(result["ok"]), review=review)


# ---------------------------------------------------------------- zones
def named_zones(zones) -> dict:
    """{name: (x0, x1, y0, y1, z0, z1)} from a dict, a list of boxes or None."""
    if not zones:
        return {}
    if isinstance(zones, dict):
        items = zones.items()
    else:
        items = ((f"zone{i}", b) for i, b in enumerate(zones))
    out = {}
    for k, b in items:
        b = tuple(float(v) for v in b)
        if len(b) != 6 or b[0] > b[1] or b[2] > b[3] or b[4] > b[5]:
            raise ValueError(f"zone {k!r} must be (x0, x1, y0, y1, z0, z1) with x0<=x1 etc, got {b}")
        out[str(k)] = b
    return out


def _box_manifold(b) -> Manifold:
    return Manifold.cube([b[1] - b[0], b[3] - b[2], b[5] - b[4]]).translate([b[0], b[2], b[4]])


def _pt_in_box(x, y, z, b, tol=1e-6):
    return (b[0] - tol <= x <= b[1] + tol and b[2] - tol <= y <= b[3] + tol
            and b[4] - tol <= z <= b[5] + tol)


def _r(v, n=3):
    return None if v is None else round(float(v), n)


def _bbox6(bb):
    """manifold (x0, y0, z0, x1, y1, z1) -> rounded [x0, y0, z0, x1, y1, z1]."""
    return [round(float(v), 2) for v in bb]


def _merge_touching(findings, key_sum=("volume_mm3",), tol=1e-3):
    """Merge findings whose 3D bboxes touch (one feature cut by a tile edge)."""
    items = [dict(f) for f in findings]
    changed = True
    while changed:
        changed = False
        out = []
        for f in items:
            for g in out:
                a, b = f["bbox"], g["bbox"]
                if all(a[i] <= b[i + 3] + tol and b[i] <= a[i + 3] + tol for i in range(3)):
                    g["bbox"] = [min(a[i], b[i]) for i in range(3)] + [max(a[i + 3], b[i + 3]) for i in range(3)]
                    for k in key_sum:
                        g[k] = round(g[k] + f[k], 4)
                    # keep the narrowest reading: a merge must never hide a thin
                    # region behind a wider one in the same feature
                    for k, fn in (("thickness_min_mm", min), ("thickness_max_mm", max),
                                  ("width_mm", min), ("width_max_mm", max)):
                        if k in g or k in f:
                            vals = [v for v in (g.get(k), f.get(k)) if v is not None]
                            g[k] = fn(vals) if vals else None
                    for k in ("n_pieces", "n_rays_thin", "layers", "layers_hard"):
                        if k in g:
                            g[k] = g[k] + f.get(k, 0)
                    changed = True
                    break
            else:
                out.append(f)
        items = out
    return items


def _groups(findings, measure: str, max_groups: int = 10):
    """Repeated features (same bbox size, volume and measure to 0.01) as one
    line each: count, size, measure and up to 3 example bbox origins."""
    g = {}
    for f in findings:
        b = f["bbox"]
        key = (round(b[3] - b[0], 2), round(b[4] - b[1], 2), round(b[5] - b[2], 2),
               round(f["volume_mm3"], 2), f.get(measure))
        g.setdefault(key, []).append(b[:3])
    out = [dict(n=len(v), size_xyz=list(k[:3]), volume_mm3=k[3], **{measure: k[4]}, at=v[:3])
           for k, v in g.items()]
    out.sort(key=lambda d: -d["n"] * d["volume_mm3"])
    return out[:max_groups]


# ---------------------------------------------------------------- z thickness
def _z_candidate_boxes(m: Manifold, min_mm: float):
    """XY boxes that together contain every point where a vertical solid span
    shorter than min_mm can exist. Complete, not exact: a span's bottom lies
    on a down-facing triangle D and its top on an up-facing triangle U above
    it at the same XY, so D's and U's XY boxes overlap and U's Z range meets
    [D.zmin, D.zmax + min_mm]. Every D with such a U is returned (its XY box)."""
    from rtree import index

    mesh = m.to_mesh()
    V = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    F = np.asarray(mesh.tri_verts, dtype=np.int64)
    if len(F) == 0:
        return np.zeros((0, 4))
    T = V[F]
    nz = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])[:, 2]
    lo, hi = T.min(axis=1), T.max(axis=1)
    down, up = np.flatnonzero(nz < 0), np.flatnonzero(nz > 0)
    if len(down) == 0 or len(up) == 0:
        return np.zeros((0, 4))
    p = index.Property()
    p.dimension = 3
    ub = np.hstack([lo[up], hi[up]])
    idx = index.Index(((i, tuple(b), None) for i, b in enumerate(ub)), properties=p)
    qlo = lo[down].copy()
    qhi = hi[down].copy()
    qhi[:, 2] += min_mm
    _, counts = idx.intersection_v(np.ascontiguousarray(qlo), np.ascontiguousarray(qhi))
    hit = down[np.asarray(counts) > 0]
    return np.column_stack([lo[hit, 0], lo[hit, 1], hi[hit, 0], hi[hit, 1]])


def _n_shifts(min_mm: float, step: float) -> int:
    return max(1, math.ceil((min_mm - step) / step - 1e-9))


def _thin_in(m: Manifold, min_mm: float, step: float, simplify_mm: float = 0.0) -> Manifold:
    """Material of m in a vertical solid span shorter than min_mm (shifted
    intersections, then grown back). simplify_mm > 0: each intermediate
    result is simplified at that tolerance, which stops the triangle count
    from multiplying on finely tessellated curved surfaces."""
    n = _n_shifts(min_mm, step)
    shifts = [k * (min_mm - step) / n for k in range(1, n + 1)]

    def s(x):
        return x.simplify(simplify_mm) if simplify_mm > 0 else x

    core = m
    for dz in shifts:
        core = s(core ^ m.translate([0.0, 0.0, -dz]))
    if core.is_empty():
        return m
    grown = s(Manifold.batch_boolean([core] + [core.translate([0.0, 0.0, dz]) for dz in shifts],
                                     OpType.Add))
    # the difference leaves zero-thickness sheets on sloped faces (near-
    # coplanar leftovers) that inflate a piece's XY footprint; simplify at
    # 1e-4 mm removes them (surfaces move < 1e-4 mm, volume unchanged)
    return (m - grown).simplify(SHEET_TOL_MM)


def _footprint(piece: Manifold) -> CrossSection:
    return CrossSection(piece.project().to_polygons(), FillRule.Positive)


def _slope(n) -> np.ndarray:
    """(dz/dx, dz/dy) of a surface with normal n; inf for a vertical face."""
    nx, ny, nz = (float(v) for v in n)
    if abs(nz) < 1e-6:
        return np.array([math.inf, math.inf])
    return np.array([-nx / nz, -ny / nz])


def _spans(m: Manifold, x: float, y: float, z0: float, z1: float, zlo: float, zhi: float):
    """Solid intervals of m along the vertical line at (x, y) that overlap
    [zlo, zhi], as (length, taper): taper = how fast the span length changes
    sideways (mm per mm), from the slopes of its bottom and top faces. None if
    the hits do not pair up."""
    hits = m.ray_cast([x, y, z0], [x, y, z1])
    # h.distance is a fraction of the segment: use the position
    hs = sorted(((float(h.position[2]), h.normal) for h in hits), key=lambda t: t[0])
    if not hs:
        return []
    ded = [hs[0]]   # drop duplicate hits on shared edges
    for z, n in hs[1:]:
        if z - ded[-1][0] > 1e-6:
            ded.append((z, n))
    if len(ded) % 2:
        return None
    out = []
    for (a, na), (b, nb) in zip(ded[0::2], ded[1::2]):
        if b >= zlo - 1e-6 and a <= zhi + 1e-6:
            g = _slope(nb) - _slope(na)
            out.append((b - a, float(np.hypot(g[0], g[1])) if np.all(np.isfinite(g)) else math.inf))
    return out


def _inside(polys, px, py):
    """Even-odd point-in-polygon for arrays of points against a polygon list."""
    inside = np.zeros(len(px), dtype=bool)
    for poly in polys:
        p = np.asarray(poly, dtype=np.float64)
        if len(p) < 3:
            continue
        xa, ya = p[:, 0], p[:, 1]
        xb, yb = np.roll(xa, -1), np.roll(ya, -1)
        for i in range(len(p)):
            c = (ya[i] > py) != (yb[i] > py)
            with np.errstate(divide="ignore", invalid="ignore"):
                xc = xa[i] + (py - ya[i]) * (xb[i] - xa[i]) / (yb[i] - ya[i])
            inside ^= c & (px < xc)
    return inside


def _sample_points(cs: CrossSection, k: int):
    """Up to k vertices of cs plus up to k grid points inside it (so a piece
    whose edges are tapered is also sampled in its middle)."""
    polys = [np.asarray(poly) for poly in cs.to_polygons()]
    pts = [p for poly in polys for p in poly]
    if not pts:
        return []
    pts = np.asarray(pts)
    if len(pts) > k:
        pts = pts[np.linspace(0, len(pts) - 1, k).astype(int)]
    out = [tuple(map(float, p)) for p in pts]
    x0, y0, x1, y1 = cs.bounds()
    n = max(2, math.ceil(math.sqrt(4 * k)))
    gx, gy = np.meshgrid(np.linspace(x0, x1, n + 2)[1:-1], np.linspace(y0, y1, n + 2)[1:-1])
    gx, gy = gx.ravel(), gy.ravel()
    sel = _inside(polys, gx, gy)
    g = np.column_stack([gx[sel], gy[sel]])
    if len(g) > k:
        g = g[np.linspace(0, len(g) - 1, k).astype(int)]
    return out + [tuple(map(float, p)) for p in g]


def _classify_z_piece(piece: Manifold, leaf: Manifold, min_mm: float, min_footprint: float,
                      min_piece_volume: float, n_rays: int, zmin: float, zmax: float,
                      min_taper: float = math.inf):
    """-> (reason_ignored or None, finding dict)."""
    vol = piece.volume()
    bb = piece.bounding_box()
    f = dict(volume_mm3=round(vol, 4), bbox=_bbox6(bb), n_pieces=1)
    if vol < min_piece_volume:
        return "volume", f
    fp = _footprint(piece)
    f["footprint_area_mm2"] = round(fp.area(), 3)
    core = fp.offset(-min_footprint / 2, JoinType.Round, 2.0, 16)
    if core.is_empty() or core.area() <= 1e-9:
        return "footprint", f
    # measure real span lengths at points inside the footprint core
    th, flat, n_valid = [], [], 0
    for x, y in _sample_points(core, n_rays):
        ls = _spans(leaf, x, y, zmin - 1.0, zmax + 1.0, bb[2], bb[5])
        if ls is None or not ls:
            continue           # odd hit count (edge graze) or no span: no evidence
        n_valid += 1
        for v, taper in ls:
            if v < min_mm + 1e-6:
                th.append(v)
                if taper < min_taper:
                    flat.append(v)
    f["n_rays"] = n_valid
    f["n_rays_thin"] = len(th)
    f["n_rays_thin_flat"] = len(flat)
    # a piece with any parallel-faced thin span is measured by those spans
    use = flat or th
    f["thickness_min_mm"] = _r(min(use)) if use else None
    f["thickness_max_mm"] = _r(max(use)) if use else None
    if n_valid > 0 and not th:
        # a real thin piece is thin at every point of its footprint; every
        # sampled vertical span through it is >= min_mm: a boolean skin artifact
        return "rays", f
    if th and not flat:
        # every thin span sampled sits between non-parallel faces whose
        # distance grows sideways by >= min_taper mm per mm: the thin edge of a
        # chamfer, a slope meeting the bed or a rounded body, not a plate
        return "taper", f
    return None, f


def z_thickness(m: Manifold, min_mm: float, step: float = LAYER_MM, zones=None,
                min_footprint: float = NOZZLE_MM, min_piece_volume: float = 1e-3,
                max_tile_tris: int = 20000, min_tile_mm: float = 2.0, simplify_mm: float = 0.01,
                time_budget_s: float = 300.0, max_findings: int = 20,
                n_rays: int = 9, max_input_tris: int = 2_000_000, min_taper: float = 0.36,
                hard_min_mm: float | None = None, log=None) -> dict:
    """Material thinner than min_mm along Z (thin roofs, floors, bridges).

    Method (exact in XY where it runs, no ray grid to fall between):
    1. Candidates: every down-facing triangle that has an up-facing triangle
       above it within min_mm (overlapping XY boxes, rtree). This set is
       complete for the mesh it runs on (the simplified mesh when
       simplify_mm > 0, within params.surface_error_bound_mm of the input):
       a thin span cannot exist outside the candidates' XY boxes.
    2. The part is split in XY (full-height prisms, which keeps every
       vertical span intact) until each piece holding candidates has at most
       max_tile_tris triangles; pieces with no candidates are skipped, proven
       thick by step 1.
    3. In each tile: K = solid with at least min_mm of solid above it
       (intersection of copies shifted down in `step` increments), grown
       back up; thin = tile - grown.
    4. Each thin piece is classified:
       - ignored "volume": volume < min_piece_volume (numerical crumbs);
       - ignored "footprint": its XY footprint vanishes when eroded by
         min_footprint / 2, i.e. it is narrower than min_footprint everywhere
         (a rim at a rounded silhouette, a facet sliver). A roof narrower than
         a nozzle line is an in-layer width problem: thin_walls() covers it;
       - ignored "rays": vertical rays at up to n_rays points inside the
         footprint core all cross a solid span >= min_mm. A real thin piece
         is thin at every point of its footprint, so this refutes it: it is
         a skin left by near-tangent facets in the shifted booleans. A piece
         where no ray gives a clean reading is kept as a finding;
       - ignored "taper": every thin span sampled (piece vertices and an
         interior grid) lies between non-parallel faces, so its length grows
         sideways by at least min_taper mm per mm (0.36: a face 20 deg off
         the other one). That is the thin edge of a chamfer, of a slope
         meeting the bed or of a rounded body sitting on the bed: a wedge,
         thin only within about min_mm / min_taper (1.7 mm at the defaults)
         of where it reaches min_mm. A roof or plate has parallel faces and
         is kept; one parallel-faced thin span keeps the piece.
         min_taper=math.inf turns this filter off;
       - excused by a zone (the part inside a zone box);
       - otherwise a finding: bbox, volume, footprint area and the measured
         span thickness at up to n_rays points inside the footprint.
    Big meshes: the part is first simplified at simplify_mm (surfaces move
    less than that) and every intermediate boolean at simplify_mm / 4.
    Without it, dense curved meshes multiply their triangle count in the
    shifted intersections (8k triangles -> 200k in one tile) and can hang
    or crash the native library. The resulting bound on how far a thin
    surface can be off is params.surface_error_bound_mm (0.018 mm by
    default); spans within that of min_mm can go either way. simplify_mm=0
    turns it off (exact, slow). time_budget_s is ADVISORY, not a runtime
    bound: it is checked between tiles, after simplification and the
    candidate pass, so one slow step can overrun it. max_input_tris refuses
    oversized meshes up front. Run heavy checks at low process priority.
    Limits: a void thinner than `step` in Z inside a span can be missed (the
    default step is one layer: such a gap cannot print anyway); spans between
    min_mm - step and min_mm are only partly flagged; a piece cut by a tile
    edge is re-merged by bbox contact. If time_budget_s runs out, the
    remaining tiles are unverified: verified False, ok False, never ok.
    ok = verified and no findings outside zones UNDER THE STATED FILTERS:
    pieces ignored by volume or footprint are not proof of absence.
    ok_strict = ok and no piece ignored by volume or footprint (pieces
    refuted by rays were measured thick and do not count against it) and
    simplification lost no body and no more volume than its error bound
    (a feature thinner than simplify_mm can vanish in it). Tapers count
    against ok_strict: they are thin, just not plates.
    ok_hard = verified and no finding thinner than hard_min_mm (default two
    layers, 2 * step): a one-layer roof or skin. A finding with no clean ray
    reading counts against it. hard_min_mm above min_mm is refused
    (ValueError): those spans would never be candidates.
    ok_hard is a filtered geometry check, not a promise that the part
    prints: it only says no measured plate is under hard_min_mm after the
    filters above. Use it as the stop gate and the findings behind ok as the
    review list for your design minimum.
    """
    if min_mm <= 0 or step <= 0:
        raise ValueError("min_mm and step must be > 0")
    if step >= min_mm:
        raise ValueError("step must be smaller than min_mm")
    hard = 2 * step if hard_min_mm is None else hard_min_mm
    if hard > min_mm + 1e-9:
        # candidates are spans < min_mm: spans in [min_mm, hard) would never be seen
        raise ValueError(f"z_thickness: hard_min_mm={hard} (default 2 * step) is above min_mm={min_mm}: "
                         "spans between them would go unchecked; raise min_mm or lower hard_min_mm")
    zs = named_zones(zones)
    t0 = time.perf_counter()
    n_in = m.num_tri()
    if n_in > max_input_tris:
        raise ValueError(f"z_thickness: {n_in} triangles > max_input_tris={max_input_tris}; "
                         "simplify or split the part first, or raise the limit knowingly")
    step_tol = simplify_mm / 4
    simplify_loss = None
    if simplify_mm > 0:
        v_in, b_in = m.volume(), len(m.decompose())
        m = m.simplify(simplify_mm)
        v_out, b_out = m.volume(), len(m.decompose())
        # a surface moving <= simplify_mm changes volume by <= area * simplify_mm
        dv_ok = abs(v_out - v_in) <= m.surface_area() * simplify_mm + 1e-9
        if b_in != b_out or not dv_ok:
            simplify_loss = dict(bodies_before=b_in, bodies_after=b_out,
                                 volume_before_mm3=round(v_in, 4), volume_after_mm3=round(v_out, 4))
    # every surface of the thin set is within this of the exact result
    err_mm = simplify_mm + (_n_shifts(min_mm, step) + 1) * step_tol + SHEET_TOL_MM
    x0, y0, z0, x1, y1, z1 = m.bounding_box()
    cand = _z_candidate_boxes(m, min_mm)
    t_cand = time.perf_counter() - t0
    say = log or (lambda msg: None)
    say(f"z_thickness: {n_in} tris, {m.num_tri()} after simplify({simplify_mm}), {len(cand)} candidate triangles ({t_cand:.1f}s)")

    findings, ignored = [], {"volume": [0, 0.0], "footprint": [0, 0.0], "rays": [0, 0.0],
                             "taper": [0, 0.0]}
    excused = {k: dict(n_pieces=0, volume_mm3=0.0, pieces=[]) for k in zs}
    stats = dict(tiles_checked=0, tiles_skipped_no_candidates=0, tiles_unverified=0,
                 max_tile_tris=0, unverified_bboxes=[])

    def handle_leaf(leaf: Manifold):
        thin = _thin_in(leaf, min_mm, step, step_tol)
        if thin.is_empty():
            return
        for name, b in zs.items():
            lb = leaf.bounding_box()
            if b[0] > lb[3] or b[1] < lb[0] or b[2] > lb[4] or b[3] < lb[1]:
                continue
            zb = _box_manifold(b)
            inside, thin = thin.split(zb)
            for pc in inside.decompose():
                why, f = _classify_z_piece(pc, leaf, min_mm, min_footprint, min_piece_volume,
                                           n_rays, z0, z1, min_taper)
                if why:
                    ignored[why][0] += 1
                    ignored[why][1] += f["volume_mm3"]
                else:
                    e = excused[name]
                    e["n_pieces"] += 1
                    e["volume_mm3"] += f["volume_mm3"]
                    e["pieces"].append(f)
        for pc in thin.decompose():
            why, f = _classify_z_piece(pc, leaf, min_mm, min_footprint, min_piece_volume,
                                       n_rays, z0, z1, min_taper)
            if why:
                ignored[why][0] += 1
                ignored[why][1] += f["volume_mm3"]
            else:
                findings.append(f)

    def recurse(part: Manifold, box, cb):
        # box = (x0, y0, x1, y1); cb = candidate boxes overlapping it
        if part.is_empty():
            return
        if len(cb) == 0:
            stats["tiles_skipped_no_candidates"] += 1
            return
        if time.perf_counter() - t0 > time_budget_s:
            stats["tiles_unverified"] += 1
            stats["unverified_bboxes"].append([round(v, 2) for v in box])
            return
        w, h = box[2] - box[0], box[3] - box[1]
        if part.num_tri() > max_tile_tris and max(w, h) > min_tile_mm:
            if w >= h:
                c = (box[0] + box[2]) / 2
                hi_p, lo_p = part.split_by_plane([1.0, 0.0, 0.0], c)
                boxes = ((box[0], box[1], c, box[3]), (c, box[1], box[2], box[3]))
            else:
                c = (box[1] + box[3]) / 2
                hi_p, lo_p = part.split_by_plane([0.0, 1.0, 0.0], c)
                boxes = ((box[0], box[1], box[2], c), (box[0], c, box[2], box[3]))
            for p, bx in ((lo_p, boxes[0]), (hi_p, boxes[1])):
                sel = ((cb[:, 0] <= bx[2]) & (cb[:, 2] >= bx[0]) & (cb[:, 1] <= bx[3]) & (cb[:, 3] >= bx[1]))
                recurse(p, bx, cb[sel])
            return
        stats["tiles_checked"] += 1
        stats["max_tile_tris"] = max(stats["max_tile_tris"], part.num_tri())
        tl = time.perf_counter()
        handle_leaf(part)
        say(f"  tile {stats['tiles_checked']} {[round(v, 1) for v in box]} {part.num_tri()} tris "
            f"{len(cb)} cands {time.perf_counter() - tl:.1f}s (t={time.perf_counter() - t0:.0f}s)")

    recurse(m, (x0, y0, x1, y1), cand)
    findings = _merge_touching(findings)
    findings.sort(key=lambda f: -f["volume_mm3"])
    for e in excused.values():
        e["volume_mm3"] = round(e["volume_mm3"], 4)
        e["pieces"] = sorted(_merge_touching(e["pieces"]), key=lambda f: -f["volume_mm3"])[:5]
    verified = stats["tiles_unverified"] == 0
    n_hard = sum(1 for f in findings
                 if f.get("thickness_min_mm") is None or f["thickness_min_mm"] < hard - 1e-6)
    stats["unverified_bboxes"] = stats["unverified_bboxes"][:10]
    out = dict(
        check="z_thickness", method="complete candidate filter + solid geometry on XY tiles",
        min_mm=min_mm, step_mm=step,
        params=dict(min_footprint_mm=min_footprint, min_piece_volume_mm3=min_piece_volume,
                    min_taper_mm_per_mm=min_taper, hard_min_mm=hard,
                    max_tile_tris=max_tile_tris, time_budget_s=time_budget_s, simplify_mm=simplify_mm,
                    triangles_in=n_in, triangles_simplified=m.num_tri(),
                    surface_error_bound_mm=round(err_mm, 4)),
        n_findings=len(findings), findings_volume_mm3=round(sum(f["volume_mm3"] for f in findings), 4),
        groups=_groups(findings, "thickness_min_mm"), findings=findings[:max_findings],
        ignored={
            f"volume_below_{min_piece_volume}_mm3": dict(n_pieces=ignored["volume"][0],
                                                         volume_mm3=round(ignored["volume"][1], 4)),
            f"footprint_narrower_than_{min_footprint}_mm": dict(n_pieces=ignored["footprint"][0],
                                                                 volume_mm3=round(ignored["footprint"][1], 4)),
            f"every_sampled_span_at_least_{min_mm}_mm": dict(n_pieces=ignored["rays"][0],
                                                             volume_mm3=round(ignored["rays"][1], 4)),
            f"taper_at_least_{min_taper}_mm_per_mm": dict(n_pieces=ignored["taper"][0],
                                                          volume_mm3=round(ignored["taper"][1], 4)),
        },
        excused_by_zone=excused, tiles=stats, candidate_triangles=int(len(cand)),
        seconds=dict(candidates=round(t_cand, 2), total=round(time.perf_counter() - t0, 2)),
        verified=verified, ok=bool(verified and not findings),
        ok_strict=bool(verified and not findings and simplify_loss is None
                       and ignored["volume"][0] == 0 and ignored["footprint"][0] == 0
                       and ignored["taper"][0] == 0),
        n_hard=n_hard, ok_hard=bool(verified and n_hard == 0))
    if simplify_loss:
        out["simplify_loss"] = simplify_loss
        out["note_simplify"] = ("simplification removed bodies or more volume than the error "
                                "bound allows (features thinner than simplify_mm): ok_strict False")
    if not verified:
        out["note"] = (f"time budget {time_budget_s}s ran out: {stats['tiles_unverified']} tiles with "
                       "candidates were not checked; raise time_budget_s or check a smaller region")
    return out


# ---------------------------------------------------------------- walls
def _inscribed_width(cs: CrossSection, hi: float, iters: int = 7) -> float:
    """Diameter of the largest disc inside cs (its widest point), by bisection
    on inward offsets, to about hi / 2^iters."""
    lo = 0.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if cs.offset(-mid / 2, JoinType.Round, 2.0, 16).is_empty():
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _lost_pieces(cs: CrossSection, r: float, min_area: float, min_len: float, counts=None):
    """Pieces of a section that vanish under a 2D opening by r (erode, dilate).
    -> list of (area, width_estimate, (bx0, by0, bx1, by1))."""
    op = cs.offset(-r, JoinType.Round, 2.0, 32).offset(r, JoinType.Round, 2.0, 32)
    lost = cs - op
    # hairlines where the offset boundary differs from the section by rounding
    h = HAIRLINE_MM / 2
    lost = lost.offset(-h, JoinType.Miter, 2.0, 8).offset(h, JoinType.Miter, 2.0, 8)
    out = []
    for piece in lost.decompose():
        a = piece.area()
        if a < min_area:
            if counts is not None:
                counts["area"] += 1
            continue
        bx0, by0, bx1, by1 = piece.bounds()
        if max(bx1 - bx0, by1 - by0) < min_len:
            if counts is not None:
                counts["length"] += 1
            continue   # convex-corner rounding, not a wall
        out.append((a, _inscribed_width(piece, 2 * r), (bx0, by0, bx1, by1)))
    return out


def thin_walls(m: Manifold, min_feature: float, zones=None, layer: float = LAYER_MM,
               min_area: float = 0.2, min_len: float = 2.0, max_findings: int = 20,
               time_budget_s: float = 300.0, zone_min_wall: bool = True,
               hard_min_mm: float = NOZZLE_MM, min_layers: int = 2) -> dict:
    """In-layer (XY) feature width: walls or pins narrower than min_feature (mm),
    found layer by layer. Says nothing about thickness along Z: use z_thickness().
    ok = verified and no findings outside zones under the stated filters
    (ignored pieces are counted, not proven absent; a feature lying between
    two sampled layers is not seen). time_budget_s is advisory (checked
    between layers).

    Each layer section (every `layer` mm) is opened by r = min_feature / 2;
    pieces that disappear are walls or pins thinner than min_feature. Pieces
    are ignored (and counted) when their area is below min_area mm2 or their
    longest side below min_len mm (convex-corner rounding, facet crumbs).
    Pieces in consecutive layers with touching XY boxes are merged into one
    finding: 3D bbox, number of layers, volume (area x layer), width_mm and
    width_max_mm. Per layer the width is the widest point of the lost piece
    (largest inscribed disc, so a wall reported 0.5 is at most 0.5 wide
    there); after merging width_mm is the narrowest layer's value and
    width_max_mm the widest, and layers_hard counts layers under hard_min_mm. Hairlines under HAIRLINE_MM
    left by the offset rounding are removed first.
    A piece is excused by a zone only when its whole XY box lies in the zone
    at that layer; a piece partly outside stays a finding.
    A merged piece seen in fewer than min_layers sampled layers is ignored
    and counted: on curved or sloped surfaces one layer's section often has
    a thin crescent that the next layer does not (the layer cuts the surface
    near its tangent); a real fin or wall shows up in several layers.
    Limits: a wall shorter than min_len or smaller than min_area per layer is
    not reported; a feature at most about one layer tall (min_layers=2) is
    counted, not reported; features between two sampled layers are not seen.
    ok = every layer checked within time_budget_s and no finding outside zones.
    ok_hard = verified and no finding with at least min_layers layers whose
    widest point is under hard_min_mm (default one nozzle line): narrower
    than one extrusion line there, so the slicer may drop it or print it as
    one weak bead. Judged per layer before merging. hard_min_mm above
    min_feature is refused (ValueError). ok_hard is a filtered geometry
    check, not a promise that the part prints. A wall between
    one line and min_feature (say 0.6 for min_feature 0.8) prints with a
    variable-width wall generator; it counts against ok, not ok_hard.
    """
    if hard_min_mm > min_feature + 1e-9:
        # the opening only removes features narrower than min_feature
        raise ValueError(f"thin_walls: hard_min_mm={hard_min_mm} is above min_feature={min_feature}: "
                         "walls between them would go unchecked; raise min_feature or lower hard_min_mm")
    zs = named_zones(zones)
    r = min_feature / 2
    t0 = time.perf_counter()
    x0, y0, z0, x1, y1, z1 = m.bounding_box()
    counts = {"area": 0, "length": 0}
    per_zone = {k: [] for k in zs}
    raw = []   # (z, area, width, bbox2d)
    layers = np.arange(z0 + layer / 2, z1, layer)
    done = 0
    for z in layers:
        if time.perf_counter() - t0 > time_budget_s:
            break
        done += 1
        cs = m.slice(float(z))
        if cs.is_empty():
            continue
        for a, w, b in _lost_pieces(cs, r, min_area, min_len, counts):
            # excused only when the whole lost piece lies in the zone (in XY,
            # at this layer): a small zone cannot excuse a long wall
            zone = next((k for k, zb in zs.items()
                         if _pt_in_box(b[0], b[1], z, zb) and _pt_in_box(b[2], b[3], z, zb)), None)
            f = dict(volume_mm3=round(a * layer, 4), bbox=[b[0], b[1], float(z) - layer / 2,
                                                            b[2], b[3], float(z) + layer / 2],
                     width_mm=_r(w), width_max_mm=_r(w), layers=1,
                     layers_hard=int(w < hard_min_mm - 1e-6))
            (per_zone[zone] if zone else raw).append(f)

    def finish(fs):
        fs = _merge_touching(fs, key_sum=("volume_mm3",))
        for f in fs:
            f["bbox"] = [round(v, 2) for v in f["bbox"]]
        return sorted(fs, key=lambda f: -f["volume_mm3"])

    findings = finish(raw)
    short = [f for f in findings if f["layers"] < min_layers]
    findings = [f for f in findings if f["layers"] >= min_layers]
    verified = done == len(layers)
    # judged per layer before merging: a feature is hard when at least
    # min_layers of its layers are under hard_min_mm (merging never hides a
    # narrow stretch under a wider one above it)
    n_hard = sum(1 for f in findings if f["layers_hard"] >= min_layers)
    out = dict(check="xy_feature_width", min_feature_mm=min_feature, layer_mm=layer,
               params=dict(min_area_mm2=min_area, min_len_mm=min_len, hard_min_mm=hard_min_mm,
                           min_layers=min_layers),
               n_findings=len(findings), groups=_groups(findings, "width_mm"),
               findings=findings[:max_findings],
               ignored={f"area_below_{min_area}_mm2": dict(n_layer_pieces=counts["area"]),
                        f"shorter_than_{min_len}_mm": dict(n_layer_pieces=counts["length"]),
                        f"fewer_than_{min_layers}_layers": dict(
                            n_features=len(short), volume_mm3=round(sum(f["volume_mm3"] for f in short), 4),
                            narrowest_mm=min((f["width_mm"] for f in short), default=None))},
               excused_by_zone={k: _zone_summary(finish(fs)) for k, fs in per_zone.items()},
               layers_checked=done, layers_total=int(len(layers)),
               seconds=round(time.perf_counter() - t0, 2), verified=verified,
               ok=bool(verified and not findings), n_hard=n_hard,
               ok_hard=bool(verified and n_hard == 0))
    if not verified:
        out["note"] = f"time budget {time_budget_s}s ran out after {done} of {len(layers)} layers"
    if zs and zone_min_wall:
        out["zone_min_wall"] = min_wall_in_zones(m, list(zs.values()), layer, min_area, min_len)
    return out


def _zone_summary(fs):
    return dict(n_features=len(fs), volume_mm3=round(sum(f["volume_mm3"] for f in fs), 4), features=fs[:5])


def min_wall_in_zones(m: Manifold, zones, layer: float = LAYER_MM, min_area: float = 0.2,
                      min_len: float = 2.0, lo: float = 0.05, hi: float = 1.0,
                      iters: int = 8) -> dict:
    """Smallest 2r at which an opening loses a piece whose centre lies in a
    zone: the thinnest wall there, to about (hi - lo) / 2^iters * 2 mm."""
    boxes = list(named_zones(zones).values())
    zmin = max(m.bounding_box()[2], min(b[4] for b in boxes))
    zmax = min(m.bounding_box()[5], max(b[5] for b in boxes))
    slices = []
    for z in np.arange(zmin + layer / 2, zmax, layer):
        cs = m.slice(float(z))
        if not cs.is_empty():
            slices.append((float(z), cs))

    def find(r):
        for z, cs in slices:
            for a, _w, b in _lost_pieces(cs, r, min_area, min_len):
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                if any(_pt_in_box(cx, cy, z, zb) for zb in boxes):
                    return (round(cx, 1), round(cy, 1), round(z, 2), round(a, 2))
        return None

    hit = find(hi)
    if hit is None:
        return dict(min_wall_mm=f">{2 * hi}", at_x_y_z_area=None)
    for _ in range(iters):
        mid = (lo + hi) / 2
        h = find(mid)
        if h is None:
            lo = mid
        else:
            hi, hit = mid, h
    return dict(min_wall_mm=round(2 * hi, 2), at_x_y_z_area=list(hit))
