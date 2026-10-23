# Agent instructions for a 3D modelling repo (template)

Copy to your repo as `AGENTS.md` (Codex) and/or `CLAUDE.md` (Claude Code).
Replace the <angle bracket> parts. Delete what you do not use.

## Printer and material (fill in, the agent reads this before picking numbers)

- Printer: <model>, nozzle <0.4>, layers <0.2>, material <PLA>.
- Measured fits live in a JSON table (example: `data/fits-measured.json` in
  ai-cad), keyed by filament, then hole axis IN THE PRINT POSE (vertical or
  horizontal), then fit kind (press, snug, slide, free). Each entry has its
  date and whether it was printed or estimated.
  - vertical hole for a 1.75 pin, <filament>: <size> grips, <size> turns
  - horizontal hole for a 1.75 pin, <filament>: <size> grips, <size> turns
  - print-in-place gap, <filament>: <size> (PETG needs more than PLA)
- Look up a fit only after the print pose is fixed. A pose change re-derives
  every fit.
- Unknown fit? Propose a gauge strip coupon first. Do not use numbers from the
  internet as final values.
- Heavy mesh work (booleans, thickness checks, slicing): run it through
  `python -m aicad.lowpri -- <command>`, one part at a time.

## Project layout

    projects/<name>/
      README.md        what it is, source (own design or remix + license), status
      DESIGN.md        requirements, measurements, decisions with dates
      generator/       the parametric generator (source of truth for geometry)
      test-prints/     coupon scripts, checklists, results, photos
      reviews/         second-opinion reviews, one file per review, dated

## How to design

0. Reuse first: if a published part or interface exists, print it before
   modelling. Show 3 or 4 shaded concept renders and get one picked before
   CAD. Take sizes from published specs or existing meshes before asking for
   a tape measure.

1. Write requirements and measurements into `DESIGN.md` before code.
2. One generator per part family. Every dimension is a named constant at the
   top. Write the coordinate frames in the docstring.
3. Export STLs already in print orientation, plus a plate 3MF and preview
   renders (sections through every joint).
4. The script prints its own checks: overlaps between parts, clearances,
   a sweep through every motion, thin walls, strain on every flexure, and
   writes them to `verification.json` with an `all_ok` flag. Choose each
   check's gate explicitly before you run it; a failing gate is a stop, not
   a warning. Thickness checks have two flags: gate on `ok_hard` and put the
   `ok` findings in the review list, e.g.
   `checks = dict(walls=gated(thin_walls(m, 0.8)), roofs=gated(z_thickness(m, 0.6)))`
   (`aicad.checks.gated`: its `ok` is the gate, the advisory findings sit
   under `review`). Read every review finding and say in `DESIGN.md` why it
   is intended or fix it. Every other check's `ok` is its gate.
5. Coupons import the generator's functions. Never copy geometry by hand into a
   coupon.

## Before a print

- Say which face carries the load in each pose. A click or snap is never the
  only thing holding a loaded part.
- Bearing faces on exact layer boundaries, no bearing face on a bridge
  underside, thin springs flex inside the layer plane.
- Check the pose in the slicer: nothing starts in mid-air, no supports inside
  bores or channels, a brim touching tall thin parts, the first layer is not
  a tiny foot under a flared part.
- Give the print time and grams from the slicer, and a numbered checklist with
  a pass condition per step.
- Prints over <1 hour>, or changes to a joint that already passed: get a
  read-only second-model review first, then answer each point in `DESIGN.md`.

## After a print

- Write the result into the coupon README with the date, in the user's words.
- Keep the failed version's script and write why it failed in its docstring.
- Change the smallest thing that explains the failure. One change per coupon
  when possible.
- When a version passes, record the exact command line that built it.

## Writing

- Plain ASCII, short sentences, numbers with units.
- Results are dated facts about this setup, never general rules.
