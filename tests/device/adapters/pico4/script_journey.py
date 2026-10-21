"""Pico composition of the shared Script journey on the existing VR input path.

Only the original Pico adapter may deliver input. All source factories require
its existing installed candidate, PID/start and OpenXR host binding; none may
launch, repair a session, submit a grant or restage a fixture while observing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat

from adapters.native_feature_observation import need
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, FILE as FILES
from adapters.native_script_observation import NativeScriptObservation, FILE as EXECUTION
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.pico4.normal_scripts import configuration as normal_configuration
from adapters.script_journey.actions import ScriptActions
from adapters.script_journey.feature import ScriptFeature, ScriptFixtureReader
from adapters.script_journey.files import ScriptFileIO, FILE as UI_FILE
from adapters.script_journey.history import ScriptHistory, DurableScriptMeasurements
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.measurements import ScriptMeasurements, fixture_scope
from adapters.script_journey.observation import ScriptObservation
from adapters.script_journey.scope import transfer_file_scope
from adapters.script_restart_handoff import ScriptRestartHandoff

VERSION = 1
OPERATIONS = frozenset('feature.scripts.' + kind for kind in ('act', 'observe', 'cleanup'))
COMMAND_FILE = 'files/overte-e2e/script-file-ui-command.json'


def configured(environment):
    enabled = environment.get('OVERTE_PICO_FEATURE_SCRIPTS', '0')
    need(enabled in ('0', '1'))
    if enabled == '0': return False
    need(normal_configuration(environment) is not None
         and bool(environment.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG'))
         and 'OVERTE_E2E_FEATURE_READER_TOKEN' not in environment)
    from adapters.feature_fixture_access import client as access_client
    access_client(Path(environment['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
        configured_url=environment.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
    return True


class PicoScriptFileSource(ScriptFileIO):
    """Nonce-only native read; ordinary actions stay on PicoNavigation."""
    def __init__(self, adapter, target, native):
        def send(envelope):
            need(set(envelope) == {'schemaVersion', 'commandId', 'action', 'request'}
                 and envelope['schemaVersion'] == 1 and envelope['action'] == 'script-file-ui')
            request = envelope['request']
            need(set(request) == {'schemaVersion', 'commandId', 'action'}
                 and request['schemaVersion'] == 1 and request['commandId'] == envelope['commandId']
                 and request['action'] == 'observe')
            native.guard()
            adapter.adb.write_debug_app_file(target, 'org.overte.pico', COMMAND_FILE,
                json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n')
            native.guard()
        super().__init__(send,
            lambda: adapter.adb.read_debug_app_file(target, 'org.overte.pico',
                'files/overte-e2e/' + UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

    def input(self, *_args, **_kwargs):
        need(False)  # This source has no input authority, including for the actor.


class PicoScriptJourney:
    def __init__(self, adapter):
        self.original = adapter

    def state_path(self, target):
        need(self.original.pico_configuration is not None)
        parent = self.original.pico_configuration[1]
        key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
        directory = parent / ('feature-scripts-' + key)
        # Only a host namespace; this does not establish a device/session owner.
        try: directory.mkdir(mode=0o700)
        except FileExistsError: pass
        info = directory.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
             and stat.S_IMODE(info.st_mode) == 0o700 and directory.resolve(strict=True) == directory)
        return directory / 'state.json'

    def _guard(self, target):
        installed = self.original._installation(target)
        identity = self.original.require_controlled_debug_identity(target)
        need(self.original.require_pico_session_identity(target) == identity
             and self.original.adb.foreground_package(target) == 'org.overte.pico')
        return installed, identity

    @contextmanager
    def existing_input_session(self, target):
        # Pico has no repairable Appium session. Pin the existing candidate and
        # target transport; each actual read/input separately checks PID/start
        # and the original OpenXR nonce journal. The explicit restart controller
        # alone may rotate that process/binding, including uncertain launch recovery.
        before = self.original._installation(target)
        configuration = self.original.pico_configuration
        need(configuration is not None)
        try: yield
        finally:
            need(self.original.pico_configuration == configuration
                 and self.original._installation(target) == before)

    def normal_feature_runtime(self, target, *, read_only=False):
        need(type(read_only) is bool)
        before = self._guard(target)
        ui, observe, binding = self.original._script_runtime(target)
        need(binding['processIdentity'] == before[1])
        def check(): need(self._guard(target) == before)
        check()
        return ui, observe, binding, check, before[0]

    def _store(self, target, name):
        return PrivateFeatureState(self.state_path(target).with_name(name))

    def script_store(self, target):
        return PrivateFeatureState(self.original._script_paths(target)[0])
    def script_files_store(self, target): return self.original._script_files_store(target)
    def script_restart_store(self, target): return self.original._script_restart_store(target)
    def script_restart_inputs_store(self, target): return self.original._script_restart_inputs_store(target)
    def script_actions_store(self, target): return self._store(target, 'script-actions.json')
    def script_feature_store(self, target): return self._store(target, 'script-feature.json')
    def script_retirement_store(self, target): return self._store(target, 'script-retirement.json')

    def script_history_store(self, target, role, *, stage=0):
        need(role in ('primary', 'actor') and type(stage) is int and stage in (0, 1))
        return self._store(target, 'script-' + role + '-history' + ('-restart' if stage else '') + '.json')

    def script_observation_store(self, target, role, *, stage=0):
        need(role in ('primary', 'actor') and type(stage) is int and stage in (0, 1))
        return self._store(target, 'script-' + role + '-observation' + ('-restart' if stage else '') + '.json')

    def _native_feature_observer(self, target, *, read_only=False):
        need(type(read_only) is bool); self._guard(target)
        return self.original._native_feature_observer(target)

    def _script_execution_observer(self, target, *, read_only=False):
        need(type(read_only) is bool); self._guard(target)
        return self.original._script_execution_observer(target)

    def _process_presence(self, target, *, read_only=False):
        need(type(read_only) is bool); self._guard(target)
        return self.original._process_presence(target)

    def _script_files(self, target, *, read_only=False):
        need(type(read_only) is bool); self._guard(target)
        return self.original._script_files(target)

    def _script_file_manager(self, target, *, read_only=False, run=None):
        need(type(read_only) is bool); self._guard(target)
        flow = self.original._script_file_manager(target)
        need(run is None or flow.file_owner.owned()['runId'] == run)
        return flow

    def _script_missing_manager(self, target):
        self._guard(target); return self.original._script_missing_manager(target)

    def _script_file_io(self, target):
        return PicoScriptFileSource(self.original, target, self._native_feature_observer(target, read_only=True))

    def _script_missing_from_files(self, target, run):
        transfer_file_scope(run, self._script_file_manager(target, read_only=True, run=run),
            self._script_execution_observer(target, read_only=True), self._script_file_io(target))
        return self._script_missing_manager(target)

    def _script_restart_inputs(self, target): return self.original._script_restart_inputs(target)
    def _script_restart_source(self, target): return self.original._script_restart_source(target)
    def _script_restart(self, target): return self.original._script_restart(target)

    def _script_measurements(self, target, run, fixture_url, *, read_only=False,
                             fixture_state='present', retired_owner=None):
        need(type(read_only) is bool and fixture_state in ('present', 'absent')
             and (retired_owner is None or fixture_state == 'absent')
             and (fixture_state == 'present' or read_only))
        retired_owner = deepcopy(retired_owner)
        store = self.script_files_store(target)
        need(retired_owner is None or store.read() is None)
        native = self._native_feature_observer(target, read_only=read_only)
        _ui, observe, binding, check, _installed = self.normal_feature_runtime(target, read_only=read_only)
        def guard():
            check(); native.guard(); need(retired_owner is None or store.read() is None)
        def original(name):
            return lambda: self.original.adb.read_debug_app_file(target, 'org.overte.pico',
                'files/overte-e2e/' + name, attempts=1)
        storage = NativeScriptFiles(native.send, original(FILES), native.clock_ms, guard, native.pid)
        class RetiredScope:
            def read(self): return deepcopy(retired_owner)
        files = OwnedScriptFiles(storage, store if retired_owner is None else RetiredScope(), binding)
        need(files.owned()['runId'] == run)
        def verify():
            need(files.owned()['runId'] == run)
            if fixture_state == 'present': return files.verify()
            location = files.locate(); need(location['exists'] is False)
            return location['directory']
        directory = verify()
        execution = NativeScriptObservation(native.send, original(EXECUTION), native.clock_ms, guard, native.pid)
        ui = PicoScriptFileSource(self.original, target, native)
        reader = ScriptMeasurements(run, directory, fixture_url, execution, ui, observe, native, verify, guard,
            file_instance=lambda: files.native.instance)
        reader.file_observation = lambda: deepcopy(storage.last_packet)
        return reader

    def _lock(self, target, source_lock=None):
        path = self.state_path(target).with_name('script-sources.lock')
        lock = ScriptSourceLock(path) if source_lock is None else source_lock
        need(isinstance(lock, ScriptSourceLock) and lock.path == path)
        return lock

    def _script_durable_measurements(self, target, run, fixture_url, *, role,
            fixture_state='present', retired_owner=None, source_lock=None, stage=0):
        lock = self._lock(target, source_lock)
        with lock.held():
            reader = self._script_measurements(target, run, fixture_url, read_only=True,
                fixture_state=fixture_state, retired_owner=retired_owner)
            _ui, _observe, binding, check, _installed = self.normal_feature_runtime(target, read_only=True)
            check(); reader.guard()
            history = ScriptHistory(self.script_history_store(target, role, stage=stage),
                binding, run, role, reader.directory, fixture_url)
            check(); reader.guard()
            return DurableScriptMeasurements(reader, history, source_lock=lock)

    def _script_observation(self, target, run, fixture_url, *, role,
            fixture_state='present', retired_owner=None, stage=0, source_lock=None):
        fixture_scope(run, fixture_url); lock = self._lock(target, source_lock)
        def make(held):
            return self._script_durable_measurements(target, run, fixture_url, role=role,
                fixture_state=fixture_state, retired_owner=retired_owner, stage=stage, source_lock=held)
        with lock.held():
            ui, _observe, binding, check, _installed = self.normal_feature_runtime(target, read_only=True)
            return ScriptObservation(self.script_observation_store(target, role, stage=stage), binding,
                run, role, fixture_url, make, lock, check, monotonic=ui.monotonic)

    def _script_actions(self, target, run, fixture_url): return ScriptActions(self, target, run, fixture_url)

    def _script_feature(self, target, run, *, role='primary', client=None):
        if client is None:
            need(role == 'primary' and configured(os.environ))
            from adapters.feature_fixture_access import client as access_client
            client = access_client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
        return ScriptFeature(self, target, ScriptFixtureReader(client, run), role=role)
