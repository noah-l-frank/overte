#!/usr/bin/env python3
"""Enforce the machine-readable compatibility and migration registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "pico-create-management": 1,
    "pico-graphics-feature-binding": 1,
    "graphics-journey-feature": 1,
    "graphics-journey-lifetime": 1,
    "graphics-lifetime-archive": 1,
    "graphics-journey-restart": 1,
    "graphics-restart-archive": 1,
    "graphics-journey-background": 1,
    "pico-graphics-lifecycle-binding": 1,
    "graphics-journey-observer": 2,
    "graphics-journey-readiness": 1,
    "graphics-journey-effects": 1,

    "pico-graphics-composition": 1,
    "stereo-graphics-surface-pixels": 1,
    "graphics-journey-samples": 5,
    "graphics-journey-measurements": 2,
    "graphics-journey-originals": 2,
    "graphics-journey-preferences": 3,
    "graphics-journey-source-history": 1,
    "graphics-journey-scene": 4,
    "graphics-journey-fixture": 1,
    "graphics-journey-geometry": 2,
    "graphics-journey-restart-proof": 2,
    "pico-graphics-scene-policy": 3,
    "stereo-graphics-archive": 2,
    "stereo-graphics-evidence": 2,
    "world-render-receipt-inventory": 1,
    "pico-graphics-capture-binding": 1,
    "pico-navigation-address-observation": 1,
    "pico-graphics-input-surface": 1,
    "vr-graphics-framework-ownership": 1,
    "native-tablet-http": 1,
    "pico-graphics-ui-observation": 2,
    "stereo-graphics-pixels": 1,
    "native-graphics-subject": 3,
    "native-scene-loads": 1,
    "native-web-runtime": 2,
    'native-qml-load-inventory': 1,
    'authentication-journey-actions': 1,
    'authentication-journey-causality': 1,
    'authentication-journey-samples': 2,
    'authentication-journey-feature': 1,
    'authentication-fixture-reader': 1,
    'authentication-fixture-origin': 1,
    'native-login-observation': 1,
    'native-login-ui-inventory': 1,
    'native-account-menu-controls': 1,
    'pico-authentication-feature-binding': 1,
    'pico-tablet-home-observation': 1,
    'pico-feature-observer': 2,
    'owned-feature-observer': 1,

    'script-journey-actions': 1,
    'script-journey-causality': 1,
    'script-journey-feature': 1,
    'script-journey-file-scope': 1,
    'script-journey-history': 1,
    'script-journey-source-lock': 1,
    'script-journey-measurements': 2,
    'script-journey-observation': 2,
    'script-journey-scope-transfer': 1,
    'script-journey-file-source': 1,
    'native-script-ui-inventory': 1,
    'pico-script-feature-binding': 1,
    'pico-script-observer': 1,

    'feature-graphics-resources': 2,
    'feature-graphics-world-surface-stimulus': 1,
    'native-script-fixture-location': 1,
    'native-script-membership': 1,
    'feature-adapter-fixture-access': 1,
    'feature-fixture-phase': 1,
    'feature-script-resources': 1,
    "native-pending-commit-owner": 1,
    "native-pending-field-commit": 1,
    "asset-input-bundle": 1,
    "native-feature-observation": 1,
    "native-location-bookmarks": 1,
    "native-places-controls": 1,
    "navigation-bookmark-operations": 1,
    "native-chat-observation": 2,
    "native-chat-domain-session": 1,
    "native-chat-view": 2,
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
    "native-animation-history": 2,
    "native-animation-caller": 2,
    "native-animation-source": 1,
    "emote-animation-pins": 1,
    "native-script-controls": 1,
    "native-private-login-input": 2,
    "native-login-controls": 2,
    "native-create-controls": 1,
    "native-chat-controls": 1,
    "native-audio-controls": 1,
    "native-graphics-controls": 1,
    "world-render-acquisition": 4,
    "native-stereo-render-trace": 4,
    "world-render-storage": 1,
    "world-render-ownership": 2,
    "world-render-receipt-cleanup": 1,
    "graphics-subject": 2,
    "native-script-code-identity": 1,
    "native-script-compilations": 1,
    "native-script-load-history": 1,
    "native-process-presence": 1,
    "native-script-manager-status": 1,
    "normal-script-missing-load": 1,
    "normal-script-file-ownership": 1,
    "script-restart-handoff": 2,
    "normal-restart-inputs": 1,
    "pico-script-restart-binding": 1,
    "android-process-query": 1,
    "emote-source-profile": 1,
    "native-script-file-controls": 1,
    "native-script-fixture-storage": 1,
    "native-script-observation": 1,
    "recorded-preview-signal": 1,
    "recorded-preview-evidence": 1,
    "recorded-preview-history": 1,
    "pico-lifecycle-ui-observation": 1,
    "lifecycle-ui-source-state": 1,
    "pico-lifecycle-back-owner": 1,
    "native-audio-preview-lifetime": 1,
    "pico-audio-page-owner": 1,
    "pico-snapshot-native-originals": 1,
    "pico-audio-capture-background": 1,
    "pico-audio-capture-owner": 2,
    "pico-audio-final-close": 1,
    "pico-audio-normal-recipe": 1,
    "pico-audio-page-observation": 1,
    "pico-audio-settings-observation": 2,
    "pico-lifecycle-drive-observation": 1,
    "pico-lifecycle-gesture-observation": 1,
    "pico-lifecycle-world-owner": 1,
    "pico-lifecycle-x-join": 1,
    "pico-lifecycle-process-owner": 1,
    "native-lifecycle-controls": 1,
    "pico-lifecycle-draft-controls": 1,
    "pico-lifecycle-editor-owner": 1,
    "pico-lifecycle-chat-owner": 1,
    "native-lifecycle-background": 1,
    "pico-lifecycle-background-owner": 1,
    "pico-lifecycle-background-originals": 1,
    "chat-journey-source-chunks": 1,
    "audio-preview-owner": 1,
    "native-navigation-replies": 2,
    "native-navigation-modals": 1,
    "native-navigation-error-controls": 1,
    "navigation-error-dismissal": 2,
    "native-navigation-environment": 1,
    "native-navigation-origin-controls": 1,
    "navigation-origin-operations": 2,
    "navigation-environment-archive": 1,
    "native-navigation-directory": 1,
    "native-navigation-panels": 2,
    "pico-navigation-lookup-controls": 1,
    "navigation-missing-lookup": 1,
    "navigation-directory-operations": 1,
    "navigation-pose": 1,
    "navigation-stereo-source": 2,
    "navigation-stereo-owner": 2,
    "navigation-transit-operations": 2,
    "navigation-tablet-close": 1,
    "navigation-frame-publication": 1,
    "stereo-navigation-evidence": 1,
    "navigation-scene-stimulus": 1,
    "feature-navigation-provider": 2,
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
