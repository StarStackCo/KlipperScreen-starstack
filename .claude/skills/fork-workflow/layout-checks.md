<!-- STARSTACK-ADDED: touchscreen layout checks for the fork-workflow skill (FORK_CHANGES.md #53) -->
# Layout checks on the 480x320 TFT

The screen is small, resistive and 16-bit. Rules from the requirements and design decisions
(klipper-ui `docs/requirements.md`, D-029, D-030, D-064):
- STOP and the left rail are never covered: dialogs, prompts, pop-ups and the keyboard all live in the
  content area (D-029, D-043, D-074).
- No scrolling lists: long lists use `ss.Pager` with arrows (D-064). Narrow columns use
  `ss.Pager(compact=True)` (D-095).
- Touch targets at least 44 px tall and kept away from the screen edges (D-030, D-056).

## Measure instead of guessing
Widget sizes depend on the theme's fonts, so measure them on the Pi with the real CSS. Run a short script
over `scripts/pi.sh` in klipper-ui: `DISPLAY=:0 ~/.KlipperScreen-env/bin/python` with
`cd ~/KlipperScreen`, define `builtins._ = lambda s: s`, load `styles/starstack/style.css` with a
`Gtk.CssProvider`, build the widgets with the `ks_includes.starstack` helpers, add them to an unshown
`Gtk.Window` and print `get_preferred_width()` / `get_preferred_height()`. It runs beside the app without
touching it. Compare with the space the page actually has (screenshot: `scripts/ks-screenshot.sh`).

## When a page misbehaves
- Goes off the right edge: something's minimum width is larger than its column (widths add up in a
  `Gtk.Box`). Find it by measuring each child.
- Shows a scroll bar: the page's minimum height is larger than the content area, so the content guard
  scrolls it. Move or shrink parts until it fits.
- Opens or closes by itself: check the KlipperScreen log for panel loads; ghost touches show as panel opens
  with no screen wake before them (D-094).
