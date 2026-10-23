"""Regression harness: run mesh_report, thin_walls and z_thickness on real
part files and print a short per-part summary (findings, ignored slivers,
timings). No part paths live in the repo: pass them on the command line or
in AICAD_REAL_PARTS (separated by os.pathsep, ';' on Windows).

    python tests/real_parts.py part.3mf other.stl --min-wall 0.8 --min-z 0.6
    python tests/real_parts.py part.3mf --zones zones.json --json out.json

zones.json: {"part.3mf": {"pin_roofs": [x0, x1, y0, y1, z0, z1], ...}} keyed
by file name. Heavy: run at low process priority, one part at a time (see
docs/checks.md). Exit code 0 = every part ok, 1 = findings, 2 = error.
--gate hard: exit 0 when every part is ok_hard (nothing under one nozzle
line in XY, nothing under two layers in Z); the findings are still listed.
Another setup: --nozzle 0.6 --layer 0.3 --min-wall 1.2 --min-z 0.9 moves
the section spacing, Z step and both hard floors together.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aicad.checks import for_printer, thin_walls, z_thickness  # noqa: E402
from aicad.mesh import load_mesh, mesh_report  # noqa: E402


def short(f, keys):
    return {k: f[k] for k in keys if k in f}


def run_one(path: Path, a, zones) -> dict:
    out = dict(file=path.name)
    t = time.perf_counter()
    out["mesh"] = mesh_report(path)
    out["mesh"]["seconds"] = round(time.perf_counter() - t, 2)
    print(f"[{path.name}] mesh ok={out['mesh']['ok']} ({out['mesh']['seconds']}s)", file=sys.stderr, flush=True)
    t = time.perf_counter()
    m, info = load_mesh(path)
    out["load"] = dict(info, seconds=round(time.perf_counter() - t, 2))
    kw = for_printer(a.nozzle, a.layer)
    if not a.skip_walls:
        out["thin_walls"] = thin_walls(m, a.min_wall, zones=zones, time_budget_s=a.budget,
                                       zone_min_wall=False, max_findings=a.max_findings,
                                       **kw["thin_walls"])
    log = (lambda msg: print(msg, file=sys.stderr, flush=True)) if a.verbose else None
    if not a.skip_z:
        out["z_thickness"] = z_thickness(m, a.min_z, zones=zones, time_budget_s=a.budget,
                                         max_findings=a.max_findings, log=log, **kw["z_thickness"])
    return out


def summary(r: dict) -> str:
    L = [f"== {r['file']}"]
    mr = r["mesh"]
    L.append(f"  mesh ok={mr['ok']} bodies={mr['bodies']} tris={mr['triangles']} watertight={mr['watertight']}"
             f" ({mr['seconds']}s)" + (f"  [{mr['stl_reload']['note'][:70]}...]" if "stl_reload" in mr else ""))
    for k in ("thin_walls", "z_thickness"):
        if k not in r:
            continue
        c = r[k]
        secs = c["seconds"] if k == "thin_walls" else c["seconds"]["total"]
        ign = {n: v.get("n_pieces", v.get("n_layer_pieces", v.get("n_features")))
               for n, v in c["ignored"].items()}
        exc = {n: v.get("n_pieces", v.get("n_features")) for n, v in c["excused_by_zone"].items()}
        L.append(f"  {k} ok={c['ok']} ok_hard={c['ok_hard']} verified={c['verified']} findings={c['n_findings']} "
                 f"ignored={ign} excused={exc} ({secs}s)")
        if k == "z_thickness":
            L.append(f"    tiles={c['tiles']['tiles_checked']} skipped={c['tiles']['tiles_skipped_no_candidates']} "
                     f"unverified={c['tiles']['tiles_unverified']} max_tile_tris={c['tiles']['max_tile_tris']}")
        for g in c["groups"][:8]:
            L.append("    - " + json.dumps(g))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min-wall", type=float, default=0.8)
    ap.add_argument("--min-z", type=float, default=0.6)
    ap.add_argument("--nozzle", type=float, default=0.4,
                    help="nozzle / line width, mm: XY hard floor and Z footprint filter")
    ap.add_argument("--layer", "--step", dest="layer", type=float, default=0.2,
                    help="layer height, mm: section spacing, Z step, Z hard floor = 2 layers")
    ap.add_argument("--budget", type=float, default=300.0, help="time budget per check, seconds")
    ap.add_argument("--zones", help="JSON file {file_name: {zone_name: box}}")
    ap.add_argument("--max-findings", type=int, default=20)
    ap.add_argument("--verbose", action="store_true", help="z_thickness progress per tile on stderr")
    ap.add_argument("--skip-walls", action="store_true")
    ap.add_argument("--skip-z", action="store_true")
    ap.add_argument("--json", help="write full results here")
    ap.add_argument("--gate", choices=("ok", "hard"), default="ok",
                    help="which flag sets the exit code: ok (design minimum) or ok_hard")
    a = ap.parse_args()
    paths = a.paths or [p for p in os.environ.get("AICAD_REAL_PARTS", "").split(os.pathsep) if p]
    if not paths:
        ap.error("give part paths or set AICAD_REAL_PARTS")
    zones_all = json.loads(Path(a.zones).read_text()) if a.zones else {}
    results, code = [], 0
    for p in map(Path, paths):
        try:
            r = run_one(p, a, zones_all.get(p.name))
            print(summary(r), flush=True)
            flag = {"mesh": "ok", "thin_walls": "ok", "z_thickness": "ok"}
            if a.gate == "hard":
                flag.update(thin_walls="ok_hard", z_thickness="ok_hard")
            if not all(r[k][flag[k]] for k in flag if k in r):
                code = max(code, 1)
        except Exception as e:  # report and continue with the next part
            r = dict(file=p.name, error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
            print(f"== {p.name}\n  ERROR {r['error']}", flush=True)
            code = 2
        results.append(r)
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1))
    sys.exit(code)


if __name__ == "__main__":
    main()
