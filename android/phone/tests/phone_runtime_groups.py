"""Closed Phone host groups, original budgets and reviewed whole-file calibration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import Counter
from copy import deepcopy
import math
import hashlib
import json
import os
import stat
from types import MappingProxyType
import re
from pathlib import Path, PurePosixPath

JOBS = 4
STARTUP_MARGIN_SECONDS = 30
FILE_PROCESS_MARGIN_SECONDS = 5
MAX_GROUP_SECONDS = 900


class GroupError(ValueError):
    pass


def need(value, message):
    if not value:
        raise GroupError(message)


def original_file_timeout(name):
    """Unmodified pre-grouping whole-file budgets, retained as independent gold."""
    if name.endswith('test_emote_feature_journey.py'):
        return 10800
    if name.endswith('test_assets_feature.py'):
        return 600
    if name.endswith(('phone-chat-native-test.py', 'phone-chat-peer-native-test.py',
                      'phone-chat-history-native-test.py', 'phone-snapshot-settings-native-test.py')):
        return 180
    if name.endswith('test_snapshots_read_ready_slot.py'):
        return 300
    if name.endswith(('test_graphics_feature.py', 'test_create_feature.py', 'test_avatar_people_feature.py',
                      'test_chat_feature.py', 'test_snapshots_full_retirement_audit.py',
                      'test_snapshots_retirement_actor_versions.py', 'test_snapshots_actor.py',
                      'test_snapshots_constructor_history_pass.py', 'test_snapshots_passive_constructor_history.py',
                      'test_snapshots_quiet_role_reuse.py', 'test_snapshots_primary_cleanup_stages.py',
                      'test_snapshots_primary_history_pass.py', 'test_snapshots_history_pass.py',
                      'test_snapshots_phase_transition.py', 'test_snapshots_feature_journey.py',
                      'test_snapshot_documents_journey_boundary.py')):
        return 240
    return 90



CALIBRATION_PATH = Path(__file__).with_name('phone-runtime-timeout-calibration.json')
_CALIBRATION_DOCUMENT_SHA256 = '2e737d21f5ec5f3d3df78aff254dd8d2e5e03c24fe71f813b4410d46e44904d0'
_ALLOWED_TIMEOUT_OVERRIDES = (
    ('android/phone/tests/device/test_snapshots_feature_journey.py', 240, 420),
    ('android/phone/tests/device/test_authentication_feature.py', 90, 210),
    ('android/phone/tests/device/test_world_web_feature.py', 90, 180),
    ('android/phone/tests/device/test_emote_inputs.py', 90, 180),
    ('android/phone/tests/device/test_graphics_feature.py', 240, 420),
    ('android/phone/tests/device/test_emote_run.py', 90, 210),
    ('android/phone/tests/device/test_emote_feature.py', 90, 270),
    ('android/phone/tests/device/test_navigation_feature.py', 90, 150),
    ('android/phone/tests/device/test_emote_role_failure.py', 90, 180),
    ('android/phone/tests/device/test_emote_actor.py', 90, 450),
    ('android/phone/tests/device/test_snapshots_resident_actor.py', 90, 180),
    ('android/phone/tests/device/test_emote_image_phase_retirement.py', 90, 270),
    ('android/phone/tests/device/test_emote_background_effects.py', 90, 150),
    ('android/phone/tests/device/test_emote_lifetime.py', 90, 240),
    ('android/phone/tests/device/test_emote_observation.py', 90, 150),
    ('android/phone/tests/device/test_emote_scene.py', 90, 180),
    ('android/phone/tests/device/test_snapshots_actor_ordinary_stages.py', 90, 150),
)


def validate_calibration(value):
    """Accept only the reviewed complete-file evidence and exact reviewed overrides.

    The referenced diagnostic reports are retained outside the checkout. Their
    logical root IDs, relative artifact names and hashes are provenance, not
    runtime dependencies or a claim of normal-profile/device qualification.
    """
    need(type(value) is dict and set(value) == {'schemaVersion', 'scope', 'marginPolicy', 'files'},
         'Invalid Phone timeout calibration schema')
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['scope'] == 'WHOLE_FILE_HOST_TEST_BUDGETS_ONLY'
         and value['marginPolicy'] == {'factorNumerator': 3, 'factorDenominator': 2,
                                      'startupAllowanceSeconds': 15, 'roundingSeconds': 30},
         'Invalid Phone timeout calibration policy')
    rows = value['files']
    need(type(rows) is list and len(rows) == len(_ALLOWED_TIMEOUT_OVERRIDES),
         'Unreviewed Phone timeout override set')
    for row, (name, old, new) in zip(rows, _ALLOWED_TIMEOUT_OVERRIDES):
        need(type(row) is dict and set(row) == {
            'file', 'originalSeconds', 'calibratedSeconds', 'reason', 'measurement'},
            'Invalid Phone timeout override fields')
        need(row['file'] == name and type(row['originalSeconds']) is int
             and row['originalSeconds'] == old == original_file_timeout(name)
             and type(row['calibratedSeconds']) is int and row['calibratedSeconds'] == new,
             'Unreviewed Phone timeout override')
        evidence = row['measurement']
        need(type(evidence) is dict and set(evidence) == {
            'scope', 'reportRootId', 'report', 'sha256', 'sourceFileSha256',
            'testsRun', 'durationSeconds', 'successful', 'failures', 'errors'},
             'Invalid Phone whole-file calibration evidence')
        need(type(evidence['report']) is str, 'Invalid Phone calibration report reference')
        relative = PurePosixPath(evidence['report'])
        need(not relative.is_absolute()
             and '..' not in relative.parts and relative.as_posix() == evidence['report']
             and type(evidence['reportRootId']) is str
             and re.fullmatch(r'[a-z0-9-]+', evidence['reportRootId'])
             and evidence['scope'] == ('HISTORICAL_COMPLETE_NORMAL_FILE_PASS_NOT_CURRENT_RUN_QUALIFICATION'
                 if name == 'android/phone/tests/device/test_snapshots_actor_ordinary_stages.py'
                 else 'COMPLETE_HOST_FILE_DIAGNOSTIC_NOT_NORMAL_QUICK_QUALIFICATION')
             and evidence['successful'] is True and type(evidence['testsRun']) is int
             and evidence['testsRun'] > 0 and type(evidence['failures']) is int
             and evidence['failures'] == 0 and type(evidence['errors']) is int
             and evidence['errors'] == 0, 'Incomplete Phone whole-file calibration proof')
        duration = evidence['durationSeconds']
        need(type(duration) in (int, float) and math.isfinite(duration)
             and 0 < duration < new and old < new and math.ceil((duration * 1.5 + 15) / 30) * 30 == new,
             'Phone calibration margin differs from reviewed measurement')
        need(all(type(evidence[key]) is str and re.fullmatch(r'[0-9a-f]{64}', evidence[key])
                 for key in ('sha256', 'sourceFileSha256'))
             and type(row['reason']) is str and bool(row['reason']),
             'Missing Phone calibration provenance')
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    need(hashlib.sha256(encoded).hexdigest() == _CALIBRATION_DOCUMENT_SHA256,
         'Phone timeout calibration differs from reviewed evidence')
    return value


def load_calibration(path=CALIBRATION_PATH):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path, 'Aliased Phone timeout calibration')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 64 * 1024,
             'Unbounded Phone timeout calibration')
        raw = stream.read(64 * 1024 + 1)
        after = os.fstat(stream.fileno())
    signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    need(signature(before) == signature(after) == signature(path.lstat())
         and len(raw) == before.st_size, 'Changed Phone timeout calibration')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            need(key not in result, 'Duplicate Phone timeout calibration key')
            result[key] = item
        return result
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _value: need(False, 'Nonfinite Phone timeout calibration'))
    return validate_calibration(value)


_CALIBRATED_TIMEOUTS = MappingProxyType({row['file']: row['calibratedSeconds']
                                       for row in load_calibration()['files']})


def file_timeout(name):
    """Apply only reviewed whole-file aggregate exceptions to original gold."""
    return _CALIBRATED_TIMEOUTS.get(name, original_file_timeout(name))


def group_timeout(files, jobs=JOBS):
    """List-scheduling bound, including explicit process and startup allowance.

    For p workers, Cmax <= sum(cost)/p + (1-1/p)*max(cost), independently of
    queue order or earlier completion. Each cost uses its reviewed whole-file
    deadline (original gold or explicit calibration) plus5 seconds for launch/process-group disposition. A further
    30 seconds covers supervisor startup, reporting and final adopted cleanup.
    This is an aggregate bound, never a replacement child timeout.
    """
    need(type(jobs) is int and 1 <= jobs <= JOBS, 'Phone jobs must be from1 through4')
    need(type(files) is list and files, 'Phone group must contain files')
    costs = [file_timeout(name) + FILE_PROCESS_MARGIN_SECONDS for name in files]
    return math.ceil((sum(costs) + (jobs - 1) * max(costs)) / jobs) + STARTUP_MARGIN_SECONDS


def validate_groups(registry, dependency_light, prepared, common, extended):
    """Reject incomplete, duplicated, unknown or unreferenced registry entries."""
    need(type(registry) is dict and set(registry) == {
        'schemaVersion', 'jobs', 'groups', 'modes', 'extendedGroups'}, 'Invalid Phone group registry fields')
    need(type(registry['schemaVersion']) is int and registry['schemaVersion'] == 1
         and type(registry['jobs']) is int and registry['jobs'] == JOBS, 'Invalid Phone group registry version/jobs')
    validate_calibration(load_calibration())
    originals = list(dependency_light) + list(prepared) + list(common) + list(extended)
    for name in originals:
        need(type(name) is str, 'Invalid original Phone file path')
        path = PurePosixPath(name)
        need(not path.is_absolute() and '..' not in path.parts and path.as_posix() == name
             and re.fullmatch(r'[a-z0-9_/-]+\.py', name)
             and (name.startswith('android/phone/tests/')
                  or name.startswith('tests/device/contracts/')
                  or name.startswith('tests/device/self_tests/')),
             'Foreign or noncanonical original Phone file path')
    need(len(originals) == len(set(originals)), 'Original Phone lists must not duplicate files')
    known = set(originals)
    rows = registry['groups']
    need(type(rows) is list and rows, 'Phone groups required')
    by_id = {}
    files = []
    for row in rows:
        need(type(row) is dict and set(row) == {'id', 'files', 'timeoutSeconds'}, 'Invalid Phone group fields')
        identifier = row['id']
        need(type(identifier) is str and re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', identifier)
             and len(identifier) <= 72 and identifier not in by_id, 'Invalid or duplicate Phone group ID')
        selected = row['files']
        need(type(selected) is list and 1 <= len(selected) <= 20
             and all(type(name) is str and name in known for name in selected), 'Unknown or empty Phone group file')
        need(type(row['timeoutSeconds']) is int and row['timeoutSeconds'] == group_timeout(selected),
             'Phone group budget does not match applied file deadlines and workers')
        need(row['timeoutSeconds'] <= MAX_GROUP_SECONDS or set(selected) <= set(extended),
             'Phone group exceeds bounded normal budget')
        by_id[identifier] = row
        files.extend(selected)
    need(Counter(files) == Counter(originals), 'Phone registry file coverage differs from original lists')
    modes = registry['modes']
    need(type(modes) is dict and set(modes) == {'default', 'execute'}, 'Invalid Phone modes')
    expected = {'default': list(dependency_light) + list(common), 'execute': list(prepared) + list(common)}
    used = set()
    for mode in ('default', 'execute'):
        identifiers = modes[mode]
        need(type(identifiers) is list and identifiers and all(type(name) is str and name in by_id for name in identifiers)
             and len(identifiers) == len(set(identifiers)), 'Unknown or duplicate Phone mode group')
        chosen = [name for identifier in identifiers for name in by_id[identifier]['files']]
        need(Counter(chosen) == Counter(expected[mode]), 'Phone mode coverage differs from original lists')
        used.update(identifiers)
    extension = registry['extendedGroups']
    need(type(extension) is list and extension and all(type(name) is str and name in by_id for name in extension)
         and len(extension) == len(set(extension)), 'Invalid Phone extended groups')
    extended_files = [name for identifier in extension for name in by_id[identifier]['files']]
    need(Counter(extended_files) == Counter(extended), 'Phone extended coverage differs from original list')
    need(not set(extension) & used and used | set(extension) == set(by_id), 'Unreferenced or overlapping Phone groups')
    return registry


def select_groups(registry, *, execute=False, extended=False, selected_ids=None):
    mode = 'execute' if execute else 'default'
    available = registry['modes'][mode] + (registry['extendedGroups'] if extended else [])
    if selected_ids is None:
        selected_ids = available
    need(type(selected_ids) is list and selected_ids and all(type(name) is str and name in available for name in selected_ids)
         and len(selected_ids) == len(set(selected_ids)), 'Unknown, duplicate or unavailable Phone group selection')
    by_id = {row['id']: row for row in registry['groups']}
    return [deepcopy(by_id[name]) for name in selected_ids]
