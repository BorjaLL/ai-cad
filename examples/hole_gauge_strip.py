"""Example: hole gauge strip for a 1.75 mm filament pin.

Vertical holes 1.90 to 2.40 mm in 0.05 steps, each engraved with its size.
Print it flat, push a piece of filament into each hole and note which size
grips and which turns freely. Those two numbers go in your AGENTS.md.

Checks run here: the file re-reads as one watertight body, no in-layer (XY)
feature is narrower than 2 perimeters, no solid span along Z is
thinner than 0.8 mm, the strip fits a small bed.

Run from the repo root:
    uv run --with-requirements requirements.txt python examples/hole_gauge_strip.py
Writes examples/out/hole_gauge_strip.{stl,3mf,png} and verification.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from aicad.checks import thin_walls, z_thickness  # noqa: E402
from aicad.coupons import hole_gauge_strip  # noqa: E402
from aicad.export import export_3mf, export_stl, plate_check, verify_3mf, write_verification  # noqa: E402
from aicad.mesh import centre_on_bed, mesh_report, section_xz  # noqa: E402
from aicad.preview import preview_png  # noqa: E402

OUT = Path(__file__).parent / "out" / "hole_gauge_strip"
DIAMETERS = [round(v, 2) for v in np.arange(1.90, 2.401, 0.05)]
THICKNESS = 4.0
MIN_Z = 0.8            # thinnest roof / floor: 4 layers at 0.2 mm
MIN_WALL = 0.9          # 2 perimeters at 0.45 mm line width
BED = (220.0, 220.0)    # any small printer


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    strip, holes = hole_gauge_strip(DIAMETERS, thickness=THICKNESS, chamfer=0.3)
    strip = centre_on_bed(strip, BED[0])

    body = mesh_report(strip, expected_bodies=1)
    # engraved size labels leave thin bits between glyphs: cosmetic, so the
    # label band is a zone (reported apart, not a failure)
    x0, y0, _, x1, _, _ = strip.bounding_box()
    label_band = (x0, x1, y0 + 2.0, y0 + 7.0, THICKNESS - 0.6, THICKNESS + 0.1)
    walls = thin_walls(strip, MIN_WALL, zones={"size_labels": label_band})
    roofs = z_thickness(strip, MIN_Z)
    plate = plate_check([strip], ["gauge"], BED, margin=5.0)
    stl = export_stl(strip, OUT / "hole_gauge_strip.stl", expected_bodies=1)
    export_3mf([strip], ["hole_gauge_strip"], OUT / "hole_gauge_strip.3mf")
    tmf = verify_3mf(OUT / "hole_gauge_strip.3mf", expected=1)

    y_mid = y0 + holes[0]["y"]
    preview_png(OUT / "hole_gauge_strip.png", [strip], "Hole gauge strip 1.90-2.40",
                sections=[dict(title="XZ section through the hole row",
                               polys=[section_xz(strip, y_mid)],
                               xlim=(x0, x0 + 30), ylim=(-1, THICKNESS + 1))])
    doc = write_verification(
        OUT / "verification.json", "hole_gauge_strip",
        checks=dict(mesh=body, thin_walls=walls, z_thickness=roofs, plate=plate),
        params=dict(diameters=DIAMETERS, thickness=THICKNESS, min_wall=MIN_WALL, min_z=MIN_Z),
        files=[stl, tmf],
        setup=dict(note="fill in your printer, material, nozzle and layer height"))
    print(f"holes: {', '.join(str(d) for d in DIAMETERS)}")
    print(f"mesh ok {body['ok']} ({body['bodies']} body, {body['size_mm']} mm), "
          f"thin walls ok {walls['ok']} (label band min {walls['zone_min_wall']['min_wall_mm']} mm), "
          f"z thickness ok {roofs['ok']} ({roofs['n_findings']} findings, {roofs['findings_volume_mm3']} mm3), "
          f"plate ok {plate['ok']}, 3mf ok {tmf['ok']}")
    print(f"all_ok {doc['all_ok']} ({doc['n_checks']} checks) -> {OUT.relative_to(ROOT)}")
    return 0 if doc["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
