# StarStack fork of KlipperScreen: change log

Private copy of [KlipperScreen/KlipperScreen](https://github.com/KlipperScreen/KlipperScreen), maintained by StarStackCo for the StarStack printer UI.
Design/plan docs live in the separate repo `StarStackCo/klipper-ui`.

## Branches and remotes
| Name | What |
|---|---|
| `upstream` remote | Official KlipperScreen (fetch only. Push is disabled) |
| `origin` remote | `StarStackCo/KlipperScreen-starstack` (private) |
| `master` | Mirror of upstream `master`. **Never commit here** |
| `starstack` | Our branch = upstream + the changes listed below. **Default/deployed branch** |

**Base:** upstream `f580242e` (v0.4.6-26), the exact version on the printer Pi as of 2026-10-04.

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

## How to merge upstream updates
```bash
git fetch upstream
git checkout master && git merge --ff-only upstream/master && git push origin master
git checkout starstack && git merge master        # resolve conflicts using the table below
# run docs/test-checklist.md (klipper-ui repo) on the bench before deploying
git push origin starstack
```

## Change list
| # | Date | Type | Files | Upstream file modified? | Why |
|---|---|---|---|---|---|
| 1 | 2026-10-04 | Docs | `FORK_CHANGES.md` | No (new file) | This change log |
| 2 | 2026-10-04 | Docs | `README.md` (top) | **Yes**, 3-line notice block | Points readers to this file |
| 3 | 2026-10-04 | Theme | `styles/starstack/` (style.css, style.conf, images/, fonts/, LICENSES.md) | No (new folder) | StarStack brand theme. **Generated**: edit `klipperscreen/style.css` in `StarStackCo/klipper-ui` and run `scripts/build_ks_theme.py`, don't hand-edit. Icons: Bootstrap Icons 1.13.1 (MIT) where marked, otherwise material-dark artwork. Font: Public Sans 2.001 (OFL), installed to `~/.local/share/fonts` by `scripts/deploy-ks-bench.sh` |
