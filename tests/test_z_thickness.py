"""z_thickness / thin_walls: find real thin material, ignore numerical slivers,
report per piece. Run: python tests/test_z_thickness.py   (pytest also works)"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manifold3d import Manifold  # noqa: E402

from aicad.checks import thin_walls, z_thickness  # noqa: E402

SLAB = Manifold.cube([20, 20, 3])


def cavity(x, y, r, h):
    """Blind hole from the bottom, h tall: leaves a 3 - h roof."""
    return Manifold.cylinder(h, r, r, 48).translate([x, y, 0])


def test_small_cavity_under_thin_roof_fails():
    # 0.55 mm hole under a 0.2 mm roof: narrower than any practical ray grid
    r = z_thickness(SLAB - cavity(10, 10, 0.275, 2.8), 0.8)
    assert r["ok"] is False and r["verified"] is True and r["n_findings"] == 1
    f = r["findings"][0]
    assert f["volume_mm3"] > 0.04
    assert 9.5 < f["bbox"][0] < 10 < f["bbox"][3] < 10.5, f["bbox"]
    assert abs(f["thickness_min_mm"] - 0.2) < 0.02, f


def test_thick_slab_passes():
    r = z_thickness(SLAB, 0.8)
    assert r["ok"] is True and r["verified"] is True and r["findings"] == []


def test_thin_plate_fails():
    r = z_thickness(Manifold.cube([20, 20, 0.6]), 0.8)
    assert r["ok"] is False and abs(r["findings"][0]["thickness_min_mm"] - 0.6) < 0.01


def test_exactly_min_passes():
    assert z_thickness(Manifold.cube([20, 20, 0.8]), 0.8)["ok"] is True


def test_measured_thickness_tells_roofs_apart():
    part = SLAB - cavity(5, 10, 1.5, 2.45) - cavity(15, 10, 1.5, 2.95)   # roofs 0.55 and 0.05
    r = z_thickness(part, 0.8)
    th = sorted(f["thickness_min_mm"] for f in r["findings"])
    assert r["n_findings"] == 2 and abs(th[0] - 0.05) < 0.01 and abs(th[1] - 0.55) < 0.01, th


def test_sphere_rim_slivers_ignored_and_counted():
    # the rim of any rounded body has vertical spans -> 0: slivers, not roofs
    r = z_thickness(Manifold.sphere(5, 96).translate([0, 0, 5]), 0.8)
    n_ign = sum(v["n_pieces"] for v in r["ignored"].values())
    assert r["ok"] is True and r["verified"] is True and n_ign >= 1, r


def test_narrow_ledge_is_a_documented_gap():
    # 0.3 mm wide, 0.2 mm thick ledge on a thick wall: z_thickness ignores it
    # (footprint narrower than a nozzle line) and thin_walls does not see it
    # either (the opening disc fits across wall + ledge). It prints as a bump
    # in the outer perimeter. Documented in docs/checks.md; if this starts
    # failing, update the docs.
    part = SLAB + Manifold.cube([0.3, 10, 0.2]).translate([20, 5, 1.4])
    r = z_thickness(part, 0.8)
    assert r["ok"] is True and r["ignored"]["footprint_narrower_than_0.4_mm"]["n_pieces"] >= 1
    assert thin_walls(part, 0.8)["ok"] is True


def test_free_thin_fin_found_by_thin_walls_and_ignored_by_z():
    # a free-standing 0.3 mm fin, 2 mm tall: an in-layer width problem
    part = SLAB + Manifold.cube([0.3, 10, 2]).translate([10, 5, 3])
    assert z_thickness(part, 0.8)["ok"] is True
    w = thin_walls(part, 0.8)
    assert w["ok"] is False and abs(w["findings"][0]["width_mm"] - 0.3) < 0.05, w["findings"][:1]


def test_named_zone_excuses_thin_material():
    part = SLAB - cavity(10, 10, 0.275, 2.8)
    r = z_thickness(part, 0.8, zones={"pin_roof": (9, 11, 9, 11, 0, 3)})
    e = r["excused_by_zone"]["pin_roof"]
    assert r["ok"] is True and e["n_pieces"] == 1 and e["volume_mm3"] > 0.04, r


def test_list_zones_still_work():
    r = z_thickness(SLAB - cavity(10, 10, 0.275, 2.8), 0.8, zones=[(9, 11, 9, 11, 0, 3)])
    assert r["ok"] is True and r["excused_by_zone"]["zone0"]["n_pieces"] == 1


def test_time_budget_gives_unverified_not_ok():
    r = z_thickness(SLAB - cavity(10, 10, 0.275, 2.8), 0.8, time_budget_s=0)
    assert r["verified"] is False and r["ok"] is False and "note" in r


def test_findings_sorted_and_capped():
    part = SLAB
    for i in range(6):
        part = part - cavity(2 + 3 * i, 10, 0.5 + 0.1 * i, 2.7)
    r = z_thickness(part, 0.8, max_findings=3)
    vols = [f["volume_mm3"] for f in r["findings"]]
    assert r["n_findings"] == 6 and len(vols) == 3 and vols == sorted(vols, reverse=True), r


def test_tiling_matches_single_tile():
    part = SLAB - cavity(5, 5, 1, 2.6) - cavity(15, 15, 1, 2.6)
    a = z_thickness(part, 0.8)
    b = z_thickness(part.refine(4), 0.8, max_tile_tris=500, simplify_mm=0)
    assert b["tiles"]["tiles_checked"] > 1
    assert a["n_findings"] == b["n_findings"] == 2, (a, b)
    assert abs(a["findings_volume_mm3"] - b["findings_volume_mm3"]) < 0.01


def test_thin_walls_reports_width_and_location():
    part = SLAB + Manifold.cube([0.5, 10, 2]).translate([20, 5, 3])   # fin 0.5 wide on top
    part = Manifold.cube([30, 30, 1]).translate([-5, -5, 0]) + part.translate([0, 0, 1])
    w = thin_walls(part, 0.8)
    f = w["findings"][0]
    assert w["ok"] is False and abs(f["width_mm"] - 0.5) < 0.1, f
    assert 19.9 <= f["bbox"][0] and f["bbox"][3] <= 20.6 and f["bbox"][2] >= 3.9, f


def test_thin_walls_named_zone():
    part = SLAB + Manifold.cube([0.5, 10, 2]).translate([20, 5, 3])
    w = thin_walls(part, 0.8, zones={"fin": (19, 21, 4, 16, 3, 5)}, zone_min_wall=False)
    assert w["ok"] is True and w["excused_by_zone"]["fin"]["n_features"] == 1, w


def test_ok_strict_false_when_simplify_drops_a_feature():
    # 0.002 mm plate vanishes in simplify(0.01): ok under the filters, not strict
    r = z_thickness(Manifold.cube([0.6, 0.6, 0.002]), 0.8)
    assert r["ok_strict"] is False


def test_ok_strict_true_on_plain_solid():
    r = z_thickness(Manifold.cube([10, 10, 3]), 0.8)
    assert r["ok"] is True and r["ok_strict"] is True


def test_max_input_tris_refuses_up_front():
    try:
        z_thickness(Manifold.cube([10, 10, 3]), 0.8, max_input_tris=5)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def ramp(run=3.0, h=3.0):
    """20 x 20 x h block whose top slopes down to the bed over `run` mm at
    x = 0 (a chamfer meeting the bed: 45 deg for run == h)."""
    pts = [[0, 0, 0], [20, 0, 0], [0, 20, 0], [20, 20, 0],
           [run, 0, h], [20, 0, h], [run, 20, h], [20, 20, h]]
    return Manifold.hull_points(pts)


def test_chamfer_edge_is_a_taper_not_a_finding():
    # the thin edge of a chamfer meeting the bed: vertical spans 0 -> 0.8 over
    # 0.8 mm. Without the taper filter it was a finding on every chamfered part
    part = ramp()
    old = z_thickness(part, 0.8, min_taper=math.inf)
    assert old["ok"] is False and old["n_findings"] >= 1, old
    r = z_thickness(part, 0.8)
    t = r["ignored"]["taper_at_least_0.36_mm_per_mm"]
    assert r["ok"] is True and r["ok_hard"] is True and t["n_pieces"] >= 1, r
    assert r["ok_strict"] is False


def test_roof_with_tapered_rim_is_still_found():
    # 0.4 mm flat roof over a hole whose top has a 45 deg chamfer: the rim is
    # a taper, the middle is a plate, so the piece stays a finding
    hole = (Manifold.cylinder(2.4, 3, 3, 64)
            + Manifold.cylinder(0.2, 3, 2.8, 64).translate([0, 0, 2.4])).translate([10, 10, 0])
    r = z_thickness(SLAB - hole, 0.8)
    assert r["ok"] is False and r["n_findings"] == 1, r
    assert abs(r["findings"][0]["thickness_min_mm"] - 0.4) < 0.02, r["findings"][0]


def test_tilted_thin_plate_is_still_found():
    # 0.5 mm plate tilted 20 deg: parallel faces, vertical span 0.53, no taper
    plate = Manifold.cube([20, 20, 0.5]).rotate([0, 20, 0]).translate([0, 0, 8])
    r = z_thickness(plate, 0.8)
    assert r["ok"] is False and r["n_findings"] >= 1, r["ignored"]
    assert all(0.5 < f["thickness_min_mm"] < 0.56 for f in r["findings"]), r["findings"]


def test_ok_hard_separates_one_layer_skins_from_design_minimum():
    a = z_thickness(Manifold.cube([20, 20, 0.6]), 0.8)       # 3 layers: prints
    assert a["ok"] is False and a["ok_hard"] is True and a["n_hard"] == 0, a
    b = z_thickness(SLAB - cavity(10, 10, 1, 2.8), 0.8)     # 0.2 roof: one layer
    assert b["ok"] is False and b["ok_hard"] is False and b["n_hard"] == 1, b


def test_thin_walls_ok_hard():
    base = SLAB
    a = thin_walls(base + Manifold.cube([0.6, 10, 2]).translate([10, 5, 3]), 0.8)
    assert a["ok"] is False and a["ok_hard"] is True, a["findings"][:1]
    b = thin_walls(base + Manifold.cube([0.3, 10, 2]).translate([10, 5, 3]), 0.8)
    assert b["ok"] is False and b["ok_hard"] is False and b["n_hard"] == 1, b["findings"][:1]


def test_thin_walls_one_layer_pieces_counted_not_reported():
    # a 0.3 x 0.2 mm rib seen in one sampled layer (like the crescent a layer
    # cuts from a near-horizontal curved surface): counted, not a finding
    one = thin_walls(SLAB + Manifold.cube([0.3, 10, 0.2]).translate([10, 5, 3]), 0.8)
    k = "fewer_than_2_layers"
    assert one["ok"] is True and one["ignored"][k]["n_features"] == 1, one["ignored"]
    assert abs(one["ignored"][k]["narrowest_mm"] - 0.3) < 0.05
    assert thin_walls(SLAB + Manifold.cube([0.3, 10, 0.2]).translate([10, 5, 3]), 0.8,
                      min_layers=1)["ok"] is False
    two = thin_walls(SLAB + Manifold.cube([0.3, 10, 0.4]).translate([10, 5, 3]), 0.8)
    assert two["ok"] is False and two["findings"][0]["layers"] == 2, two["findings"][:1]


# ---- review fixes 2026-10-23
WALL3 = Manifold.cube([0.3, 10, 2]).translate([10, 5, 3])   # 0.3 x 2 mm tall


def test_merge_keeps_narrow_stretch_under_wider_top():
    # 0.3 mm wall, 2 mm tall, topped by a 0.6 mm section: merged into one
    # finding, the narrow stretch must still fail the hard gate
    top = Manifold.cube([0.6, 10, 1]).translate([10, 5, 5])
    r = thin_walls(SLAB + WALL3 + top, 0.8)
    assert r["ok_hard"] is False and r["n_hard"] == 1, r["findings"][:2]
    f = r["findings"][0]
    assert f["width_mm"] < 0.35 and f["width_max_mm"] > 0.55 and f["layers_hard"] >= 10, f


def test_hard_floor_above_design_minimum_is_refused():
    for call in (lambda: z_thickness(Manifold.cube([20, 20, 0.3]), 0.3),
                 lambda: thin_walls(SLAB + WALL3, 0.2)):
        try:
            call()
        except ValueError as e:
            assert "unchecked" in str(e)
        else:
            raise AssertionError("expected ValueError")
    # explicit lower floors are allowed
    assert z_thickness(Manifold.cube([20, 20, 0.3]), 0.3, step=0.1)["ok_hard"] is True
    assert thin_walls(SLAB + WALL3, 0.2, hard_min_mm=0.2)["ok"] is True


def test_tiny_zone_does_not_excuse_whole_wall():
    tiny = {"tiny": (10.1, 10.2, 9.9, 10.1, 3, 5)}
    r = thin_walls(SLAB + WALL3, 0.8, zones=tiny, zone_min_wall=False)
    assert r["ok"] is False and r["ok_hard"] is False, r["excused_by_zone"]
    whole = {"all": (9.5, 11, 4.5, 15.5, 3, 5)}
    r = thin_walls(SLAB + WALL3, 0.8, zones=whole, zone_min_wall=False)
    assert r["ok"] is True and r["excused_by_zone"]["all"]["n_features"] >= 1


def test_for_printer_ties_floors_to_nozzle_and_layer():
    from aicad.checks import for_printer
    wall5 = SLAB + Manifold.cube([0.5, 10, 2]).translate([10, 5, 3])
    assert thin_walls(wall5, 1.2)["ok_hard"] is True                    # 0.4 nozzle
    kw = for_printer(0.6, 0.3)
    r = thin_walls(wall5, 1.2, **kw["thin_walls"])
    assert r["ok_hard"] is False and r["layer_mm"] == 0.3, r["findings"][:1]
    plate = Manifold.cube([20, 20, 0.5])
    assert z_thickness(plate, 0.9)["ok_hard"] is True                   # floor 0.4
    z = z_thickness(plate, 0.9, **kw["z_thickness"])                    # floor 0.6
    assert z["ok_hard"] is False and z["params"]["hard_min_mm"] == 0.6, z["params"]



if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
