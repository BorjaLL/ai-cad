# Print lessons, as measured on one setup

Setup for every line below unless it says otherwise: Elegoo Centauri Carbon 2,
PLA, 0.4 nozzle, 0.2 mm layers, 1.75 mm filament used as hinge pins, September
2026. Lessons from October and November 2026 name their material (PLA+,
PETG) because it turned out to matter, and their printer when it is the
Snapmaker U1 (0.4 nozzle) rather than the CC2. Each November lesson says
whether it was printed or is software-only. Re-test each one on your printer (a 10 to 20 minute
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
- **Crush ribs turned a free bore into a push-on fit, found with one ladder
  coupon.** A cup over a 30.0 mm foot (calipers): bore 30.4 with round
  vertical ribs standing 0.10 / 0.25 / 0.40 mm into it, one ring per rib
  height on one coupon, notches marking which is which. The 0.10 ring "fits
  nicely" and went into the real part. The same printer printed a plain
  32.2 vertical bore at 31.96 (one caliper reading). (Printed. Snapmaker U1,
  PETG, 2026-11-01 and 2026-11-02)
- **Clearance plus small crush ribs for a drop-in tab.** A T-tab at 0.25 mm per
  side (a pocket test had judged that "solid, barely a little wiggle"), plus
  vertical ribs at 0.05 mm interference with a 2 mm 45 deg lead-in, "fits
  well". (Printed. CC2, PLA+ tab, 2026-11-01)
- **The nominal size of the thing you clip onto is a poor guide.** A hook
  slot of 6.05 mm for "6 mm" shower glass was too loose; a sheet clip at sheet
  +0.10 and +0.20 was "super loose" on one printer bed. Neither mating
  thickness was measured. A 0.2 mm strip of brim pushed into the loose clip
  made it fit, which gave the next gap without a reprint. Flexing clips want
  a gap under the sheet thickness so the arms pinch. (Printed. CC2, PLA+ and
  PETG, 2026-10-28 and 2026-10-30; the narrower slot and clip are designed,
  not yet printed)
- **Seams and elephant foot decide the tight end of a tolerance test.** On a
  peg-in-hole tolerance plate the 0.1 mm cylinder was tight on one printer
  because of a raised seam ridge down its side, and on the other it first
  "did not fit" and then did on a recheck, with elephant foot or the seam in
  the way at first insertion. Calipers: holes 9.82, the 0.1 peg 9.67 to 9.72.
  Keep the seam off mating faces and chamfer the bottom edge of pegs and
  holes before you read a tight fit as a size error. Measure peg and hole at
  foot, middle and top before compensating anything. (Printed. CC2 and U1,
  PLA+, 2026-11-03)

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
- **A plate-wide brim with gap 0 fused to every part.** In PETG the brim could
  not be cleaned off and printed washers were useless; the reprint with
  per-object brims peeled clean. Brims on small Gridfinity bases were hard to
  remove too. Use a brim gap (0.3 mm is our default now) and set gap 0 per
  object, only on the tall thin parts that need it. (Printed. CC2, PETG and
  PLA+, 2026-10-28 to 2026-10-31)
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
- **Tree supports under thin organic tips were very hard to remove** (the
  tails of a figure). Look at where supports land on thin features in the
  preview, and prefer a pose or a split that keeps them off. (Printed.
  Snapmaker U1, PLA, 2026-10-31)
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
- **Put the marks where you can see them in use.** Dots inside a clip's slot
  could not be seen once the clip was on the plate; v2 moved them to notches
  on the outside corners. (Printed. 2026-10-28)
- **Every test piece gets a unique serial debossed in its bottom** (for
  example K1, K2 on one printer, C1, C2 on the other), 0.4 mm deep, mirrored
  so it reads with the piece turned over, sized to fit inside the bed face.
  Name the serial in the print request and in the result. Test pieces had
  become hard to tell apart. The bottom keeps the mark off the faces you
  judge: a letter on a wall-test box was blamed for artifacts on that wall,
  though a plain box in the same test streaked too. (Method, 2026-11-03; the
  first serialled pieces are printing, legibility not yet confirmed)

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
- **A closed internal cavity is a second mesh shell, not a second part.** A
  sealed magnet cavity adds an inside surface, so a shell count of 3 can be
  one solid. Check nesting or winding before you "fix" a disconnected part.
  (Software only, 2026-10-26)
- **Mirroring each glyph does not mirror a word.** For a stamp or a paired
  die, mirror the whole text in an explicit view frame and prove it reads
  right from the re-loaded exported assembly; letter order and flip axis were
  the errors. (Software only, 2026-10-26)
- **Zero-area triangles broke STEP-to-mesh conversion.** Two per compound in
  one family of STEP files; removing them kept area and bounds and gave
  closed meshes. Do not loosen the mesh checks to get a file through.
  (Software only, 2026-10-28)
- **Native CAD kernels crash the Python process.** One day of agent CAD work
  gave 13 crash reports: OCCT face-unify and TetGen segfaults, and a 3D render
  that aborted with no window server. Run crash-prone native calls in a child
  process, check the result, and render headless (matplotlib Agg) inside
  sandboxes. (Software only, 2026-10-26)
- **Volume meshers fail on thin or floating bits.** A surface mesher
  segfaulted on 0.25 mm design surfaces and a 0.08 mm floating ledge at the
  bed; trimming the ledge flat and switching to a robust tetrahedral mesher
  worked. Strength numbers from these models were not checked against a
  print. (Software only, 2026-10-28)
- **Cache and chunk heavy checks.** Caching the exact interface meshes and
  chunking the slit and exactness checks took one part's check run from
  16.4 GB to 1.7 GB peak memory. (Software only, 2026-10-30)
- **Heavy mesh work can freeze the machine.** Booleans, thickness checks and
  slicing on 100k+ triangle meshes pegged every core; later one run paged
  all memory until the machine hard-froze. Run them through
  `python -m aicad.lowpri` (idle priority, half the cores, timeout, memory
  cap on Windows), one part at a time. (2026-09-29 and 2026-10-22)
