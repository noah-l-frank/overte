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
    test("chat-erase-restore", "interaction", PYTHON, "pico-chat-erase-restore-test.py", requires=("c++", "pkg-config", "node")),
    test('chat-application-journey', "interaction", PYTHON, "pico-chat-application-close-test.py", 'journey'),
    test('chat-application-recovery', "interaction", PYTHON, "pico-chat-application-close-test.py", 'recovery'),
    test('chat-application-admission', "interaction", PYTHON, "pico-chat-application-close-test.py", 'admission'),
    test('chat-application-delivery', "interaction", PYTHON, "pico-chat-application-close-test.py", 'delivery'),
    test('chat-application-post-ipc', "interaction", PYTHON, "pico-chat-application-close-test.py", 'post-ipc'),
    test('chat-source-seal-positive', "interaction", PYTHON, "pico-chat-application-close-test.py", 'seal-positive'),
    test('chat-source-seal-admission', "interaction", PYTHON, "pico-chat-application-close-test.py", 'seal-admission'),
    test('chat-source-seal-freshness', "interaction", PYTHON, "pico-chat-application-close-test.py", 'seal-freshness'),
    test('chat-cleanup-factory', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cleanup-factory'),
    test('chat-cleanup-witness', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cleanup-witness'),
    test('chat-cleanup-baseline', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cleanup-baseline'),
    test('chat-baseline-composition', "interaction", PYTHON, "pico-chat-application-close-test.py", 'baseline-composition'),
    test('chat-cleanup-consumption', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cleanup-consumption'),
    test('chat-observation-cursor', "interaction", PYTHON, "pico-chat-application-close-test.py", 'observation-cursor'),
    test('chat-cursor-source-seal', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cursor-source-seal'),
    test('chat-cursor-cleanup-consumption', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cursor-cleanup-consumption'),
    test('chat-cursor-archive', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cursor-archive'),
    test('chat-cursor-actor', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cursor-actor'),
    test('chat-cursor-stop', "interaction", PYTHON, "pico-chat-application-close-test.py", 'cursor-stop'),
    test('chat-remote-publication', "interaction", PYTHON, "pico-chat-application-close-test.py", 'remote-publication'),
    test('chat-remote-journey-components', "interaction", PYTHON, "pico-chat-application-close-test.py", 'remote-journey-components'),
    test('chat-remote-cleanup-positive', "interaction", PYTHON, "pico-chat-application-close-test.py", 'remote-cleanup-positive'),
    test('chat-remote-cleanup-failures', "interaction", PYTHON, "pico-chat-application-close-test.py", 'remote-cleanup-failures'),
    test('chat-application-archive', "interaction", PYTHON, "pico-chat-application-close-test.py", 'archive'),
    test("chat-composition", "interaction", PYTHON, "device/test_chat_composition.py"),
    test("chat-cache-release-positive", "interaction", PYTHON, "pico-chat-cache-release-test.py", "positive"),
    test("chat-cache-release-admission", "interaction", PYTHON, "pico-chat-cache-release-test.py", "admission"),
    test("chat-cache-release-quiet", "interaction", PYTHON, "pico-chat-cache-release-test.py", "quiet"),
    test("chat-cache-release-final-clock", "interaction", PYTHON, "pico-chat-cache-release-test.py", "final-clock"),
    test("chat-cache-release-deferred", "interaction", PYTHON, "pico-chat-cache-release-test.py", "deferred"),
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
    test("script-object-lifetimes", "interaction", PYTHON, "pico-script-object-lifetimes-test.py", requires=("c++", "pkg-config", "node")),
    test("tablet-web-owner", "interaction", PYTHON, "pico-tablet-web-owner-test.py"),
    test("tablet-web-journey", "interaction", PYTHON, "pico-tablet-web-journey-test.py"),
    test("tablet-web-actor-retirement", "interaction", PYTHON, "pico-browser-actor-retirement-test.py"),
    test("tablet-web-actor-return", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "return"),
    test("tablet-web-independent-process", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "independent"),
    test("tablet-web-archive-source", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "archive-source"),
    test("tablet-web-evidence-archive", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "evidence-archive"),
    test("tablet-web-host-close-fences", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "host-close-fences"),
    test("tablet-web-independent-journey", "interaction", PYTHON, "pico-browser-actor-retirement-test.py", "--part", "independent-journey"),
    test("tablet-web-capture-retirement", "interaction", PYTHON, "pico-browser-capture-retirement-test.py"),
    test("world-render-retirements", "interaction", PYTHON, "pico-world-render-retirements-test.py", requires=("c++", "pkg-config", "node")),
    test("browser-entry", "interaction", PYTHON, "pico-browser-entry-test.py"),
    test("browser-originals", "webview", PYTHON, "pico-browser-originals-test.py", requires=("c++", "pkg-config", "javac", "java", "node")),
    test("world-web-ray", "webview", PYTHON, "device/test_world_web_ray.py", requires=("c++", "pkg-config")),
    test("world-current-input-native", "webview", PYTHON, "device/test_world_current_input_native.py", requires=("c++", "pkg-config", "javac", "java", "unshare")),
    test("world-current-input-java", "webview", PYTHON, "device/test_world_current_input_java.py", requires=("javac", "java")),
    test("world-current-input-reader", "webview", PYTHON, "device/test_world_current_input_reader.py"),
    test("world-current-focus-parent", "webview", PYTHON, "device/test_world_current_focus_parent.py"),
    test("world-current-document-native", "webview", PYTHON, "device/test_world_current_document_native.py", requires=("c++", "pkg-config", "javac", "java", "unshare")),
    test("world-current-document-java", "webview", PYTHON, "device/test_world_current_document_java.py", requires=("javac", "java")),
    test("world-current-document-reader", "webview", PYTHON, "device/test_world_current_document_reader.py"),
    test("world-web-retained-resume-source", "webview", PYTHON, "device/test_world_web_resume_native.py", requires=("c++", "pkg-config", "javac", "java", "unshare")),
    test("world-web-stereo-join", "webview", PYTHON, "device/test_world_web_stereo_join.py"),
    test("world-web-source-process", "webview", PYTHON, "device/test_world_web_source_process.py"),
    test("world-web-actor-publication", "webview", PYTHON, "device/test_world_web_actor_publication.py"),
    test("world-web-normal-close", "webview", PYTHON, "device/test_world_web_normal_close.py"),
    test("world-web-recovery-prefix", "webview", PYTHON, "device/test_world_web_recovery_prefix.py"),
    test("world-web-navigation-prefix", "webview", PYTHON, "device/test_world_web_navigation_prefix.py"),
    test("world-web-prefix", "webview", PYTHON, "device/test_world_web_prefix.py"),
    test("world-web-stereo", "webview", PYTHON, "device/test_world_web_stereo.py"),
    test("lifecycle-pending-progress", "interaction", PYTHON, "pico-lifecycle-pending-test.py", "progress"),
    test("lifecycle-pending-failure", "interaction", PYTHON, "pico-lifecycle-pending-test.py", "failure"),
    test("lifecycle-pending-originals", "interaction", PYTHON, "pico-lifecycle-pending-test.py", "originals"),
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
    test("snapshot-save-owner", "interaction", PYTHON, "device/test_snapshot_save_owner.py", "SnapshotSaveFlowTests.test_normal_cancel_still_save_independent_provider_png_and_current_original_quiet"),
    test("snapshot-save-fences", "interaction", PYTHON, "device/test_snapshot_save_owner.py", "SnapshotSaveAdmissionTests", "SnapshotSaveEnvelopeTests", "SnapshotSaveFenceTests", "SnapshotSaveFactoryTests", "SnapshotSaveOriginalsTests", "SnapshotSavePreparationRecoveryTests", "SnapshotSaveAcquisitionTests", "SnapshotOriginalFrameMemoTests", "SnapshotSavePublicationTests", "SnapshotSyntheticAnalyzerTests", "SnapshotSystemSourceTests"),
    test("snapshot-settings-originals", "interaction", PYTHON, "device/test_snapshot_settings_originals.py"),
    test("snapshot-reply-grammar", "interaction", PYTHON, "device/test_snapshot_reply_grammar_owner.py"),
    test("snapshot-settings-baseline", "interaction", PYTHON, "device/test_snapshot_settings_baseline.py"),
    test("snapshot-settings-close", "interaction", PYTHON, "device/test_snapshot_settings_close.py"),
    test("navigation-environment-originals", "interaction", PYTHON, "device/test_navigation_environment.py", requires=("c++", "pkg-config")),
    test("navigation-bookmark-prefix", "interaction", PYTHON, "device/test_navigation_bookmark_prefix.py", requires=("openssl",)),
    test("navigation-dismissal-prefix", "interaction", PYTHON, "device/test_navigation_dismissal_prefix.py", requires=("openssl",)),
    test("navigation-missing-prefix", "interaction", PYTHON, "device/test_navigation_missing_prefix.py", requires=("openssl",)),
    test("navigation-transit-prefix", "interaction", PYTHON, "device/test_navigation_transit_prefix.py", requires=("openssl",)),
    test("navigation-normal-prefix", "interaction", PYTHON, "device/test_navigation_prefix.py", requires=("openssl",)),
    test("snapshot-close-statuses", "interaction", PYTHON, "device/test_snapshot_close_statuses.py"),
    test("snapshot-close-owner", "interaction", PYTHON, "device/test_snapshot_close_owner.py"),
    test("snapshot-close-recovery", "interaction", PYTHON, "device/test_snapshot_close_recovery.py"),
    test("snapshot-close-fences", "interaction", PYTHON, "device/test_snapshot_close_fences.py"),
    test("snapshot-return-image", "interaction", PYTHON, "device/test_snapshot_return_image.py"),
    test("snapshot-return-fences", "interaction", PYTHON, "device/test_snapshot_return_fences.py"),
    test("snapshot-background-owner", "interaction", PYTHON, "device/test_snapshot_background_owner.py"),
    test("snapshot-background-fences", "interaction", PYTHON, "device/test_snapshot_background_fences.py"),
    test("snapshot-upload-owner", "interaction", PYTHON, "device/test_snapshot_upload_owner.py", requires=("openssl",)),
    test("snapshot-upload-fences", "interaction", PYTHON, "device/test_snapshot_upload_fences.py"),
    test("snapshot-upload-tls", "interaction", PYTHON, "device/test_snapshot_upload_tls.py", requires=("openssl",)),
    test("snapshot-upload-originals", "interaction", PYTHON, "device/test_snapshot_upload_source.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-export-originals", "interaction", PYTHON, "device/test_snapshot_exports.py", requires=("node", "javac", "java", "c++", "pkg-config")),
    test("snapshot-cancel-still-owner", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotStillSequenceTests.test_continuous_normal_cancel_then_still_original_png_fd_ui_and_live_work_quiet"),
    test("snapshot-still-recovery", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotStillSequenceTests.test_v1_original_migration_and_lost_still_reply_recover_without_new_capture_or_baseline_facts"),
    test("snapshot-still-no-output", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotStillSequenceTests.test_acknowledged_ignored_still_never_creates_original_png_or_allows_cold_resend"),
    test("snapshot-still-fences", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotStillSequenceTests.test_final_still_parent_cas_phase_advance_refuses_actual_second_capture"),
    test("snapshot-still-originals", "interaction", PYTHON, "device/test_snapshot_cancel_originals.py"),
    test("snapshot-normal-cancel-owner", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotCancelOwnerTests.test_normal_open_plan_name_capture_cancel_pinned_vm_and_three_second_original_quiet"),
    test("snapshot-cancel-quiet", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotCancelOwnerTests.test_late_unowned_file_prevents_quiet_and_cold_archived_clock_gap_is_rejected"),
    test("snapshot-cancel-recovery", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotCancelOwnerTests.test_actual_lost_reply_recovery_queries_original_job_without_second_capture_or_cancel", "SnapshotCancelOwnerTests.test_uncertain_undelivered_start_never_resends_or_fabricates_an_original_job", "SnapshotCancelOwnerTests.test_original_armed_source_recovers_after_lost_reply_without_second_arm", "SnapshotCancelOwnerTests.test_original_completed_open_recovers_readonly_after_child_return_loss"),
    test("snapshot-cancel-fences", "interaction", PYTHON, "device/test_snapshot_cancel_owner.py", "SnapshotCancelOwnerTests.test_final_parent_cas_phase_change_blocks_actual_local_capture_writer", "SnapshotCancelOwnerTests.test_slow_final_cas_with_frozen_device_clock_blocks_actual_local_capture", "SnapshotCancelOwnerTests.test_foreign_vm_or_reviewed_source_cannot_qualify_capture_cancel", "SnapshotCancelOwnerTests.test_orphan_original_file_journal_blocks_base_cleanup_and_public_input", "SnapshotCancelOwnerTests.test_last_original_guard_phase_change_refuses_input_and_controller_publish_is_host_only", "SnapshotCancelOwnerTests.test_fresh_original_retained_timer_cannot_hide_behind_historical_cancelled_timer_absence", "CancelOwnerGuardTests"),
    test("snapshot-capture-file-owner", "interaction", PYTHON, "device/test_snapshot_capture_owner.py"),
    test("snapshot-file-originals", "interaction", PYTHON, "device/test_snapshot_capture_files.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-fast-cancel", "interaction", PYTHON, "device/test_snapshot_cancel.py", requires=("c++", "pkg-config")),
    test("snapshot-review-originals", "interaction", PYTHON, "device/test_snapshot_review.py", requires=("c++", "pkg-config")),
    test("snapshot-script-originals", "interaction", PYTHON, "device/test_snapshot_script_originals.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-native-originals", "interaction", PYTHON, "device/test_snapshot_originals.py", requires=("node", "c++", "pkg-config")),
    test("snapshot-normal-still-owner", "interaction", PYTHON, "device/test_snapshot_still_owner.py"),
    test("openxr-loader", "openxr", PYTHON, "pico-openxr-loader-test.py"),
    test("openxr-input", "openxr", PYTHON, "pico-openxr-input-test.py"),
    test("openxr-display", "openxr", PYTHON, "pico-openxr-display-test.py"),
    test("stereo-world-render", "openxr", PYTHON, "device/test_stereo_world_render.py"),
    test("graphics-sources", "interaction", PYTHON, "device/test_graphics_sources.py", "GraphicsSubjectTests", "VrGraphicsSubjectTests", "SceneLoadTests", "TabletHttpTests", "WebRuntimeTests", "WebRendererTests", "OwnedWorldRenderTests", "WorldRenderReceiptTests", "WorldReceiptInventoryTests"),
    test("graphics-scene-owners", "interaction", PYTHON, "device/test_graphics_sources.py", "PicoGraphicsSourceTests", "PicoGraphicsSurfaceTests", "PicoGraphicsSceneTests", "PicoGraphicsPreferenceTests"),
    test("graphics-lifecycle-owners", "interaction", PYTHON, "device/test_graphics_sources.py", "PicoGraphicsBackgroundTests", "PicoGraphicsLifecycleBindingTests", "PicoGraphicsRestartFrameworkTests", "PicoGraphicsRestartTests", "PicoGraphicsLifetimeTests"),
    test("graphics-feature-flow", "interaction", PYTHON, "device/test_graphics_sources.py", "PicoGraphicsFeatureTests", "PicoGraphicsConfigurationTests", "PicoGraphicsPublicBindingTests", "PicoFeatureObserverTests", "PicoGraphicsCompositionTests", "PicoGraphicsSurfaceSceneTests", "PicoGraphicsCaptureTests"),
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
    test("lifecycle-world-codec", "interaction", PYTHON, "device/test_lifecycle_world_codec.py"),
    test("lifecycle-close-owner", "interaction", PYTHON, "device/test_lifecycle_close_owner.py"),
    test("lifecycle-restore-owner", "interaction", PYTHON, "device/test_lifecycle_restore_owner.py"),
    test("lifecycle-primary-observation", "interaction", PYTHON, "device/test_lifecycle_observation.py"),
    test("lifecycle-process-v2", "interaction", PYTHON, "device/test_lifecycle_process_v2.py"),
    test("lifecycle-process-finalization", "interaction", PYTHON, "device/test_lifecycle_process_finalization.py"),
    test("avatar-people-native-ui", "interaction", PYTHON, "device/test_avatar_people_controls_native.py", requires=("c++", "pkg-config", "node")),
    test("avatar-state-native", "interaction", PYTHON, "device/test_avatar_state_native.py", requires=("c++", "pkg-config")),
    test('avatar-urls-owner', "interaction", PYTHON, "device/test_avatar_urls_owner.py",
        'AvatarUrlsTests.test_normal_paging_url_failure_original_restore_and_retained_owner',
        'AvatarUrlsTests.test_preferences_baseline_waits_for_real_agreement_and_preserves_each_original_leaf',
        'AvatarUrlsTests.test_missing_original_preferences_never_creates_a_default_baseline_or_sends_input'),
    test('avatar-urls-recovery', "interaction", PYTHON, "device/test_avatar_urls_owner.py",
        'AvatarUrlsTests.test_legacy_pending_owner_is_read_only_reconciled_without_new_preference_baseline',
        'AvatarUrlsTests.test_lost_confirm_is_only_observed_after_cold_reconstruction',
        'AvatarUrlsTests.test_lost_final_delivery_cold_reconcile_never_replays_and_copy_age_is_checked'),
    test('avatar-urls-fences', "interaction", PYTHON, "device/test_avatar_urls_owner.py",
        'AvatarUrlsTests.test_version_two_retains_strict_scale_without_favorite_admission',
        'AvatarUrlsTests.test_foreign_original_leaf_binding_refuses_cold_reconstruction_and_preserves_owner',
        'AvatarUrlsTests.test_last_original_guard_phase_advance_or_frozen_clock_prevents_writer',
        'AvatarUrlsTests.test_wrong_geometry_resource_generation_or_scale_cannot_supply_a_model_effect',
        'AvatarUrlsTests.test_cold_reconstruction_rejects_forged_quiet_flags_and_preserves_original_bytes',
        'AvatarUrlsTests.test_changed_original_preferences_or_unowned_storage_never_admit_normal_input',
        'AvatarUrlsTests.test_preference_acquisition_phase_advance_or_host_age_prevents_first_input',
        'AvatarUrlsTests.test_leaf_written_before_lost_first_root_cas_stays_owned_without_input',
        'AvatarUrlsTests.test_warm_leaf_delete_replace_or_change_at_last_native_guard_prevents_input'),
    test('avatar-urls-cleanup', "interaction", PYTHON, "device/test_avatar_urls_owner.py",
        'AvatarUrlsTests.test_owned_uri_is_normally_restored_after_uncertain_input_but_foreign_uri_is_preserved',
        'AvatarUrlsTests.test_ack_without_load_stays_pending_and_cleanup_retains_uncertain_ticket'),
    test('avatar-favorites-owner', "interaction", PYTHON, "device/test_avatar_favorites_owner.py",
        'AvatarFavoritesTests.test_normal_save_scale_missing_choose_restore_delete_remains_owned'),
    test('avatar-favorites-fences', "interaction", PYTHON, "device/test_avatar_favorites_owner.py",
        'AvatarFavoritesTests.test_lost_original_scale_confirm_reconciles_without_resend',
        'AvatarFavoritesTests.test_phase_advance_at_final_native_guard_prevents_favorite_input',
        'AvatarFavoritesTests.test_foreign_preferences_before_scale_cannot_be_adopted_by_url_effect_proof',
        'AvatarFavoritesTests.test_nonempty_persisted_entity_size_refuses_even_with_empty_live_handles',
        'AvatarFavoritesTests.test_unowned_avatar_data_refuses_before_any_normal_favorite_input'),
    test('assets-upload-native', "interaction", PYTHON, "device/test_assets_upload_originals_native.py", requires=("c++", "pkg-config")),
    test('assets-cancel-cache-fences', "interaction", PYTHON, "device/test_assets_cancel_owner.py",
        'AssetsCancelOwnerTests.test_changed_file_budget_behind_cached_journal_refuses_first_pointer',
        'AssetsCancelOwnerTests.test_json_equivalent_previous_tuple_behind_cached_journal_refuses_first_pointer',
        'AssetsCancelOwnerTests.test_equal_replacement_of_admitted_validation_cache_refuses_first_pointer', requires=("c++", "pkg-config", "unshare")),
    test('assets-cancel-reopen', "interaction", PYTHON, "device/test_assets_cancel_owner.py",
        'AssetsCancelOwnerTests.test_next_stage_reopens_after_original_cancel_without_adopting_retired_browser',
        'AssetsCancelOwnerTests.test_next_stage_with_live_original_consumers_refuses_before_staging_or_pointer',
        'AssetsCancelOwnerTests.test_next_stage_lost_first_open_reply_never_adopts_retired_or_new_browser',
        'AssetsCancelOwnerTests.test_retained_stage1_lost_cancel_then_stage2_lost_open_never_adopts_or_releases', requires=("c++", "pkg-config", "unshare")),
    test('assets-cancel-owner', "interaction", PYTHON, "device/test_assets_cancel_owner.py",
        'AssetsCancelOwnerTests.test_normal_cancel_exact_files_originals_and_retained_contexts',
        'AssetsCancelOwnerTests.test_lost_cancel_reply_cold_reconcile_never_replays_original_input',
        'AssetsCancelOwnerTests.test_undelivered_cancel_is_retained_with_live_consumers_and_original_bytes',
        'AssetsCancelOwnerTests.test_lost_navigation_reply_uses_admitted_originals_and_distinct_cancel',
        'AssetsCancelOwnerTests.test_lost_first_open_reply_cancel_retains_files_without_adoption',
        'AssetsCancelOwnerTests.test_final_owner_cas_age_refuses_open_result_and_keeps_exact_inputs',
        'AssetsCancelOwnerTests.test_final_original_native_guard_phase_advance_prevents_first_pointer', requires=("c++", "pkg-config", "unshare")),
    test('assets-cancel-recovery', "interaction", PYTHON, "device/test_assets_cancel_owner.py",
        'AssetsCancelOwnerTests.test_undelivered_navigation_cancel_preserves_unsent_original',
        'AssetsCancelOwnerTests.test_lost_navigation_and_cancel_replies_cold_reconcile_keeps_both_originals', requires=("c++", "pkg-config", "unshare")),
    test('assets-cancel-file-recovery', "interaction", PYTHON, "device/test_assets_cancel_owner.py",
        'AssetsCancelOwnerTests.test_lost_file_release_reply_after_normal_cancel_reconciles_without_resend',
        'AssetsCancelOwnerTests.test_undelivered_file_release_after_normal_cancel_keeps_exact_files_without_resend',
        'AssetsCancelOwnerTests.test_original_unavailable_primary_error_then_normal_cancel_retires_companions',
        'AssetsCancelOwnerTests.test_lost_primary_retirement_reply_reconciles_before_original_error_and_cancel', requires=("c++", "pkg-config", "unshare")),
    test('assets-page-home', "interaction", PYTHON, "device/test_assets_page_home.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-home-owner', "interaction", PYTHON, "device/test_assets_home_owner.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-server-state', "interaction", PYTHON, "device/test_assets_server_state.py", requires=("c++", "pkg-config")),
    test('assets-mapping-pair', "interaction", PYTHON, "device/test_assets_mapping_pair.py", requires=("c++", "pkg-config")),
    test('assets-cancel-effects', "interaction", PYTHON, "device/test_assets_cancel_effects.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-mapping-model', "interaction", PYTHON, "device/test_assets_mapping_model.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-entity-effect', "interaction", PYTHON, "device/test_assets_entity_effect.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-entity-resources', "interaction", PYTHON, "device/test_assets_entity_resources.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-request-lifetimes', "interaction", PYTHON, "device/test_assets_request_lifetimes.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-resource-manager', "interaction", PYTHON, "device/test_assets_resource_manager.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-resource-data', "interaction", PYTHON, "device/test_assets_resource_data.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-geometry-parser', "interaction", PYTHON, "device/test_assets_geometry_parser.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-geometry-resource', "interaction", PYTHON, "device/test_assets_geometry_resource.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-model-cache', "interaction", PYTHON, "device/test_assets_model_cache.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-model-baker', "interaction", PYTHON, "device/test_assets_model_baker.py", requires=("c++", "pkg-config", "unshare")),
    test('assets-read-native', "interaction", PYTHON, "device/test_assets_read_native.py", requires=("c++", "pkg-config")),
    test('assets-read-job', "interaction", PYTHON, "device/test_assets_read_job_native.py", requires=("c++", "pkg-config")),
    test('assets-backend-source', "interaction", PYTHON, "device/test_assets_source.py", requires=("c++", "pkg-config")),
    test('assets-read-probe', "interaction", "node", "device/assets-read-probe-test.js", requires=("node",)),
    test('assets-native-files', "interaction", PYTHON, "device/test_assets_files_native.py", requires=("c++", "pkg-config")),
    test('assets-file-owner', "interaction", PYTHON, "device/test_assets_file_owner.py", requires=("c++", "pkg-config")),
    test('assets-native-ui', "interaction", PYTHON, "device/test_assets_native_ui.py", requires=("c++", "pkg-config")),
    test('assets-controls', "interaction", PYTHON, "device/test_assets_controls.py"),
    test("normal-create", "interaction", PYTHON, "device/test_normal_create.py"),
    test("create-file-ui", "interaction", PYTHON, "device/test_create_file_ui.py"),
    test("create-file-native-ui", "interaction", PYTHON, "device/test_create_file_ui_native.py", requires=("c++", "pkg-config")),
    test("create-original-files", "interaction", PYTHON, "device/test_create_files_native.py", requires=("c++", "pkg-config")),
    test("create-callback-native", "interaction", PYTHON, "device/test_create_callbacks_native.py", requires=("c++", "pkg-config")),
    test("create-browse-setting", "interaction", PYTHON, "device/test_create_browse_setting.py"),
    test("create-browse-setting-native", "interaction", PYTHON, "device/test_create_browse_setting_native.py", requires=("c++", "pkg-config")),
    test("create-rez-permissions", "interaction", PYTHON, "device/test_create_rez_permissions.py"),
    test("create-rez-owner", "interaction", PYTHON, "device/test_create_rez_owner.py"),
    test("create-recovery-flow", "interaction", PYTHON, "device/test_create_recovery_flow.py"),
    test("create-recovery-guards", "interaction", PYTHON, "device/test_create_recovery_guards.py"),
    test("create-recovery-native", "interaction", PYTHON, "device/test_create_recovery_native.py", requires=("c++", "pkg-config")),
    test("create-native-budget-owner", "interaction", PYTHON, "device/test_create_budget_owner.py"),
    test("create-voxel-owner", "interaction", PYTHON, "device/test_create_voxel_owner_flow.py"),
    test("create-voxel-guards", "interaction", PYTHON, "device/test_create_voxel_owner_guards.py"),
    test("create-primitives-owner", "interaction", PYTHON, "device/test_create_primitives_owner.py"),
    test("create-polyvox-native-ui", "interaction", PYTHON, "device/test_create_polyvox_controls_native.py", requires=("c++", "pkg-config", "node")),
    test("create-voxel-source-native", "interaction", PYTHON, "device/test_create_voxel_source_native.py", requires=("c++", "pkg-config", "unshare", "ninja")),
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
