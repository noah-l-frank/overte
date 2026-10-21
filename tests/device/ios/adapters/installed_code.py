"""Persistent iOS session/OS/native-byte association, never launch acknowledgments.

Callers supply original process, plugin and nonce-bound native bundle readers.
The journal records intent before launch/termination and retains failed ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time

from adapters.normal_feature_state import context
from ios.adapters.bundle_identity import compare
from ios.adapters.bundle_observation import validate
from adapters.restart_inputs import RestartInputs, validate_native_restart
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_process_presence import NativeProcessPresence

VERSION = 2
READS = (1, 2)
SCOPE = {'sourceRevision', 'artifactSha256', 'sessionId', 'generation', 'targetFingerprint'}
SDK = {'appium': '3.7.0', 'xcuitest': '12.8.0', 'remoteXpc': '5.15.3'}


def need(value):
    if not value:
        raise ValueError('OVT_IOS_INSTALLED_CODE_BINDING_REJECTED')


def source(value):
    need(type(value) is dict and set(value) == {'processSourceVersion', 'source', 'instance',
         'available', 'cleanupPending', 'sdk'}
         and type(value['processSourceVersion']) is int and value['processSourceVersion'] == 1
         and value['source'] == 'dvt-bundle-pid-xcuitest-state'
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and value['available'] is True and value['cleanupPending'] is False
         and type(value['sdk']) is dict and value['sdk'] == SDK)
    return value


class InstalledCodeBinding:
    def __init__(self, store, scope, bundle, process, process_source, native_bundle):
        need(type(scope) is dict and set(scope) == SCOPE)
        context(dict(scope, processIdentity='1'))
        compare(bundle, bundle)
        need(all(callable(v) for v in (process, process_source, native_bundle)))
        self.store, self.scope, self.bundle = store, deepcopy(scope), deepcopy(bundle)
        self.process, self.process_source, self.native_bundle = process, process_source, native_bundle
        self.started = False

    def original_process(self, *, foreground=True):
        value = self.process()
        if value is None:
            return None
        need(type(value) is dict and set(value) == {'bundleId', 'pid', 'foreground'}
             and value['bundleId'] == self.bundle['bundleId'] and type(value['pid']) is int
             and value['pid'] > 0 and type(value['foreground']) is bool
             and (not foreground or value['foreground']))
        return deepcopy(value)

    def record(self):
        value = self.store.read()
        if value is None:
            return None
        need(type(value) is dict and set(value) == {'bindingVersion', 'phase', 'scope',
             'source', 'process', 'observation', 'previousInstance'}
             and type(value['bindingVersion']) is int and value['bindingVersion'] in READS
             and value['scope'] == self.scope and value['phase'] in
             ('preparing', 'bound', 'retiring', 'retired'))
        previous = value['previousInstance']
        need(previous is None or type(previous) is str and re.fullmatch('[0-9a-f]{32}', previous))
        context(dict(value['scope'], processIdentity='1'))
        if value['phase'] == 'preparing':
            need(all(value[k] is None for k in ('process', 'observation')))
            if value['bindingVersion'] == 1: need(value['source'] is None)
            else: source(value['source'])
        else:
            source(value['source'])
            observed, process = value['observation'], value['process']
            need(type(process) is dict and set(process) == {'bundleId', 'pid', 'foreground'}
                 and process['bundleId'] == self.bundle['bundleId'] and type(process['pid']) is int
                 and process['pid'] > 0 and process['foreground'] is True)
            self.observation(observed, process['pid'])
        return value

    def observation(self, value, pid):
        need(type(value) is dict)
        validate(value, dict(schemaVersion=1, commandId=value.get('commandId'), action='ios-bundle-observe'), pid)
        need(value['status'] == 'ready')
        compare(value['bundle'], self.bundle)
        return value

    def begin(self):
        previous = self.record()
        need(previous is None or previous['phase'] == 'retired')
        if previous is not None: self.retired_absence()
        provenance = deepcopy(source(self.process_source()))
        need(previous is None or provenance == previous['source'])
        # The caller must journal this before the controlled launch. An existing
        # process may only be handled by the original controlled-launch path.
        current = dict(bindingVersion=VERSION, phase='preparing', scope=deepcopy(self.scope),
                       source=provenance, process=None, observation=None,
                       previousInstance=previous['observation']['instance'] if previous else None)
        self.store.write(current, previous)
        self.started = True

    def bind(self):
        previous = self.record()
        need(self.started and previous is not None and previous['phase'] == 'preparing'
             and previous['bindingVersion'] == VERSION)
        provenance = deepcopy(source(self.process_source()))
        need(provenance == previous['source'])
        process = self.original_process()
        need(process is not None)
        observed = deepcopy(self.observation(self.native_bundle(), process['pid']))
        need(observed['instance'] != previous['previousInstance'])
        need(self.original_process() == process and source(self.process_source()) == provenance)
        current = dict(previous, phase='bound', source=provenance, process=process, observation=observed)
        self.store.write(current, previous)
        self.started = False
        return self._claim()

    def preparing_continuity(self, pid):
        """Read-only continuity for a separately proven recovery readiness read."""
        previous = self.record()
        need(previous is not None and previous['bindingVersion'] == VERSION and previous['phase'] == 'preparing'
             and type(pid) is int and pid > 0 and source(self.process_source()) == previous['source'])
        actual = self.original_process()
        need(actual is not None and actual['pid'] == pid and source(self.process_source()) == previous['source'])
        return actual

    def recover_prepared(self, inputs, native, presence, ready, *, monotonic=time.monotonic):
        try:
            return self._recover_prepared(inputs, native, presence, ready, monotonic)
        except Exception:
            raise ValueError('OVT_IOS_INSTALLED_CODE_BINDING_REJECTED') from None

    def _recover_prepared(self, inputs, native, presence, ready, monotonic):
        # Explicit restart recovery only; ordinary new-CLI bind still refuses.
        # No SDK input or session creation occurs in this transaction.
        need(isinstance(inputs, RestartInputs) and inputs.component_only
             and isinstance(native, NativeFeatureObservation) and isinstance(presence, NativeProcessPresence)
             and callable(ready) and callable(monotonic))
        started = previous_clock = monotonic()
        def bound():
            nonlocal previous_clock
            now = monotonic(); need(now >= previous_clock and now - started < 30)
            previous_clock = now
        previous = self.record(); intent = inputs.read()
        need(previous is not None and previous['bindingVersion'] == VERSION and previous['phase'] == 'preparing'
             and intent['phase'] == 'launch-issued' and inputs.store.path.parent == self.store.path.parent
             and intent['oldBinding']['targetFingerprint'] == self.scope['targetFingerprint']
             and intent['oldBinding']['generation'] == self.scope['generation']
             and native.pid == presence.pid and native.pid != intent['oldNative']['pid'])
        bound()
        process = self.preparing_continuity(native.pid); bound()
        def verify(packet):
            validate_native_restart(intent['oldNative'], dict(pid=packet['processId'], instance=packet['instance'],
                lifecycle=packet['lifecycle']))
        first = native.read(native.sequence); verify(first); bound()
        exited = presence.require_absent(intent['oldNative']['pid']); bound()
        need(exited['instance'] == first['instance'])
        observed = deepcopy(self.observation(self.native_bundle(), native.pid)); bound()
        need(observed['instance'] != previous['previousInstance']
             and observed['capturedEpochMs'] >= first['capturedEpochMs'])
        need(self.preparing_continuity(native.pid) == process and inputs.read() == intent
             and self.record() == previous); bound()
        # The physical caller must run its original fresh first-probe check and
        # save actual launch flags here, before binding becomes publicly usable.
        ready(deepcopy(process), first['capturedEpochMs']); bound()
        final = native.read(native.sequence); verify(final); bound()
        need(final['instance'] == first['instance'] and final['capturedEpochMs'] >= exited['capturedEpochMs']
             and self.preparing_continuity(native.pid) == process and inputs.read() == intent
             and self.record() == previous); bound()
        self.store.write(dict(previous, phase='bound', process=process, observation=observed), previous)
        bound()
        return self._claim()

    def _claim(self):
        record = self.record()
        need(record is not None and record['phase'] == 'bound')
        return dict(schemaVersion=1, sourceRevision=self.scope['sourceRevision'],
                    artifactSha256=self.scope['artifactSha256'], installedCandidateVerified=True)

    def continuity(self, *, allow_background=False):
        return self._continuity('bound', allow_background=allow_background)

    def retirement_continuity(self):
        return self._continuity('retiring', allow_background=True)

    def _continuity(self, phase, *, allow_background=False):
        previous = self.record()
        need(previous is not None and previous['phase'] == phase)
        need(source(self.process_source()) == previous['source'])
        process = self.original_process(foreground=not allow_background)
        need(process is not None and process['pid'] == previous['process']['pid'])
        need(source(self.process_source()) == previous['source'])
        return process

    def verify(self):
        previous = self.record()
        self.continuity()
        observed = deepcopy(self.observation(self.native_bundle(), previous['process']['pid']))
        old = previous['observation']
        need(observed['instance'] == old['instance'] and observed['preparedEpochMs'] == old['preparedEpochMs']
             and observed['sequence'] > old['sequence'] and observed['capturedEpochMs'] >= old['capturedEpochMs']
             and observed['commandId'] != old['commandId'])
        self.continuity()
        self.store.write(dict(previous, observation=observed), previous)
        return self._claim()

    def begin_retirement(self):
        previous = self.record()
        self.continuity(allow_background=True)
        self.store.write(dict(previous, phase='retiring'), previous)

    def finish_retirement(self):
        previous = self.record()
        need(previous is not None and previous['phase'] == 'retiring')
        need(source(self.process_source()) == previous['source'] and self.original_process(foreground=False) is None)
        need(source(self.process_source()) == previous['source'])
        self.store.write(dict(previous, phase='retired'), previous)


    def retired_absence(self):
        previous = self.record()
        need(previous is not None and previous['phase'] == 'retired')
        need(source(self.process_source()) == previous['source'])
        need(self.original_process(foreground=False) is None)
        need(source(self.process_source()) == previous['source'])

