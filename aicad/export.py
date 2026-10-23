"""Export helpers: STL / 3MF writers that re-read what they wrote, a plate
check, and a verification.json writer.

A generator should never report "done" on a file it has not re-opened.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time
import zipfile
from pathlib import Path

import trimesh
from manifold3d import Manifold

from .checks import pairwise_overlaps
from .mesh import mesh_report, to_trimesh


def atomic_write(write_fn, path, tries: int = 20) -> None:
    """Write via a temp file, then replace, retrying: on Windows a slicer or an
    indexer can hold the target file open for a moment."""
    path = str(path)
    tmp = path + ".part" + os.path.splitext(path)[1]
    for k in range(tries):
        try:
            write_fn(tmp)
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.5 + 0.5 * k)
    write_fn(tmp)
    os.replace(tmp, path)


def export_stl(m: Manifold | trimesh.Trimesh, path, expected_bodies: int | None = None) -> dict:
    """Write an STL, load it back and compare it with the source mesh.

    ok = the file re-reads with the same triangle count and bounds, and the
    source mesh passes mesh_report() (watertight, expected bodies).

    Why not re-check watertightness from the file: STL stores loose
    triangles. manifold3d output can hold geometrically coincident vertices
    that are topologically separate (valid in memory, and in 3MF, which keeps
    the indexed mesh). Merging them after an STL round trip can join two
    surfaces at one edge, so "watertight after merge" is reported as info
    only. Prefer the 3MF (verify_3mf) as the file you slice.
    """
    tm = to_trimesh(m) if isinstance(m, Manifold) else m
    atomic_write(lambda p: tm.export(p, file_type="stl"), path)
    back = trimesh.load(str(path), force="mesh", process=False)
    src = mesh_report(tm, expected_bodies)
    same_tris = len(back.faces) == len(tm.faces)
    same_bounds = bool(abs(back.bounds - tm.bounds).max() < 1e-3)
    merged = back.copy()
    merged.merge_vertices()
    return dict(path=Path(path).name, triangles=int(len(back.faces)), triangles_match=same_tris,
                bounds_match=same_bounds, source_mesh=src,
                info_watertight_after_merge=bool(merged.is_watertight),
                ok=bool(same_tris and same_bounds and src["ok"]))


def export_3mf(parts: list, names: list, path) -> None:
    """One 3MF object (build item) per part, world coordinates, millimetres.
    Slicers keep them as separate objects on one plate."""
    if len(parts) != len(names):
        raise ValueError(f"export_3mf: {len(parts)} parts but {len(names)} names; give one name per part")
    sc = trimesh.Scene()
    for m, n in zip(parts, names):
        tm = to_trimesh(m) if isinstance(m, Manifold) else m
        sc.add_geometry(tm, node_name=n, geom_name=n)
    atomic_write(lambda p: Path(p).write_bytes(sc.export(file_type="3mf")), path)


def verify_3mf(path, expected: int) -> dict:
    """Re-read a 3MF: count mesh objects and build items in the XML and the
    meshes trimesh loads; check each object is one watertight shell."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("3D/3dmodel.model").decode("utf-8")
    objs = len(re.findall(r"<object\b[^>]*type=\"model\"", xml))
    items = len(re.findall(r"<item\b", xml))
    unit = re.search(r'unit="(\w+)"', xml)
    sc = trimesh.load(str(path), force="scene", process=False)
    geoms = list(sc.geometry.values())
    shells = [int(g.body_count) for g in geoms]
    tight = [bool(g.is_watertight) for g in geoms]
    ok = (objs == items == len(geoms) == expected and all(s == 1 for s in shells)
          and all(tight) and (unit is None or unit.group(1) == "millimeter"))
    return dict(path=Path(path).name, expected_objects=expected, xml_objects=objs,
                build_items=items, loaded_meshes=len(geoms), shells_per_object=shells,
                watertight_per_object=tight, unit=unit.group(1) if unit else None, ok=bool(ok))


def plate_check(parts: list, names: list, bed_xy: tuple[float, float], margin: float = 5.0,
                exclude: tuple[float, float, float, float] | None = None) -> dict:
    """Do the parts fit the bed as placed (bed coords, origin at a bed corner)?

    bed_xy  : (width, depth) mm
    margin  : minimum distance from every part to the bed edge
    exclude : optional keep-out rectangle (x0, y0, x1, y1), e.g. a purge corner
    Also reports parts overlapping each other and parts below z = 0.
    """
    boxes = [m.bounding_box() for m in parts]
    lo = [min(b[i] for b in boxes) for i in range(3)]
    hi = [max(b[i + 3] for b in boxes) for i in range(3)]
    edge = min(lo[0], lo[1], bed_xy[0] - hi[0], bed_xy[1] - hi[1])
    in_exclude = []
    if exclude is not None:
        ex0, ey0, ex1, ey1 = exclude
        for n, b in zip(names, boxes):
            if b[0] < ex1 and b[3] > ex0 and b[1] < ey1 and b[4] > ey0:
                in_exclude.append(n)
    overlaps = pairwise_overlaps(parts, names, tol_mm3=0.001)
    below = [n for n, b in zip(names, boxes) if b[2] < -1e-3]
    ok = edge >= margin - 1e-6 and not in_exclude and not overlaps and not below
    return dict(bed_xy=list(bed_xy), extent_x=[round(lo[0], 2), round(hi[0], 2)],
                extent_y=[round(lo[1], 2), round(hi[1], 2)], height=round(hi[2] - lo[2], 2),
                edge_margin=round(edge, 2), required_margin=margin, in_exclude_zone=in_exclude,
                overlapping_parts=overlaps, below_bed=below, ok=bool(ok))


def write_verification(path, name: str, checks: dict, params: dict | None = None,
                       files: list | None = None, setup: dict | None = None) -> dict:
    """Write verification.json: what was built, with which parameters, and the
    result of every check. all_ok is the AND of every "ok" key. Every declared
    check (each entry of `checks`, each item when it is a list) and every file
    result must carry a boolean "ok"; one that does not is listed under
    "unassessed" and forces all_ok False.

    setup: the printer / material / layer height the numbers assume, e.g.
           {"printer": "...", "material": "PLA", "nozzle": 0.4, "layer": 0.2}
    """
    def oks(obj, path):
        """Yield (path, ok) for every "ok" key found; a non-bool ok yields None."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "ok":
                    yield (path, v if isinstance(v, bool) else None)
                else:
                    yield from oks(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                yield from oks(v, f"{path}[{i}]")

    def has_own_ok(v):
        return isinstance(v, dict) and isinstance(v.get("ok"), bool)

    unassessed = []
    # every declared check and every file result must itself carry a bool ok
    for k, v in checks.items():
        if isinstance(v, list) and v:
            items = [(f"checks.{k}[{i}]", x) for i, x in enumerate(v)]
        else:
            items = [(f"checks.{k}", v)]
        unassessed += [p for p, x in items if not has_own_ok(x)]
    for i, f in enumerate(files or []):
        if not has_own_ok(f):
            unassessed.append(f"files[{i}]")
    found = list(oks(checks, "checks")) + list(oks(files or [], "files"))
    unassessed += [p for p, v in found if v is None]
    flags = [v for _, v in found if v is not None]
    unassessed = sorted(set(unassessed))
    doc = dict(name=name, generated=_dt.datetime.now().isoformat(timespec="seconds"),
               setup=setup or {}, params=params or {}, files=files or [], checks=checks,
               n_checks=len(flags), unassessed=unassessed,
               all_ok=bool(flags) and all(flags) and not unassessed)
    Path(path).write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="ascii")
    return doc
