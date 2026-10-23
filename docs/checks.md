# Thickness and mesh checks: what they report and what they miss

`aicad.checks` re-exports `thin_walls`, `z_thickness`, `min_wall_in_zones` and
`named_zones` from `aicad/thickness.py`; `mesh_report` and `load_mesh` live in
`aicad/mesh.py`. Every check returns a dict with a boolean `ok`. A check reports
`ok` True only after it has verified its claim; when it runs out of time, it
says `verified: False` and `ok: False`.

## Two verdicts: ok_hard and ok (2026-10-23)

The first version (2026-09-29) flagged every real part we tried, including
parts that printed fine, so it was useless as a gate. Two things were wrong:

1. **Measurement artifacts in `z_thickness`.** Most findings were the thin
   edge of a wedge: where a chamfer meets the bed, where a sloped face meets
   a flat one, where a rounded body sits on the bed. A vertical span there
   runs from 0 up to `min_mm` over a short distance. That is geometry the
   slicer handles every day, not a thin roof. Fixed by the taper filter
   (below).
2. **One threshold for two questions.** `thin_walls(m, 0.8)` reports every
   wall under two lines, but walls of 0.5 to 0.8 mm print fine with a
   variable-width wall generator. "Will it print" and "is it under my design
   minimum" need different thresholds. Fixed by `ok_hard`.

| Flag | Means | Default floor |
|---|---|---|
| `ok_hard` | verified, and no finding under the hard floor | `thin_walls`: at least `min_layers` layers whose widest point is under one nozzle line (0.4), judged per layer before merging; `z_thickness`: thinnest span under two layers (`2 * step`, 0.4) |
| `ok` | verified, and no finding at all under your `min_feature` / `min_mm` | yours |
| `ok_strict` (`z_thickness`) | `ok`, and nothing filtered except pieces measured thick | |

`ok_hard` is a filtered geometry check, not a promise that a part prints:
it says no measured feature is under the hard floor after the filters below.
Use it as the stop gate and read the `ok` findings as a review list.
`gated(result)` writes a result into `verification.json` that way (its `ok`
is the gate, the findings go under `review`).
`tests/real_parts.py --gate hard` sets its exit code from `ok_hard`.
A hard floor above the design minimum (`hard_min_mm > min_mm` or
`> min_feature`) raises ValueError: those features would never be candidates.

Another nozzle or layer height: `kw = for_printer(0.6, 0.3)`, then
`thin_walls(m, 1.2, **kw["thin_walls"])` and `z_thickness(m, 0.9,
**kw["z_thickness"])`. That moves the section spacing, the Z step, the
footprint filter and both hard floors together (`tests/real_parts.py
--nozzle 0.6 --layer 0.3`).

## Results on real parts (2026-10-23)

11 parts (STL / 3MF, 2k to 567k triangles) for an Elegoo Centauri Carbon 2
with a 0.4 nozzle, 0.2 layers: 6 printed (the job log shows them complete)
and 5 only sliced without errors; none failed for thinness. The parts are
anonymised and their meshes are not in the repo, so the numbers are a
record, not a benchmark you can rerun:
hinge and spine coupons, a 250 mm board plate with 24 bodies, a print-in-place
hinge coupon, two organic figures, three plain functional parts, a
thin-walled crate and a 567k-triangle decorated panel. Run with
`--min-wall 0.8 --min-z 0.6`, one part at a time at idle priority. Per-part
numbers, evidence (printed or sliced, with date) and the code commit tested: [data/real-parts-thickness-2026-10-23.json](../data/real-parts-thickness-2026-10-23.json).

- `z_thickness`: `ok` on 10 of 11 (before the fix: 3 of the 6 parts measured
  with the old code). The 11th, the board plate, keeps 4 findings, `ok_hard`
  False: horizontal pin bores whose crown comes within 0.30 mm of the top
  face and of the bed. They are real, measured, intended skins (about 1.5
  layers); a named zone excuses them.
