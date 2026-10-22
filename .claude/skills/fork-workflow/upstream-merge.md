<!-- STARSTACK-ADDED: upstream merge steps for the fork-workflow skill (FORK_CHANGES.md #53) -->
# Merging upstream KlipperScreen

The steps are in FORK_CHANGES.md ("How to merge upstream KlipperScreen updates"); follow them. Notes from
the last merge (v0.4.7-196, klipper-ui D-060):

- The weekly `starstack-upstream-sync` workflow pushes upstream's new commits to `upstream-sync` and fails
  on purpose with a compare link (D-051). Merging is a decision for the user (it was backlog B-2).
- Conflicts can only be inside `STARSTACK-CHANGE` blocks. Re-apply each block's intent on the new upstream
  code and keep its number; then `check_markers.py` and update `tools/starstack/UPSTREAM_BASE`.
- Upstream changes behavior under you. In v0.4.7: the app became a `Gtk.Application` that joined the SSH
  login's D-Bus and restarted when it ended (#15); the REST client was removed (pages moved to the
  websocket API); the title bar stopped showing temperatures on our pages until #48 restored them
  (found two days later, klipper-ui D-086). Walk every StarStack page on the screen after a merge, not just
  the ones the conflicts touched.
- The Pi's Python packages may need upstream's new requirements; Mainsail's updater installs them on
  printers (D-060).
- Bench-test from `dev`, record a Run in klipper-ui's test checklist, then release through the `release`
  skill.
