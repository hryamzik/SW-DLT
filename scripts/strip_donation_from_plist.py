#!/usr/bin/env python3
"""Remove donation fields from src/SW-DLT.plist and fix About HTML token offsets."""

import plistlib
import re
from pathlib import Path

DONATION_BLOCK = (
    "            <hr />\n"
    "            <h3>Donations ❤️</h3>\n"
    "            <p>If this shortcut has helped you, please consider leaving a small tip by scanning or holding on the QR code. Thank you!</p>\n"
    "            <a href='￼'><img src='￼' width=\"40%\" /></a>\n"
    "            <hr />\n"
)


def dict_key_for_payload(payload: dict) -> str | None:
    for agg in payload.get("Aggrandizements", []):
        if agg.get("Type") == "WFDictionaryValueVariableAggrandizement":
            return agg.get("DictionaryKey")
    return None


def reindex_attachments(token_string: dict) -> None:
    text = token_string.get("string", "")
    attachments = token_string.get("attachmentsByRange", {})
    ordered = []
    for key, payload in attachments.items():
        m = re.match(r"\{(\d+),\s*(\d+)\}", key)
        if m:
            ordered.append((int(m.group(1)), payload))
    ordered.sort(key=lambda x: x[0])
    payloads = [p for _, p in ordered]

    new_attachments = {}
    pi = 0
    for i, ch in enumerate(text):
        if ch == "￼" and pi < len(payloads):
            new_attachments[f"{{{i}, 1}}"] = payloads[pi]
            pi += 1
    token_string["attachmentsByRange"] = new_attachments


def strip_dict_items(value: dict) -> None:
    """Recursively drop bitcoincash / qrLink from WFDictionaryFieldValueItems trees."""
    items = value.get("WFDictionaryFieldValueItems")
    if not isinstance(items, list):
        return
    kept = []
    for item in items:
        key = item.get("WFKey", {}).get("Value", {}).get("string")
        if key in ("bitcoincash", "qrLink"):
            continue
        wf_val = item.get("WFValue", {})
        if isinstance(wf_val, dict):
            inner = wf_val.get("Value")
            if isinstance(inner, dict):
                strip_dict_items(inner)
                if "Value" in inner and isinstance(inner["Value"], dict):
                    strip_dict_items(inner["Value"])
        kept.append(item)
    value["WFDictionaryFieldValueItems"] = kept


def walk_actions(actions) -> None:
    for action in actions:
        params = action.get("WFWorkflowActionParameters", {})
        ident = action.get("WFWorkflowActionIdentifier")
        if ident == "is.workflow.actions.dictionary":
            if params.get("CustomOutputName") == "properties":
                items = params.get("WFItems", {})
                value = items.get("Value") if isinstance(items, dict) else None
                if isinstance(value, dict):
                    strip_dict_items(value)
        if ident == "is.workflow.actions.gettext":
            wf_text = params.get("WFTextActionText")
            if isinstance(wf_text, dict):
                inner = wf_text.get("Value", {})
                if not isinstance(inner, dict):
                    continue
                s = inner.get("string", "")
                if "ORG:Donate, helpful links" in s:
                    inner["string"] = s.replace(
                        "ORG:Donate, helpful links, report issues;",
                        "ORG:Helpful links, report issues;",
                    )
                if "Donations" in s and "SW-DLT: About" in s:
                    attachments = inner.get("attachmentsByRange", {})
                    filtered = {}
                    for k, payload in attachments.items():
                        dk = dict_key_for_payload(payload)
                        if dk in ("vars.bitcoincash", "vars.qrLink"):
                            continue
                        filtered[k] = payload
                    inner["attachmentsByRange"] = filtered
                    inner["string"] = s.replace(
                        DONATION_BLOCK, "            <hr />\n"
                    )
                    reindex_attachments(inner)


def main():
    path = Path(__file__).resolve().parents[1] / "src" / "SW-DLT.plist"
    with path.open("rb") as fh:
        data = plistlib.load(fh)
    walk_actions(data.get("WFWorkflowActions", []))
    with path.open("wb") as fh:
        plistlib.dump(data, fh)
    print("Updated", path)


if __name__ == "__main__":
    main()
