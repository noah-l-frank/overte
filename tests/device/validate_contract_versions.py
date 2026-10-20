#!/usr/bin/env python3
"""Enforce the machine-readable compatibility and migration registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "native-pending-commit-owner": 1,
    "native-pending-field-commit": 1,
    "asset-input-bundle": 1,
    "native-feature-observation": 1,
    "native-chat-observation": 1,
    "native-chat-view": 1,
    "native-chat-actor-files": 1,
    "owned-messages-mixer": 1,
    "independent-chat-receiver": 1,
    "native-account-observation": 1,
    "native-account-probe": 1,
    "native-account-origin": 1,
    "feature-account-provider": 2,
    "feature-browser-resources": 1,
    "web-dom-observation": 1,
    "native-web-dom-observation": 1,
    "native-animation-history": 1,
    "native-script-controls": 1,
    "native-private-login-input": 2,
    "native-login-controls": 2,
    "native-create-controls": 1,
    "native-chat-controls": 1,
    "native-audio-controls": 1,
    "native-graphics-controls": 1,
    "world-render-acquisition": 1,
    "world-render-storage": 1,
    "world-render-ownership": 1,
    "world-render-receipt-cleanup": 1,
    "graphics-subject": 1,
    "native-script-code-identity": 1,
    "native-script-load-history": 1,
    "native-process-presence": 1,
    "native-script-manager-status": 1,
    "phone-script-ui-inventory": 1,
    "phone-script-measurements": 2,
    "phone-existing-input-session": 1,
    "phone-account-fixture-launch": 1,
    "phone-script-source-lock": 1,
    "phone-script-actions": 1,
    "phone-script-causality": 1,
    "phone-script-feature": 1,
    "phone-script-observer": 1,
    "phone-script-observation": 2,
    "phone-script-file-scope": 1,
    "phone-script-history": 1,
    "phone-script-scope-transfer": 1,
    "native-script-membership": 1,
    "normal-script-missing-load": 1,
    "normal-script-file-ownership": 1,
    "script-restart-handoff": 2,
    "normal-restart-inputs": 1,
    "android-process-query": 1,
    "emote-source-profile": 1,
    "native-script-file-controls": 1,
    "native-script-fixture-location": 1,
    "native-script-fixture-storage": 1,
    "native-script-observation": 1,
    "recorded-preview-signal": 1,
    "recorded-preview-evidence": 1,
    "recorded-preview-history": 1,
    "native-navigation-replies": 1,
    "feature-navigation-provider": 1,
    "feature-script-resources": 1,
    "feature-journey": 16, "acceptance-policy": 1, "adapter-manifest": 1, "artifact-manifest": 1,
    "capability-registry": 1, "fixture-environment": 1, "matrix-summary": 1,
    "voice-test": 1, "probe-snapshot": 2, "run-manifest": 1, "run-summary": 1, "timeline": 1,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path,
        default=Path(__file__).resolve().with_name("contract-versions.json"))
    args = parser.parse_args()
    value = json.loads(args.registry.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or value.get("schemaVersion") != 1
            or set(value) != {"schemaVersion", "contracts", "migrationRules"}
            or set(value.get("contracts", {})) != set(REQUIRED)):
        raise ValueError("contract version registry shape is invalid")
    for name, expected in REQUIRED.items():
        item = value["contracts"][name]
        if (not isinstance(item, dict) or set(item) != {"current", "reads"}
                or item.get("current") != expected
                or not isinstance(item.get("reads"), list)
                or item["reads"] != sorted(set(item["reads"]))
                or expected not in item["reads"]
                or not all(isinstance(version, int) and version > 0
                           for version in item["reads"])):
            raise ValueError(f"contract {name} compatibility declaration is invalid")
    rules = value["migrationRules"]
    if (not isinstance(rules, dict)
            or set(rules) != {"additiveChange", "breakingChange", "removal"}
            or not all(isinstance(text, str) and text for text in rules.values())):
        raise ValueError("contract migration rules are invalid")
    root = args.registry.resolve().parent
    observed = {
        "capability-registry": json.loads(
            (root / "capabilities.json").read_text(encoding="utf-8"))["schemaVersion"],
        "run-manifest": json.loads(
            (root / "schemas/run-manifest.schema.json").read_text(encoding="utf-8"))[
                "properties"]["schemaVersion"]["const"],
        "matrix-summary": json.loads(
            (root / "schemas/matrix-summary.schema.json").read_text(encoding="utf-8"))[
                "properties"]["schemaVersion"]["const"],
        "probe-snapshot": json.loads(
            (root / "schemas/probe-snapshot.schema.json").read_text(encoding="utf-8"))[
                "properties"]["schemaVersion"]["const"],
    }
    feature_inventory = root / "feature_journeys/adapter-contract.v16.json"
    if feature_inventory.is_file():
        observed["feature-journey"] = json.loads(feature_inventory.read_text())["contractVersion"]
    acceptance_policy = root / "acceptance-policy.json"
    if acceptance_policy.is_file():
        observed["acceptance-policy"] = json.loads(
            acceptance_policy.read_text(encoding="utf-8"))["contractVersion"]
    for name, version in observed.items():
        if value["contracts"][name]["current"] != version:
            raise ValueError(f"contract {name} registry and producer version disagree")
    print("PASS: contract versions and migration rules are coherent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=__import__("sys").stderr)
        raise SystemExit(2)
