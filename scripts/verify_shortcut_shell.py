#!/usr/bin/env python3
"""Verify SW-DLT shortcut shell text tokens and simulate a-Shell invocation (Mac or CI)."""

from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from pathlib import Path

OBJ = "\ufffc"  # Shortcuts object replacement character in exported plists
ROOT = Path(__file__).resolve().parents[1]
PLIST = ROOT / "src" / "SW-DLT.plist"
PY = ROOT / "src" / "SW_DLT.py"

TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLtest"
TEST_ARGS = "-v 720 30"
TEST_SBJSON = '{"sponsor":true}'


def load_actions() -> list[dict]:
    with PLIST.open("rb") as fh:
        data = plistlib.load(fh)
    return data["WFWorkflowActions"]


def find_text_action(actions: list[dict], output_name: str) -> dict | None:
    for action in actions:
        if action.get("WFWorkflowActionIdentifier") != "is.workflow.actions.gettext":
            continue
        params = action.get("WFWorkflowActionParameters") or {}
        if params.get("CustomOutputName") == output_name:
            return params
    return None


def text_token_string(params: dict) -> tuple[str, dict]:
    block = params["WFTextActionText"]["Value"]
    return block["string"], block.get("attachmentsByRange") or {}


def check_attachments(label: str, text: str, attachments: dict) -> None:
    for key, _meta in attachments.items():
        start, length = (int(x) for x in key.strip("{}").split(","))
        chunk = text[start : start + length]
        if chunk != OBJ:
            raise SystemExit(
                f"{label}: attachment {key} expected {OBJ!r}, got {chunk!r} "
                f"(context: {text[max(0, start - 12) : start + length + 12]!r})"
            )


def build_cli_payload(url: str, args: str) -> str:
    return f"RUN||{url}||{args}"


def simulate_shell(cli_payload: str, sbjson: str) -> list[str]:
    """Same quoting as the shortcut runScript (single-quoted argv)."""
    script = (
        f"cd $HOME/Documents/SW-DLT\n"
        f"SW-DLT-ENV/bin/python SW_DLT.py '{cli_payload}' --sbjson='{sbjson}'\n"
        f"clear && cd"
    )
    # Extract the python line like a-Shell would after variable substitution
    line = [ln for ln in script.splitlines() if "SW_DLT.py" in ln][0]
    # Parse: ... SW_DLT.py '<payload>' --sbjson='<sb>'
    m = re.match(
        r".*SW_DLT\.py '(.*)' --sbjson='(.*)'$",
        line,
    )
    if not m:
        raise SystemExit(f"Could not parse simulated command line: {line!r}")
    payload, sb = m.groups()
    return ["SW_DLT.py", payload, f"--sbjson={sb}"]


def run_python_argv(argv_tail: list[str]) -> None:
    code = (
        "import sys\n"
        f"sys.argv = {['SW_DLT.py'] + argv_tail!r}\n"
        f"exec(open({str(PY)!r}).read().split('if __name__')[0])\n"
        "SW_DLT('test_id', *sys.argv[1:])\n"
        "print('OK primary_action=', SW_DLT('test_id', *sys.argv[1:]).primary_action)\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT / "src")


def main() -> int:
    actions = load_actions()
    cli_params = find_text_action(actions, "cliPayload")
    run_params = find_text_action(actions, "runScript")
    if not cli_params or not run_params:
        raise SystemExit("cliPayload or runScript gettext action not found")

    cli_text, cli_att = text_token_string(cli_params)
    run_text, run_att = text_token_string(run_params)

    check_attachments("cliPayload", cli_text, cli_att)
    check_attachments("runScript", run_text, run_att)

    if cli_text != f"RUN||{OBJ}||{OBJ}":
        raise SystemExit(f"unexpected cliPayload template: {cli_text!r}")
    if set(cli_att) != {"{5, 1}", "{8, 1}"}:
        raise SystemExit(f"cliPayload attachments should be {{5,1}} and {{8,1}}, got {set(cli_att)}")
    if set(run_att) != {"{59, 1}", "{72, 1}"}:
        raise SystemExit(f"runScript attachments should be {{59,1}} and {{72,1}}, got {set(run_att)}")

    payload = build_cli_payload(TEST_URL, TEST_ARGS)
    argv = simulate_shell(payload, TEST_SBJSON)
    print("Simulated argv:", argv)
    run_python_argv(argv[1:])
    print("verify_shortcut_shell: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
