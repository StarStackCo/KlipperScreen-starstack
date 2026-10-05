#!/usr/bin/env python3
# STARSTACK-ADDED: keeps the fork easy to merge (FORK_CHANGES.md #32).
# Run by CI and before releases.
"""Checks:
 1. every STARSTACK-CHANGE #n BEGIN has a matching END in the same file (and no nesting)
 2. every change number used in the code is listed in FORK_CHANGES.md
 3. every upstream file we modified (vs tools/starstack/UPSTREAM_BASE) has a STARSTACK-CHANGE block
 4. every file we added starts with a STARSTACK-ADDED note (code/CSS/SVG/Markdown only)
Usage: python tools/starstack/check_markers.py   (needs the upstream base commit in the git history)
"""

import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BEGIN = re.compile(r"STARSTACK-CHANGE #(\d+) BEGIN")
END = re.compile(r"STARSTACK-CHANGE #(\d+) END")
TEXT = (".py", ".css", ".md", ".svg", ".cfg", ".conf", ".sh", ".yml", ".yaml", ".txt", ".gitignore")
errors = []


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def read(path):
    try:
        return open(os.path.join(ROOT, path), encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return None


base = open(os.path.join(ROOT, "tools", "starstack", "UPSTREAM_BASE")).read().strip()
changed = [
    line.split("\t")
    for line in git("diff", "--name-status", "--no-renames", base, "HEAD").splitlines()
]
modified = [p for s, p in changed if s == "M"]
added = [p for s, p in changed if s == "A"]

used = set()
for path in git("ls-files").splitlines():
    if not path.endswith(TEXT) or path.startswith("docs/"):
        continue
    text = read(path)
    if text is None:
        continue
    open_n = None
    for i, line in enumerate(text.splitlines(), 1):
        b, e = BEGIN.search(line), END.search(line)
        if b:
            if open_n:
                errors.append(f"{path}:{i}: BEGIN #{b.group(1)} inside open block #{open_n}")
            open_n = b.group(1)
            used.add(int(open_n))
        if e:
            if e.group(1) != open_n:
                errors.append(f"{path}:{i}: END #{e.group(1)} without matching BEGIN")
            open_n = None
    if open_n:
        errors.append(f"{path}: BEGIN #{open_n} never closed")

listed = set()
for line in read("FORK_CHANGES.md").splitlines():
    m = re.match(r"\|\s*([\d–\-, ]+)\s*\|", line)
    if m:
        for part in re.split(r"[ ,]+", m.group(1).strip()):
            if re.fullmatch(r"\d+[–-]\d+", part):
                a, b = map(int, re.split(r"[–-]", part))
                listed.update(range(a, b + 1))
            elif part.isdigit():
                listed.add(int(part))
for n in sorted(used - listed):
    errors.append(f"change #{n} is used in the code but not listed in FORK_CHANGES.md")

for path in modified:
    text = read(path)
    if path == "FORK_CHANGES.md" or text is None:
        continue
    if "STARSTACK-CHANGE #" not in text:
        errors.append(f"{path}: modified upstream file without a STARSTACK-CHANGE block")

for path in added:
    if (
        not path.endswith((".py", ".css", ".svg", ".md"))
        or path.startswith(".github/")
        or path == "FORK_CHANGES.md"
    ):
        continue
    head = (read(path) or "")[:400]
    if "STARSTACK-ADDED" not in head and "STARSTACK" not in path.upper():
        errors.append(f"{path}: new file without a STARSTACK-ADDED note at the top")

print(
    f"upstream base {base[:8]}: {len(modified)} modified, {len(added)} added files; "
    f"change numbers used: {sorted(used)}"
)
if errors:
    print("\n".join("ERROR " + e for e in errors))
    sys.exit(1)
print("markers OK")
