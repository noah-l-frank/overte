"""Real durable Create journals and NativeInput HTTP/AFC with SDK seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import create_action_owner as source
from ios.adapters.create_inputs import IOSCreateUI
from ios.self_tests import test_ios_create_controls as controls_tests
from ios.self_tests.test_ios_create_files import BINDING, RUN, URL

QUERY = dict(contractVersion=16,runId=RUN,ticket='b'*32,fixtureUrl=URL,verb='open',inputs={})


class CreateActionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.harness = controls_tests.IOSCreateControlsTests(); self.harness.setUp(); self.addCleanup(self.harness.doCleanups)
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name); self.path.chmod(0o700)
        self.store = PrivateFeatureState(self.path/'ios-create-inputs.json'); self.lock = ScriptSourceLock(self.path/'script-feature-sources.lock')
        self.native = self.harness.flow.io.original.native

    def owner(self,binding=BINDING):
        owner = source.CreateActionOwner(self.store,self.lock,binding,RUN,URL,self.native._check); owner.load(); return owner
    def ui(self,owner):
        return IOSCreateUI(source.CreateBoundIO(self.native,owner),self.harness.widget.intents.append,
                           monotonic=lambda:self.harness.world.clock,sleep=self.harness.world.sleep)

    def test_actual_command_original_and_consumed_widget_cursor_survive_reconstruction(self):
        with self.lock.held():
            owner = self.owner(); owner.begin(QUERY); ui = self.ui(owner)
            ui.choose('create.host',1); ui.replace('create.resource','actual-owned-resource'); owner.finish()
            state = self.owner().state; events = state['calls'][0]['events']
            self.assertEqual('actual-owned-resource',self.harness.widget.texts['create.resource'])
            self.assertGreater(len(events),2)
            for event in events:
                self.assertEqual('observed',event['phase'])
                self.assertEqual(event['intent']['command']['commandId'],event['receipt']['status']['commandId'])
                self.assertEqual(event['intent']['command']['sequence'],event['observed']['scope']['sequence'])
                self.assertEqual(42,event['intent']['admission']['processId'])
                self.assertNotIn('state',event['receipt']['status'])
            with self.assertRaises(source.CreateInputPending): self.owner().begin(QUERY)

    def test_storage_failure_prevents_all_input(self):
        with self.lock.held():
            owner = self.owner(); owner.begin(QUERY); ui = self.ui(owner)
            with patch.object(self.store,'write',side_effect=NativeUIError('Journal unavailable')):
                with self.assertRaises(NativeUIError): ui.input('create.tab.0')
            self.assertFalse(any(row.get('operation')=='edit' for row in self.harness.native.commands))
            self.assertEqual([],self.owner().state['calls'][0]['events'])

    def test_lost_delivery_stays_issued_and_never_resends_recipe_or_input(self):
        with self.lock.held():
            owner = self.owner(); owner.begin(QUERY); ui = self.ui(owner); deliver = self.native.deliver
            def lose(command,*,before_send=None): deliver(command,before_send=before_send); raise NativeUIError('Lost delivery return')
            with patch.object(self.native,'deliver',side_effect=lose):
                with self.assertRaises(NativeUIError): ui.input('create.tab.4')
            self.assertEqual(4,self.harness.widget.tab)
            state = self.owner().state; self.assertEqual('issued',state['calls'][0]['events'][-1]['phase'])
            count = sum(row.get('operation')=='edit' for row in self.harness.native.commands)
            recovered = self.owner()
            with self.assertRaises(source.CreateInputPending): recovered.begin(QUERY)
            with self.assertRaises(NativeUIError): self.ui(recovered).input('create.tab.0')
            self.assertEqual(count,sum(row.get('operation')=='edit' for row in self.harness.native.commands))

    def test_candidate_reference_receipt_nonce_and_native_timestamp_tampering_are_rejected(self):
        with self.lock.held():
            owner = self.owner(); owner.begin(QUERY); self.ui(owner).input('create.tab.0'); owner.finish(); original = deepcopy(owner.state)
            with self.assertRaises(NativeUIError): self.owner(BINDING|dict(artifactSha256='a'*64))
            for fault in ('token','sequence','receipt','time','pid','admission'):
                altered = deepcopy(original); event = altered['calls'][0]['events'][0]
                if fault=='token': event['intent']['command']['fieldToken']='ffffffff-ffff-4fff-8fff-ffffffffffff'
                elif fault=='sequence': event['observed']['scope']['sequence'] += 1
                elif fault=='receipt': event['receipt']['status']['commandId']='ffffffff-ffff-4fff-8fff-ffffffffffff'
                elif fault=='time': event['receipt']['status']['sampleEpochMs']=1
                elif fault=='pid': event['intent']['admission']['processId']=43
                else: event['intent']['admission']['lastSequence'] += 1
                with self.subTest(fault=fault),self.assertRaises(NativeUIError): owner.decode(owner.envelope(altered))


if __name__ == '__main__': unittest.main()
