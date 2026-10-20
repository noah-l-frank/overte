"""Explicit durable Script file/manager ownership across a mobile restart.

This component never stops/launches an app, opens UI, loads a script, or stages
files. The caller performs normal lifecycle input between prepare and adopt.
Only original observations can authorize changing the two ownership bindings.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import posixpath
import re
import time
from urllib.parse import unquote, urlsplit

from adapters.native_feature_observation import integer, number
from adapters.native_process_presence import NativeProcessPresence
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, originals
from adapters.native_script_observation import (NativeScriptObservation, loaded_relative_modules,
    measured_effect, running_owned_engine, submitted_source)
from adapters.normal_feature_state import PrivateFeatureState, context, need
from adapters.normal_script_manager import NormalScriptManager, diagnostic
from adapters.token_script_file_ui import TokenScriptFilePicker, file_url

VERSION = 1


def _same(left, right):
    # JSON booleans and numbers are distinct ownership values (True != 1).
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


class _Snapshot:
    """Validate historical records with existing strict readers; never mutate."""
    def __init__(self, value): self.value = deepcopy(value)
    def read(self): return deepcopy(self.value)


def _records(files, manager, *, component_only):
    need(type(files) is dict and type(manager) is dict)
    binding = context(files['binding'], component_only=component_only)
    owner = OwnedScriptFiles(None, _Snapshot(files), binding, component_only=component_only)
    owner.owned()
    need(type(manager.get('fileOwner')) is dict)
    directory = manager['fileOwner']['directory']
    picker = TokenScriptFilePicker(None, directory)
    flow = NormalScriptManager(None, None, _Snapshot(manager), binding,
        component_only=component_only, source_kind='script-file-bundle', file_owner=owner, file_picker=picker)
    need(flow.state == manager and manager['fileOwner'] is not None)
    return directory


def _under(url, directory):
    # URL aliases must not hide an engine/module in the owned fixture tree.
    need(type(url) is str)
    parsed = urlsplit(url)
    path = posixpath.normpath(unquote(parsed.path))
    return (parsed.scheme == 'file' and not parsed.netloc
            and (path == file_url(directory) or path.startswith(file_url(directory) + '/')))


class ScriptRestartHandoff:
    def __init__(self, store, files_store, manager_store, *, component_only=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(isinstance(value, PrivateFeatureState) for value in (store, files_store, manager_store))
             and len({value.path for value in (store, files_store, manager_store)}) == 3
             and type(component_only) is bool and callable(monotonic) and callable(sleep))
        self.store, self.files_store, self.manager_store = store, files_store, manager_store
        self.component_only, self.monotonic, self.sleep = component_only, monotonic, sleep

    def _read(self):
        value = self.store.read()
        need(type(value) is dict and set(value) == {'handoffVersion', 'componentOnly', 'oldFiles',
             'oldManager', 'oldNative', 'next'} and type(value['handoffVersion']) is int
             and value['handoffVersion'] == VERSION and type(value['componentOnly']) is bool
             and value['componentOnly'] == self.component_only)
        directory = _records(value['oldFiles'], value['oldManager'], component_only=self.component_only)
        manager = value['oldManager']
        need(manager['source'] == directory + '/script-bundle/main.js'
             and manager['loadAttempted'] and manager['tabletOwned'] and manager['managerOwned']
             and not manager['pickerOwned'] and not manager['dialogOwned'])
        native = value['oldNative']
        need(type(native) is dict and set(native) == {'pid', 'instance', 'engineInstance', 'effectId'}
             and integer(native['pid'], 1, 2147483647)
             and all(type(native[key]) is str and re.fullmatch('[0-9a-f]{32}', native[key])
                     for key in ('instance', 'engineInstance')))
        from adapters.native_script_observation import entity_id
        need(entity_id(native['effectId']))
        target = value['next']
        if target is not None:
            need(type(target) is dict and set(target) == {'binding', 'nativeInstance', 'pid', 'files', 'manager'}
                 and integer(target['pid'], 1, 2147483647) and target['pid'] != native['pid']
                 and type(target['nativeInstance']) is str and re.fullmatch('[0-9a-f]{32}', target['nativeInstance'])
                 and target['nativeInstance'] != native['instance'])
            self._binding(value['oldFiles']['binding'], target['binding'])
            need(_same(target['files'], value['oldFiles'] | {'binding': target['binding']}))
            adopted = value['oldManager'] | dict(binding=target['binding'], tabletOwned=False,
                managerOwned=False, dialogOwned=False, pickerOwned=False, source=None,
                loadAttempted=False, observerInstance=None, afterSequence=0)
            need(_same(target['manager'], adopted))
            _records(target['files'], target['manager'], component_only=self.component_only)
        return value, directory

    def _binding(self, old, new):
        context(new, component_only=self.component_only)
        immutable = {'targetFingerprint'} | (set() if self.component_only else {'sourceRevision', 'artifactSha256'})
        need(all(old[key] == new[key] for key in immutable)
             and old['processIdentity'] != new['processIdentity'] and new['generation'] >= old['generation'])

    def directory(self):
        """Validated frozen input path for a new raw native picker reader."""
        return self._read()[1]

    def prepare(self, manager, execution):
        """Freeze validated existing intent before any normal app-stop input."""
        need(self.store.read() is None and isinstance(manager, NormalScriptManager)
             and manager.source_kind == 'script-file-bundle'
             and isinstance(execution, NativeScriptObservation)
             and isinstance(manager.file_owner.native, NativeScriptFiles)
             and manager.store.path == self.manager_store.path
             and manager.file_owner.store.path == self.files_store.path
             and manager.file_owner.component_only == self.component_only)
        directory = manager.file_owner.verify()
        manager.sample_full()  # Preserve the last actual service cursor before shutdown.
        current = execution.read(execution.sequence, require_effects=True,
            require_code_identity=True, require_load_history=True)
        source = manager.state['source']
        need(source == directory + '/script-bundle/main.js' and manager.state['loadAttempted']
             and not manager.state['pickerOwned'] and manager.state['managerOwned']
             and manager.file_owner.native.pid == current['processId']
             and manager.file_owner.native.instance == current['instance'])
        engine = running_owned_engine(current, source)
        code = submitted_source(current, source)
        raw = originals(manager.file_owner.owned()['runId'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
        need(code['sha256'] == hashlib.sha256(raw).hexdigest() and code['codeUnits'] == len(raw) // 2
             and loaded_relative_modules(engine) == ['companion.js'])
        effect = measured_effect(current, manager.file_owner.owned()['runId'])
        need(effect is not None and integer(effect['ticks'], 1))
        value = dict(handoffVersion=VERSION, componentOnly=self.component_only,
            oldFiles=manager.file_owner.owned(), oldManager=deepcopy(manager.state),
            oldNative=dict(pid=current['processId'], instance=current['instance'],
                engineInstance=engine['required']['instance'], effectId=effect['id']), next=None)
        need(_same(self.files_store.read(), value['oldFiles']) and _same(self.manager_store.read(), value['oldManager']))
        self.store.write(value, None)
        self._read()
        return deepcopy(current)  # Raw source only; no restart has happened.

    def adopt(self, binding, presence, execution, files, ui, observe, picker):
        """Observe a new empty process, then CAS-transfer both intents.

        Interrupted transfers recheck all current native facts. Neither phase
        permits an automatic retry of lifecycle or Script input.
        """
        value, directory = self._read()
        self._binding(value['oldFiles']['binding'], binding)
        need(isinstance(presence, NativeProcessPresence) and isinstance(execution, NativeScriptObservation)
             and isinstance(files, NativeScriptFiles) and isinstance(picker, TokenScriptFilePicker)
             and presence.pid == execution.pid == files.pid and presence.pid != value['oldNative']['pid']
             and picker.directory == directory and callable(observe))
        if value['next'] is not None:
            need(_same(value['next']['binding'], binding) and value['next']['pid'] == presence.pid)
        allowed_files = [value['oldFiles']]
        allowed_manager = [value['oldManager']]
        if value['next'] is not None:
            allowed_files.append(value['next']['files']); allowed_manager.append(value['next']['manager'])
        need(any(_same(self.files_store.read(), candidate) for candidate in allowed_files)
             and any(_same(self.manager_store.read(), candidate) for candidate in allowed_manager))
        # Use historical immutable owner data only to read the original files;
        # do not bypass ordinary live OwnedScriptFiles context equality.
        old_files = OwnedScriptFiles(files, _Snapshot(value['oldFiles']), value['oldFiles']['binding'],
            component_only=self.component_only)
        started = previous = self.monotonic(); need(number(started, 0, 1e15))
        first = first_epoch = None; samples = 0; service_instance = None; service_sequence = 0
        while True:
            now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous and now - started < 20)
            previous = now
            exit_source = presence.require_absent(value['oldNative']['pid'])
            current = execution.read(execution.sequence, require_effects=True,
                require_code_identity=True, require_load_history=True)
            need(current['instance'] == exit_source['instance'] and current['instance'] != value['oldNative']['instance'])
            if value['next'] is not None: need(current['instance'] == value['next']['nativeInstance'])
            need(old_files.verify() == directory and files.instance == current['instance'])
            # Include stopped/stopping engines and loaded module aliases: a
            # hidden row cannot turn retained owned code into empty execution.
            need(not any(_under(engine['url'], directory)
                or engine['required']['instance'] == value['oldNative']['engineInstance']
                or any(_under(module['url'], directory) for module in engine['required']['modules'])
                for engine in current['source']['engines']))
            need(not any(_under(event['url'], directory) for event in current['source']['loads']['events']))
            need(measured_effect(current, value['oldFiles']['runId']) is None
                 and not any(row['id'] == value['oldNative']['effectId'] for row in current['source']['effects']['entities']))
            service, epoch = observe(service_sequence); diagnostic(service, epoch)
            need(service_instance in (None, service['instance']) and service['sampleSequence'] > service_sequence
                 and service['instance'] != value['oldManager']['observerInstance']
                 and not any(_under(row['url'], directory) or _under(row['path'], directory) for row in service['scripts']))
            service_instance, service_sequence = service['instance'], service['sampleSequence']
            need(ui.tablet_visible() is False and ui.manager_visible() is False
                 and picker.picker(picker.observe_absent()) is None)
            # Include original I/O and guard time in the whole handoff bound.
            need(presence.guard() is not False and execution.guard() is not False and files.guard() is not False)
            now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous and now - started < 20)
            previous = now; first = now if first is None else first; samples += 1
            first_epoch = current['capturedEpochMs'] if first_epoch is None else first_epoch
            need(current['capturedEpochMs'] >= first_epoch)
            if now - first >= 3 and current['capturedEpochMs'] - first_epoch >= 3000 and samples >= 2: break
            self.sleep(0.25)
        target = dict(binding=deepcopy(binding), nativeInstance=current['instance'], pid=current['processId'],
            files=value['oldFiles'] | {'binding': deepcopy(binding)},
            manager=value['oldManager'] | dict(binding=deepcopy(binding), tabletOwned=False,
                managerOwned=False, dialogOwned=False, pickerOwned=False, source=None,
                loadAttempted=False, observerInstance=None, afterSequence=0))
        if value['next'] is None:
            pending = value | {'next': target}
            self.store.write(pending, value); value = pending
        else: need(_same(value['next'], target))
        # Persisted exact old/new records authorize partial-write recovery only.
        for store, old, new in ((self.files_store, value['oldFiles'], target['files']),
                                (self.manager_store, value['oldManager'], target['manager'])):
            actual = store.read(); need(_same(actual, old) or _same(actual, new))
            if _same(actual, old): store.write(new, old)
        need(_same(self.files_store.read(), target['files']) and _same(self.manager_store.read(), target['manager']))
        need(presence.guard() is not False and execution.guard() is not False and files.guard() is not False)
        now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous and now - started < 20)
        self.store.discard(value)
        return {'exit': deepcopy(exit_source), 'execution': deepcopy(current), 'service': deepcopy(service)}
