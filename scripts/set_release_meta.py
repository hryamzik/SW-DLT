#!/usr/bin/env python3
"""Write api/updates/latest.json and release_links.json for the version in src/SW-DLT.plist.

  set_release_meta.py --check-bump
      fail if src/SW-DLT.plist still has the version latest.json already announces
  set_release_meta.py --main URL --audio URL --video URL --notes TEXT [--date YYYY-MM-DD]
      write both files, then validate them with prepare_release.py
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_release as pr  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-bump", action="store_true")
    parser.add_argument("--main")
    parser.add_argument("--audio")
    parser.add_argument("--video")
    parser.add_argument("--notes")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    args = parser.parse_args()

    version = pr.plist_version()
    released = json.loads(pr.LATEST.read_text(encoding="utf-8")).get("version")

    if args.check_bump:
        if version == released:
            pr.fail(f"src/SW-DLT.plist is still {version}, which latest.json already announces: "
                    "bump the version first (or FORCE=1 to rebuild the same version)")
        print(f"releasing {version} (current release {released})")
        return 0

    links = {"SW-DLT": args.main, "SW-DLT Audio": args.audio, "SW-DLT Video 720p": args.video}
    missing = [name for name, url in links.items() if not url]
    if missing or not args.notes:
        pr.fail("need MAIN, AUDIO, VIDEO (iCloud links) and NOTES, e.g.\n"
                '  make release-meta MAIN=https://www.icloud.com/shortcuts/... AUDIO=... VIDEO=... NOTES="..."')
    for name, url in links.items():
        if not pr.ICLOUD_RE.match(url):
            pr.fail(f"{name}: not an iCloud shortcut link: {url!r}")
    if "/shortcut" in args.notes:
        pr.fail('NOTES must not contain "/shortcut": the updater uses the first one in latest.json')

    notes = args.notes if args.notes.startswith(f"{version}:") else f"{version}: {args.notes}"
    write_json(pr.LATEST, {"version": version, "url": args.main, "notes": notes, "release": args.date})
    write_json(pr.LINKS, links)
    print(f"wrote {pr.LATEST.relative_to(pr.ROOT)} and {pr.LINKS.relative_to(pr.ROOT)} for {version}")

    subprocess.run([sys.executable, str(pr.ROOT / "scripts" / "prepare_release.py"), "--skip-commit-check"],
                   check=True, stdout=subprocess.DEVNULL)
    print("release metadata valid; commit the signed shortcuts and api/updates/*.json, then merge to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
