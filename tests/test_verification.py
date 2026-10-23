"""Self-test: write_verification must not report all_ok without a real bool ok.

Run: python tests/test_verification.py   (pytest also works)
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aicad.export import write_verification  # noqa: E402


def run(checks, files=None):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "verification.json"
        doc = write_verification(p, "t", checks, files=files)
        assert json.loads(p.read_text())["all_ok"] == doc["all_ok"]
        return doc


def test_all_ok_when_every_check_has_bool_ok():
    doc = run(dict(a=dict(ok=True), b=[dict(ok=True), dict(ok=True)]), files=[dict(ok=True)])
    assert doc["all_ok"] is True and doc["unassessed"] == []


def test_missing_ok_fails():
    doc = run(dict(a=dict(ok=True), b=dict(value=1)))
    assert doc["all_ok"] is False and "checks.b" in doc["unassessed"]


def test_non_bool_ok_fails():
    for bad in (1, "yes", None):
        doc = run(dict(a=dict(ok=True), b=dict(ok=bad)))
        assert doc["all_ok"] is False and "checks.b" in doc["unassessed"], bad


def test_list_item_without_ok_fails():
    doc = run(dict(a=[dict(ok=True), dict(x=1)]))
    assert doc["all_ok"] is False and "checks.a[1]" in doc["unassessed"]


def test_file_without_ok_fails():
    doc = run(dict(a=dict(ok=True)), files=[dict(path="x.stl")])
    assert doc["all_ok"] is False and "files[0]" in doc["unassessed"]


def test_false_ok_and_empty_fail():
    assert run(dict(a=dict(ok=False)))["all_ok"] is False
    assert run({})["all_ok"] is False


def test_gated_thickness_result_puts_advisory_findings_in_review():
    from manifold3d import Manifold
    from aicad.checks import gated, thin_walls
    slab = Manifold.cube([20, 20, 3])
    walls = thin_walls(slab + Manifold.cube([0.6, 10, 2]).translate([10, 5, 3]), 0.8)
    assert walls["ok"] is False and walls["ok_hard"] is True
    assert run({"walls": walls})["all_ok"] is False            # raw: advisory ok is a stop
    d = run({"walls": gated(walls)})
    assert d["all_ok"] is True and d["checks"]["walls"]["gate"] == "ok_hard"
    assert d["checks"]["walls"]["review"]["n_findings"] == 1
    assert run({"walls": gated(walls, "ok")})["all_ok"] is False


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
