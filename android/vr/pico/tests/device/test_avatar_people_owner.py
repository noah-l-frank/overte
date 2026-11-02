"""Real Parent/People journals and original Pal engines; SDK/QML are models.

No compiler, installed product, account service, real ray or device is used.
The original complete Pal/protocol JavaScript runs in separate VM contexts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import traceback
import unittest
from unittest.mock import patch
import uuid

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT / 'tests/device'), str(HERE)]
import test_avatar_parent_owner as parent_fixture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.avatar_people import PicoAvatarPeople, consent
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI, project, same_reference
from adapters.pico4.avatar_state import NativePicoAvatarState
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.scenarios import VERSION

PEER = '22222222-2222-4222-8222-222222222222'


class AvatarPeopleOwnerTests(unittest.TestCase):
    def setUp(self):
        self.parent_case = parent_fixture.AvatarParentOwnerTests(methodName='runTest')
        self.parent_case.setUp(); self.addCleanup(self.parent_case.doCleanups)
        self.f = self.parent_case.f; f = self.f
        if os.environ.get('OVERTE_AVATAR_PEOPLE_ARTIFACTS'):
            temporary = f.fixture.fixture.fixture.fixture.temporary
            temporary._finalizer.detach()
            temporary.cleanup = lambda: None
        self.host = subprocess.Popen(['node', str(HERE / 'avatar-people-protocol-host.js'), f.source['sessionId'], PEER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.addCleanup(self.close_host)
        self.sent, self.received, self.sequence, self.native_sequence = [], [], dict(primary=0, peer=0), dict(primary=0, peer=0)
        self.ignore = None; self.replace_request_id = False; self.guard_delay = None; self.sleep_records = []; self.stall_on_wait = False
        self.malformed_role = None
        self.replace_parent_at_issue = False
        self.peer_lock = ScriptSourceLock(f.root / 'peer-script-sources.lock')
        if os.environ.get('OVERTE_AVATAR_PEOPLE_DIAGNOSTICS') == '1':
            original_lock = ScriptSourceLock.held
            @contextmanager
            def traced_lock(lock):
                with original_lock(lock):
                    try:
                        yield
                    except Exception:
                        traceback.print_exc()
                        raise
            self.enterContext(patch.object(ScriptSourceLock, 'held', traced_lock))
        with f.lock.held():
            self.parent = f.instance._avatar_parent(f.target, parent_fixture.favorite_fixture.RUN, source_lock=f.lock)
        primary = deepcopy(self.parent.binding)
        peer = dict(primary, processIdentity='456:200', sessionId='99999999-9999-4999-8999-999999999999', targetFingerprint='8' * 64)
        self.bindings = dict(primary=primary, peer=peer)
        key = self.parent.key; self.store = PrivateFeatureState(f.root / ('avatar-people-owner-' + key + '-' + self.parent.run + '.json'))
        self.roles = {}
        for role in ('primary', 'peer'):
            self.roles[role] = dict(binding=self.bindings[role], lock=f.lock if role == 'primary' else self.peer_lock,
                native=lambda role=role: self.native(role), widgets=lambda role=role: self.widgets(role),
                controls=lambda intent, before_send, role=role: self.controls(role, intent, before_send),
                guard=lambda role=role: self.guard(role))
        def factory():
            return PicoAvatarPeople(self.store, primary, f.phase, f.lock, self.roles,
                monotonic=lambda: f.clock, sleep=self.sleep)
        self.parent.people_factory = factory

    def rpc(self, **command):
        self.sent.append(deepcopy(command)); self.host.stdin.write(json.dumps(command) + '\n'); self.host.stdin.flush()
        with selectors.DefaultSelector() as ready:
            ready.register(self.host.stdout, selectors.EVENT_READ)
            if not ready.select(5):
                self.fail('Original Pal host did not return within five seconds')
        raw = self.host.stdout.readline()
        if not raw:
            self.fail('Original Pal host exited: ' + self.host.stderr.read())
        self.received.append(raw)
        return json.loads(raw)

    def close_host(self):
        if self.host.poll() is None:
            result = self.rpc(operation='stop')
            self.assertEqual(0, result['timers']); self.assertEqual([], result['posts'])
            self.assertEqual([], result['subscriptions']['primary']); self.assertEqual([], result['subscriptions']['peer'])
            self.host.wait(timeout=5)
        for stream in (self.host.stdin, self.host.stdout, self.host.stderr):
            stream.close()
        if os.environ.get('OVERTE_AVATAR_PEOPLE_ARTIFACTS'):
            destination = Path(os.environ['OVERTE_AVATAR_PEOPLE_ARTIFACTS']) / (self._testMethodName + '-' + uuid.uuid4().hex)
            destination.mkdir(mode=0o700)
            (destination / 'transport-requests.json').write_text(json.dumps(self.sent, indent=2) + '\n')
            (destination / 'transport-replies.jsonl').write_text(''.join(self.received))
            (destination / 'source-state.json').write_text(json.dumps(dict(sourceRoot=str(self.f.root),
                files={str(p.relative_to(self.f.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in self.f.root.rglob('*') if p.is_file() and not p.is_symlink()}), indent=2) + '\n')

    def guard(self, role):
        lock = self.roles[role]['lock']; lock.assert_held()
        if self.guard_delay is not None:
            callback, self.guard_delay = self.guard_delay, None; callback(role)
        return True

    def sleep(self, seconds):
        self.assertIsNone(self.f.lock._owner); self.assertIsNone(self.peer_lock._owner)
        self.sleep_records.append(seconds)
        if self.stall_on_wait:
            seconds += 20; self.stall_on_wait = False
        self.f.sleep(seconds); self.rpc(operation='advance', ms=round(seconds * 1000))

    def native(self, role):
        packet = {}
        def send(request):
            self.roles[role]['lock'].assert_held(); self.native_sequence[role] += 1
            value = deepcopy(self.f.source); value['sessionId'] = self.f.source['sessionId'] if role == 'primary' else PEER
            for name in ('avatarLoads', 'modelLoads'):
                value[name]['sequence'] = self.native_sequence[role]
                value[name]['capturedEpochMs'] = self.f.epoch
            if role == 'peer':
                value['modelInstance'] = '7' * 32
            packet.update(schemaVersion=1, requestId=request['commandId'], instance=('c' if role == 'primary' else 'd') * 32,
                sequence=self.native_sequence[role], processId=123 if role == 'primary' else 456,
                requestedEpochMs=self.f.epoch, capturedEpochMs=self.f.epoch, source=value)
            if self.malformed_role == role:
                packet['source'] = {}
        return NativePicoAvatarState(send, lambda: json.dumps(packet), lambda: self.f.epoch,
            lambda: self.guard(role), 123 if role == 'primary' else 456, monotonic=lambda: self.f.clock, sleep=self.sleep)

    def widgets(self, role):
        self.roles[role]['lock'].assert_held(); state = self.rpc(operation='capture')[role]
        current = deepcopy(state['state'])
        if self.replace_request_id and role == 'peer' and current['phase'] == 'incoming':
            current['requestId'] = '33333333-3333-4333-8333-333333333333'
        controls = []
        def add(identifier, **extra):
            row = dict(id=identifier, enabled=True, focused=False)
            if not identifier.startswith('tablet.'):
                row.update(inputReady=not identifier.endswith('.page'))
                if identifier != 'people.entry':
                    row.update(consent=deepcopy(current), tab='nearbyTab')
            row.update(extra)
            row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(row, sort_keys=True)))
            controls.append(row)
        add('tablet.home')
        if not state['open']:
            add('people.entry')
        else:
            add('people.page'); add('people.nearby')
            add('people.row.0', peerSession='{' + (PEER if role == 'primary' else self.f.source['sessionId']) + '}', userName='')
            if current['phase'] == 'idle':
                add('people.RequestConnection')
            elif current['phase'] == 'incoming':
                add('people.ConnectionAccept'); add('people.ConnectionDecline')
            else:
                add('people.ConnectionCancel')
        return dict(schemaVersion=1, bridgeId=self.bindings[role]['sessionId'], generation='55555555-5555-4555-8555-555555555555',
            processId=123 if role == 'primary' else 456, elapsedMs=round(self.f.clock * 1000), updatedEpochMs=self.f.epoch,
            lastCommandSequence=self.sequence[role], open=True, ready=True, controls=controls, avatarPeopleControlsVersion=1)

    def controls(self, role, intent, before_send):
        fixture = self
        class IO:
            def capture(self):
                return project(fixture.widgets(role))
            def input(self, identifier, action, reference, **args):
                current = self.capture(); row = same_reference(reference, current, identifier)
                s = reference['scope']
                command = dict(schemaVersion=1, commandId=uuid.uuid4().hex, bridgeId=s['instance'], generation=s['generation'],
                    sequence=s['sequence'] + 1, observedElapsedMs=s['elapsedMs'], controlId=identifier,
                    controlToken=row['token'], action=action)
                if fixture.replace_parent_at_issue:
                    fixture.replace_parent_at_issue = False
                    original = fixture.parent.store.path
                    replacement = original.with_name('same-byte-parent-' + uuid.uuid4().hex)
                    replacement.write_bytes(original.read_bytes()); replacement.chmod(0o600)
                    os.replace(replacement, original)
                before_send(command, self)
                if fixture.ignore != identifier:
                    fixture.rpc(operation='input', role=role, control=identifier)
                fixture.sequence[role] += 1
        return TokenAvatarPeopleUI(IO(), intent, monotonic=lambda: self.f.clock, sleep=self.sleep)

    def request(self, verb):
        inputs = dict(peer='owned-peer') if verb == 'connection-request' else {}
        ticket = self.f.activate(verb, inputs)
        return dict(contractVersion=VERSION, runId=self.parent.run, fixtureUrl=self.f.phase.fixture_url,
                    ticket=ticket, verb=verb, inputs=inputs)

    def act(self, request):
        with self.f.lock.held():
            self.parent.reserve_people(request)
        receipt = self.parent.execute_people(request)
        with self.f.lock.held():
            return self.parent.complete_people(request, receipt)

    def test_original_two_pal_request_cancel_and_both_close_join_same_parent(self):
        request = self.request('connection-request'); self.assertEqual(dict(performed=True), self.act(request))
        original = self.rpc(operation='capture')
        self.assertEqual('outgoing', original['primary']['state']['phase']); self.assertEqual('incoming', original['peer']['state']['phase'])
        self.assertEqual(original['primary']['state']['requestId'], original['peer']['state']['requestId'])
        self.assertEqual([], original['posts'])
        cancel = self.request('connection-cancel'); self.assertEqual(dict(performed=True), self.act(cancel))
        final = self.rpc(operation='capture')
        self.assertEqual('idle', final['primary']['state']['phase']); self.assertEqual('idle', final['peer']['state']['phase'])
        self.assertEqual(0, final['timers']); self.assertEqual([], final['posts'])
        self.assertEqual([dict(role='primary', control='people.ConnectionCancel')] * 2 +
                         [dict(role='peer', control='people.ConnectionCancel')],
                         [r for r in final['controls'] if r['control'] == 'people.ConnectionCancel'])
        self.assertGreaterEqual(sum(self.sleep_records), 3)
        self.assertEqual(2, self.parent.store.read()['picoAvatarParentVersion'])
        self.assertEqual(['people', 'people'], [r['child']['kind'] for r in self.parent.state['calls']])
        self.assertTrue(self.f.instance._avatar_parent_owned(self.f.target))
        self.assertIsNotNone(self.store.read())

    def test_ignored_request_stays_pending_and_cannot_resend(self):
        self.ignore = 'people.RequestConnection'; self.stall_on_wait = True; request = self.request('connection-request')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        count = len(self.parent.people_instance.state['inputs'])
        with self.assertRaises((ValueError, RuntimeError)):
            self.parent.execute_people(request)
        self.assertEqual(count, len(self.parent.people_instance.state['inputs']))
        self.assertEqual(request['ticket'], self.parent.state['pending'])
        self.assertFalse(self.rpc(operation='capture')['posts'])

    def test_foreign_peer_request_id_is_not_observed_as_matching_consent(self):
        self.replace_request_id = True; self.stall_on_wait = True; request = self.request('connection-request')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        self.assertEqual(request['ticket'], self.parent.state['pending'])
        owner = self.parent.people_instance
        self.assertTrue(any(consent(f['roles']['peer']['widgets']) is not None
                            and consent(f['roles']['peer']['widgets'])['phase'] == 'incoming' for f in owner.state['frames']))
        self.assertIsNone(owner.state['calls'][-1]['after'])

    def test_holding_primary_lock_cannot_execute_or_wait_on_peer(self):
        request = self.request('connection-request')
        with self.f.lock.held():
            self.parent.reserve_people(request)
            with self.assertRaises((ValueError, RuntimeError)):
                self.parent.execute_people(request)
        self.assertFalse(any(r.get('operation') == 'input' for r in self.sent))

    def test_reused_target_binding_refuses_before_any_peer_source(self):
        self.roles['peer']['binding'] = deepcopy(self.bindings['primary'])
        request = self.request('connection-request')
        with self.f.lock.held(), self.assertRaises((ValueError, RuntimeError)):
            self.parent.reserve_people(request)
        self.assertEqual([], self.sent)

    def test_frozen_native_clock_cannot_refresh_child_consent_at_parent_completion(self):
        request = self.request('connection-request')
        with self.f.lock.held():
            self.parent.reserve_people(request)
        receipt = self.parent.execute_people(request)
        count = len(self.parent.people_instance.state['inputs'])
        self.f.freeze = True; self.f.sleep(2)
        with self.f.lock.held(), self.assertRaises((ValueError, RuntimeError)):
            self.parent.complete_people(request, receipt)
        durable = unpack(self.parent.store.read()['payload'])[0]
        self.assertEqual(request['ticket'], durable['pending'])
        self.assertIsNone(durable['calls'][-1]['after'])
        self.assertEqual(count, len(self.parent.people_instance.state['inputs']))

    def test_cold_parent_receipt_reopens_full_originals_without_resending(self):
        request = self.request('connection-request'); self.act(request)
        count = len(self.parent.people_instance.state['inputs'])
        p = self.parent
        with self.f.lock.held():
            cold = type(p)(p.store, p.binding, p.phase, p.lock, p.urls, p.favorites, p.sources, p.guard,
                           people=p.people_factory, monotonic=p.monotonic)
            self.assertEqual(2, cold.version)
            self.assertEqual(p.state, cold.state)
            self.assertEqual(count, len(cold.people_instance.state['inputs']))
        self.assertEqual(count, len(self.parent.people_instance.state['inputs']))

    def test_pre_input_pair_cannot_replace_the_parent_child_receipt(self):
        request = self.request('connection-request'); self.act(request)
        p = self.parent; owner = p.people_instance
        with self.f.lock.held():
            record = p.store.read(); state = unpack(record['payload'])[0]
            state['calls'][-1]['child']['frame'] = owner.archive.frame_reference(owner.state['frames'][0])
            from adapters.script_journey.history import pack
            p.store.write(dict(record, payload=pack([state])), record)
            with self.assertRaises((ValueError, RuntimeError)):
                type(p)(p.store, p.binding, p.phase, p.lock, p.urls, p.favorites, p.sources, p.guard,
                        people=p.people_factory, monotonic=p.monotonic)

    def test_unavailable_peer_native_raw_is_retained_before_reader_refusal(self):
        self.malformed_role = 'peer'; request = self.request('connection-request')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        owner = self.parent.people_instance; role = owner.role_store('peer').read()
        self.assertEqual(1, len(role['raws'])); self.assertEqual([], role['frames'])
        original = owner.archive.frame_original(role['raws'][0])
        self.assertEqual({}, json.loads(original['raw'])['source'])
        self.assertFalse(any(row.get('operation') == 'input' for row in self.sent))
        self.assertEqual(request['ticket'], self.parent.state['pending'])

    def test_same_byte_parent_replacement_before_first_issue_sends_no_input(self):
        self.replace_parent_at_issue = True; request = self.request('connection-request')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        owner = self.parent.people_instance
        self.assertEqual(request['ticket'], self.parent.state['pending'])
        self.assertTrue(owner.state['inputs']); self.assertIsNone(owner.state['inputs'][-1]['command'])
        self.assertFalse(any(row.get('operation') == 'input' for row in self.sent))
        with self.assertRaises((ValueError, RuntimeError)):
            self.parent.execute_people(request)
        self.assertFalse(any(row.get('operation') == 'input' for row in self.sent))


if __name__ == '__main__':
    unittest.main()
