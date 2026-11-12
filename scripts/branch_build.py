#!/usr/bin/env python3
"""Write a build copy of a shortcut plist adjusted for the branch being built.

On main the plist is copied unchanged. On any other branch:
  * the installer downloads SW_DLT.py from that branch instead of main, and
  * a step before the download refreshes SW_DLT.py from that branch on every
    run, so a phone always tests the branch's latest pushed script.

The source plists always point at main, so nothing has to be reverted before
merging. Usage: branch_build.py <branch> <in.plist> <out.plist>
"""

from __future__ import annotations

import plistlib
import sys
import uuid
from pathlib import Path

REPO = "hryamzik/SW-DLT"
MAIN_SCRIPT_URL = f"https://raw.githubusercontent.com/{REPO}/refs/heads/main/src/SW_DLT.py"
OBJ = "￼"


def walk_strings(node, fn):
    """Apply fn to every plain string and token-string text, in place."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                node[key] = fn(value)
            else:
                walk_strings(value, fn)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            if isinstance(value, str):
                node[i] = fn(value)
            else:
                walk_strings(value, fn)


def check_token_safe(node, old: str) -> None:
    """Replacing text after a token would move it; only allow it before any token."""
    if isinstance(node, dict):
        if "attachmentsByRange" in node and isinstance(node.get("string"), str) and old in node["string"]:
            text = node["string"]
            first_token = text.find(OBJ)
            if first_token != -1 and text.index(old) < first_token and node["attachmentsByRange"]:
                raise SystemExit(f"{old!r} appears before a variable token; offsets would shift")
        for value in node.values():
            check_token_safe(value, old)
    elif isinstance(node, list):
        for value in node:
            check_token_safe(value, old)


def refresh_actions(script_url: str, branch: str) -> list[dict]:
    target = "$HOME/Documents/SW-DLT/SW_DLT.py"
    # a-Shell runs "close" commands without a shell, so && must go through dash
    # (like the shortcut's other close-mode commands); otherwise curl gets "&&" as a URL (exit 3).
    command = f"dash -c 'curl -sfL {script_url} -o {target}.new && mv {target}.new {target}'"
    return [
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": f"BRANCH BUILD ({branch}): refresh SW_DLT.py from this branch on every run. "
                "Added by scripts/branch_build.py; not present in builds from main.",
            },
        },
        {
            "WFWorkflowActionIdentifier": "AsheKube.app.a-Shell.ExecuteCommandIntent",
            "WFWorkflowActionParameters": {
                "UUID": str(uuid.uuid4()).upper(),
                "ShowWhenRun": False,
                "keepGoing": False,
                "openWindow": "close",
                "command": {
                    "Value": {"string": command, "attachmentsByRange": {}},
                    "WFSerializationType": "WFTextTokenString",
                },
            },
        },
    ]


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    branch, src, dst = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    with src.open("rb") as fh:
        data = plistlib.load(fh)

    if branch != "main":
        branch_url = MAIN_SCRIPT_URL.replace("/refs/heads/main/", f"/refs/heads/{branch}/")
        text = src.read_text(encoding="utf-8")
        if MAIN_SCRIPT_URL in text:
            check_token_safe(data, MAIN_SCRIPT_URL)
            walk_strings(data, lambda s: s.replace(MAIN_SCRIPT_URL, branch_url))

        actions = data["WFWorkflowActions"]
        open_app = [i for i, a in enumerate(actions) if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.openapp"]
        if MAIN_SCRIPT_URL in text:
            # Only the main shortcut installs/runs the script; wrappers have no openapp step.
            if len(open_app) != 1:
                raise SystemExit(f"{src}: expected exactly one Open App action, found {len(open_app)}")
            actions[open_app[0]:open_app[0]] = refresh_actions(branch_url, branch)
        print(f"branch_build: {src.name} -> {dst} (script from '{branch}')")
    else:
        print(f"branch_build: {src.name} -> {dst} (main, unchanged)")

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as fh:
        plistlib.dump(data, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
