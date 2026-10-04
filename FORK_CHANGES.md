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
2. When an upstream file *must* change, keep the edit small and mark it with `# STARSTACK:` comments.
3. Every change gets a row in the table below.
4. Never reformat or reorder upstream code.

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
