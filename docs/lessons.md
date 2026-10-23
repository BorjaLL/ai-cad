# Print lessons, as measured on one setup

Setup for every line below unless it says otherwise: Elegoo Centauri Carbon 2,
PLA, 0.4 nozzle, 0.2 mm layers, 1.75 mm filament used as hinge pins, September
2026. Lessons from October 2026 name their material (PLA+, PETG) because it
turned out to matter. Re-test each one on your printer (a 10 to 20 minute
coupon, for example `examples/hole_gauge_strip.py`) before you design around
it. Measured fit numbers are in [data/fits-measured.json](../data/fits-measured.json).

## Holes and pins

- **Vertical holes print small.** Axis along Z: a 2.0 mm hole printed about
  1.5 mm. For a 1.75 filament pin: 2.2 = slight friction (pin stays), 2.3 =
  spins free (pivot), 2.4 = loose. (2026-09-25)
- **Horizontal holes print closer to size,** but a long horizontal pin path
  through several parts still binds: 2.0 needed a 2 mm drill, 2.2 with an
  entry chamfer pushed through by hand. (2026-09-25)
- **Gauge strips beat calipers.** Holes 1.90 to 2.40 mm in 0.05 steps read
  0.2 to 0.4 mm under on calipers, and calipers are unreliable at this size.
  Whether the filament enters, grips or turns in each hole is the real test.
  (2026-09-28)

- **Clearance belongs to the hole's axis in the print pose, not to the
  part.** A magnet pocket sized with a vertical-hole allowance came out loose
  after the part was re-posed and the pocket axis became horizontal
  (horizontal holes print about true). Look up every fit after the print
  pose is fixed, from the axis measured in the print frame; a pose change
  re-derives every fit. (CC2, PLA+, 2026-10-16)
- **"PLA" is not one fit value.** The same hex tester was free at 0.1 mm per
  side in one matte PLA and needed 0.2 in a PLA+ from another brand (0.1 was
  too tight even after sanding). Key your fit table by filament, then hole
  axis, then fit kind. (CC2, 2026-10-01 and 2026-10-06)
- **A press fit for a 10 mm magnet in a horizontal pocket is tighter than you
  think.** +0.2 per side: the magnet falls out; +0.1 with crush ribs: very
  loose. (CC2, PLA+, 2026-10-15 and 2026-10-16)

## Fits and bearing faces

- **A +0.1 mm CAD interference printed as +0.2 to +0.4** on a bearing face
  (layer rounding plus bridge sag). The moving part sat 1 to 2 layers proud
  and a thin finger snapped when forced into place. Fix: bearing faces on
  exact 0.2 layer boundaries, zero designed interference, never on a bridge
  underside. (2026-09-25)
- **Bridged ceilings droop.** 6 to 8 mm wide bridge undersides printed as
  sagging, stringy strands, 0.2 to 0.4 mm low. Keep them out of the load path
  with at least 0.6 to 0.8 mm clearance. (2026-09-25)

## Print-in-place gaps

- **A 1-layer (0.2 mm) Z gap over a flat shelf snapped free as easily as a
  0.4 mm gap** on this printer. 0.4 is the safe default; a 1-layer gap is a
  support interface and fuses on many printers. (2026-09-28)
- **A 45 deg teardrop bore has a bigger top gap than its nominal gap.** With a
  2.4 mm axle, 0.5 side and 0.4 bottom gap, the apex sits about 1.1 mm above
  the axle. State top, bottom and side gaps separately
  (`aicad.ppi_hinge.clearances`). (2026-09)

- **Bigger is not always freer.** On a print-in-place hinge tolerance test,
  0.10 and 0.15 mm gaps moved easily and 0.20 stuck in places. Print the
  designer's tolerance test before picking a gap. (CC2, PLA+, 2026-10-09)
- **PETG needs larger print-in-place gaps than PLA.** A 0.10 mm hinge gap
  fused in PETG; we design PETG at 0.4 until a test passes. (CC2, PETG HF,
  2026-10-17)
- **An outer brim can weld two print-in-place parts together** when it fills
  the gap between them on the first layer. Check the first layer of every PPI
  object. (CC2, 2026-10-21)

## Clicks, snaps and flexures

- **A click is not a lock.** A bump in a dip holds a part at one angle but not
  lying flat under load. Anything that must stay put in a pose needs a
  positive stop (pin, hook, tab root); the click only tells you that you
  arrived. (2026-09-28)
- **Make thin springs flex inside the layer plane.** Layer lines are the weak
  direction: a spring that bends across layers is a design-stage reject.
  Print flexing prongs so they bend within a layer. (2026-09-29)
- **Small bumps do not click.** 0.45 mm engagement on a 1.6 mm PLA arm gave no
  click; 1.3 mm out x 1.6 mm tall bumps clicked and held. (2026-09-29)
- **Snap-fit rules of thumb were conservative here.** A clip that computes to
  4.4 to 5.0 % bending strain on paper (over the usual 2 % PLA rule) held.
  Watch for whitening after many cycles. (2026-09-29)

