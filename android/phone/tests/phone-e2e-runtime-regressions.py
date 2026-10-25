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
    "android/phone/tests/phone-feature-build-flag-test.py",
    "android/phone/tests/device/test_snapshot_documents_journey_boundary.py",
    "android/phone/tests/device/test_snapshot_documents_acquisition_lease.py",
    "android/phone/tests/device/test_snapshot_cancel_followfloor_audit.py",
    "android/phone/tests/device/test_snapshot_handoff_audit_native.py",
    "android/phone/tests/device/test_snapshot_private_publication.py",
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
    "android/phone/tests/device/test_create_marker_refresh.py",
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
    "android/phone/tests/device/test_snapshots_registration.py",
    "android/phone/tests/device/test_snapshots_role.py",
    "android/phone/tests/device/test_snapshots_marker_phase.py",
    "android/phone/tests/device/test_snapshots_retirement_audit.py",
    "android/phone/tests/device/test_snapshots_retirement_actor_versions.py",
    "android/phone/tests/device/test_snapshot_retired_inspections.py",
    "android/phone/tests/device/test_snapshots_publication_guard.py",
    "android/phone/tests/device/test_snapshots_storage_intent.py",
    "android/phone/tests/device/test_snapshots_distinct.py",
    "android/phone/tests/device/test_snapshots_ephemeral_role_disposal.py",
    "android/phone/tests/device/test_snapshots_constructor_history_pass.py",
    "android/phone/tests/device/test_snapshots_passive_constructor_history.py",
    "android/phone/tests/device/test_snapshots_read_ready_slot.py",
    "android/phone/tests/device/test_snapshots_closing_cancel_history.py",
    "android/phone/tests/device/test_snapshots_active_cancel_history.py",
    "android/phone/tests/device/test_snapshots_actor_maintenance.py",
    "android/phone/tests/device/test_snapshots_actor_history.py",
    "android/phone/tests/device/test_snapshots_input_replay_guard.py",
    "android/phone/tests/device/test_snapshots_locked_slot_rebuild.py",
    "android/phone/tests/device/test_snapshots_cleanup_constructor_scope.py",
    "android/phone/tests/device/test_snapshots_historical_png.py",
    "android/phone/tests/device/test_snapshots_original_clone.py",
    "android/phone/tests/device/test_snapshot_catalog_pass.py",
    "android/phone/tests/device/test_snapshots_full_retirement_audit.py",
    "android/phone/tests/device/test_snapshots_actor.py",
    "android/phone/tests/device/test_snapshots_actor_schedule_migration.py",
    "android/phone/tests/device/test_snapshots_actor_primary_cue.py",
    "android/phone/tests/device/test_snapshots_actor_ordinary_stages.py",
    "android/phone/tests/device/test_snapshots_cleanup_close_race.py",
    "android/phone/tests/device/test_snapshots_actor_schedule.py",
    "android/phone/tests/device/test_snapshots_polling.py",
    "android/phone/tests/device/test_snapshots_feature_journey.py",
    "android/phone/tests/device/test_snapshots_resident_actor.py",
    "android/phone/tests/device/test_snapshots_partial_read_resume.py",
    "android/phone/tests/device/test_snapshots_phase_transition.py",
    "android/phone/tests/device/test_snapshots_primary_cleanup_stages.py",
    "android/phone/tests/device/test_snapshots_history_pass.py",
    "android/phone/tests/device/test_snapshots_primary_history_pass.py",
    "android/phone/tests/device/test_snapshots_quiet_role_reuse.py",
    "android/phone/tests/device/test_snapshot_handoff_admission_audit.py",
    "android/phone/tests/device/test_navigation_foundations.py",
    "android/phone/tests/device/test_snapshots_observer.py",
    "android/phone/tests/device/test_create_collaboration_foundation.py",
    "android/phone/tests/device/test_navigation_scene.py",
    "android/phone/tests/device/test_snapshot_handoff_audit.py",
    "android/phone/tests/device/test_snapshot_system_files.py",
    "android/phone/tests/device/test_snapshots_measurements.py",
    "android/phone/tests/device/test_snapshots_feature.py",
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
    "android/phone/tests/device/test_snapshot_scope_status_boundary.py",
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

# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
import os
import re
import signal
import tempfile
import time
import xml.etree.ElementTree as ET

from phone_runtime_groups import (JOBS, GroupError, file_timeout, group_timeout,
                                 select_groups, validate_groups)

REGISTRY_PATH = Path(__file__).with_name('phone-runtime-groups.json')


def load_registry(path=REGISTRY_PATH):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise GroupError('Duplicate Phone registry key')
            value[key] = item
        return value
    registry = json.loads(Path(path).read_text(), object_pairs_hook=unique)
    return validate_groups(registry, DEPENDENCY_LIGHT_CHECKS, PREPARED_HOST_CHECKS,
                           COMMON_HOST_CHECKS, EXTENDED_HOST_CHECKS)


