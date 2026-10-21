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
from adapters.restart_inputs import RestartInputs, validate_native_restart, native as validate_restart_native
from adapters.native_feature_observation import NativeFeatureObservation, number, validate as validate_native
from adapters.native_process_presence import NativeProcessPresence, validate as validate_presence

VERSION = 4
READS = (1, 2, 3, 4)
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
        fields = {'bindingVersion', 'phase', 'scope', 'source', 'process', 'observation', 'previousInstance'}
        need(type(value) is dict)
        if value.get('bindingVersion') in (3, 4): fields.add('recovery')
        need(set(value) == fields
             and type(value['bindingVersion']) is int and value['bindingVersion'] in READS
             and value['scope'] == self.scope and value['phase'] in
             ('preparing', 'bound', 'retiring', 'retired'))
        if value['bindingVersion'] in (3, 4):
            need(value['recovery'] is None or value['phase'] in ('bound', 'retiring', 'retired'))
            if value['recovery'] is not None:
                need(type(value['recovery']) is dict)
                need(value['bindingVersion']!=3 or value['recovery'].get('launchRecoveryVersion')==1)
                self._recovery_proof(value)
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
                       previousInstance=previous['observation']['instance'] if previous else None, recovery=None)
        self.store.write(current, previous)
        self.started = True

    def bind(self):
        previous = self.record()
        need(self.started and previous is not None and previous['phase'] == 'preparing'
             and previous['bindingVersion'] in (2, 3, VERSION))
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
        need(previous is not None and previous['bindingVersion'] in (2, 3, VERSION) and previous['phase'] == 'preparing'
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
        need(isinstance(inputs, RestartInputs)
             and isinstance(native, NativeFeatureObservation) and isinstance(presence, NativeProcessPresence)
             and native.ios and presence.ios and callable(ready) and callable(monotonic))
        started = previous_clock = monotonic(); need(number(started, 0, 1e15))
        def bound():
            nonlocal previous_clock
            now = monotonic(); need(number(now, 0, 1e15) and now >= previous_clock and now - started < 30)
            previous_clock = now
        previous = self.record(); intent = inputs.read()
        need(previous is not None and previous['bindingVersion'] in (2, 3, VERSION) and previous['phase'] == 'preparing'
             and previous['previousInstance'] is not None
             and intent['phase'] == 'launch-issued' and inputs.store.path.parent == self.store.path.parent
             and intent['oldBinding']['targetFingerprint'] == self.scope['targetFingerprint']
             and intent['oldBinding']['generation'] == self.scope['generation']
             and native.pid == presence.pid and native.pid != intent['oldNative']['pid'])
        if not inputs.component_only:
            need(all(intent['oldBinding'][key] == self.scope[key] for key in ('sourceRevision', 'artifactSha256', 'sessionId')))
        bound()
        process = self.preparing_continuity(native.pid); bound()
        def verify(packet):
            validate_native_restart(intent['oldNative'], dict(pid=packet['processId'], instance=packet['instance'],
                lifecycle=packet['lifecycle']))
        first = native.read(native.sequence); verify(first); bound()
        exited = presence.require_absent(intent['oldNative']['pid']); bound()
        need(exited['instance'] == first['instance'] and exited['capturedEpochMs'] >= first['capturedEpochMs'])
        observed = deepcopy(self.observation(self.native_bundle(), native.pid)); bound()
        need(observed['instance'] != previous['previousInstance']
             and observed['capturedEpochMs'] >= first['capturedEpochMs'])
        need(self.preparing_continuity(native.pid) == process and inputs.read() == intent
             and self.record() == previous); bound()
        # The physical caller must run its original fresh first-probe check and
        # save actual launch flags here, before binding becomes publicly usable.
        ready(deepcopy(process), first['capturedEpochMs']); bound()
        final = native.read(native.sequence); verify(final); bound()
        need(final['instance'] == first['instance'] and final['capturedEpochMs'] >= max(exited['capturedEpochMs'], observed['capturedEpochMs'])
             and self.preparing_continuity(native.pid) == process and inputs.read() == intent
             and self.record() == previous); bound()
        recovery = dict(launchRecoveryVersion=1 if inputs.component_only else 2, oldBinding=deepcopy(intent['oldBinding']),
            oldNative=deepcopy(intent['oldNative']), firstNative=first, oldProcessAbsent=exited,
            bundleObservation=deepcopy(observed), finalNative=final)
        if not inputs.component_only: recovery['componentOnly'] = False
        current = dict(previous, bindingVersion=VERSION, phase='bound', process=process, observation=observed, recovery=recovery)
        self._recovery_proof(current)
        self.store.write(current, previous)
        bound()
        return self._claim()

    def _recovery_proof(self, record):
        proof = record['recovery']
        need(type(proof) is dict and type(proof.get('launchRecoveryVersion')) is int and proof['launchRecoveryVersion'] in (1, 2))
        component = proof['launchRecoveryVersion'] == 1
        need(set(proof) == {'launchRecoveryVersion', 'oldBinding',
            'oldNative', 'firstNative', 'oldProcessAbsent', 'bundleObservation', 'finalNative'} | (set() if component else {'componentOnly'})
            and (component or proof['componentOnly'] is False))
        old = validate_restart_native(proof['oldNative'])
        binding = context(proof['oldBinding'], component_only=component)
        if not component:
            need(all(binding[key] == self.scope[key] for key in ('sourceRevision', 'artifactSha256', 'sessionId')))
        need(binding['targetFingerprint'] == self.scope['targetFingerprint']
             and binding['generation'] == self.scope['generation']
             and binding['processIdentity'] == str(old['pid']))
        first, final, absence = proof['firstNative'], proof['finalNative'], proof['oldProcessAbsent']
        bundle = self.observation(proof['bundleObservation'], record['process']['pid'])
        need(record['observation']['instance'] == bundle['instance']
             and record['observation']['preparedEpochMs'] == bundle['preparedEpochMs']
             and record['observation']['sequence'] >= bundle['sequence']
             and record['observation']['capturedEpochMs'] >= bundle['capturedEpochMs'])
        for packet in (first, final):
            validate_native(packet, packet.get('requestId'), record['process']['pid'], packet.get('capturedEpochMs'))
            validate_native_restart(old, dict(pid=packet['processId'], instance=packet['instance'], lifecycle=packet['lifecycle']))
        request = dict(schemaVersion=1, commandId=absence.get('commandId'), action='feature-process-presence', queryProcessId=old['pid'])
        validate_presence(absence, request, record['process']['pid'], absence.get('capturedEpochMs'))
        need(absence['presence'] == 'absent' and first['instance'] == absence['instance'] == final['instance']
             and final['sequence'] > first['sequence'] and final['requestId'] != first['requestId']
             and first['capturedEpochMs'] <= absence['capturedEpochMs'] <= final['capturedEpochMs']
             and first['capturedEpochMs'] <= bundle['capturedEpochMs'] <= final['capturedEpochMs']
             and all(final['lifecycle'][key] >= count for key, count in first['lifecycle'].items()))

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