## Print orientation

- **Small tall parts: grow them off their widest face.** Thin leaves printed
  tip-down failed twice (spaghetti); printed standing on the wide boss, tips
  up, with a 4 mm brim, they printed clean. (2026-09-29)

- **Tall thin parts need a brim that touches the part.** Height 40 mm or more
  and height over width 4 or more: a brim with gap 0. A tall PETG tower
  without one came off the bed. With a gap-0 brim, set elephant-foot
  compensation to 0 or the brim does not fuse to the part. (Snapmaker U1,
  PETG, 2026-10-18)
- **A tiny foot under a flared part comes off the bed** even when every other
  check passes: 0.6 mm2 on the bed growing to about 49 mm2 3 mm up. Compare
  the first-layer area with the area a few mm up. (CC2, PLA, 2026-10-21)
- **Supports inside a sloped bore cannot be removed.** "Supports everywhere"
  filled the tubes of an adapter; it was reprinted. Before printing, find
  every bore and channel and confirm in the slicer preview that no support is
  inside it; fix with the pose, build-plate-only supports or a support
  blocker. (CC2, PLA, 2026-10-22)
- **A long part standing on thin straight supports wobbled, strung and went to
  spaghetti** at a side branch (165 mm, upright). On its side with support
  blockers it printed. (CC2, PLA, 2026-10-22)
- **A slender part can fail by leaning even when no wall is steep.** Walls at
  27 to 45 deg passed every per-layer overhang metric, but the centre of mass
  of the material above drifted outside the section under it and the part
  tipped under the nozzle. One failure, so treat the threshold as a guess.
  (CC2, PLA, 2026-10-14)
- **Load inside the layer plane.** Hooks and clips print on their side so the
  load runs along the layers. A 45 deg tilt is a compromise between the two;
  a small tilt does nothing and tight fits split along tilted layers. (Advice
  from published layer-adhesion tests, applied once, 2026-10-08; we have not
  measured the strength gain ourselves)

## Fit coupons

- **Fit coupons test shape and fit, not strength.** Two walls, 10 to 15 %
  infill, everything cut away but the tested feature and its mating part.
  Solid coupons wasted filament and time. (Method, 2026-10-17)
- **Mark every variant on a test plate** (dots, notches, a number) so a
  result maps back to its variant after the parts leave the bed.
  (Method, 2026-10)

## Mesh and file handling

- **STL validity depends on the exported mesh and the import path.**
  Observed: manifold3d output kept geometrically coincident vertices
  separate. Reloading the STL merged them into non-manifold edges, while the
  3MF of the same mesh stayed clean and re-read watertight. Check the file
  you actually slice by re-reading it. (2026-09-29)
- **Downloaded STLs can be upside down.** One model had its clip tips on the
  bed and the plate floating. The slicer CLI exited 0 and did not surface its
  own "floating regions" warning. Check the pose yourself: the best signal
  was "area of new material more than 10 mm from anything in the layer
  below" (993 mm2 on the bad file, 0 on 13 good ones); naive overhang area
  flagged 4 of 13 good files. Section each body on its own: merging the
  meshes first gave a false 42.6 mm on a 6-body file. (2026-10-06)
- **Do not let the slicer auto-orient designed parts.** Try the 6 axis
  rotations and rank them (floating area, then lean, then bed contact).
  (2026-10-06)
- **Nearest-surface normal signs can disagree with solid membership.** An
  implicit-distance query produced false "missing support" and "outside the
  source" findings. Verify disputed points by ray parity or winding number
  before rebuilding geometry. (Method, 2026-10-21)
- **Concatenating two overlapping cutter meshes is not a union.** One
  subtraction left a 0.1 mm skin across a mouth. Union the cutters first or
  subtract them one by one. (Method, 2026-10-18)
- **A cut with a flipped sign passes every validity check.** Counterbores cut
  outside the frame were watertight and manifold. Section or render through
  every cut. (Method, 2026-10-19)
- **Check the exported mesh, not the CAD model.** build123d's STL export uses
  a relative meshing tolerance, so the first STLs exceeded the requested
  deflection; flex slots under about 0.3 mm can close in export or slicing.
  Pre-mesh with an absolute tolerance and re-measure the file. (2026-10-03)
- **Assembly exports arrive in assembly pose, wrong units or Y-up.** Fix scale
  and pose before any check or slice. (2026-10-22)
- **Do not cut, bridge or smooth an AI-generated mesh at a joint.** Eight
  attempts failed in a row. Split at a plain round section, or draw the joint
  into the input image before generating. (Method, 2026-10-05)
- **Heavy mesh work can freeze the machine.** Booleans, thickness checks and
  slicing on 100k+ triangle meshes pegged every core; later one run paged
  all memory until the machine hard-froze. Run them through
  `python -m aicad.lowpri` (idle priority, half the cores, timeout, memory
  cap on Windows), one part at a time. (2026-09-29 and 2026-10-22)
