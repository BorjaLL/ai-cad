"""Mesh conversions and basic mesh checks.

manifold3d does the robust booleans; trimesh does file IO, rays and reports.
These helpers move meshes between the two and answer "is this printable as one
closed shell?".
"""
from __future__ import annotations

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh


def to_trimesh(m: Manifold) -> trimesh.Trimesh:
    """manifold3d Manifold -> trimesh.Trimesh (no processing, vertices kept as is)."""
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=False)


def to_manifold(tm: trimesh.Trimesh) -> Manifold:
    """trimesh.Trimesh -> manifold3d Manifold. The mesh must be closed and oriented."""
    return Manifold(Mesh(vert_properties=np.asarray(tm.vertices, dtype=np.float32),
                         tri_verts=np.asarray(tm.faces, dtype=np.uint32)))


def to_bed(m: Manifold) -> Manifold:
    """Translate so the bounding box starts at x = y = z = 0 (sits on the bed)."""
    x0, y0, z0, *_ = m.bounding_box()
    return m.translate([-x0, -y0, -z0])


def centre_on_bed(m: Manifold, bed_xy: float) -> Manifold:
    """Centre the part in X and Y on a square bed of side bed_xy, bottom at z = 0."""
    x0, y0, z0, x1, y1, _ = m.bounding_box()
    return m.translate([bed_xy / 2 - (x0 + x1) / 2, bed_xy / 2 - (y0 + y1) / 2, -z0])


def _manifold_from_soup(tm: trimesh.Trimesh) -> Manifold:
    """Manifold from a triangle soup (for example an STL): manifold3d merges
    vertices only along open edges, so bodies that touch at an edge stay
    separate. Check .status() on the result."""
    mesh = Mesh(vert_properties=np.ascontiguousarray(tm.vertices, dtype=np.float32),
                tri_verts=np.ascontiguousarray(tm.faces, dtype=np.uint32))
    mesh.merge()
    return Manifold(mesh)


def load_mesh(path) -> tuple[Manifold, dict]:
    """Read an STL / 3MF / OBJ / PLY file as one Manifold (all objects of a 3MF
    composed, placed by their build transforms). Raises ValueError with the
    reason when the file is not a closed, oriented solid.

    STL stores loose triangles, so its vertices are re-merged along open
    edges by manifold3d (see mesh_report). Prefer 3MF: it keeps the indexed
    mesh and needs no merge."""
    from pathlib import Path
    path = Path(path)
    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        geoms = loaded.dump() if hasattr(loaded, "dump") else list(loaded.geometry.values())
    else:
        geoms = [loaded]
    parts, bad = [], []
    for i, g in enumerate(geoms):
        mf = to_manifold(g) if path.suffix.lower() != ".stl" else _manifold_from_soup(g)
        if mf.status().name != "NoError":
            mf2 = _manifold_from_soup(g)   # indexed mesh with duplicate vertices: merge
            if mf2.status().name != "NoError":
                bad.append((i, mf.status().name))
                continue
            mf = mf2
        parts.append(mf)
    if bad:
        raise ValueError(f"{path.name}: {len(bad)} of {len(geoms)} objects are not closed solids: {bad[:5]}")
    m = Manifold.compose(parts) if len(parts) > 1 else parts[0]
    return m, dict(file=path.name, objects=len(geoms), triangles=int(m.num_tri()))


def mesh_report(m, expected_bodies: int | None = None) -> dict:
    """Printability basics: watertight, winding consistent, body count, volume, size.

    m: Manifold, trimesh.Trimesh or a file path (STL / 3MF / ...).
    ok = watertight and consistent winding and positive volume (and, when given,
    the number of separate bodies equals expected_bodies).

    Known STL issue: manifold3d output can hold geometrically coincident but
    topologically separate vertices (two bodies touching at an edge, a
    print-in-place joint). STL keeps no vertex indices; trimesh's reload
    merges every coincident vertex, which joins those bodies at the edge and
    reports "not watertight". When that happens the report also rebuilds the
    mesh with manifold3d, which merges only along open edges: if that gives a
    valid manifold, the file is a closed solid (verified by manifold3d's own
    check) and ok is True, with `stl_reload` explaining both results.
    """
    from pathlib import Path
    if isinstance(m, (str, Path)):
        m = trimesh.load(str(m), force="mesh", process=False)
    tm = to_trimesh(m) if isinstance(m, Manifold) else m
    ext = [round(float(e), 3) for e in tm.extents]

    def basic(t):
        return dict(watertight=bool(t.is_watertight), winding_consistent=bool(t.is_winding_consistent),
                    bodies=int(t.body_count), volume_mm3=round(float(t.volume), 2), size_mm=ext,
                    triangles=int(len(tm.faces)))

    rep = basic(tm)
    ok = rep["watertight"] and rep["winding_consistent"] and rep["volume_mm3"] > 0
    if not ok and not isinstance(m, Manifold):
        merged = tm.copy()
        merged.merge_vertices()
        rep = basic(merged)
        ok = rep["watertight"] and rep["winding_consistent"] and rep["volume_mm3"] > 0
    if not ok and not isinstance(m, Manifold):
        mf = _manifold_from_soup(tm)
        valid = mf.status().name == "NoError" and not mf.is_empty()
        rep["stl_reload"] = dict(
            trimesh_merge_watertight=rep["watertight"],
            manifold3d_open_edge_merge=mf.status().name,
            note=("closed solid: coincident vertices of bodies touching at an edge were merged by "
                  "trimesh (known STL reload issue); manifold3d merging only open edges gives a valid "
                  "manifold. Prefer the 3MF.") if valid else
                 "not a closed solid under either merge: real holes or non-manifold edges")
        if valid:
            parts = mf.decompose()
            rep.update(watertight=True, winding_consistent=True, bodies=len(parts),
                       volume_mm3=round(mf.volume(), 2))
            ok = rep["volume_mm3"] > 0
    if expected_bodies is not None:
        rep["expected_bodies"] = expected_bodies
        ok = ok and rep["bodies"] == expected_bodies
    rep["ok"] = bool(ok)
    return rep


def section_yz(m: Manifold, x: float) -> list[np.ndarray]:
    """Polygons of the section of m by the plane X = x, as (y, z) point arrays."""
    t = m.transform([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]])  # (x, y, z) -> (y, z, x)
    return [np.asarray(pl) for pl in t.slice(float(x)).to_polygons()]


def section_xz(m: Manifold, y: float) -> list[np.ndarray]:
    """Polygons of the section of m by the plane Y = y, as (x, z) point arrays."""
    t = m.transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0]])  # (x, y, z) -> (x, z, -y)
    return [np.asarray(pl) for pl in t.slice(-float(y)).to_polygons()]
