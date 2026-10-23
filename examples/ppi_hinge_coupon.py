"""Example: print-in-place hinge clearance coupon.

Three 3-link chains on one plate, one per side clearance (xy_gap), all with
explicit top and bottom Z gaps. Each chain is a plain bar split twice with
aicad.ppi_hinge, so the coupon tests the same code a real part would use.

Checks run here, per chain: 3 separate bodies, ray-measured clearances equal
the design values, both hinges swing free over +-60 deg (sampled every 1 deg) and stop
between 55 and 75 deg (stops bisected to 0.05 deg).
Plate: fits the bed, no overlaps, 3MF re-reads as 9 watertight objects.

Run from the repo root:
    uv run --with-requirements requirements.txt python examples/ppi_hinge_coupon.py
Writes examples/out/ppi_hinge_coupon/{coupon.stl, coupon.3mf, coupon.png,
verification.json}.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from manifold3d import Manifold, OpType  # noqa: E402

from aicad.checks import hinge_measured_clearances, swing_sweep  # noqa: E402
from aicad.coupons import _fmt, hinge_chain  # noqa: E402
from aicad.export import export_3mf, export_stl, plate_check, verify_3mf, write_verification  # noqa: E402
from aicad.mesh import mesh_report, section_yz  # noqa: E402
from aicad.ppi_hinge import HingeParams, clearances, rotate_about_axis  # noqa: E402
from aicad.preview import preview_png  # noqa: E402

OUT = Path(__file__).parent / "out" / "ppi_hinge_coupon"
XY_GAPS = [0.3, 0.4, 0.5]
Z_TOP, Z_BOTTOM = 0.6, 0.4
STOP_RANGE_DEG = (55.0, 75.0)   # design expectation: |stop| within this (swing_deg is 60)
PITCH_X = 20.0
BED = (220.0, 220.0)


def check_chain(links, hinges, p):
    des = clearances(p)
    bodies = len(Manifold.batch_boolean(links, OpType.Add).decompose())
    meas = [hinge_measured_clearances(links[1], hinges[0]),
            hinge_measured_clearances(links[2], hinges[1])]
    meas_ok = all(m[k] is not None and abs(m[k] - des[kk]) < 0.02
                  for m in meas for k, kk in (("top", "top"), ("bottom", "bottom"),
                                              ("side_fwd", "side"), ("side_back", "side")))
    # joint 1: link 1 fixed, links 2+3 swing; joint 2: links 1+2 fixed, link 3 swings
    swings = [swing_sweep(links[0], links[1] + links[2],
                          lambda m, a: rotate_about_axis(m, hinges[0], a), limit_deg=p.swing_deg),
              swing_sweep(links[0] + links[1], links[2],
                          lambda m, a: rotate_about_axis(m, hinges[1], a), limit_deg=p.swing_deg)]
    # design expectation: the V-notches close at +-swing_deg, so contact starts just
    # past it (observed: +60.03, and -66 to -71 growing with xy_gap); a stop outside
    # STOP_RANGE_DEG, or no stop found, fails
    stops_ok = all(st is not None and STOP_RANGE_DEG[0] <= abs(st) <= STOP_RANGE_DEG[1]
                   for sw in swings for st in sw["stops_deg"])
    ok = bodies == 3 and meas_ok and all(sw["ok"] for sw in swings) and stops_ok
    return dict(xy_gap=p.xy_gap, design=des, measured_joint1=meas[0], measured_joint2=meas[1],
                measured_ok=meas_ok, bodies=bodies, swing_joint1=swings[0], swing_joint2=swings[1],
                stops_within_tolerance=stops_ok, stop_range_deg=list(STOP_RANGE_DEG), ok=bool(ok))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chains, reports = [], []
    for i, xy in enumerate(XY_GAPS):
        p = HingeParams(xy_gap=xy, z_gap_top=Z_TOP, z_gap_bottom=Z_BOTTOM)
        links, hinges = hinge_chain(p, x0=i * PITCH_X,
                                    label_lines=[f"X{_fmt(xy)}", f"T{_fmt(Z_TOP)}", f"B{_fmt(Z_BOTTOM)}"])
        chains.append((links, hinges, p))
        reports.append(check_chain(links, hinges, p))
        r = reports[-1]
        print(f"xy {xy}: bodies {r['bodies']}, measured {r['measured_joint1']}, "
              f"stops j1 {r['swing_joint1']['stops_deg']} j2 {r['swing_joint2']['stops_deg']}, ok {r['ok']}")

    # move the whole plate onto the bed centre
    allp = Manifold.batch_boolean([l for c in chains for l in c[0]], OpType.Add)
    x0, y0, z0, x1, y1, _ = allp.bounding_box()
    shift = [BED[0] / 2 - (x0 + x1) / 2, BED[1] / 2 - (y0 + y1) / 2, -z0]
    parts, names = [], []
    for (links, _h, p) in chains:
        for k, l in enumerate(links):
            parts.append(l.translate(shift))
            names.append(f"xy{_fmt(p.xy_gap)}_link{k + 1}")
    plate = plate_check(parts, names, BED, margin=5.0)
    whole = Manifold.batch_boolean(parts, OpType.Add)
    body = mesh_report(whole, expected_bodies=len(parts))
    stl = export_stl(whole, OUT / "coupon.stl", expected_bodies=len(parts))
    export_3mf(parts, names, OUT / "coupon.3mf")
    tmf = verify_3mf(OUT / "coupon.3mf", expected=len(parts))

    secs = []
    for links, hinges, p in chains:
        xa = hinges[0].frame[0, 3]
        c = clearances(p)
        secs.append(dict(title=f"xy {p.xy_gap}: side {c['side']} top {c['top']} bottom {c['bottom']}",
                         polys=[section_yz(l, xa) for l in links[:2]],
                         circles=[(0, p.thickness / 2, p.axle_d / 2)], xlim=(-6, 6), ylim=(-0.5, 8.5)))
    preview_png(OUT / "coupon.png", [l for c in chains for l in c[0]],
                "PPI hinge coupon: 3 chains, link 1 labelled X/T/B", sections=secs)
    doc = write_verification(
        OUT / "verification.json", "ppi_hinge_coupon",
        checks=dict(chains=reports, plate=plate, mesh=body),
        params=dict(xy_gaps=XY_GAPS, z_gap_top=Z_TOP, z_gap_bottom=Z_BOTTOM,
                    hinge=HingeParams().__dict__, stop_range_deg=list(STOP_RANGE_DEG)),
        files=[stl, tmf],
        setup=dict(note="fill in your printer, material, nozzle and layer height"))
    print(f"plate ok {plate['ok']} (edge margin {plate['edge_margin']} mm), "
          f"mesh ok {body['ok']} ({body['bodies']} bodies), 3mf ok {tmf['ok']}")
    print(f"all_ok {doc['all_ok']} ({doc['n_checks']} checks) -> {OUT.relative_to(ROOT)}")
    return 0 if doc["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
