# Second-opinion review with a second model

The agent that wrote the design is a poor judge of it. Before a print over
about an hour, or any change to a joint that already passed, a different model
reviews the plan read-only. Here that was Codex reviewing Claude Code's work
(September 2026); any two models work.

## When

- After the plan, before code: "is this mechanism sound, what will fail?"
- After the code, before printing: "do the checks prove what the doc claims?"
- After a failed print: "here is the photo and my note, what is the cause?"

## How

1. The working agent writes a short prompt file: goal, the doc and script
   paths, what to check, "read-only, do not edit files", answer format
   (ranked list, numbers, max one page).
2. Run the reviewer on it, for example with the Codex CLI:

       codex exec --sandbox read-only - < review-prompt.md > reviews/codex-<topic>-<date>.md

3. The working agent answers every point in the design doc under a heading
   "After the review": changed (what, to which value) or rejected (why).
4. The review file is committed next to the design. Future sessions read it.

## What reviews caught (September 2026)

- A tolerance claim the geometry could not meet: a 0.02 mm seat error at the
  joint already gave 0.11 mm at the tip of a 100 mm part, beyond the 0.1 mm
  pass limit in the checklist.
- A bridge clearance with only 0.2 mm margin against the droop measured on the
  previous coupon (raised from 0.6 to 0.8 mm before printing).
- A hole described as "0.4 mm top gap" whose 45 deg teardrop apex was really
  1.1 mm above the pin.
- "Guaranteed" wording in a checklist for things only a print can show
  (reworded as goals).

## What reviews do not replace

The print. Reviews flagged risks; every fit number that ended up in the design
still came from a coupon.

## What we saw (October 2026)

- An independent second-model critique of a non-trivial plan found real
  errors 3 times out of 3 in one week of use.
- It works best one-shot: a fresh session, a brief under about 2 KB (goal,
  files to read, what is already ruled out), never a resumed session that
  already shares the author's assumptions.
- A reviewer handed your hypothesis tends to confirm it. Give it the code and
  the checks, not your conclusion.
