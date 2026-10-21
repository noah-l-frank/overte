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
    "ios-native-feature-clock-binding": 1,
    "native-ios-bundle-observation": 1,
    "ios-bundle-byte-identity": 1,
    "ios-physical-candidate-consumer": 1,
    "ios-process-observer": 1,
    "ios-installed-code-binding": 4,
    "native-chat-observation": 1,
    "native-chat-view": 1,
    "native-chat-actor-files": 1,
    "owned-messages-mixer": 1,
    "independent-chat-receiver": 1,
    "native-account-observation": 1,
    "native-account-probe": 1,
    "native-account-origin": 1,
    "feature-fixture-adapter-access": 1,
    "feature-account-provider": 2,
    "feature-browser-resources": 1,
    "web-dom-observation": 1,
    "ios-feature-image-provenance": 1,
    "ios-web-closures": 5,
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
    "graphics-subject": 2,
    "native-graphics-subject": 3,
    "native-scene-loads": 1,
    "native-completed-frame": 1,
    "native-completed-draw-trace": 1,
    "native-completed-frame-storage": 1,
    "completed-frame-lease": 1,
    "native-vulkan-world-frame": 1,
    "native-vulkan-world-storage": 1,
    "owned-vulkan-world-frame": 1,
    "vulkan-world-chunk-summary": 1,
    "recorded-render-view": 1,
    "feature-graphics-resources": 1,
    "feature-phase-fixture": 1,
    "native-script-code-identity": 1,
    "native-script-load-history": 1,
    "native-process-presence": 1,
    "native-script-manager-status": 1,
    "normal-script-missing-load": 1,
    "normal-script-file-ownership": 1,
    "script-restart-handoff": 2,
    "normal-restart-inputs": 1,
    "android-process-query": 1,
    "emote-source-profile": 1,
    "native-script-file-controls": 1,
    "native-script-fixture-storage": 1,
    "native-script-membership": 1,
    "native-script-fixture-location": 1,
    "ios-login-ui-source": 1,
    "ios-graphics-ui-source": 1,
    "ios-graphics-surface": 1,
    "ios-original-geometry": 1,
    "ios-screen-png-acquisition": 1,
    "ios-graphics-screen-images": 1,
    "graphics-subject-geometry": 1,
    "ios-graphics-measurements": 1,
    "ios-graphics-effects": 1,
    "graphics-subject-pixels": 1,
    "ios-graphics-world-measurements": 1,
    "ios-graphics-current-effects": 1,
    "ios-graphics-world-effects": 1,
    "ios-graphics-fixture-reader": 1,
    "ios-graphics-scene": 1,
    "ios-graphics-preferences": 1,
    "ios-graphics-source-floors": 1,
    "ios-graphics-samples": 2,
    "ios-graphics-lifetime": 2,
    "ios-graphics-lifetime-record": 2,
    "ios-graphics-background": 1,
    "ios-graphics-restart": 1,
    "ios-graphics-calibration": 1,
    "ios-graphics-observer": 2,
    "ios-graphics-observer-frame": 1,
    "ios-graphics-observer-phase-retirement": 1,
    "ios-graphics-world-effect-readiness": 1,
    "feature-image-marker-readiness": 1,
    "ios-graphics-restart-proof": 1,
    "feature-graphics-viewpoint-query": 1,
    "native-view-menu-controls": 1,
    "native-account-preferences": 2,
    "native-account-preference-controls": 1,
    "native-ios-login-clear-input": 1,
    "native-account-menu-controls": 1,
    "ios-script-ui-source": 1,
    "native-script-ui-inventory": 1,
    "script-feature-measurements": 2,
    "script-feature-source-history": 1,
    "script-feature-source-observation": 2,
    "script-feature-file-scope": 1,
    "script-feature-actions": 1,
    "script-feature-source-lock": 1,
    "script-feature-causality": 1,
    "script-feature-scope-transfer": 1,
    "ios-script-feature": 1,
    "ios-script-clock-observation": 1,
    "ios-script-feature-configuration": 1,
    "ios-script-observer": 1,
    "ios-authentication-feature": 1,
    "ios-authentication-actions": 2,
    "ios-authentication-samples": 3,
    "ios-authentication-causality": 1,
    "ios-authentication-observer": 1,
    "feature-restart-background-notification": 1,
    "feature-script-resources": 1,
    "native-host-clock-join": 1,
    "native-script-observation": 1,
    "recorded-preview-signal": 1,
    "recorded-preview-evidence": 1,
    "recorded-preview-history": 1,
    "native-navigation-replies": 1,
    "feature-navigation-provider": 1,
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
