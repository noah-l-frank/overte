#!/usr/bin/env python3
"""Mandatory Phone-native contracts excluded from the shared source profile."""
import argparse
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
DEPENDENCY_LIGHT_CHECKS = (
    "android/phone/tests/phone-test-inventory-test.py",
    "android/phone/tests/test_phone_ime.py",
    "android/phone/tests/phone-apk-provenance-test.py",
)
PREPARED_HOST_CHECKS = (
    "android/phone/tests/device/test_snapshot_handoff_audit_native.py",
    "android/phone/tests/device/test_snapshot_handoff_native.py",
    "android/phone/tests/device/test_lifecycle_editor_native.py",
    "android/phone/tests/device/test_lifecycle_world_native.py",
    "android/phone/tests/phone-chat-native-test.py",
    "android/phone/tests/phone-chat-peer-native-test.py",
    "android/phone/tests/phone-chat-history-native-test.py",
    "android/phone/tests/phone-snapshot-settings-native-test.py",
    "android/phone/tests/device/test_assets_feature.py",
    "android/phone/tests/device/test_assets_bake_originals.py",
    "android/phone/tests/device/test_snapshot_capture_files_native.py",
    "android/phone/tests/device/test_snapshot_capture_gif_native.py",
    "android/phone/tests/device/test_assets_upload_originals.py",
    "android/phone/tests/device/test_assets_geometry_input.py",
    "android/phone/tests/device/test_assets_native_ui.py",
    "android/phone/tests/device/test_assets_files.py",
    "android/phone/tests/snapshot-upload-source-contract-test.py",
    "android/phone/tests/device/test_assets_native_reads.py",
    "android/phone/tests/audio-fixture-source-contract-test.py",
    "android/phone/tests/phone-navigation-native-test.py",
    "android/phone/tests/device/test_snapshot_native_history.py",
    "android/phone/tests/device/test_snapshot_native_review.py",
    "android/phone/tests/device/test_snapshot_native_controls.py",
    "android/phone/tests/device/test_snapshot_export_originals.py",
    "android/phone/tests/device/test_snapshot_readback_jobs.py",
    "android/phone/tests/device/test_snapshot_readback_publication.py",

    "android/phone/tests/device/test_snapshot_destination_owner.py",
    "android/phone/tests/device/test_snapshot_consumer_owner.py",
    "android/phone/tests/phone-snapshot-export-native-test.py",
    "android/phone/tests/phone-snapshot-readback-contract-test.py",
    "android/phone/tests/device/test_create_native_ui.py",
    "android/phone/tests/device/test_create_files.py",
    "android/phone/tests/device/test_create_native_measurements.py",
    "android/phone/tests/device/test_create_texture_state.py",
    "android/phone/tests/device/test_create_native_fixture.py",
    "android/phone/tests/device/test_create_feature.py",
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
    "android/phone/tests/device/test_navigation_foundations.py",
    "android/phone/tests/device/test_snapshots_observer.py",
    "android/phone/tests/device/test_create_collaboration_foundation.py",
    "android/phone/tests/device/test_navigation_scene.py",
    "android/phone/tests/device/test_snapshot_handoff_audit.py",
    "android/phone/tests/device/test_snapshot_system_files.py",
    "android/phone/tests/device/test_snapshots_measurements.py",
    "android/phone/tests/device/test_snapshots_evidence.py",
    "android/phone/tests/device/test_snapshot_upload_bytes.py",
    "android/phone/tests/device/test_snapshot_documents.py",
    "android/phone/tests/device/test_snapshot_documents_ui.py",
    "android/phone/tests/device/test_snapshot_handoff.py",
    "android/phone/tests/device/test_snapshot_handoff_input.py",
    "android/phone/tests/device/test_lifecycle_editor.py",
    "android/phone/tests/device/test_lifecycle_world.py",
    "android/phone/tests/device/test_lifecycle_measurements.py",
    "android/phone/tests/device/test_lifecycle_feature.py",
    "tests/device/self_tests/test_token_chat_ui.py",
    "android/phone/tests/device/test_snapshot_capture_source.py",
    "android/phone/tests/device/test_snapshot_capture_files.py",
    "android/phone/tests/device/test_snapshot_foundation.py",
    "android/phone/tests/device/test_feature_dispatch.py",
    "android/phone/tests/device/test_chat_feature.py",
    "android/phone/tests/device/test_chat_foundation.py",

    "android/phone/tests/device/test_snapshot_os_retirement_source.py",
    "android/phone/tests/device/test_snapshot_documents_native.py",
    "android/phone/tests/device/test_snapshot_documents_access.py",
    "android/phone/tests/device/test_snapshot_documents_os_source.py",
    "android/phone/tests/device/test_snapshot_share_grants_source.py",
    "android/phone/tests/device/test_snapshot_consumer_source.py",
    "android/phone/tests/device/test_snapshot_upload_source.py",
    "android/phone/tests/device/test_assets_backend.py",
    "android/phone/tests/device/test_assets_evidence.py",
    "android/phone/tests/device/test_assets_registration.py",
    "tests/device/self_tests/test_assets_originals.py",
    "android/phone/tests/device/test_assets_uploads.py",
    "android/phone/tests/device/test_assets_controls.py",
    "android/phone/tests/device/test_assets_source.py",
    "android/phone/tests/device/test_audio_source.py",
    "android/phone/tests/device/test_audio_mute.py",
    "android/phone/tests/device/test_audio_feature.py",
    "android/phone/tests/device/test_audio_registration.py",
    "android/phone/tests/device/test_navigation_feature.py",
    "android/phone/tests/device/test_snapshot_source.py",
    "android/phone/tests/device/test_snapshot_controls.py",
    "android/phone/tests/device/test_snapshot_ui.py",
    "android/phone/tests/device/test_snapshot_cancel.py",
    "android/phone/tests/device/test_snapshot_script_history.py",
    "android/phone/tests/device/test_snapshot_measurements.py",
    "android/phone/tests/device/test_snapshot_capture_facts.py",
    "android/phone/tests/device/test_snapshot_settings.py",
    "android/phone/tests/device/test_snapshot_platform.py",
    "android/phone/tests/device/test_snapshot_system_ui.py",
    "android/phone/tests/device/test_snapshot_resolution.py",
    "android/phone/tests/device/test_snapshot_system_context.py",
    "android/phone/tests/device/test_snapshot_script_native.py",
    "android/phone/tests/device/test_snapshot_readback_source.py",
    "android/phone/tests/device/test_snapshot_saved_files.py",
    "android/phone/tests/device/test_create_source.py",
    "android/phone/tests/device/test_create_workflows.py",
    "android/phone/tests/device/test_create_marker.py",
    "android/phone/tests/device/test_create_measurements.py",
    "android/phone/tests/device/test_create_registration.py",
    "tests/device/self_tests/test_create_permissions.py",
    "tests/device/self_tests/test_assets_permissions.py",
    "tests/device/self_tests/test_phone_control_poll.py",
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
    "android/phone/tests/device/test_web_reference.py",
    "android/phone/tests/device/test_world_web_feature.py",
    "android/phone/tests/device/test_world_web_registration.py",
    "android/phone/tests/device/test_tablet_controls.py",
    "android/phone/tests/device/test_tablet_web_feature.py",
    "android/phone/tests/device/test_tablet_web_registration.py",
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
    "android/phone/tests/device/test_emote_replay.py",
    "android/phone/tests/device/test_emote_source_failure.py",
    "android/phone/tests/device/test_emote_failures.py",
    "android/phone/tests/device/test_emote_namespaces.py",
    "android/phone/tests/device/test_emote_originals.py",
    "android/phone/tests/device/test_emote_inputs.py",
    "android/phone/tests/device/test_emote_cleanup.py",
    "android/phone/tests/device/test_emote_run.py",
    "android/phone/tests/device/test_emote_feature.py",
    "android/phone/tests/device/test_emote_journey_registration.py",
    "android/phone/tests/device/test_emote_registration.py",
    "android/phone/tests/device/test_emote_early_cleanup.py",
    "android/phone/tests/device/test_emote_admission_owner.py",
    "android/phone/tests/device/test_emote_admission_retirement.py",
    "android/phone/tests/device/test_emote_effects.py",
    "android/phone/tests/device/test_emote_motion_files.py",
    "android/phone/tests/device/test_emote_role.py",
    "android/phone/tests/device/test_emote_actor.py",
    "android/phone/tests/device/test_emote_retirement.py",
    "android/phone/tests/device/test_emote_unissued_retirement.py",
    "android/phone/tests/device/test_emote_setup_retirement.py",
    "android/phone/tests/device/test_emote_role_failure.py",
    "android/phone/tests/device/test_emote_phase_retirement.py",
    "android/phone/tests/device/test_emote_image_phase_retirement.py",
    "android/phone/tests/device/test_emote_background.py",
    "android/phone/tests/device/test_emote_background_effects.py",
    "android/phone/tests/device/test_emote_lifetime.py",
    "android/phone/tests/device/test_emote_lifetime_failure.py",
    "android/phone/tests/device/test_emote_pixels.py",
    "android/phone/tests/device/test_avatar_people_pixels.py",
    "android/phone/tests/device/test_avatar_people_feature.py",
    "android/phone/tests/device/test_emote_images.py",
    "android/phone/tests/device/test_emote_capture.py",
    "android/phone/tests/device/test_emote_observation.py",
    "android/phone/tests/device/test_emote_incomplete.py",
    "android/phone/tests/device/test_emote_phase_observation.py",
    "android/phone/tests/device/test_emote_scene.py",
    "android/phone/tests/device/test_emote_view.py",
    "android/phone/tests/device/test_script_roots.py",
    "android/phone/tests/device/test_animation_inventory.py",
    "android/phone/tests/device/test_script_work.py",
    "android/phone/tests/device/test_graphics_effects.py",
    "android/phone/tests/device/test_graphics_surface.py",
    "android/phone/tests/device/test_graphics_scene.py",
    "android/phone/tests/device/test_graphics_preferences.py",
    "android/phone/tests/device/test_graphics_background.py",
    "android/phone/tests/device/test_graphics_restart_scope.py",
    "android/phone/tests/device/test_graphics_restart.py",
)
# The complete original-file Emote replay is deliberately registered in this
# same runner as an explicit expensive host composition. Existing mandatory
# profiles/deadlines are unchanged; the extended result is never device proof.
EXTENDED_HOST_CHECKS = (
    "android/phone/tests/device/test_emote_feature_journey.py",
)
CHECKS = DEPENDENCY_LIGHT_CHECKS + PREPARED_HOST_CHECKS + COMMON_HOST_CHECKS + EXTENDED_HOST_CHECKS
parser = argparse.ArgumentParser()
parser.add_argument("--execute", action="store_true",
                    help="execute the Qt/GLM native contracts on the prepared host")
