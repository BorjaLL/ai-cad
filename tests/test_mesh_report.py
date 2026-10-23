"""mesh_report / load_mesh on files: the STL coincident-vertex reload case is
explained and verified, a real hole still fails. Run: python tests/test_mesh_report.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from manifold3d import Manifold  # noqa: E402

from aicad.mesh import load_mesh, mesh_report, to_trimesh  # noqa: E402


def two_cubes_sharing_an_edge():
    # touching along the edge x = 10, z = 10: a valid 2-body solid, but
    # merging every coincident STL vertex joins them at that edge
    return Manifold.compose([Manifold.cube([10, 10, 10]),
                             Manifold.cube([10, 10, 10]).translate([10, 0, 10])])


def write_stl(tm, d):
    p = Path(d) / "part.stl"
    tm.export(str(p), file_type="stl")
    return p


def test_stl_touching_bodies_ok_with_explanation():
    with tempfile.TemporaryDirectory() as d:
        p = write_stl(to_trimesh(two_cubes_sharing_an_edge()), d)
        r = mesh_report(p, expected_bodies=2)
        assert r["ok"] is True and r["bodies"] == 2, r
        assert r["stl_reload"]["trimesh_merge_watertight"] is False
        assert "known STL reload issue" in r["stl_reload"]["note"]
        m, info = load_mesh(p)
        assert len(m.decompose()) == 2 and abs(m.volume() - 2000) < 1e-3


def test_stl_with_a_hole_fails():
    tm = to_trimesh(Manifold.cube([10, 10, 10]))
    tm = trimesh.Trimesh(tm.vertices, tm.faces[1:], process=False)   # drop one triangle
    with tempfile.TemporaryDirectory() as d:
        p = write_stl(tm, d)
        r = mesh_report(p)
        assert r["ok"] is False and "not a closed solid" in r["stl_reload"]["note"], r
        try:
            load_mesh(p)
        except ValueError as e:
            assert "not closed solids" in str(e)
        else:
            raise AssertionError("load_mesh accepted an open mesh")


def test_3mf_objects_composed():
    with tempfile.TemporaryDirectory() as d:
        sc = trimesh.Scene()
        sc.add_geometry(to_trimesh(Manifold.cube([5, 5, 5])), geom_name="a")
        sc.add_geometry(to_trimesh(Manifold.cube([5, 5, 5]).translate([10, 0, 0])), geom_name="b")
        p = Path(d) / "two.3mf"
        p.write_bytes(sc.export(file_type="3mf"))
        m, info = load_mesh(p)
        assert info["objects"] == 2 and len(m.decompose()) == 2
        assert np.allclose(m.bounding_box(), (0, 0, 0, 15, 5, 5))
        assert mesh_report(p, expected_bodies=2)["ok"] is True


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
