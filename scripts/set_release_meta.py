#!/usr/bin/env python3
"""Write api/updates/latest.json and release_links.json for the version in src/SW-DLT.plist.

  set_release_meta.py --bump {patch,minor,major}
      if src/SW-DLT.plist still has the version latest.json announces, bump it and
      commit just that change (git); if it is already newer, leave it as is
  set_release_meta.py [--main URL --audio URL --video URL] [--notes TEXT] [--date YYYY-MM-DD]
      write both files, then validate them with prepare_release.py. Missing links are
      read from the clipboard (pbpaste) one by one, missing notes are asked for; this
      needs a terminal and macOS.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_release as pr  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


PLIST_REL = "src/SW-DLT.plist"


def parse(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        pr.fail(f"unsupported version {version!r} (expected e.g. 4.4.0)")


def bump(version: str, part: str) -> str:
    major, minor, patch = (parse(version) + (0, 0, 0))[:3]
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=pr.ROOT, capture_output=True, text=True, check=check)


def set_plist_version(old: str, new: str) -> None:
    """Replace the metadata version in the plist and commit only that change.

    The bump has to be its own commit, before the signed shortcuts are built and
    committed: the release workflow rejects signed files older than their plist.
    """
    if git("diff", "--quiet", "HEAD", "--", PLIST_REL, check=False).returncode:
        pr.fail(f"{PLIST_REL} has uncommitted changes: commit them first, then run make release")
    path = pr.ROOT / PLIST_REL
    text = path.read_text(encoding="utf-8")
    needle = f"<string>{old}</string>"
    if text.count(needle) != 1:
        pr.fail(f"expected exactly one {needle} in {PLIST_REL}, found {text.count(needle)}")
    path.write_text(text.replace(needle, f"<string>{new}</string>"), encoding="utf-8")
    if pr.plist_version() != new:
        path.write_text(text, encoding="utf-8")
        pr.fail(f"replacing {needle} did not change the metadata version; {PLIST_REL} restored")
    git("commit", "-q", "-m", f"Bump version to {new}", "--", PLIST_REL)


def ask_clipboard_link(name: str) -> str:
    """Prompt until the clipboard holds an iCloud shortcut link."""
    while True:
        input(f"In Shortcuts, right-click {name!r} > Share > Copy iCloud Link, then press Enter: ")
        url = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
        if pr.ICLOUD_RE.match(url):
            print(f"  {name}: {url}")
            return url
        print(f"  clipboard has {url[:80]!r}, not an iCloud shortcut link; try again")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bump", choices=("patch", "minor", "major"))
    parser.add_argument("--main")
    parser.add_argument("--audio")
    parser.add_argument("--video")
    parser.add_argument("--notes")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()

    version = pr.plist_version()
    released = json.loads(pr.LATEST.read_text(encoding="utf-8")).get("version")

    if args.bump:
        if parse(version) > parse(released):
            print(f"releasing {version} (already bumped; current release {released})")
            return 0
        if parse(version) < parse(released):
            pr.fail(f"src/SW-DLT.plist version {version} is older than the released {released}")
        new = bump(version, args.bump)
        set_plist_version(version, new)
        print(f"bumped {PLIST_REL} {version} -> {new} and committed it")
        return 0

    links = {"SW-DLT": args.main, "SW-DLT Audio": args.audio, "SW-DLT Video 720p": args.video}
    missing = [name for name, url in links.items() if not url]
    interactive = sys.stdin.isatty()
    if missing and not (interactive and shutil.which("pbpaste")):
        pr.fail("need MAIN, AUDIO and VIDEO iCloud links (or run in a macOS terminal to paste them), e.g.\n"
                '  make release-meta MAIN=https://www.icloud.com/shortcuts/... AUDIO=... VIDEO=... NOTES="..."')
    for name in missing:
        links[name] = ask_clipboard_link(name)
    if not args.notes:
        if not interactive:
            pr.fail('need NOTES="what changed"')
        args.notes = input(f"Release notes for {version}: ").strip()
    for name, url in links.items():
        if not pr.ICLOUD_RE.match(url):
            pr.fail(f"{name}: not an iCloud shortcut link: {url!r}")
    if "/shortcut" in args.notes:
        pr.fail('NOTES must not contain "/shortcut": the updater uses the first one in latest.json')

    notes = args.notes if args.notes.startswith(f"{version}:") else f"{version}: {args.notes}"
    write_json(pr.LATEST, {"version": version, "url": links["SW-DLT"], "notes": notes, "release": args.date})
    write_json(pr.LINKS, links)
    print(f"wrote {pr.LATEST.relative_to(pr.ROOT)} and {pr.LINKS.relative_to(pr.ROOT)} for {version}")

    check = subprocess.run([sys.executable, str(pr.ROOT / "scripts" / "prepare_release.py"), "--skip-commit-check"],
                           stdout=subprocess.DEVNULL)
    if check.returncode:
        return check.returncode  # prepare_release.py already printed the reason
    print("release metadata valid; commit the signed shortcuts and api/updates/*.json, then merge to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
