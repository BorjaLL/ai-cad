"""ppi_hinge and export edge cases. Run: python tests/test_hinge_export.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manifold3d import Manifold  # noqa: E402

from aicad.export import export_3mf  # noqa: E402
from aicad.ppi_hinge import split_with_hinge  # noqa: E402


def test_hinge_keeps_bodies_larger_than_default_territory():
    # 1000 mm long bar (Y -500..500): the halves must reach both ends
    bar = Manifold.cube([20, 1000, 8]).translate([-10, -500, 0])
    a, b, _ = split_with_hinge(bar, (0, 0, 4), (1, 0, 0), (0, 1, 0))
    ya = a.bounding_box()[1]
    yb = b.bounding_box()[4]
    assert ya < -499.9 and yb > 499.9, (ya, yb)
    assert abs(a.volume() + b.volume() - bar.volume()) / bar.volume() < 0.01


def test_export_3mf_refuses_mismatched_names():
    parts = [Manifold.cube([1, 1, 1]), Manifold.cube([1, 1, 1]).translate([3, 0, 0])]
    with tempfile.TemporaryDirectory() as d:
        try:
            export_3mf(parts, ["only_one"], Path(d) / "x.3mf")
        except ValueError as e:
            assert "2 parts but 1 names" in str(e)
        else:
            raise AssertionError("expected ValueError")
        assert not (Path(d) / "x.3mf").exists()


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
