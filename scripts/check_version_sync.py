#!/usr/bin/env python3
"""Fail if the version strings in the repo disagree (or don't match a release tag).

Usage:  python scripts/check_version_sync.py [vX.Y.Z]
Checks backend/app/version.py, frontend/src/version.ts, frontend/package.json
and the top released entry in CHANGELOG.md. Pass a tag (or set GITHUB_REF_NAME)
to also require that the tag equals that version. Stdlib only.
"""
import json, os, re, sys, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
found = {
    "backend/app/version.py": re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (root/"backend/app/version.py").read_text()).group(1),
    "frontend/src/version.ts": re.search(r"APP_VERSION\s*=\s*'([^']+)'", (root/"frontend/src/version.ts").read_text()).group(1),
    "frontend/package.json": json.loads((root/"frontend/package.json").read_text())["version"],
}
m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (root/"CHANGELOG.md").read_text(), re.M)
found["CHANGELOG.md (top release)"] = m.group(1) if m else "MISSING"

tag = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")).lstrip("v")
if re.fullmatch(r"\d+\.\d+\.\d+", tag):
    found["release tag"] = tag

for k, v in found.items():
    print(f"  {k:32s} {v}")
if len(set(found.values())) != 1:
    print("VERSION MISMATCH"); sys.exit(1)
print("OK: all versions agree")
