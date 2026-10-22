<!-- STARSTACK-ADDED: instructions for Claude Code sessions (FORK_CHANGES.md #52) -->
# KlipperScreen-starstack: the StarStack S1 touchscreen

StarStack's copy of KlipperScreen for the S1's 480x320 TFT35: StarStack pages (`panels/ss_*`), shared code
(`ks_includes/starstack*.py`, `ks_includes/ss_*.py`), theme source in `tools/starstack/`. Not here: the
printer config, macros, installer and all plans and decisions, which live in `StarStackCo/klipper-ui`
(its CLAUDE.md and `docs/`). Business facts (prices, published specs, claims) live in a claude.ai
project: never state one, say it needs checking there.

## Read first
`FORK_CHANGES.md` (branches, release flow, upstream merges, every change we made) and, in klipper-ui,
`docs/DECISIONS.md`, `docs/PLAN.md` and `docs/test-checklist.md`. Upstream's `CHANGELOG.md` and `docs/` are
upstream's, not ours.

## Workflow (from FORK_CHANGES.md and klipper-ui's decisions)
- `master` mirrors upstream: never commit there. Work on `dev`. Debug builds go on `bench` (no CI, never
  merged, D-061). `starstack` is what printers install; it changes only by a PR from `dev` after the
  klipper-ui bench checklist passes.
- Prefer new files over editing upstream files; never reformat or reorder upstream code. Mark every change
  and list it in FORK_CHANGES.md; `python tools/starstack/check_markers.py` must pass.
- The theme in `styles/starstack/` is generated: edit `tools/starstack/style.css`, run `build_theme.py`.
- Nothing is installed on the printer or pushed without the user's OK for that step (klipper-ui D-003).
  Installs and screenshots run from klipper-ui (`scripts/ks-update.sh`, `scripts/ks-screenshot.sh`).
- Skill: `fork-workflow` (any change here, theme, installs, upstream merges).

## Recording work
A FORK_CHANGES.md row for every change; the decision itself goes in klipper-ui's DECISIONS.md (D-NNN, top
of the table) and test runs in its test-checklist.md.

## Hazards and open defects
- The S1's resistive panel gets ghost touches and SPI color bands from cable noise; the screen guard
  handles both (klipper-ui D-094).
- Any page taller than the screen gets a scroll bar from the content guard (D-043, D-095).
- A touchscreen build and the klipper-ui macros it calls must be released together (D-072, D-097).
- Pulling the Pi's power can corrupt `~/KlipperScreen/.git` (klipper-ui Q-045, D-035).

## Style
American spelling. Direct, and say why. No em dashes or dash-style hyphens. Point to docs, don't repeat them.
