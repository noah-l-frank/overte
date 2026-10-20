"""One-send normal restart input intent and original native lifecycle evidence.

This component owns input delivery only. Old-PID death, empty Script execution,
file handoff, independent actors and complete cleanup remain separate checks.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time

from adapters.native_feature_observation import NativeFeatureObservation, integer, number
from adapters.normal_feature_state import PrivateFeatureState, context, need
from adapters.normal_ui import NativeUIError
from adapters.script_restart_handoff import ScriptRestartHandoff, _same

VERSION = 1
PHASES = ('prepared', 'stop-issued', 'launch-issued', 'observed')


class RestartDeliveryUncertain(NativeUIError):
    pass


def native(value):
    need(type(value) is dict and set(value) == {'pid', 'instance', 'lifecycle'}
         and integer(value['pid'], 1, 2147483647) and type(value['instance']) is str
         and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and type(value['lifecycle']) is dict
         and set(value['lifecycle']) == {'backgrounds', 'activations', 'launches'}
         and all(integer(count, 0, 1000000) for count in value['lifecycle'].values())
         and value['lifecycle']['launches'] >= 1)
    return value


class RestartInputs:
    def __init__(self, store, owners, *, component_only=False, monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and type(component_only) is bool and callable(monotonic))
        need(type(owners) in (list, tuple) and len(owners) == 3
             and all(isinstance(owner, PrivateFeatureState) for owner in owners)
             and len({owner.path for owner in owners} | {store.path}) == 4
             and all(owner.path.parent == store.path.parent for owner in owners))
        self.store, self.component_only, self.monotonic = store, component_only, monotonic
        self.owners = tuple(owners)
        self.owner_files = [str(owner.path) for owner in owners]

    def _binding(self, value, measured):
        context(value, component_only=self.component_only)
        pid = str(measured['pid'])
        need(value['processIdentity'] == pid or value['processIdentity'].startswith(pid + ':'))

    def _new(self, old, new, old_native, new_native):
        self._binding(new, new_native)
        immutable = {'targetFingerprint'} | (set() if self.component_only else {'sourceRevision', 'artifactSha256'})
        need(all(old[key] == new[key] for key in immutable)
             and old['processIdentity'] != new['processIdentity'] and new['generation'] >= old['generation']
             and new_native['pid'] != old_native['pid'] and new_native['instance'] != old_native['instance']
             and new_native['lifecycle']['launches'] == old_native['lifecycle']['launches'] + 1
             and new_native['lifecycle']['activations'] >= old_native['lifecycle']['activations'] + 1
             and new_native['lifecycle']['backgrounds'] >= old_native['lifecycle']['backgrounds'])

    def read(self):
        value = self.store.read()
        need(type(value) is dict and set(value) == {'restartInputVersion', 'componentOnly', 'oldBinding',
            'oldNative', 'phase', 'newBinding', 'newNative', 'ownerFiles', 'scriptHandoff'}
            and type(value['restartInputVersion']) is int and value['restartInputVersion'] == VERSION
            and type(value['componentOnly']) is bool and value['componentOnly'] == self.component_only
            and value['phase'] in PHASES and value['ownerFiles'] == self.owner_files)
        native(value['oldNative']); self._binding(value['oldBinding'], value['oldNative'])
        if value['scriptHandoff'] is not None:
            plan, _directory = ScriptRestartHandoff(*self.owners, component_only=self.component_only).validate_snapshot(value['scriptHandoff'])
            need(plan['next'] is None and _same(plan['oldFiles']['binding'], value['oldBinding'])
                 and plan['oldNative']['pid'] == value['oldNative']['pid']
                 and plan['oldNative']['instance'] == value['oldNative']['instance'])
        if value['phase'] == 'observed':
            native(value['newNative']); self._new(value['oldBinding'], value['newBinding'], value['oldNative'], value['newNative'])
        else: need(value['newBinding'] is None and value['newNative'] is None)
        return value

    @staticmethod
    def _source(source):
        need(isinstance(source, NativeFeatureObservation))
        value = source.read(source.sequence)
        measured = native(dict(pid=value['processId'], instance=value['instance'], lifecycle=deepcopy(value['lifecycle'])))
        return value, measured

    def capture(self, binding, source, *, handoff=None):
        need(self.store.read() is None)
        original, measured = self._source(source); self._binding(binding, measured)
        plan = None
        if handoff is not None:
            need(isinstance(handoff, ScriptRestartHandoff) and handoff.component_only == self.component_only
                 and tuple(owner.path for owner in self.owners)
                    == (handoff.store.path, handoff.files_store.path, handoff.manager_store.path))
            plan = handoff.snapshot()
            need(plan['next'] is None and _same(plan['oldFiles']['binding'], binding)
                 and plan['oldNative']['pid'] == measured['pid'] and plan['oldNative']['instance'] == measured['instance'])
        self.store.write(dict(restartInputVersion=VERSION, componentOnly=self.component_only,
            oldBinding=deepcopy(binding), oldNative=measured, phase='prepared', newBinding=None,
            newNative=None, ownerFiles=self.owner_files, scriptHandoff=plan), None)
        return original

    def _start(self):
        started = self.monotonic(); need(number(started, 0, 1e15)); return started

    def _bound(self, started, previous):
        now = self.monotonic()
        need(number(now, 0, 1e15) and now >= previous and now - started < 30)
        return now

    def stop(self, deliver):
        value = self.read(); need(value['phase'] == 'prepared' and callable(deliver))
        started = self._start()
        self.store.write(value | {'phase': 'stop-issued'}, value)
        previous = self._bound(started, started)
        try: result = deliver()  # Exactly once; exceptions retain issued intent.
        except Exception: raise RestartDeliveryUncertain('Normal app stop receipt is uncertain') from None
        self._bound(started, previous)
        return result  # Original input receipt only, never process-death proof.

    def launch(self, stopped, deliver):
        value = self.read(); need(value['phase'] == 'stop-issued' and callable(stopped) and callable(deliver))
        started = self._start()
        observed = stopped()  # Separate current OS application-state read.
        need(type(observed) is dict and set(observed) == {'running', 'identity'}
             and observed['running'] is False and observed['identity'] is None)
        previous = self._bound(started, started)
        self.store.write(value | {'phase': 'launch-issued'}, value)
        previous = self._bound(started, previous)
        try: result = deliver()  # Never replay an uncertain launch on reconstruction.
        except Exception: raise RestartDeliveryUncertain('Normal app launch receipt is uncertain') from None
        self._bound(started, previous)
        return result

    def observe(self, binding, source):
        value = self.read(); need(value['phase'] in ('launch-issued', 'observed'))
        # Reject a changed candidate/target before even querying its source.
        context(binding, component_only=self.component_only)
        immutable = {'targetFingerprint'} | (set() if self.component_only else {'sourceRevision', 'artifactSha256'})
        need(all(value['oldBinding'][key] == binding[key] for key in immutable))
        original, measured = self._source(source)
        self._new(value['oldBinding'], binding, value['oldNative'], measured)
        if value['phase'] == 'observed':
            need(value['newBinding'] == binding and measured['pid'] == value['newNative']['pid']
                 and measured['instance'] == value['newNative']['instance']
                 and all(measured['lifecycle'][key] >= count for key, count in value['newNative']['lifecycle'].items()))
        self.store.write(value | dict(phase='observed', newBinding=deepcopy(binding), newNative=measured), value)
        return original  # Measured persisted counters, not increments from requests.

    def retire(self, binding, source):
        # Full feature cleanup must independently establish resource absence.
        # This method retires only input intent after those separate owners
        # have been retired; it neither deletes them nor reports feature success.
        value = self.read(); need(value['phase'] == 'observed')
        self.observe(binding, source)
        value = self.read()
        need(all(owner.read() is None for owner in self.owners) and source.guard() is not False)
        self.store.discard(value)


def run_script_restart(inputs, handoff, source, prepare, stop, stopped, launch, adopt):
    """Compose the original platform seams; recovery never repeats input."""
    need(isinstance(inputs, RestartInputs) and isinstance(handoff, ScriptRestartHandoff)
         and inputs.component_only == handoff.component_only
         and tuple(owner.path for owner in inputs.owners)
            == (handoff.store.path, handoff.files_store.path, handoff.manager_store.path)
         and all(callable(callback) for callback in (source, prepare, stop, stopped, launch, adopt)))
    if inputs.store.read() is None:
        if handoff.store.read() is None: prepare()
        binding, native_source = source()
        inputs.capture(binding, native_source, handoff=handoff)
    value = inputs.read(); need(value['scriptHandoff'] is not None)
    if handoff.store.read() is not None:
        live = handoff.snapshot()
        need(_same(live | {'next': None}, value['scriptHandoff']))
    else:
        need(value['phase'] == 'observed')
    if value['phase'] == 'prepared':
        inputs.stop(stop)
    value = inputs.read()
    if value['phase'] == 'stop-issued':
        inputs.launch(stopped, launch)
    binding, native_source = source()
    original = inputs.observe(binding, native_source)
    value = inputs.read()
    if handoff.store.read() is None:
        handoff.recover_transferred(value['scriptHandoff'], binding, original['processId'], original['instance'])
    proof = adopt()
    need(type(proof) is dict and proof['execution']['processId'] == original['processId']
         and proof['execution']['instance'] == original['instance'])
    return {'native': original, 'handoff': proof}
