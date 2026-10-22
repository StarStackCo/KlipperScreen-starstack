---
# STARSTACK-ADDED: Claude Code skill (FORK_CHANGES.md #53)
name: fork-workflow
description: Make and ship changes in the StarStack KlipperScreen fork (STARSTACK markers, FORK_CHANGES rows, theme builds, bench and dev branches, upstream merges, layout checks on the 480x320 TFT). Use when editing panels/ss_*, screen.py or any upstream file, changing the touchscreen theme or a touchscreen page, installing a build on the Pi with ks-update.sh, or merging upstream KlipperScreen.
---

# Changing the StarStack touchscreen fork

## Procedure
1. Read the FORK_CHANGES.md rows for the files you touch and the related klipper-ui decisions.
2. Branch: debug experiments on `bench`, real work on `dev` (D-061). Never `master`.
3. Prefer a new `ss_*` file. If an upstream file must change, keep the edit tiny and wrap it in
   `STARSTACK-CHANGE #n BEGIN: <why>` / `STARSTACK-CHANGE #n END`; a new file starts with a
   `STARSTACK-ADDED: <what>` note within its first lines. Each gets its own FORK_CHANGES row and number,
   and the "Numbers ..." line above the tables is updated to match.
4. Checks, as CI runs them: `ruff check screen.py ks_includes panels tools/starstack`,
   `ruff format --check` on `ks_includes/starstack*.py panels/ss_*.py tools/starstack` only,
   `python tools/starstack/check_markers.py`, and `build_theme.py --check` after theme changes.
5. Commit, then install on the Pi with the user's OK from klipper-ui:
   `scripts/ks-update.sh --branch bench|dev [shot.png]`. It restarts only the touchscreen app, but still
   wait for an idle printer unless the user agrees. Read the KlipperScreen log for tracebacks afterwards.
6. Check the result on the real screen (screenshot, then the user's taps) and record a Run in klipper-ui's
   test checklist. Layout work: [layout-checks.md](layout-checks.md).
7. Ship: PR `dev` to `starstack` through klipper-ui's `release` skill, together with any klipper-ui change
   it depends on. Upstream merges: [upstream-merge.md](upstream-merge.md).

## Gotchas
- **An edit and the file it adds are two rows.** The screen guard needed #50 (the `screen.py` hook) and #51
  (the new file); `check_markers.py` fails on an unlisted number or an added file without its note.
- **Never hand-edit `styles/starstack/`**: it is regenerated from `tools/starstack/` and CI checks it (#3).
- **TFT greys must be multiples of 8** or they tint green on the RGB565 panel (D-038).
- **Never reformat upstream files**, and keep hook imports in `# isort: split` blocks so ruff leaves
  upstream's import order alone (rule 4, #4).
- **A page taller than the content area gets the guard's scroll bar** (D-043). The cancel-object page grew a
  phantom scroll bar until its buttons moved under the map (D-095).
- **Measure widths on the Pi, don't guess**: the pager bar measured 214 px for a 184 px column (D-095).
- **The touchscreen resets its pages when the print turns "paused"**, closing anything opened just before
  (klipper-ui D-090). Macro prompts must come after that.
- **Screen code that sends a macro twice moves twice** when the printer is already in the target state
  (D-097: load and unload). Send heat-only first (`HEAT=1`), then the move once.
- **Ghost touches are single ~24 ms readings and color bands are SPI noise**; the screen guard filters and
  repaints, so don't add workarounds in panels (D-094).
- **`ks-update.sh` pushes the local branch.** A stale local `bench` is rejected; reset it to the commit you
  want to test (`git branch -f bench dev`) first.
- **Commits that went only to `bench` stay local on `dev`.** Branch new work from `origin/dev`, or they ride
  along unreviewed.
- **Keep `.github/dependabot.yml` deleted** when a merge brings it back (#14).
- **Upstream sync runs are red on purpose** when updates wait; that's the notice, not a failure (D-051).
