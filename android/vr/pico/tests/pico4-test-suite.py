#!/usr/bin/env python3
"""Hardware-independent Pico 4 regression-suite orchestrator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


TEST_DIR = Path(__file__).resolve().parent
ANDROID_DIR = TEST_DIR.parent


@dataclass(frozen=True)
class Test:
    name: str
    category: str
    command: tuple[str, ...]
    requires: tuple[str, ...] = ()


def test(name: str, category: str, *command: str, requires: tuple[str, ...] = ()) -> Test:
    return Test(name, category, command, requires)


PYTHON = sys.executable
TESTS = (
    test("suite-runner", "infrastructure", PYTHON, "pico4-test-suite-self-test.py"),
    test("coverage-matrix", "infrastructure", PYTHON, "pico4-coverage-test.py"),
    test("normal-input-transport", "interaction", PYTHON, "pico-normal-transport-test.py"),
    test("navigation-bookmark-restart", "interaction", PYTHON, "pico-navigation-bookmark-restart-test.py"),
    test("navigation-lookup-close", "interaction", PYTHON, "pico-navigation-lookup-close-test.py"),
    test("chat-dispatcher-journey", "interaction", PYTHON, "pico-chat-dispatcher-test.py", "journey"),
    test("chat-dispatcher-recovery", "interaction", PYTHON, "pico-chat-dispatcher-test.py", "recovery"),
    test("chat-input-phase", "interaction", PYTHON, "pico-chat-dispatcher-test.py", "phase"),
    test("chat-compiled-source", "interaction", PYTHON, "pico-chat-compiled-source-test.py"),
    test("chat-erase-restore", "interaction", PYTHON, "pico-chat-erase-restore-test.py"),
    test("chat-composition", "interaction", PYTHON, "device/test_chat_composition.py"),
    test("chat-cache-release-positive", "interaction", PYTHON, "pico-chat-cache-release-test.py", "positive"),
    test("chat-cache-release-admission", "interaction", PYTHON, "pico-chat-cache-release-test.py", "admission"),
    test("chat-cache-release-quiet", "interaction", PYTHON, "pico-chat-cache-release-test.py", "quiet"),
    test("chat-cache-release-final-clock", "interaction", PYTHON, "pico-chat-cache-release-test.py", "final-clock"),
    test("chat-actor-source", "interaction", PYTHON, "pico-chat-actor-source-test.py", requires=("cmake", "git", "c++", "pkg-config")),
    test("shell-syntax", "infrastructure", "bash", "pico-shell-syntax-test.sh"),
    test("source-inputs-v1", "android", PYTHON, "test_source_inputs.py"),
    test("source-inputs-v2", "android", PYTHON, "test_qualified_reuse.py"),
    test("source-inputs-v3", "android", PYTHON, "test_qualified_reuse_v3.py"),
    test("package-contract", "android", PYTHON, "pico-package-contract-test.py"),
    test("apk-verifier", "android", PYTHON, "pico-apk-verifier-test.py"),
    test("release-contract", "android", PYTHON, "pico-release-contract-test.py"),
    test("platform-glue", "android", PYTHON, "pico-platform-glue-test.py"),
    test("android-entrypoints", "android", PYTHON, "pico-android-entrypoints-test.py"),
    test("activity-ingress", "android", PYTHON, "device/test_activity_ingress.py", requires=("javac", "java")),
    test("browser-originals", "webview", PYTHON, "pico-browser-originals-test.py", requires=("c++", "pkg-config", "javac", "java", "node")),
    test("embedded-web", "webview", PYTHON, "pico-embedded-web-test.py", requires=("c++", "pkg-config")),
    test("legacy-web-lifecycle", "webview", PYTHON, "device/test_legacy_web_lifecycle.py", requires=("javac", "java")),
    test("legacy-web-qt-jni", "webview", PYTHON, "device/test_legacy_web_qt.py", requires=("c++", "pkg-config", "javac", "java")),
    test("webview-bridge", "webview", PYTHON, "pico-webview-bridge-test.py"),
    test("webview-touch-state", "webview", "bash", "pico-webview-input-test.sh", requires=("javac", "java")),
    test("audio-capture-state", "audio", "bash", "pico-audio-capture-state-test.sh", requires=("javac", "java")),
    test("audio-native-transport", "audio", PYTHON, "pico-audio-transport-test.py"),
    test("audio-preview-owner", "audio", PYTHON, "device/test_audio_preview.py"),
    test("audio-capture-owner", "audio", PYTHON, "device/test_audio_capture_owner.py"),
    test("audio-background-owner", "audio", PYTHON, "pico-audio-background-test.py"),
    test("audio-final-close", "audio", PYTHON, "device/test_audio_final_close.py", "AudioFinalCloseTests", "PicoAudioFinalBindingTests"),
    test("audio-normal-recipe-flow", "audio", PYTHON, "device/test_audio_normal_recipe.py", "AudioRecipeFlowTests"),
    test("audio-normal-recipe-fences", "audio", PYTHON, "device/test_audio_normal_recipe.py", "AudioRecipeTests", "PicoAudioRecipeBindingTests"),
    test("audio-final-retirement", "audio", PYTHON, "device/test_audio_final_close.py", "AudioFinalRetirementTests"),
    test("audio-page-owner", "audio", PYTHON, "device/test_audio_page_owner.py"),
    test("audio-settings-source", "audio", PYTHON, "device/test_audio_settings.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-fast-cancel", "interaction", PYTHON, "device/test_snapshot_cancel.py", requires=("c++", "pkg-config")),
    test("snapshot-review-originals", "interaction", PYTHON, "device/test_snapshot_review.py", requires=("c++", "pkg-config")),
    test("snapshot-script-originals", "interaction", PYTHON, "device/test_snapshot_script_originals.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-native-originals", "interaction", PYTHON, "device/test_snapshot_originals.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-normal-still-owner", "interaction", PYTHON, "device/test_snapshot_still_owner.py"),
    test("openxr-loader", "openxr", PYTHON, "pico-openxr-loader-test.py"),
    test("openxr-input", "openxr", PYTHON, "pico-openxr-input-test.py"),
    test("openxr-display", "openxr", PYTHON, "pico-openxr-display-test.py"),
    test("stereo-world-render", "openxr", PYTHON, "device/test_stereo_world_render.py"),
    test("graphics-sources", "interaction", PYTHON, "device/test_graphics_sources.py"),
    test("native-classloader", "android", PYTHON, "device/test_pico_native_classloader.py", requires=("javac", "java")),
    test("interaction-diagnostics", "interaction", "node", "pico-interaction-diagnostics-test.js", requires=("node",)),
    test("tablet-lifecycle", "interaction", "node", "pico-tablet-lifecycle-test.js", requires=("node",)),
    test("tablet-settings", "interaction", "node", "pico-tablet-settings-test.js", requires=("node",)),
    test("emote", "interaction", "node", "pico-emote-test.js", requires=("node",)),
    test("tablet-e2e-adapter", "interaction", PYTHON, "pico-tablet-e2e-adapter-test.py"),
    test("feature-observation", "interaction", PYTHON, "device/test_feature_observation.py"),
    test("normal-scripts", "interaction", PYTHON, "device/test_normal_scripts.py"),
    test("script-feature-journey", "interaction", PYTHON, "device/test_script_journey.py", "PicoScriptJourneyTests"),
    test("script-feature-engine", "interaction", PYTHON, "device/test_script_journey.py", "PicoSharedScriptJourneyTests"),
    test("authentication-feature-journey", "interaction", PYTHON, "device/test_authentication_journey.py", "PicoAuthenticationTests"),
    test("authentication-feature-engine", "interaction", PYTHON, "device/test_authentication_journey.py", "PicoAuthenticationEngineTests"),
    test("tablet-home-ray", "interaction", PYTHON, "device/test_tablet_home.py"),
    test("lifecycle-input-owner", "interaction", PYTHON, "device/test_lifecycle_input.py", requires=("node",)),
    test("lifecycle-background-owner", "interaction", PYTHON, "device/test_lifecycle_background_owner.py", requires=("node",)),
    test("normal-create", "interaction", PYTHON, "device/test_normal_create.py"),
    test("create-file-ui", "interaction", PYTHON, "device/test_create_file_ui.py"),
    test("create-file-native-ui", "interaction", PYTHON, "device/test_create_file_ui_native.py", requires=("c++", "pkg-config")),
    test("create-original-files", "interaction", PYTHON, "device/test_create_files_native.py", requires=("c++", "pkg-config")),
    test("create-callback-native", "interaction", PYTHON, "device/test_create_callbacks_native.py", requires=("c++", "pkg-config")),
    test("create-browse-setting", "interaction", PYTHON, "device/test_create_browse_setting.py"),
    test("create-browse-setting-native", "interaction", PYTHON, "device/test_create_browse_setting_native.py", requires=("c++", "pkg-config")),
    test("create-rez-permissions", "interaction", PYTHON, "device/test_create_rez_permissions.py"),
    test("create-rez-owner", "interaction", PYTHON, "device/test_create_rez_owner.py"),
    test("create-voxel-owner", "interaction", PYTHON, "device/test_create_voxel_owner_flow.py"),
    test("create-voxel-guards", "interaction", PYTHON, "device/test_create_voxel_owner_guards.py"),
    test("create-primitives-owner", "interaction", PYTHON, "device/test_create_primitives_owner.py"),
    test("create-polyvox-native-ui", "interaction", PYTHON, "device/test_create_polyvox_controls_native.py", requires=("c++", "pkg-config", "node")),
    test("create-feature-owner", "interaction", PYTHON, "device/test_create_feature_owner.py"),
    test("create-model-resource-join", "interaction", PYTHON, "device/test_create_model_resource_join.py"),
    test("create-model-resources-native", "interaction", PYTHON, "device/test_create_model_resources_native.py", requires=("c++", "pkg-config")),
    test("create-model-owner", "interaction", PYTHON, "device/test_create_models.py", requires=("node",)),
    test("create-model-native-ui", "interaction", PYTHON, "device/test_create_model_controls_native.py", requires=("c++", "pkg-config")),
    test("create-picker-owner", "interaction", PYTHON, "device/test_create_picker_owner.py"),
    test("create-entities-native", "interaction", PYTHON, "device/test_create_entities_native.py", requires=("c++", "pkg-config")),
    test("create-dialog-native", "interaction", PYTHON, "device/test_create_dialogs_native.py", requires=("c++", "pkg-config")),
    test("normal-chat", "interaction", PYTHON, "device/test_normal_chat.py"),
    test("normal-emote", "interaction", PYTHON, "device/test_normal_emote.py"),
    test("emote-view-native-ui", "interaction", PYTHON, "pico-view-menu-native-test.py", requires=("c++", "pkg-config")),
    test("emote-scene-native", "interaction", PYTHON, "pico-emote-scene-native-test.py", requires=("c++", "pkg-config")),
    test("emote-original-sources", "interaction", PYTHON, "pico-emote-sources-test.py"),
    test("emote-input-effects", "interaction", PYTHON, "pico-emote-input-effects-test.py"),
    test("emote-lifetime", "interaction", PYTHON, "pico-emote-lifetime-test.py"),
    test("emote-stereo-capture", "interaction", PYTHON, "pico-emote-stereo-capture-test.py"),
    test("emote-background-effects", "interaction", PYTHON, "pico-emote-background-test.py"),
    test("normal-login", "interaction", PYTHON, "device/test_normal_login.py"),
    test("create-qml", "interaction", PYTHON, "pico-create-qml-test.py"),
    test("create-properties", "interaction", "node", "pico-create-properties-validation-test.js", requires=("node",)),
    test("create-message", "interaction", "node", "pico-create-message-validation-test.js", requires=("node",)),
    test("avatar-hotpath", "performance", PYTHON, "pico-avatar-hotpath-test.py"),
    test("shadergen-jobs", "performance", PYTHON, "pico-shadergen-jobs-test.py"),
    test("world-state", "world", PYTHON, "pico-world-state-test.py"),
    test("microphone-runner", "tooling", "bash", "pico-microphone-test-test.sh"),
    test("unattended-runner", "tooling", "bash", "pico-unattended-test-test.sh"),
    test("device-lock", "tooling", "bash", "pico-device-lock-test.sh"),
    test("device-acceptance", "tooling", "bash", "pico-device-acceptance-test.sh"),
    test("serverless-fixtures", "world", "bash", "serverless-hub-fixture-test.sh", requires=("jq",)),
    test("power-analyzer", "performance", PYTHON, "test_analyze_pico4_power.py"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list tests without running them")
    parser.add_argument("--category", action="append", default=[], help="run a category (repeatable)")
    parser.add_argument("--test", action="append", default=[], help="run a named test (repeatable)")
    parser.add_argument("--timeout", type=int, default=120, help="seconds allowed per test (default: 120)")
    parser.add_argument("--junit", type=Path, help="write a JUnit XML report")
    parser.add_argument("--fail-fast", action="store_true", help="stop after the first failure")
    parser.add_argument("--skip-missing", action="store_true", help="report missing tools as skipped (the incomplete selection still exits nonzero)")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def selected_tests(args: argparse.Namespace) -> list[Test]:
    names = set(args.test)
    categories = set(args.category)
    known_names = {item.name for item in TESTS}
    known_categories = {item.category for item in TESTS}
    unknown = sorted(names - known_names)
    unknown_categories = sorted(categories - known_categories)
    if unknown or unknown_categories:
        details = []
        if unknown:
            details.append("unknown tests: " + ", ".join(unknown))
        if unknown_categories:
            details.append("unknown categories: " + ", ".join(unknown_categories))
        raise ValueError("; ".join(details))
    if not names and not categories:
        return list(TESTS)
    return [item for item in TESTS if item.name in names or item.category in categories]


def junit_report(path: Path, results: list[dict[str, object]], elapsed: float) -> None:
    failures = sum(result["status"] == "failed" for result in results)
    skipped = sum(result["status"] == "skipped" for result in results)
    suite = ET.Element("testsuite", name="pico4-device-free", tests=str(len(results)),
                       failures=str(failures), skipped=str(skipped), time=f"{elapsed:.3f}")
    properties = ET.SubElement(suite, "properties")
    complete = bool(results) and not failures and not skipped
    full_catalog = {str(result["name"]) for result in results} == {item.name for item in TESTS}
    for name, value in (("catalog_tests", str(len(TESTS))),
                        ("selection_complete", str(complete).lower()),
                        ("full_catalog_selected", str(full_catalog).lower()),
                        ("full_catalog_passed", str(complete and full_catalog).lower())):
        ET.SubElement(properties, "property", name=name, value=value)
    for result in results:
        case = ET.SubElement(suite, "testcase", name=str(result["name"]),
                             classname=f"pico4.{result['category']}", time=f"{result['time']:.3f}")
        if result["status"] == "failed":
            node = ET.SubElement(case, "failure", message=str(result["message"]))
            node.text = str(result["output"])
        elif result["status"] == "skipped":
            ET.SubElement(case, "skipped", message=str(result["message"]))
        output = str(result["output"])
        if output:
            ET.SubElement(case, "system-out").text = output
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    args = parse_args()
    try:
        chosen = selected_tests(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.list:
        for item in chosen:
            print(f"{item.name:<26} {item.category}")
        return 0

    results: list[dict[str, object]] = []
    started = time.monotonic()
    stopped = False
    for item in chosen:
        if stopped:
            results.append(dict(name=item.name, category=item.category, status="skipped",
                                message="not run after fail-fast", output="", time=0.0))
            continue
        missing = [tool for tool in item.requires if shutil.which(tool) is None]
        if missing:
            message = "missing tools: " + ", ".join(missing)
            status = "skipped" if args.skip_missing else "failed"
            print(f"{status.upper():7} {item.name} ({message})")
            results.append(dict(name=item.name, category=item.category, status=status,
                                message=message, output="", time=0.0))
            if args.fail_fast:
                stopped = True
            continue
        command = list(item.command)
        if len(command) > 1 and not os.path.isabs(command[1]):
            command[1] = str(TEST_DIR / command[1])
        test_started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=TEST_DIR, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=args.timeout, check=False)
            duration = time.monotonic() - test_started
            output = completed.stdout
            status = "passed" if completed.returncode == 0 else "failed"
            message = "" if completed.returncode == 0 else f"exit code {completed.returncode}"
        except subprocess.TimeoutExpired as error:
            duration = time.monotonic() - test_started
            # TimeoutExpired may retain bytes even with text=True. Preserve
            # the owning test's partial diagnostics in its failed report.
            output = error.stdout.decode('utf-8',errors='replace') if isinstance(error.stdout,bytes) else (error.stdout or "")
            status, message = "failed", f"timeout after {args.timeout}s"
        except OSError:
            duration = time.monotonic() - test_started
            # Keep paths and environment details out of the diagnostic.
            output = ""
            status, message = "failed", "test process could not be started"
        print(f"{status.upper():7} {item.name:<26} {duration:7.3f}s")
        if status == "failed" and output:
            print(output.rstrip(), file=sys.stderr)
        results.append(dict(name=item.name, category=item.category, status=status,
                            message=message, output=output, time=duration))
        if status == "failed" and args.fail_fast:
            stopped = True

    elapsed = time.monotonic() - started
    if args.junit:
        junit_report(args.junit, results, elapsed)
        print(f"JUnit: {args.junit}")
    passed = sum(result["status"] == "passed" for result in results)
    failed = sum(result["status"] == "failed" for result in results)
    skipped = sum(result["status"] == "skipped" for result in results)
    print(f"Pico 4 device-free selection ({len(results)}/{len(TESTS)} catalog cases): {passed} passed, {failed} failed, {skipped} skipped ({elapsed:.2f}s)")
    return 1 if failed or skipped or not results else 0


if __name__ == "__main__":
    raise SystemExit(main())
