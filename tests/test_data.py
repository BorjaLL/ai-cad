"""data/*.json: well-formed and complete. Run: python tests/test_data.py"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
KINDS = {"press", "snug", "slide", "free"}
AXES = {"vertical", "horizontal", "unknown"}


def test_fits_measured_entries_complete():
    d = json.loads((DATA / "fits-measured.json").read_text())
    assert d["entries"], "no entries"
    for e in d["entries"]:
        assert e["axis"] in AXES and e["target_fit"] in KINDS | {None}, e
        assert e["observed_fit"] in KINDS | {"fused"} and isinstance(e["passed"], bool), e
        assert e["per_side_basis"] in ("cad_nominal", "measured"), e
        assert 0 <= e["per_side_mm"] < 1 and e["material"] and e["outcome"] and e["case"], e
        assert len(e["date"]) == 10 and e["date"].startswith("2026-"), e
        if e["target_fit"] and e["observed_fit"] != e["target_fit"]:
            assert e["passed"] is False, e     # missed its target: a failure


def recommended(entries, fit):
    """Starting clearances for a fit: passed trials that showed that fit."""
    return [e for e in entries if e["passed"] and e["observed_fit"] == fit]


def test_failed_trials_are_never_recommended():
    d = json.loads((DATA / "fits-measured.json").read_text())
    failed = [e for e in d["entries"] if not e["passed"]]
    assert failed, "the table should keep its failures"
    for fit in KINDS:
        assert not any(e in failed for e in recommended(d["entries"], fit))
    # the loose magnet pockets are not press fits, the fused PETG hinge not a slide
    press = recommended(d["entries"], "press")
    assert all("magnet" not in e["case"] for e in press), press
    assert all(e["material"] != "PETG" for e in recommended(d["entries"], "slide"))


def test_real_parts_results_consistent():
    d = json.loads((DATA / "real-parts-thickness-2026-10-23.json").read_text())
    for p in d["parts"]:
        for k in ("thin_walls", "z_thickness"):
            r = p["after"][k]
            assert r["ok_hard"] in (True, False) and r["findings"] >= 0, p
            if r["ok"]:
                assert r["findings"] == 0 and r["ok_hard"], p


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
