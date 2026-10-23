# ai-cad

Tooling and method for using AI coding agents (Claude Code, Codex) to design
functional 3D prints in Python. No CAD GUI: the agent writes a parametric
generator, the generator checks itself, you print a small test piece, report
what failed, and the agent iterates.

The numbers in `docs/lessons.md` come from one setup (Elegoo Centauri Carbon 2,
PLA, PLA+ and PETG, 0.4 nozzle, 0.2 mm layers, September and October 2026). Your printer and filament
will give different numbers. The method carries over; the numbers are a
starting point to test, not values to copy.

## The method in one paragraph: coupon-driven design

Do not print the whole part to find out a hinge is wrong. Cut the risky
feature out as a **coupon** (a 15 to 60 minute print that holds only that
joint), have the agent build it from the same code as the full part, and give
it a numbered pass/fail checklist. Print, test by hand, write the result down
with the date, and let the agent change one thing at a time. A second model
reviews each plan before you spend filament. Details: [docs/method.md](docs/method.md).

## What's inside

| Path | What |
|---|---|
| `aicad/` | Small Python package of reusable helpers (below) |
| `examples/` | Three self-contained examples that run and verify themselves |
| `docs/method.md` | The coupon-driven design loop |
| `docs/review-loop.md` | Second-opinion review with a second model |
| `docs/lessons.md` | Generic print lessons, each dated with its setup |
| `docs/checks.md` | What the thickness and mesh checks report, what they miss, timings, results on 11 real parts |
| `data/` | Measured fit clearances (`fits-measured.json`) and the real-part check results, as JSON |
| `templates/AGENTS.md` | An `AGENTS.md` / `CLAUDE.md` starting point for a modelling repo |

## The `aicad` helpers

| Module | What it gives you |
|---|---|
| `mesh` | manifold3d <-> trimesh conversion, `load_mesh` (STL / 3MF file to one Manifold), `mesh_report` (watertight, body count, size; explains the STL coincident-vertex reload case), YZ / XZ sections, place on bed |
| `ppi_hinge` | Captive print-in-place hinge: `split_with_hinge(body, pivot, axis, forward)` splits a body that encloses the hinge band (width x thickness, one thickness each side of the pivot) into two linked parts, and raises if it does not; explicit top / bottom / side clearances |
| `checks` | Ray-measured clearances, `swing_sweep` (overlap vs angle, stop angles), serial-chain pose collisions, pairwise overlaps; re-exports the thickness checks below |
| `thickness` | `thin_walls` (in-layer XY width, per layer) and `z_thickness` (thin roofs / floors along Z, by solid geometry on XY tiles): per-piece findings with location and measured size, sliver, taper and one-layer filters with reported thresholds, named zones for intended thin features, and two verdicts: `ok_hard` (stop gate: nothing under one line / two layers after the stated filters) and `ok` (review list: anything under your design minimum). See [docs/checks.md](docs/checks.md) |
| `lowpri` | `python -m aicad.lowpri -- <command>`: idle priority, half the cores, timeout, and a whole-tree memory cap on Windows, for heavy mesh work |
| `sweep2d` | 2D side-view mechanism sweep with shapely: minimum gap per part pair over the motion, first colliding angle, free range |
| `coupons` | Test-piece builders: labelled hole gauge strip, 3-link hinge chain |
| `label` | Embossed / engraved text from matplotlib fonts (no font files) |
| `export` | STL / 3MF writers that re-read what they wrote, `verify_3mf`, `plate_check` (bed fit, keep-out zone, overlaps), `write_verification` (`verification.json` with `all_ok`) |
| `preview` | Headless matplotlib PNGs: shaded 3D view plus section panels, so the agent can look at every joint |

## Run the examples

