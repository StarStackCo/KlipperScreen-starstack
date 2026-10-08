# StarStack fork of KlipperScreen: change log

Private copy of [KlipperScreen/KlipperScreen](https://github.com/KlipperScreen/KlipperScreen), maintained by StarStackCo for the StarStack printer UI.
Design/plan docs live in the separate repo `StarStackCo/klipper-ui`.

## Branches and remotes
| Name | What |
|---|---|
| `upstream` remote | Official KlipperScreen (fetch only. Push is disabled) |
| `origin` remote | `StarStackCo/KlipperScreen-starstack` (public) |
| `master` | Mirror of upstream `master`. **Never commit here** |
| `dev` | **Work happens here.** Bench-tested with `klipper-ui/scripts/ks-update.sh --branch dev` |
| `bench` | Throw-away debug builds for the bench Pi (`ks-update.sh --branch bench`). No CI runs on it and it's never merged. **Debug commits go here, never on `dev`** |
| `starstack` | **Stable.** What printers install through Mainsail's update manager. Only updated by a pull request from `dev` after the bench checklist passes |

**Base:** upstream `f2eb6919` (v0.4.7-196, merged 2026-10-05), recorded in `tools/starstack/UPSTREAM_BASE`.

## Release flow (dev → stable)
1. Work on `dev`, push, and test on the bench Pi: `scripts/ks-update.sh --branch dev` (klipper-ui repo).
2. Run the checklist in `klipper-ui/docs/test-checklist.md` and record the run.
3. Open a pull request `dev` → `starstack`. CI must pass (style, markers, theme freshness).
4. Merge. Printers see the update in Mainsail (Machine › Update Manager › KlipperScreen).

## How to merge upstream KlipperScreen updates
**Automatic (optional):** the `starstack-upstream-sync` workflow runs weekly. When upstream has new commits it
pushes them to branch `upstream-sync` and **fails on purpose** with a one-click "create pull request" link in the
run summary (the StarStackCo org doesn't let workflows open PRs or issues; GitHub emails failed runs).
**Red run = updates waiting, green = nothing new.** It's a setting: repository
**Settings › Secrets and variables › Actions › Variables › `UPSTREAM_SYNC_ENABLED`** = `true` (on) or `false` (off).
It can always be run by hand from the Actions tab.

**By hand:**
```bash
git fetch upstream
git checkout master && git merge --ff-only upstream/master && git push origin master
git checkout dev && git merge master        # conflicts can only be inside STARSTACK-CHANGE blocks (#2-#16)
python tools/starstack/check_markers.py     # every block still balanced and listed
git push origin dev                          # then bench-test, then PR dev → starstack
```
After merging a new upstream base, update `tools/starstack/UPSTREAM_BASE` to the merged upstream commit.

## Rules for keeping merges easy
1. Prefer **new files** (new theme folder, new panels) over editing upstream files.
2. When an upstream file *must* change, keep the edit as small as possible.
3. Every change gets a row in the table below, with its number `#n`.
4. Never reformat or reorder upstream code.

## How changes are marked in the code
| Kind | Marker | Where |
|---|---|---|
| New file we added | `STARSTACK-ADDED: <what it is>` in the file's first comment | Python `#`, CSS `/* */`, SVG/Markdown `<!-- -->` |
| Edit inside an upstream file | `STARSTACK-CHANGE #n BEGIN: <why>` … `STARSTACK-CHANGE #n END` around the edited lines (`#n` = row in the table below) | Same comment style as the file |
| Find everything | `git grep -n "STARSTACK-"` | |

When merging upstream: conflicts can only happen inside `STARSTACK-CHANGE` blocks. Re-apply the block's intent on top of the new upstream code and keep the same `#n`.

## Change list
Numbers **2–19 and 48–50** are edits inside upstream KlipperScreen files: the code carries
`STARSTACK-CHANGE #n BEGIN/END` markers with the same number. Numbers **20–47** are files we added
(each starts with a `STARSTACK-ADDED` note). `python tools/starstack/check_markers.py` verifies this.

### Edits inside upstream files (merge conflicts can only happen here)
| # | Date | File | What and why |
|---|---|---|---|
| 2 | 2026-10-04 | `README.md` (top) | Fork notice pointing to this file |
| 4 | 2026-10-04 | `panels/base_panel.py` (import + end of `__init__`). Hook imports use `# isort: split` so ruff leaves upstream's import order alone | Install the StarStack rail when the theme is "starstack" |
| 5 | 2026-10-04 | `panels/base_panel.py` `add_content` | Rail manages page highlight and STOP. Skip stock action-bar logic |
| 6 | 2026-10-04 | `panels/base_panel.py` `process_update` | Keep STOP color in sync with printer activity |
| 7 | 2026-10-04 | `panels/base_panel.py` `reload_icons`, `_reconfigure_main_grid` | Rail icons are built by the rail (STOP has no plain image). Around upstream's grid rebuild: unwrap the content guard first, then restore rail width + guard (added 2026-10-05 with the v0.4.7 merge) |
| 8 | 2026-10-04 | `screen.py` (import, `state_ready/printing/paused/error/shutdown`, `_ss_stopped`) | `ss_home` replaces main_menu/job_status. `ss_stopped` replaces the splash for shutdown/error |
| 9 | 2026-10-05 | `ks_includes/widgets/prompts.py` `show/end` | Macro prompts shown in-page (`ss_prompt`) so STOP is never covered |
| 10 | 2026-10-05 | `ks_includes/notification_handler.py` (import, `_gcode_response`). Was in `screen.py` before upstream v0.4.7 moved it | Routine `echo:` messages are not pop-ups (still in the console). Cold-extrude warning doesn't jump to the stock panel |
| 11 | 2026-10-05 | `screen.py` `printer_initializing`; `ks_includes/notification_handler.py` power-update guard | `ss_starting` replaces the stock splash while Klipper starts/restarts/reconnects |
| 12 | 2026-10-05 | `.gitignore` | Ignore `tools/starstack/.cache/` (downloaded theme sources) |
| 13 | 2026-10-05 | `screen.py` `show_keyboard` | Touch-sized on-screen keyboard (4 rows × 44 px keys, edge margins, `.ss-keyboard` style) next to the rail |
| 14 | 2026-10-05 | `.github/dependabot.yml` **(deleted)** | Dependabot off on the fork: it opened PRs for upstream's own dependencies. Updates arrive through the upstream sync. If a merge reports a modify/delete conflict on this file, keep it deleted |
| 15 | 2026-10-05 | `screen.py` (before `import gi`) | On X11, don't connect to the per-login session D-Bus. Upstream v0.4.7 runs as a `Gtk.Application`, which joined `/run/user/<uid>/bus` whenever someone was logged in over SSH. When that login ended, GLib stopped KlipperScreen and the touchscreen restarted (found on the bench, D-059). Wayland is unchanged (it needs the bus for idle-inhibit) |
| 16 | 2026-10-05 | `.github/workflows/linter.yml`, `codeql.yml` (push trigger) | Skip branch `bench`: throw-away debug builds for the bench Pi don't run CI or send failure emails |
| 17 | 2026-10-06 | `screen.py` `show_popup_message` | Pop-up warnings only as wide as the area right of the StarStack rail (was 90 % of the screen, covering the rail buttons) |
| 18 | 2026-10-06 | `screen.py` (before `import gi`) | `GDK_GL=disable`: GDK no longer sets up OpenGL, which loaded Mesa's software renderer (~160 MB with LLVM) at every start and cost ~8 s of SD-card reads during boot. Nothing in KlipperScreen draws with GL (klipper-ui D-076) |
| 19 | 2026-10-06 | `screen.py` `_init_printer`, `websocket_disconnected` retry checks, new `_ss_retry` | Connection retries every 1 s for the first minute (was 4 s) and up to ~6 min (was 4 tries). The touchscreen now starts before Moonraker at boot, so the first try is usually refused (klipper-ui D-077) |
| 48 | 2026-10-08 | `screen.py` `set_titlebar_items` | The nozzle/bed temperatures in the top bar show on the StarStack pages again. Upstream (since the v0.4.7 merge, D-060) only shows them on its own `main_menu` / `job_status`, so they had disappeared; the boot cover (`ss_starting`) still hides them |
| 49 | 2026-10-08 | `screen.py` `ws_subscribe` | Also subscribes to `gcode_macro PRINT_START` (`stage`, `target`, `soak`: heat soak D-096): while the start of a print heats up the file is paused in the background (klipper-ui D-089), and Home shows "Heating bed 40/60°" instead of "Paused" |
| 50 | 2026-10-08 | `screen.py` (imports, after the first `show_all`) | Starts the screen guard (row 51): ghost-touch filter and a full repaint every 5 s (klipper-ui D-094) |

### Files we added (never conflict)
| # | Date | Files | What |
|---|---|---|---|
| 1 | 2026-10-04 | `FORK_CHANGES.md` | This file |
| 3 | 2026-10-04 | `styles/starstack/` | Theme. **Generated** by `tools/starstack/build_theme.py`, never hand-edit |
| 20 | 2026-10-04 | `ks_includes/starstack.py` | Shared helpers, materials, Advanced-mode store, in-page dialogs, **rail + STOP**, content guard (no page can push STOP off-screen), color-change scanner |
| 21 | 2026-10-04 | `ks_includes/starstack_devtools.py` | Bench test helper. **Off** unless `~/.starstack_dev` exists |
| 22 | 2026-10-04 | `panels/ss_home.py` | Home: idle / printing / paused / done, color-change countdown, reheat-then-resume |
| 23 | 2026-10-04 | `panels/ss_print.py` | File grid, sort, pager |
| 24 | 2026-10-04 | `panels/ss_controls.py` | Temps, fan, filament (remembered), movement (locked while printing) |
| 25 | 2026-10-04 | `panels/ss_settings.py` | Settings + Advanced mode |
| 26 | 2026-10-04 | `panels/ss_dialog.py`, `panels/ss_adjust.py` | In-page confirmations and value adjuster |
| 27 | 2026-10-04 | `panels/ss_cancel_object.py` | Bed map + part list |
| 28 | 2026-10-04 | `panels/ss_filament.py` | Guided load / unload / change filament |
| 29 | 2026-10-05 | `panels/ss_prompt.py` | In-page macro prompts (hook #9) |
| 30 | 2026-10-05 | `panels/ss_stopped.py` | "Printer stopped / error" (hook #8) |
| 31 | 2026-10-05 | `panels/ss_starting.py` | "Starting printer…" (hook #11) |
| 32 | 2026-10-05 | `tools/starstack/` | Theme source (`style.css`, `brand/`), `build_theme.py` (pinned downloads), `check_markers.py`, `UPSTREAM_BASE` |
| 33 | 2026-10-05 | `.github/workflows/starstack-ci.yml`, `starstack-upstream-sync.yml` | CI checks + optional weekly upstream merge PR |
| 34 | 2026-10-05 | `TRADEMARKS.md` | StarStack name/logo are not covered by the AGPL license |
| 35 | 2026-10-05 | `panels/ss_console.py` | Console with the command box at the top (stock one has it at the bottom edge); opened from Settings › Advanced |
| 36 | 2026-10-05 | `panels/ss_network.py` | StarStack Wi-Fi page (klipper-ui B-6): one row per network, tap to connect, password with the StarStack keyboard, Disconnect/Forget in `ss_dialog` (now with an optional third button). Upstream's `sdbus_nm` backend unchanged; enterprise Wi-Fi via the stock page |
| 37 | 2026-10-05 | `panels/ss_usb.py` | "USB stick: N new files copied" prompt with "Print this one now?" for the newest file (klipper-ui D-065). Opened by `StarStackRail` when klipper-ui's USB import writes `gcodes/.starstack/usb_import.json` |
| 38 | 2026-10-06 | `panels/ss_choose.py` | Generic "pick one" page (`ss.choose()`), pages with arrows |
| 39 | 2026-10-06 | `panels/ss_screen.py` | Screen & language (replaces stock settings): screen sleep, sleep while printing, 24 h clock, language, **Confirm emergency stop** (StarStack setting, default ON, used by the STOP button) |
| 40 | 2026-10-06 | `panels/ss_about.py` | About this printer (replaces stock system panel) |
| 41 | 2026-10-06 | `panels/ss_power.py` | Shut down / reboot / restart Klipper / restart touchscreen, each confirmed, locked while printing (replaces stock shutdown panel) |
| 42 | 2026-10-06 | `panels/ss_extrude.py` | Extrude / retract (replaces stock extrude panel): nozzle temp, amount + speed chips, blocked when cold |
| 43 | 2026-10-06 | `panels/ss_updates.py` | Updates (replaces stock updater): Moonraker update manager in pages, confirmed, locked while printing |
| 44 | 2026-10-06 | `panels/ss_fans.py` | Fans: settable part/generic fans, automatic fans read-only |
| 45 | 2026-10-06 | `panels/ss_move.py` | Move axes with fine steps, only homed axes move |
| 46 | 2026-10-06 | `panels/ss_bed_mesh.py` | Bed mesh: colour map, Calibrate, Profile, Clear, Save (SAVE_CONFIG) |
| 47 | 2026-10-06 | `panels/ss_shaper.py` | Input shaper: current shaper, Measure (needs accelerometer), Save |
| 51 | 2026-10-08 | `ks_includes/ss_screen_guard.py` | Ghost touches on the resistive panel (single ~24 ms readings) are dropped: each press waits up to 80 ms and a press released in under 40 ms is ignored. Full window repaint every 5 s so SPI noise bands on the display disappear (klipper-ui D-094) |