- `thin_walls`: `ok_hard` on 10 of 11. The 11th, the decorated panel, has 6
  hard features (rerun after the per-layer hard fix; the first run counted
  3): walls 0.27 to 0.35 mm wide and up to 25 layers tall, and walls that are
  0.33 mm for about 17 layers and widen to 0.6 mm above (the old merge kept
  only the wider value). Real sub-line walls that the slicer printed as
  single beads. `ok` is False on 4 parts with walls of
  0.5 to 0.8 mm (the crate's 0.52 to 0.62 mm walls give 76 findings), all
  printed fine.
- Time: under 60 s per part for both checks together, except one 85k-triangle
  part with 5 bodies whose `z_thickness` took about 175 s.

So: the false positives we could trace to the method are fixed; the
findings left on known-good parts are real thin features, reported with
size and place. They are not proof that the checks catch every bad part:
the corpus has no part that failed for thinness, and the bad cases are
synthetic (tests/test_z_thickness.py).

## Run heavy checks at low priority

`z_thickness` and `thin_walls` on a 100k+ triangle part use every core the
geometry library can get and can make the machine unusable for a minute. Run
them (and `tests/real_parts.py`) at idle priority on part of the cores, one
part at a time, with a timeout:

    python -m aicad.lowpri -- python tests/real_parts.py part.3mf

`aicad.lowpri` gives idle priority, half the cores, a timeout (900 s, or
`--timeout SEC`) and on Windows a memory cap for the whole process tree
(`--mem-gb GB`, default 12). Without `aicad.lowpri`:

    # Windows (cmd): low priority, cores 0-7, no memory cap
    start /low /affinity FF /wait python tests/real_parts.py part.3mf
    # Linux
    nice -n 19 taskset -c 0-7 timeout 600 python tests/real_parts.py part.3mf

## Result shape (thin_walls and z_thickness)

| Key | What |
|---|---|
| `findings` | thin features outside zones, largest volume first, capped at `max_findings`; each has `bbox` [x0, y0, z0, x1, y1, z1] and `volume_mm3`, plus a measure (below) |
| `n_findings` | the total before the cap |
| `groups` | repeated findings (same size, volume and measure) as one line: `n`, `size_xyz`, up to 3 `at` origins |
| `ignored` | what was dropped as a numerical artifact, per reason, with the threshold in the key name and a count |
| `excused_by_zone` | per named zone: count, volume and the largest pieces it excused |
| `params` | every threshold used |
| `verified` | False if the time budget ran out; then `ok` is False and `note` says what was not checked |

Zones: pass `zones={"pin_roofs": (x0, x1, y0, y1, z0, z1), ...}`. A list of
boxes still works (named `zone0`, `zone1`, ...). Use a zone for thin material
you intend (a sacrificial roof over a pin hole, embossed text, the inside of a
joint); the report shows what each zone excused, so a zone that hides too much
is visible.

## z_thickness(m, min_mm, step=0.2, ...)

Finds material in a vertical solid span shorter than `min_mm` (thin roofs,
floors, bridges, feather edges on the bed).

1. Candidates, complete: a thin span's bottom lies on a down-facing triangle
   and its top on an up-facing triangle above it within `min_mm`. Every such
   pair is found from triangle bounding boxes (rtree). Regions without a
   candidate are proven thick and skipped. This proof holds for the mesh
   the pass runs on: after simplification (default 0.01 mm) that is the
   simplified mesh, so it covers the original only within the reported
   `surface_error_bound_mm`.
2. The part is split in XY into full-height prisms (this keeps every vertical
   span intact, so the split is exact) until a tile has at most
   `max_tile_tris` triangles.
3. Per tile, by solid geometry: the part minus the part grown back from its
   "at least `min_mm` of solid above" core (copies shifted in `step`).
4. Each thin piece is measured and classified:

| Outcome | Rule (defaults for a 0.4 mm nozzle) |
|---|---|
| ignored `volume_below_0.001_mm3` | numerical crumbs |
| ignored `footprint_narrower_than_0.4_mm` | the piece's XY footprint vanishes under an erosion by `min_footprint / 2`: narrower than one extrusion line everywhere. Typical: the rim of any rounded body, facet slivers round holes, knife edges along chamfers |
| ignored `every_sampled_span_at_least_<min>_mm` | vertical rays at up to `n_rays` vertices of the eroded footprint plus up to `n_rays` interior grid points all cross a span >= `min_mm`. A real thin piece is thin at every point of its footprint, so this refutes it (a skin left by near-tangent facets) |
| ignored `taper_at_least_<t>_mm_per_mm` | every thin span sampled lies between non-parallel faces: its length grows sideways by at least `min_taper` mm per mm (default 0.36, a face 20 deg off the other). A wedge is thin only within about `min_mm / min_taper` (1.7 mm at the defaults) of where it reaches `min_mm`. One parallel-faced thin span keeps the piece (a flat roof with a chamfered rim stays a finding). `min_taper=math.inf` turns it off. Counts against `ok_strict` |
| excused by a zone | the part of the piece inside the zone box |
| finding | `thickness_min_mm` / `thickness_max_mm` measured by those rays (`n_rays`, `n_rays_thin`), `footprint_area_mm2` |

Big meshes: the part is simplified at `simplify_mm` (0.01) and each
intermediate boolean at a quarter of that. Without this, dense curved meshes
multiply their triangle count in the shifted intersections (one 8k-triangle
tile of an organic part became 200k triangles and took 47 s; a whole
250k-triangle part crashed the native library with no traceback). The bound
on how far a thin surface can be off is `params.surface_error_bound_mm`
(about 0.018 mm); spans within that of `min_mm` can go either way.
`simplify_mm=0` is exact and slow.

What it can miss or blur:
- a wedge-shaped thin feature (a knife edge, a tapered flap with faces more
  than about 20 deg apart) is filtered as a taper and counted, not reported;
- the taper and ray filters sample points (vertices plus a grid), so a small
  parallel-faced patch between samples can be missed;
- a void thinner than `step` (one layer) inside a span: the span counts as solid;
- spans between `min_mm - step` and `min_mm` are only partly flagged;
- a roof narrower than `min_footprint` is ignored by design. A free-standing
  fin that narrow is found by `thin_walls`, but a narrow ledge on a thick
  wall (for example 0.3 wide, 0.2 thick) is seen by neither check: it prints
  as a bump in the outer perimeter (pinned by a test);
- a piece cut by a tile edge is merged back by bbox contact, so two pieces
  whose boxes touch are reported as one;
- the time budget is checked between tiles: one slow tile can overrun it.

## thin_walls(m, min_feature, layer=0.2, ...)

Per layer, the section is opened (eroded and dilated) by `min_feature / 2`;
what disappears is narrower than `min_feature`. Pieces in consecutive layers
with touching boxes become one finding with `layers`, `width_mm` and
`width_max_mm`: per layer the width is the widest point of the lost piece
(largest inscribed disc); after merging `width_mm` is the narrowest layer and
`width_max_mm` the widest, and `layers_hard` counts the layers under
`hard_min_mm`, so a narrow stretch under a wider top still fails `ok_hard`.

| Outcome | Rule |
|---|---|
| ignored `area_below_0.2_mm2` | per-layer crumbs (facet corners) |
| ignored `shorter_than_2.0_mm` | convex-corner rounding: every sharp outside corner loses a small crescent |
| ignored `fewer_than_2_layers` | a merged piece seen in fewer than `min_layers` sampled layers: usually the crescent one layer cuts from a near-horizontal curved surface. Reported with count, volume and the narrowest width. A real fin or wall shows in several layers. `min_layers=1` turns it off |
| excused by a zone | the piece's whole XY box inside the zone box at that layer (a piece partly outside stays a finding) |

Hairlines under 0.01 mm left by offset rounding are removed first.
What it can miss: features between two sampled layers, walls shorter than
`min_len` or smaller than `min_area` per layer, and thin material along Z
(use `z_thickness`). `width_mm` is the widest point, not the thinnest:
`min_wall_in_zones` bisects the thinnest wall inside zones.

## mesh_report and load_mesh

`mesh_report(path_or_mesh)` checks watertight, winding, bodies, volume.
STL stores loose triangles; manifold3d output can hold coincident but
separate vertices where two bodies touch at an edge (print-in-place joints).
Re-merging every coincident vertex after an STL reload joins those bodies and
reports "not watertight". The report then rebuilds the mesh with manifold3d,
which merges only along open edges: if that gives a valid manifold, `ok` is
True and `stl_reload` explains both results. A real hole still fails.
Prefer 3MF: it keeps the indexed mesh. `load_mesh(path)` returns one
Manifold (3MF objects composed) or raises with the reason.

## Timings (2026-09-29)

Measured 2026-09-29 on a 16-core desktop at idle priority on 8 cores,
min_wall 0.8, min_z 0.6, step 0.2 (`tests/real_parts.py`):

| Part | Triangles | thin_walls | z_thickness |
|---|---|---|---|
| flat board part, 250 x 197 x 6 mm | 16k | 0.2 s | 3.5 s |
| tall block, 105 x 250 x 32 mm | 24k | 0.1 s | 3 s |
| hinge test coupon, 30 bodies (STL) | 72k | 0.9 s | 5 s |
| organic figure, 4 bodies | 204k | 2.4 s | 11 s |
| organic figure, 10 bodies | 254k | 34 s | 4 s |
| organic figure, 7 bodies | 393k | 11.5 s | 15 s |

Before the tiling and simplification, `z_thickness` on the 254k part crashed
with no traceback.

## What real parts look like (2026-09-29, before the ok_hard split)

On seven real parts that printed or were sliced without problems, the checks
went from "fail with thousands of pieces" (13 mm3 across 4416 pieces on one
board part) to 0-15 findings per part, each a real, measured feature: roofs
and floors round pin counterbores (0.3-0.5 mm), a slot floor cut by a seam
chamfer (0.2-0.4 mm), shelves under print-in-place knuckle feet (0.1-0.5 mm
on the bed), hoods over hinge bands, embossed text strokes (0.65-0.77 mm), and
knife edges where a chamfer meets a pocket. These are intended; a named zone
per feature family turns them into `excused_by_zone` entries. `ok` False on
such a part means "look at these N features", not "it will not print".

## ok, ok_strict and the time budget

- `ok`: verified, and no finding outside zones under the stated filters.
  Ignored pieces are counted, not proven absent.
- `ok_strict` (z_thickness only): `ok`, no piece ignored by volume or
  footprint, and simplification lost no body and no more volume than its
  error bound (a feature thinner than `simplify_mm` can vanish in it).
  Pieces refuted by vertical rays (measured thick) do not count against it.
- `thin_walls` has no strict flag: it always ignores convex-corner rounding,
  and a feature lying between two sampled layers is not seen.
- `time_budget_s` is advisory: it is checked between tiles or layers, so a
  single slow step can overrun it. `z_thickness` refuses meshes above
  `max_input_tris` (default 2,000,000) up front. Run heavy checks at low
  process priority, one part at a time.
