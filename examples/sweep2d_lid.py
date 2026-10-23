"""Example: 2D sweep of a hinged lid on a box, before any 3D CAD.

Side view: a box with walls, a lid on a pivot at the back top edge. Where
must the pivot sit so the lid opens to 110 deg without its back edge hitting
the box? The sweep answers it for two pivot positions.

Run from the repo root:
    uv run --with-requirements requirements.txt python examples/sweep2d_lid.py
Writes examples/out/sweep2d_lid/{sweep.png, verification.json}.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely.geometry import box  # noqa: E402

from aicad.export import write_verification  # noqa: E402
from aicad.sweep2d import draw_states, free_range, rotate_about, sweep  # noqa: E402

OUT = Path(__file__).parent / "out" / "sweep2d_lid"
W, H, WALL, LID_T = 60.0, 30.0, 2.0, 3.0
MIN_GAP = 0.4           # print-in-place gap you trust on your printer
OPEN_TO = 110           # deg


def mechanism(pivot_dx: float):
    """pivot_dx: pivot distance behind the back wall's outer face (x = W)."""
    body = box(0, 0, W, H).difference(box(WALL, WALL, W - WALL, H + 1))  # box(minx, miny, maxx, maxy)
    pivot = (W + pivot_dx, H + LID_T / 2)
    lid = box(0, H + MIN_GAP, W + pivot_dx + LID_T / 2, H + MIN_GAP + LID_T)
    return {"lid": lambda t: rotate_about(lid, -t, pivot), "box": lambda t: body}, pivot


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = {}
    fig, axs = plt.subplots(1, 2, figsize=(12, 5))
    for ax, dx in zip(axs, (0.0, 3.0)):
        parts, pivot = mechanism(dx)
        rep = sweep(parts, [("lid", "box")], ts=range(0, OPEN_TO + 1, 2), min_gap=MIN_GAP)
        pr = rep["pairs"]["lid|box"]
        rng = free_range(parts, ("lid", "box"), range(0, 181), MIN_GAP)
        results[f"pivot_dx_{dx}"] = dict(pivot=pivot, min_gap=pr["min_gap"], at_deg=pr["at_t"],
                                         first_violation_deg=pr["first_violation_t"],
                                         free_range_deg=rng, ok=rep["ok"])
        print(f"pivot {dx:.1f} mm behind the wall: min gap {pr['min_gap']} mm at {pr['at_t']} deg, "
              f"first violation {pr['first_violation_t']}, free range {rng} (sampled every 2 deg, refined to {pr['refine_tol']} deg), ok {rep['ok']}")
        draw_states(ax, parts, (0, 45, 90, OPEN_TO))
        ax.plot(*pivot, "r+", ms=12)
        ax.set_title(f"pivot {dx:.1f} mm behind wall: {'OK' if rep['ok'] else 'COLLIDES'}"
                     f" (min gap {pr['min_gap']} mm)")
        ax.set_xlim(-5, W + 40)
        ax.set_ylim(-5, H + 70)
    fig.tight_layout()
    fig.savefig(OUT / "sweep.png", dpi=110)
    plt.close(fig)

    # the example is meant to show one failing and one passing layout
    expected = dict(ok=(not results["pivot_dx_0.0"]["ok"]) and results["pivot_dx_3.0"]["ok"],
                    layouts={k: {("layout_ok" if kk == "ok" else kk): vv for kk, vv in v.items()}
                             for k, v in results.items()})
    doc = write_verification(OUT / "verification.json", "sweep2d_lid",
                             checks=dict(flush_pivot_fails_offset_pivot_passes=expected),
                             params=dict(W=W, H=H, wall=WALL, lid_t=LID_T, min_gap=MIN_GAP,
                                         open_to=OPEN_TO))
    print(f"all_ok {doc['all_ok']} -> {OUT.relative_to(ROOT)}")
    return 0 if doc["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
