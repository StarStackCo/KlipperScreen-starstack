<!-- STARSTACK-ADDED: what a reviewer looks for in this fork (FORK_CHANGES.md #57) -->
# Reviewing a change to the StarStack touchscreen

For any reviewer, human or Claude. This code drives a heated, moving printer from a 480x320 resistive
touchscreen, often for someone who has never used a 3D printer. Report the way klipper-ui's `REVIEW.md` says
("How to report" and "Rounds"); this file says what to look for here.

## What failure looks like here

| Area | It fails when it... |
|---|---|
| Pages and flows (`panels/ss_*`) | heats, moves, homes, probes or extrudes without the user asking, sends a macro twice, or leaves a heater on when the user leaves, stops or a step fails |
| STOP and the rail (`ks_includes/starstack.py`) | lets any page, dialog or setup step hide STOP or push it off screen |
| Shared code (`ks_includes/starstack*.py`, `ks_includes/ss_*.py`) | blocks the GTK main loop (the screen freezes, STOP included) or crashes on a missing or late Moonraker value |
| Upstream files | change without `STARSTACK-CHANGE` markers, get reformatted or reordered, or change more than the fix needs |
| Layout and theme | make a page taller than the screen, put a gray that isn't a multiple of 8 on the panel (D-038), or edit `styles/starstack/` by hand |
| Words on screen | confuse a first-time user, or ask "are you sure" about something that can't be undone without saying what happens |

## Always flag as Important

- A heater turned on with no path that turns it off again (fail, Stop, back, leaving by the rail, page reset).
- A move, home, probe or extrude sent while a print is running or paused, unless the page is built for that.
- A blocking call (`time.sleep`, a synchronous request, `subprocess.run` without a short timeout) on the GTK
  thread.
- The same command sent twice when the printer may already be in the target state (D-097).
- STOP hidden, covered or made untappable.
- A macro name or parameter that klipper-ui doesn't have on the same release (D-072, D-097).
- A price, published spec or business claim stated as fact.

## Missing paperwork (Important when the code changed)

- No `FORK_CHANGES.md` row, or a new file without its `STARSTACK-ADDED` note.
- A behavior change without a decision row in klipper-ui's `docs/DECISIONS.md`.
- An install on the S1 without a deploy log row, or a test without a Run, in klipper-ui.

## Already checked by CI, don't repeat

`ruff check`, `ruff format --check` on StarStack files, `check_markers.py`, `build_theme.py --check`.
Flag a gap in these checks instead.

## Skip

Upstream files and folders the change doesn't touch, `styles/starstack/` (generated), upstream's `docs/` and
`CHANGELOG.md`, `__pycache__/`.
