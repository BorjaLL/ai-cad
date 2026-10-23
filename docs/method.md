# Coupon-driven design with an AI agent

One person's workflow (September 2026, Claude Code and Codex, build123d and
manifold3d in Python, one Elegoo Centauri Carbon 2 printing PLA), written down
so you can copy the parts that fit yours. The helpers in `aicad/` implement
steps 2, 3 and 5.

## The loop

1. **Describe the part in words and numbers.** Take sizes from what already
   exists first: published specs, or a mesh of a part that already fits (one
   listing figure read as 7.29 was 17.28 on the mesh). A photo with a printed
   scale card comes next, calipers last. The agent writes these into a
   design doc (`DESIGN.md`) before any code, as a short brief: target, what
   changes from the last version, what is out of scope, units and reference
   frame, the chosen concept picture, and a measurable "done means".
2. **Agent writes a parametric generator.** One Python script, every dimension a
   named constant at the top, frames and axes written down in the docstring.
   It exports STLs in print orientation, a plate 3MF and preview renders
   (`aicad.export`, `aicad.preview`).
3. **Agent checks the geometry in software.** The script prints its own checks:
   overlaps between parts (boolean volume with manifold3d), a sweep through the
   motion (does the hinge collide at 30, 60, 90 deg?), clearances, thin walls,
   beam strain (`aicad.checks`, `aicad.sweep2d`). The results go into a
   `verification.json`. A check that fails stops the print.
4. **Second opinion.** A second model (Codex in my case) reviews the plan and
   the checks, read-only. The agent answers each point in the doc: changed, or
   rejected and why. See [review-loop.md](review-loop.md).
5. **Cut a coupon.** Only the risky joint, full scale, 15 to 60 minutes of
   printing. The coupon is built from the same functions as the full part, so a
   pass means the real part has the same geometry (`aicad.coupons`).
6. **Print and test with a checklist.** Numbered steps, each with a pass
   condition you can check by hand ("folds 180 deg with one finger", "lies flat,
   tip height under 0.3 mm"). Take close-up photos of every failure.
7. **Report back, one line per failure.** What happened, in your words. The
   agent writes it into the doc with the date, finds the cause and changes the
   smallest thing that fixes it. Then back to step 3.
8. **Record the decision.** When a version passes, the doc says which version,
   which command line, and the date. Losing alternatives stay behind a switch
   (`--joint glued|ppi|clip`) so you can compare later.

## Rules that paid off

- **Keep every failed version.** `coupon_v2.py` stays next to v3 with its
  failure written in the docstring. The next agent session reads why v2 failed
  before it proposes v4.
- **Print a gauge before trusting a size.** Holes, gaps and clearances depend on
  the printer. A strip of holes in 0.05 mm steps costs 10 minutes and replaces
  guessing.
- **Change one thing per coupon** when you can. When a coupon fails with three
  changes in it, you do not know which one failed.
- **Say where the load goes.** For every joint, write which face carries the
  load in each pose (flat, folded, lifted). A click, a bump or a snap is not
  allowed to be the only thing holding a loaded part.
- **Design for the layer grid.** Bearing faces on exact layer boundaries,
  loaded thin features flexing inside the layer plane, no bearing face on a
  bridge underside.
- **Write results as dated facts,** not as general truths: "2.0 mm vertical
  hole printed about 1.5 mm (CC2, PLA, 0.2 layers, 2026-09-25)".

## What the agent is good and bad at here

Good: turning a sentence like "the lid must lock flat but fold to 90" into a
parametric part, sweeping a mechanism through 180 deg in software, catching
collisions, keeping docs and checklists in step with the code, preparing
coupons for several independent designs at once (one agent per design; two
agents rebuilding the same design compete and waste both runs).

Bad: knowing how your printer really prints a 2 mm hole, a 0.2 mm gap or a
bridge. Every fit number that mattered came from a printed coupon, not from the
model or from the internet. Treat the agent's first numbers as a guess to test.

Also bad (October 2026): organic shapes from hand-typed coordinates. About
12 versions of one organic part got no approval. Code-CAD works for
prismatic, functional parts; organic shapes came out better traced from a 2D
picture (plates, reliefs) or generated whole from an image, with the
functional features (holes, joints, flat bases) added in code afterwards.

## Before you design (added October 2026)

- **Reuse first.** If someone already published the part or the interface,
  print theirs on their recommended settings before modelling anything.
  Remix only to fix a complaint you wrote down after that print.
- **Remixing a multi-part design: print the designer's first stage first.**
  Design nothing that attaches to a part until that part is printed, in your
  hand and measured. Check the filament you have against the planned grams
  before slicing the rest.
- **Concept pictures before CAD.** Show 3 or 4 small shaded 3D concept renders
  (about 1024 px; flat line sketches were hard to judge) and let the person
  pick one. A change of direction is a new brief, not a message relayed into a
  running agent.
- **A coupon before version 3.** Two unprinted versions of the same part in a
  row is the signal to cut a coupon of the risky feature instead.
- **Stop signs.** Three or more versions with no print: park the design. The
  person says "worse": stop and ask what changed. The same complaint twice
  with no new detail: change the method, not the parameters.

## Gates before a print (added October 2026)

Geometry checks (step 3) did not catch most real failures. These did, each
one after a failed print:

| Gate | What it catches | Helper |
|---|---|---|
| Fit lookup by hole axis in the print pose | loose or tight pockets after a pose change | `data/fits-measured.json` as a starting table |
| Pose / floating material per layer | upside-down downloads, mid-air islands | not in `aicad` yet (see lessons) |
| Supports inside bores | supports you cannot remove | slicer preview, by hand |
| First-layer foot vs area a few mm up; brim on tall parts | parts knocked off the bed | slicer preview, by hand |
| Thin walls and thin roofs | features the slicer drops or prints as one weak line | `aicad.thickness`, gate on `ok_hard` |

Report every gate by name, result and what it covers. Keep hypotheses ("it
should hold") apart from physical results ("it held, 2026-10-16").

A render can reject a direction or pick between options; it cannot approve a
print. Four measurable faults (first-layer section, pose, print profile, bed
fit) were found only after five rounds of render approval on one part.

Approve the design and its slicing recipe (pose, supports, fits), not a
G-code file: re-slice at print time so printer and speed settings are
current.

## Agents and tools (October 2026)

- **One CAD agent with the CAD tools.** A dedicated CAD subagent gets the CAD
  MCP servers (a build123d server for generators, a FreeCAD server for
  interactive parameter edits); other sessions stay lean. Editing a FreeCAD
  spreadsheet parameter took 0.4 to 0.65 s against about 20 s for a full
  generator rerun. One writer per FreeCAD document, a saved checkpoint
  before risky operations, heavy booleans in a headless worker with a
  timeout.
- **One owning agent per iteration loop.** Fixed camera views, a cheap render
  check before an expensive build. Parallel agents only across independent
  designs.
- **Image budget.** Four views at about 1024 px per review; downscale anything
  over 2048 px before it reaches the model.
- **Numbers live in files, not in agent memory.** Fit values and printer
  limits kept in an agent's memory drifted and contradicted the state files.
  Keep numbers in JSON, and turn a correction that repeats into a check in
  code: code-enforced rules did not recur, memory-only rules did.
- **Heavy geometry at low priority.** `python -m aicad.lowpri -- <command>`.
- **Licence gate for generated meshes.** Record the image-to-3D generator's
  licence before you build on its output; at least one excludes some
  countries from its licence.
