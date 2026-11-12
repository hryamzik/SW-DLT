#!/usr/bin/env python3
"""Fail if shortcut sources point at this repo on any branch other than the target.

Feature branches may temporarily point the installer at themselves
(raw.githubusercontent.com/<owner>/SW-DLT/refs/heads/<branch>/...) so that
phones can test unmerged code. This check makes sure that never reaches main.

Usage: check_branch_urls.py [--branch main] [files...]
Defaults to every src/*.plist plus api/updates/latest.json.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER_REPO = "hryamzik/SW-DLT"

# raw.githubusercontent.com/<repo>/refs/heads/<branch>/<path> or .../<branch>/<path>
RAW_RE = re.compile(
    r"https?://raw\.githubusercontent\.com/" + re.escape(OWNER_REPO)
    + r"/(?:refs/heads/)?(?P<rest>[^\s\"'<>]+)"
)
# github.com/<repo>/(blob|tree|raw)/<branch>/<path>
WEB_RE = re.compile(
    r"https?://github\.com/" + re.escape(OWNER_REPO)
    + r"/(?:blob|tree|raw)/(?P<rest>[^\s\"'<>)]+)"
)
# Files the URLs point at always live under one of these top-level paths,
# which lets branch names containing "/" (fix/foo) be split off correctly.
KNOWN_TOP = ("src/", "api/", "scripts/", "images/", "Docs.md", "README.md", "SW-DLT")


def branch_of(rest: str) -> str:
    for top in KNOWN_TOP:
        idx = rest.find("/" + top)
        if idx > 0:
            return rest[:idx]
    return rest.split("/", 1)[0]


def default_files() -> list[Path]:
    files = sorted((ROOT / "src").glob("*.plist"))
    files.append(ROOT / "api" / "updates" / "latest.json")
    return [f for f in files if f.exists() and f.name != "tmp.plist"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", default="main")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()

    files = args.files or default_files()
    problems = []
    for path in files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for rx in (RAW_RE, WEB_RE):
                for m in rx.finditer(line):
                    branch = branch_of(m.group("rest"))
                    if branch != args.branch:
                        rel = path.relative_to(ROOT) if path.is_absolute() else path
                        problems.append(f"{rel}:{lineno}: points at branch '{branch}': {m.group(0)}")

    if problems:
        print(f"Repo URLs must point at '{args.branch}' before merging:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
            # GitHub Actions annotation
            file_, line_ = p.split(":", 2)[:2]
            print(f"::error file={file_},line={line_}::{p.split(': ', 1)[1]}")
        return 1
    print(f"check_branch_urls: all repo URLs point at '{args.branch}' ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
