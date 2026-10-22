"""Owned Pico Cube/history/JSON flow on the existing normal Create route.

This is the existing create-management catalog foundation, not the complete
feature.create contract. Original effects remain the independent fixture's job.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math

from adapters.normal_create import NormalCreate
from adapters.normal_feature_state import PrivateFeatureState, context, need
from adapters.normal_ui import NativeUIError
from adapters.normal_script_manager import NormalScriptManager
from adapters.pico4.normal_create import PicoCreateIO
from adapters.pico4.normal_scripts import configuration as script_configuration
from adapters.pico4.tablet_home import bind_home, validate_input as validate_home
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import TokenCreateUI, VERSION as CONTROL_VERSION, control_id, nonce, scope
from contracts import validate_operation_arguments
from create_observation import OPERATIONS, PREFIX, owned_url

VERSION = 1


def configuration(environment):
    enabled = environment.get('OVERTE_PICO_NORMAL_CREATE', '0')
    need(enabled in ('0', '1'))
    if enabled == '0':
        return None
    scene = script_configuration(environment)
    need(scene is not None)
    return scene


class CreateInputs:
    """One bounded original input record; no ACK or requested effect is a fact."""
    def __init__(self, store, binding, owner):
        self.store, self.binding, self.owner = store, dict(context(binding)), owner
        self.previous = store.read()
        if self.previous is not None:
            value = self.previous
            need(set(value) == {'schemaVersion', 'binding', 'scriptUrl', 'count', 'last'}
                 and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
                 and context(value['binding']) == self.binding
                 and type(value['count']) is int and 1 <= value['count'] <= 4096)
            owned_url(value['scriptUrl'], {'observer.js'})
            self.validate(value['last'])

    def validate(self, value):
        need(type(value) is dict and set(value) == {'kind', 'original'})
        original = value['original']
        if value['kind'] == 'create':
            need(type(original) is dict and set(original) == {
                'createInputVersion', 'action', 'controlId', 'controlToken', 'scope'}
                and type(original['createInputVersion']) is int and original['createInputVersion'] == CONTROL_VERSION
                and original['action'] in ('activate', 'replace', 'select-index', 'scroll')
                and control_id(original['controlId']) and original['controlId'] != 'create.page'
                and nonce(original['controlToken']))
            scope(original['scope'])
            need(original['scope']['processId'] == int(self.binding['processIdentity'].split(':')[0])
                 and original['scope']['instance'] == self.binding['sessionId'])
        else:
            need(value['kind'] == 'home' and type(original) is dict)
            validate_home(original, int(self.binding['processIdentity'].split(':')[0]),
                original['capturedEpochMs'], 'tablet.home-ray')

    def record(self, value):
        self.validate(value)
        current = self.owner.read()
        need(current is not None and context(current['binding']) == self.binding
             and current['scriptUrl'] is not None and current == self.active_owner.previous)
        owned_url(current['scriptUrl'], {'observer.js'})
        need(self.previous is None or self.previous['scriptUrl'] == current['scriptUrl'])
        record = dict(schemaVersion=1, binding=self.binding, scriptUrl=current['scriptUrl'],
            count=1 if self.previous is None else self.previous['count'] + 1, last=deepcopy(value))
        need(record['count'] <= 4096)
        self.store.write(record, self.previous)
        self.previous = record

    def create(self, original):
        self.record(dict(kind='create', original=original))

    def home(self, stage, original, control):
        need(stage == 'tablet-home-ray' and control == 'tablet.home-ray')
        self.record(dict(kind='home', original=original))

    def retire(self):
        need(self.owner.read() is None)
        self.store.discard(self.previous)
        self.previous = None


class CreateRecipe(TokenCreateUI):
    def __init__(self, original, inputs, home):
        self.home, self.inputs = home, inputs
        super().__init__(PicoCreateIO(original.io), inputs.create,
            monotonic=original.monotonic, sleep=original.sleep)

    def open_create(self):
        # Native VR Home is a Gizmo outside the QML page, not tablet.home.
        self.home.ensure(self.inputs.home)
        return super().open_create()


class ScriptRecipe:
    def __init__(self, original, inputs, home):
        self.original, self.inputs, self.home = original, inputs, home

    def __getattr__(self, name):
        return getattr(self.original, name)

    def open_manager(self):
        self.home.ensure(self.inputs.home)
        return self.original.open_manager()


class OwnedCreate(NormalCreate):
    def quiet(self, script_url, *, stopped=False):
        prefix = PREFIX + owned_url(script_url, {'observer.js'}) + '_'
        started = previous = self.scripts.monotonic()
        need(type(started) in (int, float) and math.isfinite(started))
        for _attempt in range(33):
            rows = self.sample()
            need(not any(row['name'].startswith(prefix) for row in rows))
            if stopped:
                need(not any(row['url'] == script_url for row in self.scripts.sample()))
            now = self.scripts.monotonic()
            need(type(now) in (int, float) and math.isfinite(now) and now >= previous)
            previous = now
            if now - started >= 3:
                return
            self.scripts.sleep(.1)
        raise NativeUIError('Pico Create cleanup did not complete its quiet window')

    def close(self, script_url):
        need(self.state['scriptUrl'] in (None, script_url))
        if self.state['scriptUrl'] is not None:
            self.delete(self.state['names'])
            self.recover_pending()
            self.quiet(script_url)
            self.scripts.open()
            if self.scripts.state['source'] is not None:
                self.scripts.stop_source(script_url)
            self.quiet(script_url, stopped=True)
        self.scripts.close()
        self.store.discard(self.previous)
        self.previous = None


class PicoCreateManagement:
    def __init__(self, adapter, target):
        self.adapter, self.target = adapter, target
        need(adapter.pico_configuration is not None)
        key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
        parent = adapter.pico_configuration[1]
        self.paths = {role: parent / ('normal-create-' + role + '-' + key + '.json')
            for role in ('owner', 'scripts', 'inputs', 'attempt')}
        self.lock = ScriptSourceLock(parent / ('normal-create-sources-' + key + '.lock'))

    def store(self, role):
        return PrivateFeatureState(self.paths[role])

    def owned(self):
        return any(self.store(role).read() is not None for role in self.paths)

    def flow(self):
        self.lock.assert_held()
        from adapters.pico4.create_journey import PicoCreateJourney
        need(not PicoCreateJourney.owned_target(self.adapter,self.target))
        need(not getattr(self.adapter,'_create_picker_owned',lambda _target:False)(self.target)
            and not getattr(self.adapter,'_create_models_owned',lambda _target:False)(self.target))
        # Do not adopt an unrelated regular Script manager reservation.
        script_path, _ui_path = self.adapter._script_paths(self.target)
        need(PrivateFeatureState(script_path).read() is None)
        ui, _observe, binding = self.adapter._script_runtime(self.target)
        original = self.adapter._feature_observer(self.target)
        def observe(after):
            self.lock.assert_held()
            value = original.read(after, include_avatar_entities=True)
            return value, self.adapter.adb.epoch_milliseconds(self.target)
        inputs = CreateInputs(self.store('inputs'), binding, self.store('owner'))
        native = self.adapter._native_feature_observer(self.target)
        home = bind_home(self.adapter, self.target, native)
        scripts = NormalScriptManager(ScriptRecipe(ui, inputs, home), observe, self.store('scripts'), binding,
            source_kind='create-observer', monotonic=ui.monotonic, sleep=ui.sleep)
        flow = OwnedCreate(CreateRecipe(ui, inputs, home), scripts, self.store('owner'), binding)
        inputs.active_owner = flow
        return flow, inputs

    def invoke(self, operation, arguments):
        need(operation in OPERATIONS)
        arguments = validate_operation_arguments(operation, arguments)
        with self.lock.held():
            flow, inputs = self.flow()
            store = self.store('attempt')
            previous = store.read()
            if previous is not None:
                need(set(previous) == {'schemaVersion', 'binding', 'operation', 'arguments'}
                     and type(previous['schemaVersion']) is int and previous['schemaVersion'] == 1
                     and context(previous['binding']) == flow.binding
                     and previous['operation'] in OPERATIONS)
                validate_operation_arguments(previous['operation'], previous['arguments'])
                # A lost input result never authorizes another history/create/
                # update/import/open attempt. Only measured cleanup can proceed.
                need(operation in ('create.reference.close', 'create.delete'))
            else:
                previous = dict(schemaVersion=1, binding=flow.binding,
                    operation=operation, arguments=deepcopy(arguments))
                store.write(previous, None)
            result = flow.invoke(operation, arguments)
            if operation == 'create.reference.close':
                need(self.store('scripts').read() is None)
                inputs.retire()
                store.discard(previous)
            elif previous['operation'] == operation and previous['arguments'] == arguments:
                store.discard(previous)
            return result

    def cleanup(self):
        with self.lock.held():
            owner = self.store('owner').read()
            if owner is None:
                if not self.owned():
                    return
                # Initial baseline sampling may have persisted a Script reader
                # before refusing foreign/incomplete entities. With no input
                # record or UI/source lease, only that unused reader may retire.
                flow, inputs = self.flow()
                need(inputs.previous is None)
                value = flow.scripts.state
                need(value['source'] is None and not any(value[key] for key in (
                    'loadAttempted', 'tabletOwned', 'managerOwned', 'dialogOwned')))
                attempt = self.store('attempt').read()
                if attempt is not None:
                    need(set(attempt) == {'schemaVersion', 'binding', 'operation', 'arguments'}
                         and type(attempt['schemaVersion']) is int and attempt['schemaVersion'] == 1
                         and context(attempt['binding']) == flow.binding
                         and attempt['operation'] == 'create.reference.open')
                    validate_operation_arguments(attempt['operation'], attempt['arguments'])
                flow.scripts.close()
                self.store('attempt').discard(attempt)
                return
            need(owner['scriptUrl'] is not None)
            self.invoke('create.reference.close', {'scriptUrl': owner['scriptUrl']})
