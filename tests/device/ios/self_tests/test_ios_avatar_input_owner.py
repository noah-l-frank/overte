"""Real private durable files and HTTP/AFC logic; synthetic original Qt state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import avatar_controls as controls, normal_input
from ios.adapters.avatar_input_owner import AvatarInputOwner, AvatarInputPending
from ios.self_tests.test_ios_avatar_controls import Boundary

RUN, TICKET = 'a'*32, 'b'*32
FIXTURE = 'http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
BINDING = dict(sourceRevision='a'*40, artifactSha256='b'*64, processIdentity='42', sessionId='actual-session',
               generation=1, targetFingerprint='c'*64)
CALL = dict(contractVersion=16, runId=RUN, ticket=TICKET, fixtureUrl=FIXTURE, verb='avatar-url', inputs=dict(resource='avatar-a.fst'))


class InputOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name); os.chmod(self.path, 0o700)
        self.store = PrivateFeatureState(self.path/'ios-avatar-primary-inputs.json')
        self.lock = ScriptSourceLock(self.path/'sources.lock')
        self.source = Boundary(); self.native = self.source.input(); self.io = controls.IOSAvatarIO(self.native)
    def owner(self, **changes):
        return AvatarInputOwner(self.store, self.lock, changes.get('binding', BINDING), RUN, 'primary', FIXTURE, lambda: True)
    def ui(self, owner):
        return controls.AvatarUI(self.io, owner.intent, delivered=owner.delivered, observed=owner.observed,
            monotonic=lambda: self.source.clock, sleep=lambda seconds: setattr(self.source, 'clock', self.source.clock+seconds))
    def test_original_UUID_reference_delivery_and_readback_are_durable_before_action_return(self):
        owner = self.owner()
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            self.assertTrue(owner.begin(CALL)); self.ui(owner).avatar_url('https://controlled.invalid/avatar-a.fst')
            self.assertEqual({'performed': True}, owner.finish())
            restored = self.owner(); state = restored.load()
            self.assertFalse(restored.begin(CALL))
        events = state['calls'][0]['events']; self.assertTrue(events)
        for event in events:
            self.assertEqual('observed', event['phase']); self.assertEqual(event['intent']['nativeCommand'], event['delivery']['command'])
            self.assertEqual(event['intent']['nativeCommand']['sequence'], event['observed']['scope']['sequence'])
        self.assertEqual(0o600, self.store.path.stat().st_mode & 0o777)
        self.assertNotIn('avatar', state)  # Input ownership never supplies a measured model outcome.
    def test_lost_actual_return_retains_original_intent_and_blocks_all_replay_after_reconstruction(self):
        owner = self.owner(); self.source.lost = True
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            owner.begin(CALL)
            with self.assertRaises(NativeUIError): self.ui(owner).input('avatar.url-open')
            restored = self.owner(); state = restored.load(); event = state['calls'][0]['events'][0]
            self.assertEqual('issued', event['phase']); self.assertIsNone(event['delivery'])
            self.assertEqual(self.source.requests[-1]['input'], event['intent']['nativeCommand'])
            count = len(self.source.requests)
            for query in (CALL, CALL | dict(ticket='d'*32)):
                with self.assertRaises(AvatarInputPending): restored.begin(query)
            self.assertEqual(count, len(self.source.requests)); self.assertTrue(self.store.path.exists())
    def test_ACK_then_lost_UI_read_retains_delivery_without_inventing_readback(self):
        owner = self.owner()
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            owner.begin(CALL); ui = self.ui(owner)
            original = owner.delivered
            def delivered(intent, receipt):
                original(intent, receipt)
                self.source.mutation = 'foreign-instance'
            ui.delivered = delivered
            with self.assertRaises(NativeUIError): ui.input('avatar.url-open')
            state = self.owner().load(); event = state['calls'][0]['events'][0]
            self.assertEqual('acknowledged', event['phase']); self.assertIsNotNone(event['delivery']); self.assertIsNone(event['observed'])
            with self.assertRaises(NativeUIError): self.owner().begin(CALL)
    def test_store_failure_prevents_delivery_and_original_event_cannot_be_forged_as_complete(self):
        owner = self.owner()
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            owner.begin(CALL)
            with patch.object(self.store, 'write', side_effect=NativeUIError('Storage unavailable')):
                with self.assertRaises(NativeUIError): self.ui(owner).input('avatar.url-open')
            self.assertFalse(any(row['operation'] == 'edit' for row in self.source.requests))
            state = self.owner().load(); self.assertEqual([], state['calls'][0]['events'])
    def test_wrong_candidate_and_reused_ticket_with_different_action_are_rejected(self):
        owner = self.owner()
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            owner.begin(CALL); self.ui(owner).input('avatar.url-open'); owner.finish()
            with self.assertRaises(NativeUIError): self.owner(binding=BINDING | dict(artifactSha256='d'*64)).load()
            with self.assertRaises(NativeUIError): self.owner().begin(CALL | dict(inputs=dict(resource='missing.fst')))
    def test_full_original_delivery_and_consumed_sequence_survive_copy_and_detect_tampering(self):
        owner = self.owner()
        with self.lock.held(), patch.object(normal_input, 'urlopen', self.source.post):
            owner.begin(CALL); self.ui(owner).input('avatar.url-open'); owner.finish()
            state = owner.load()
            for fault in ('pid', 'nonce', 'query', 'sequence', 'effect', 'timestamp'):
                altered = deepcopy(state); event = altered['calls'][0]['events'][0]
                if fault == 'pid': event['delivery']['originalReceipt']['status']['processId'] = 43
                elif fault == 'nonce': event['delivery']['originalReceipt']['status']['commandId'] = 'ffffffff-ffff-4fff-8fff-ffffffffffff'
                elif fault == 'query': event['intent']['nativeCommand']['fieldToken'] = 'ffffffff-ffff-4fff-8fff-ffffffffffff'
                elif fault == 'sequence': event['observed']['scope']['sequence'] += 1
                elif fault == 'timestamp': event['delivery']['originalReceipt']['status']['sampleEpochMs'] = 1
                else: event['delivery']['avatarLoaded'] = True
                with self.subTest(fault=fault), self.assertRaises(NativeUIError): owner.decode(owner.envelope(altered))


if __name__ == '__main__': unittest.main()
