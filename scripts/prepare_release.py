#!/usr/bin/env python3
"""Validate release metadata and write release notes; used by .github/workflows/release.yml.

Checks, failing loudly before anything is published:
  * api/updates/latest.json "version" equals the version in src/SW-DLT.plist
  * its "url" is an iCloud shortcut link, and "/shortcut" occurs exactly once in
    the file: the shortcut's "Update Now" step turns the first "/shortcut" it finds
    into a shortcuts:// import link, so notes must not contain another one
  * api/updates/release_links.json "SW-DLT" equals that url
  * the committed SW-DLT*.shortcut files are signed (AEA1) and were committed no
    earlier than the last change to their plist source (i.e. rebuilt on main)

Usage: prepare_release.py [--notes-out FILE]   prints the version on success
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "api" / "updates" / "latest.json"
LINKS = ROOT / "api" / "updates" / "release_links.json"
SHORTCUTS = {
    "SW-DLT": "src/SW-DLT.plist",
    "SW-DLT Audio": "src/SW-DLT-Audio.plist",
    "SW-DLT Video 720p": "src/SW-DLT-Video-720p.plist",
}
ICLOUD_RE = re.compile(r"^https://www\.icloud\.com/shortcuts/[0-9a-f]{32}$")


def fail(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    raise SystemExit(1)


def plist_version() -> str:
    with (ROOT / "src" / "SW-DLT.plist").open("rb") as fh:
        actions = plistlib.load(fh)["WFWorkflowActions"]
    for action in actions:
        params = action["WFWorkflowActionParameters"]
        if params.get("CustomOutputName") != "metadata":
            continue
        for item in params["WFItems"]["Value"]["WFDictionaryFieldValueItems"]:
            if item["WFKey"]["Value"]["string"] == "version":
                return item["WFValue"]["Value"]["string"]
    fail("version not found in src/SW-DLT.plist metadata dictionary")


def last_commit_time(path: str) -> int:
    out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", path],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return int(out or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes-out", type=Path)
    args = parser.parse_args()

    latest_text = LATEST.read_text(encoding="utf-8")
    latest = json.loads(latest_text)
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    version, url, notes = latest.get("version"), latest.get("url", ""), latest.get("notes", "")

    if version != plist_version():
        fail(f"latest.json version {version!r} != src/SW-DLT.plist version {plist_version()!r}")
    if not ICLOUD_RE.match(url):
        fail(f"latest.json url must be an iCloud shortcut link, got {url!r}")
    if latest_text.count("/shortcut") != 1:
        fail('latest.json must contain "/shortcut" exactly once (in "url"); "Update Now" uses the first one')
    if links.get("SW-DLT") != url:
        fail("release_links.json SW-DLT link must equal latest.json url")
    for name in SHORTCUTS:
        if not ICLOUD_RE.match(links.get(name, "")):
            fail(f"release_links.json needs an iCloud link for {name!r}")

    for name, source in SHORTCUTS.items():
        signed = f"{name.replace(' ', '-')}.shortcut"
        path = ROOT / signed
        if not path.is_file() or path.read_bytes()[:4] != b"AEA1":
            fail(f"{signed} missing or not signed")
        if last_commit_time(signed) < last_commit_time(source):
            fail(f"{signed} is older than {source}: run `make build` on main and commit it")

    if args.notes_out:
        lines = [notes, "", "**Install** (tap on iPhone/iPad):"]
        lines += [f"- [{name}]({links[name]})" for name in SHORTCUTS]
        lines += ["", "The quick shortcuts (Audio, Video 720p) need the main SW-DLT shortcut.",
                  "Requires [a-Shell](https://apps.apple.com/app/id1473805438) or "
                  "[a-Shell mini](https://apps.apple.com/app/id1543537943)."]
        args.notes_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