With [uv](https://docs.astral.sh/uv/), from the repo root:

    uv run --with-requirements requirements.txt python examples/hole_gauge_strip.py
    uv run --with-requirements requirements.txt python examples/ppi_hinge_coupon.py
    uv run --with-requirements requirements.txt python examples/sweep2d_lid.py

Or install the package into a Python 3.12+ venv and run the examples with
`python` (on Python 3.11 or older pip fails with "No matching distribution
found for numpy"):

    python3.12 -m venv .venv  # or: uv venv --python 3.12 --seed .venv
    .venv/bin/python -m pip install -e .        # Windows: .venv\Scripts\python
    .venv/bin/python examples/hole_gauge_strip.py

`requirements.txt` pins the exact versions the examples were run with
(Python 3.12); `pyproject.toml` allows the same minor up to the next major,
which is untested.

Self-tests: every `tests/test_*.py` runs with plain Python (prefix each with
`uv run --with-requirements requirements.txt` when using uv):

    python tests/test_data.py
    python tests/test_hinge_export.py
    python tests/test_lowpri.py
    python tests/test_mesh_report.py
    python tests/test_verification.py
    python tests/test_z_thickness.py

or all at once with pytest:
`uv run --with-requirements requirements.txt --with pytest pytest tests`.

Checking your own parts: `python -m aicad.lowpri -- python tests/real_parts.py part.3mf --gate hard`
prints per part the mesh report and the thickness findings (grouped, with
location and measured size), what was ignored as a sliver and why, and the
timings. Prefer 3MF over STL. The thickness checks are heavy on 100k+
triangle meshes: run them at low process priority, one part at a time
([docs/checks.md](docs/checks.md)).

What the thickness checks can tell you: `ok_hard` is a filtered geometry
check, not a promise that the part prints. True means no measured feature is
narrower than one nozzle line in XY or thinner than two layers along Z, at the
stated resolution and filters; on 11 real parts (6 printed, 5 sliced, none
failed for thinness), 9 passed `ok_hard` and the other 2 each showed one real, measured
feature (details and limits in [docs/checks.md](docs/checks.md)). `ok` True
means nothing is under your design minimum either; `ok` False on a real part
is a short list of measured features to look at (walls of 0.5 to 0.8 mm that
print fine, pin roofs, embossed text), not a failed part. Put intended
features in named zones. Filtered pieces (numerical crumbs, footprints
narrower than a line, chamfer tapers, one-layer crescents) are counted in
`ignored`, not proven absent; `z_thickness` also returns `ok_strict`.
The defaults assume a 0.4 nozzle and 0.2 layers. For another setup pass
both: `python tests/real_parts.py part.3mf --nozzle 0.6 --layer 0.3
--min-wall 1.2 --min-z 0.9`, or in code `kw = for_printer(0.6, 0.3)` and
`thin_walls(m, 1.2, **kw["thin_walls"])`, `z_thickness(m, 0.9,
**kw["z_thickness"])`.

Each example prints its checks and exits non-zero if any check fails. Outputs
go to `examples/out/` (git-ignored): `hole_gauge_strip` and `ppi_hinge_coupon`
write STL, 3MF, PNG and `verification.json`; `sweep2d_lid` writes a PNG and
`verification.json`.

Sweeps are sampled, not exhaustive: `swing_sweep` tests every 1 deg over the
claimed range and bisects the first contact to 0.05 deg; `sweep2d.sweep`
samples at the spacing of `ts` and refines around gap minima and the first
violation to 0.01 deg. Contact narrower than one step can be missed. The
resolution is stored in each result. `write_verification` sets `all_ok` False
and lists `unassessed` for any check or file without a boolean `ok`.

| Example | What it builds and checks |
|---|---|
| `hole_gauge_strip.py` | 11 labelled vertical holes, 1.90 to 2.40 mm: one watertight body, no in-layer feature under 2 perimeters, no Z span under 0.8 mm, fits the bed, 3MF re-reads |
| `ppi_hinge_coupon.py` | Three 3-link hinge chains at side gaps 0.3 / 0.4 / 0.5: 3 bodies each, measured gaps equal design gaps, both joints free over +-60 deg with stops between 55 and 75 deg |
| `sweep2d_lid.py` | A lid on a box in side view, two pivot positions: the flush pivot collides, the offset pivot clears 0.4 mm through 110 deg |

The 3D helpers use [manifold3d](https://github.com/elalish/manifold) for
booleans and [trimesh](https://github.com/mikedh/trimesh) for IO. Your own
generators can use anything (build123d, CadQuery, OpenSCAD via a wrapper);
convert to a trimesh or manifold mesh to use the checks.

## Slicing

Command-line slicing, calibration prints and printer notes live in
[cc2-toolkit](https://github.com/BorjaLL/cc2-toolkit). This repo stops at the
checked 3MF.

## Related work

Other projects where an AI agent writes CAD code (checked 2026-09-29). They
iterate on screen (renders, assertions); this repo adds printed test coupons,
the maker's feedback and a second-model review.

- [flowful-ai/cad-skill](https://github.com/flowful-ai/cad-skill): Claude Code skill, CadQuery script, render, iterate
- [cyberchitta/cad-khana](https://github.com/cyberchitta/cad-khana): diagnostics-first build123d wrapper for LLM iteration
- [pzfreo/build123d-mcp](https://github.com/pzfreo/build123d-mcp): MCP server to build, render, measure and export build123d parts
- [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad): large library of agent skills for CAD, CAE and CAM

Checked 2026-10-23:

- [jdilla1277/agentcad](https://github.com/jdilla1277/agentcad): CAD CLI and MCP server for AI agents
- [pzfreo/cadgenbench-build123d](https://github.com/pzfreo/cadgenbench-build123d): benchmark pipeline, Claude Code plus build123d
- [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp) and [spkane/freecad-addon-robust-mcp-server](https://github.com/spkane/freecad-addon-robust-mcp-server): MCP servers that drive FreeCAD
- [m-esm/3d-print-modeling](https://github.com/m-esm/3d-print-modeling): Claude Code skill for FDM parts with a similar Python stack
- [iancanderson/openscad-agent](https://github.com/iancanderson/openscad-agent): Claude Code environment for OpenSCAD models
- [Adam-CAD/CADAM](https://github.com/Adam-CAD/CADAM): open source text-to-CAD web app
- [ahujasid/mcp-for-blender](https://github.com/ahujasid/mcp-for-blender): drive Blender from an LLM (mesh and organic work rather than CAD)

## License

Code MIT (`LICENSE`), docs and data CC BY 4.0. Details: `NOTICE.md`.