def file_command(name, *, root=ROOT, python=sys.executable, build_id=None):
    if name not in CHECKS:
        raise GroupError('Unknown Phone contract command')
    root = Path(root)
    arguments = [python, str(root / name)]
    if name.endswith('phone-test-inventory-test.py'):
        arguments.append(str(root))
    if name.endswith(('phone-chat-native-test.py', 'phone-chat-peer-native-test.py',
                      'phone-chat-history-native-test.py', 'phone-snapshot-settings-native-test.py')):
        build_id = uuid.uuid4().hex if build_id is None else build_id
        if type(build_id) is not str or re.fullmatch('[0-9a-f]{32}', build_id) is None:
            raise GroupError('Invalid Phone native build namespace')
        arguments.extend(('--build-dir', str(root / 'build' / ('phone-chat-runtime-' + build_id))))
    return arguments


def supervisor():
    # Reuse the reviewed main-thread process-group and adopted-child lifecycle.
    path = ROOT / 'tests/run-unittest-suite.py'
    spec = importlib.util.spec_from_file_location('_phone_host_process_supervisor', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def event(root, row):
    row = dict(schemaVersion=1, monotonicNs=time.monotonic_ns(), **row)
    raw = json.dumps(row, sort_keys=True)
    with os.fdopen(os.open(root / 'events.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600), 'a') as output:
        output.write(raw + '\n')
        output.flush()
    print('PHONE_HOST_EVENT ' + raw, flush=True)


def reports(root, groups, records, jobs, interrupted, cleanup_error):
    public_rows = [{key: value for key, value in record.items()
                    if key in {'file', 'groupId', 'timeoutSeconds', 'status', 'returncode',
                               'durationSeconds', 'outputBytes', 'outputSha256'}} for record in records]
    successful = (not interrupted and not cleanup_error and len(public_rows) == sum(len(row['files']) for row in groups)
                  and all(row.get('status') == 'passed' for row in public_rows))
    by_file = {row['file']: row for row in public_rows}
    group_rows = []
    for group in groups:
        rows = [by_file[name] for name in group['files']]
        group_rows.append({'id': group['id'], 'files': group['files'],
                           'timeoutSeconds': group_timeout(group['files'], jobs),
                           'status': 'passed' if successful or all(row['status'] == 'passed' for row in rows)
                           and not cleanup_error and not interrupted else 'failed',
                           'results': rows})
    document = {'schemaVersion': 1, 'scope': 'HOST_CONTRACTS_NOT_DEVICE_ACCEPTANCE',
                'jobs': jobs, 'status': 'passed' if successful else 'failed',
                'interrupted': interrupted, 'cleanupError': cleanup_error,
                'selectedFiles': len(records), 'completedFiles': sum(row['status'] in ('passed', 'failed') for row in public_rows),
                'groups': group_rows, 'results': public_rows}
    atomic_json(root / 'summary.json', document)
    suite = ET.Element('testsuite', name='phone-host-runtime', tests=str(len(records) + bool(cleanup_error)),
                       errors=str(sum(row['status'] != 'passed' for row in public_rows) + bool(cleanup_error)),
                       failures='0', skipped='0')
    for row in public_rows:
        case = ET.SubElement(suite, 'testcase', classname='phone-host.' + row['groupId'],
                             name=row['file'], time=str(row.get('durationSeconds', 0)))
        if row['status'] != 'passed':
            ET.SubElement(case, 'error', message='PHONE_HOST_CONTRACT_NOT_PASSED').text = row['status']
    if cleanup_error:
        cleanup = ET.SubElement(suite, 'testcase', classname='phone-host.supervisor', name='owned-process-cleanup')
        ET.SubElement(cleanup, 'error', message='PHONE_HOST_OWNED_PROCESS_CLEANUP_FAILED')
    with os.fdopen(os.open(root / 'junit.xml', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
        output.write(ET.tostring(suite, encoding='utf-8', xml_declaration=True))
    return document


def run_groups(groups, *, jobs=JOBS, output_dir=None, mode='default'):
    """One main-thread owner; each original file runs in its own process group."""
    if type(jobs) is not int or not 1 <= jobs <= JOBS:
        raise GroupError('Phone jobs must be from1 through4')
    if (not sys.platform.startswith('linux') or len(list(Path('/proc/self/task').iterdir())) != 1
            or Path('/proc/self/task/' + str(os.getpid()) + '/children').read_text().strip()):
        raise GroupError('Phone process owner requires one thread and no existing children')
    owner = supervisor()
    root = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix='overte-phone-host-'))
    if output_dir:
        if not root.is_absolute() or root.resolve(strict=False) != root or root.exists():
            raise GroupError('Phone output directory must be new, absolute and free of aliases')
        root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    records = [{'file': name, 'groupId': group['id'], 'timeoutSeconds': file_timeout(name), 'status': 'not-run'}
               for group in groups for name in group['files']]
    if not records or len({row['file'] for row in records}) != len(records):
        raise GroupError('Phone execution selection must be nonempty and unique')
    atomic_json(root / 'selection.json', {'schemaVersion': 1, 'mode': mode, 'jobs': jobs,
                                        'scope': 'HOST_CONTRACTS_NOT_DEVICE_ACCEPTANCE', 'groups': groups})
    active, previous_handlers = [], {}
    previous_subreaper = owner.subreaper(1)
    interrupted = 0
    cleanup_error = False
    pending = 0
    def cancel(signum, _frame):
        raise owner.TerminationRequested(signum)
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, cancel)
        try:
            while active or pending < len(records):
                while pending < len(records) and len(active) < jobs:
                    record = records[pending]
                    record['log'] = root / ('file-' + str(pending + 1).zfill(4) + '.log')
                    pending += 1
                    mask = signal.pthread_sigmask(signal.SIG_BLOCK, previous_handlers)
                    try:
                        with os.fdopen(os.open(record['log'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
                            record['process'] = subprocess.Popen(file_command(record['file']), cwd=ROOT,
                                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                        record['started'] = time.monotonic()
                        record['status'] = 'running'
                        active.append(record)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    event(root, {'event': 'begin', 'groupId': record['groupId'], 'file': record['file'],
                                 'timeoutSeconds': record['timeoutSeconds']})
                for record in active[:]:
                    process = record['process']
                    timed_out = process.poll() is None and time.monotonic() - record['started'] >= record['timeoutSeconds']
                    if process.poll() is None and not timed_out:
                        continue
                    owner.stop_worker(process)
                    record['returncode'] = process.returncode
                    record['durationSeconds'] = round(time.monotonic() - record['started'], 6)
                    record['status'] = 'timeout' if timed_out else 'passed' if process.returncode == 0 else 'failed'
                    raw = record['log'].read_bytes()
                    record.update(outputBytes=len(raw), outputSha256=hashlib.sha256(raw).hexdigest())
                    event(root, {'event': 'end', 'groupId': record['groupId'], 'file': record['file'],
                                 'timeoutSeconds': record['timeoutSeconds'], 'durationSeconds': record['durationSeconds'],
                                 'returncode': record['returncode'], 'status': record['status']})
                    if record['status'] != 'passed':
                        print(record['log'].read_text(errors='replace'), file=sys.stderr, flush=True)
                    active.remove(record)
                if active:
                    time.sleep(.02)
        except owner.TerminationRequested as error:
            interrupted = error.signum
        except BaseException:
            cleanup_error = True
            raise
        finally:
            # No adopted-child reap while any scheduled worker may still run.
            for signum in previous_handlers:
                signal.signal(signum, signal.SIG_IGN)
            for record in active:
                try:
                    owner.stop_worker(record['process'])
                except BaseException:
                    cleanup_error = True
                record['status'] = 'cancelled'
                record['returncode'] = record['process'].returncode
                record['durationSeconds'] = round(time.monotonic() - record['started'], 6)
                event(root, {'event': 'end', 'groupId': record['groupId'], 'file': record['file'],
                             'durationSeconds': record['durationSeconds'], 'returncode': record['returncode'],
                             'status': 'cancelled'})
            try:
                owner.reap_adopted_children()
            except BaseException:
                cleanup_error = True
            document = reports(root, groups, records, jobs, interrupted, cleanup_error)
            print(json.dumps({'scope': document['scope'], 'status': document['status'],
                              'selectedFiles': len(records), 'outputDirectory': str(root)}, sort_keys=True), flush=True)
    finally:
        try:
            owner.subreaper(previous_subreaper)
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
    return 128 + interrupted if interrupted else 0 if document['status'] == 'passed' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--execute', action='store_true', help='select all original prepared and common contracts')
    parser.add_argument('--extended', action='store_true', help='also select the original expensive Emote host composition')
    parser.add_argument('--list-groups', action='store_true', help='emit validated metadata without executing host commands')
    parser.add_argument('--group', action='append', dest='groups', help='select a registered group; repeat for distinct groups')
    parser.add_argument('--jobs', type=int, default=JOBS, help='isolated contract processes, from1 through4 (default4)')
    parser.add_argument('--output-dir', type=Path, help='new absolute private log/JSON/JUnit directory')
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= JOBS:
        parser.error('--jobs must be from1 through4')
    try:
        registry = validate_groups(load_registry(), DEPENDENCY_LIGHT_CHECKS, PREPARED_HOST_CHECKS,
                                   COMMON_HOST_CHECKS, EXTENDED_HOST_CHECKS)
        # Preserve original admission: all242 declared contract files must exist,
        # even in default dependency-light mode or a selected subgroup.
        for name in CHECKS:
            path = ROOT / name
            if not path.is_file() or path.is_symlink() or path.resolve() != path:
                raise GroupError('Missing or aliased mandatory Phone runtime contract: ' + name)
        groups = select_groups(registry, execute=args.execute, extended=args.extended, selected_ids=args.groups)
        if args.list_groups:
            print(json.dumps({'schemaVersion': 1, 'mode': 'execute' if args.execute else 'default',
                              'jobs': args.jobs, 'groups': [dict(row, timeoutSeconds=group_timeout(row['files'], args.jobs))
                                                         for row in groups]}, sort_keys=True))
            return 0
        return run_groups(groups, jobs=args.jobs, output_dir=args.output_dir,
                          mode='execute' if args.execute else 'default')
    except (GroupError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
