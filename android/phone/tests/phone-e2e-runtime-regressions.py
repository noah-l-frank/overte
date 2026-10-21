#!/usr/bin/env python3
"""Mandatory Phone-native contracts excluded from the shared source profile."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
DEPENDENCY_LIGHT_CHECKS = (
    "android/phone/tests/phone-test-inventory-test.py",
    "android/phone/tests/test_phone_ime.py",
    "android/phone/tests/phone-apk-provenance-test.py",
)
PREPARED_HOST_CHECKS = (
    "android/phone/tests/phone-snapshot-journey-test.py",
    "android/phone/tests/phone-snapshot-ui-test.py",
    "android/phone/tests/test_phone_voice_signal.py",
    "tests/device/contracts/world-entry/test_phone_feet_alignment.py",
    "tests/device/contracts/world-entry/test_phone_pad_projection.py",
    "tests/device/contracts/tablet/test_phone_settings_click.py",
    "tests/device/contracts/lifecycle/test_phone_native_startup.py",
    "tests/device/contracts/test_phone_accessibility_tree.py",
    "android/phone/tests/phone-voice-clock-test.py",
)
COMMON_HOST_CHECKS = (
    "android/phone/tests/device/test_installed_identity.py",
    "android/phone/tests/device/test_feature_adapters.py",
    "android/phone/tests/device/test_script_measurements.py",
    "android/phone/tests/device/test_script_scope.py",
    "android/phone/tests/device/test_script_history.py",
    "android/phone/tests/device/test_script_actions.py",
    "android/phone/tests/device/test_script_causality.py",
    "android/phone/tests/device/test_script_feature.py",
    "android/phone/tests/device/test_script_feature_journey.py",
    "android/phone/tests/device/test_account_fixture_launch.py",
    "android/phone/tests/device/test_account_menu.py",
    "android/phone/tests/device/test_authentication_samples.py",
    "android/phone/tests/device/test_authentication_causality.py",
    "android/phone/tests/device/test_authentication_actions.py",
    "android/phone/tests/device/test_authentication_feature.py",
    "android/phone/tests/device/test_graphics_measurements.py",
    "android/phone/tests/device/test_graphics_images.py",
    "android/phone/tests/device/test_graphics_samples.py",
    "android/phone/tests/device/test_graphics_readiness.py",
    "android/phone/tests/device/test_graphics_fixture_reader.py",
    "android/phone/tests/device/test_graphics_lifetime.py",
    "android/phone/tests/device/test_graphics_observer.py",
    "android/phone/tests/device/test_graphics_feature.py",
    "android/phone/tests/device/test_emote_controls.py",
    "android/phone/tests/device/test_emote_sources.py",
    "android/phone/tests/device/test_emote_originals.py",
    "android/phone/tests/device/test_emote_inputs.py",
    "android/phone/tests/device/test_emote_effects.py",
    "android/phone/tests/device/test_emote_background.py",
    "android/phone/tests/device/test_emote_lifetime.py",
    "android/phone/tests/device/test_emote_pixels.py",
    "android/phone/tests/device/test_emote_images.py",
    "android/phone/tests/device/test_script_roots.py",
    "android/phone/tests/device/test_script_work.py",
    "android/phone/tests/device/test_graphics_effects.py",
    "android/phone/tests/device/test_graphics_surface.py",
    "android/phone/tests/device/test_graphics_scene.py",
    "android/phone/tests/device/test_graphics_preferences.py",
    "android/phone/tests/device/test_graphics_background.py",
    "android/phone/tests/device/test_graphics_restart_scope.py",
    "android/phone/tests/device/test_graphics_restart.py",
)
CHECKS = DEPENDENCY_LIGHT_CHECKS + PREPARED_HOST_CHECKS + COMMON_HOST_CHECKS
parser = argparse.ArgumentParser()
parser.add_argument("--execute", action="store_true",
                    help="execute the Qt/GLM native contracts on the prepared host")
args = parser.parse_args()
# Every declared input is required even in dependency-light platform checks.
for name in CHECKS:
    if not (ROOT / name).is_file():
        raise SystemExit("Missing mandatory Phone runtime contract: " + name)
# The installed-candidate/normal UI binding uses only Python host fixtures.
# Keep it mandatory in both modes; prepared contracts retain their existing
# host compiler/Qt prerequisites.
selected = PREPARED_HOST_CHECKS if args.execute else DEPENDENCY_LIGHT_CHECKS
for name in selected + COMMON_HOST_CHECKS:
    path = ROOT / name
    if not path.is_file():
        raise SystemExit("Missing mandatory Phone runtime contract: " + name)
    print("Phone runtime contract: " + name, flush=True)
    arguments = [sys.executable, str(path)]
    if name.endswith("phone-test-inventory-test.py"):
        arguments.append(str(ROOT))
    # The complete Graphics composition also runs the fifteen-step common
    # journey; its host-only file/image checks need a larger aggregate budget.
    subprocess.run(arguments, cwd=ROOT, check=True,
                   timeout=240 if name.endswith("test_graphics_feature.py") else 90)
