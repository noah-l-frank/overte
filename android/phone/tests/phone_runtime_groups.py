"""Pure closed registry and original per-file budgets for Phone host contracts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import Counter
from copy import deepcopy
import math
import re
from pathlib import PurePosixPath

JOBS = 4
STARTUP_MARGIN_SECONDS = 30
FILE_PROCESS_MARGIN_SECONDS = 5
MAX_GROUP_SECONDS = 900


class GroupError(ValueError):
    pass


def need(value, message):
    if not value:
        raise GroupError(message)


def file_timeout(name):
    """The original inner deadline; grouping never changes this value."""
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


def group_timeout(files, jobs=JOBS):
    """List-scheduling bound, including explicit process and startup allowance.

    For p workers, Cmax <= sum(cost)/p + (1-1/p)*max(cost), independently of
    queue order or earlier completion. Each cost retains its original child
    deadline plus5 seconds for launch/process-group disposition. A further
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
             'Phone group budget does not match original file deadlines and workers')
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