parser.add_argument("--extended", action="store_true",
                    help="also execute expensive complete original-file host compositions; no device acceptance")
args = parser.parse_args()
# Every declared input is required even in dependency-light platform checks.
for name in CHECKS:
    if not (ROOT / name).is_file():
        raise SystemExit("Missing mandatory Phone runtime contract: " + name)
# The installed-candidate/normal UI binding uses only Python host fixtures.
# Keep it mandatory in both modes; prepared contracts retain their existing
# host compiler/Qt prerequisites.
selected = PREPARED_HOST_CHECKS if args.execute else DEPENDENCY_LIGHT_CHECKS
for name in selected + COMMON_HOST_CHECKS + (EXTENDED_HOST_CHECKS if args.extended else ()):
    path = ROOT / name
    if not path.is_file():
        raise SystemExit("Missing mandatory Phone runtime contract: " + name)
    print("Phone runtime contract: " + name, flush=True)
    arguments = [sys.executable, str(path)]
    if name.endswith("phone-test-inventory-test.py"):
        arguments.append(str(ROOT))
    if name.endswith(("phone-chat-native-test.py","phone-chat-peer-native-test.py","phone-chat-history-native-test.py","phone-snapshot-settings-native-test.py")):
        arguments.extend(("--build-dir",str(ROOT / "build" / ("phone-chat-runtime-"+uuid.uuid4().hex))))
    # Assets runs its full common journey, actor and interrupted/idempotent
    # retirement probes. Only this aggregate host budget is larger; source,
    # checkpoint and quiet-window deadlines remain unchanged.
    # The complete Graphics/Create/Chat compositions execute unchanged common
    # journeys; their file/image/actor checks need a larger aggregate budget.
    # Chat measured 139.197s for 20 source/host cases at the parent integration;
    # its aggregate must not inherit the 90s single-component deadline.
    # Per-source freshness and common checkpoint deadlines remain unchanged.
    subprocess.run(arguments, cwd=ROOT, check=True,
                   timeout=10800 if name in EXTENDED_HOST_CHECKS else 600 if name.endswith("test_assets_feature.py") else 180 if name.endswith(("phone-chat-native-test.py","phone-chat-peer-native-test.py","phone-chat-history-native-test.py","phone-snapshot-settings-native-test.py")) else 240 if name.endswith(("test_graphics_feature.py","test_create_feature.py","test_avatar_people_feature.py","test_chat_feature.py")) else 90)
