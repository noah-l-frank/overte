"""Original private input/independent source joins with synthetic product effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.chat_actor_files import ChatActorFiles, SOURCE, encode, node
from adapters.chat_peer_input import ChatPeerInput, COMMAND, RECEIPT
from adapters.chat_journey.peer_send import ChatPeerSend
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_actor_files as actor_seams
from self_tests import test_chat_journey_samples as source_seams
from feature_journeys.fixtures import context
from self_tests.test_native_chat_observation import RUN


class PeerSendTests(unittest.TestCase):
    def setUp(self):
        self.h = source_seams.ChatSamplesTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.actor = self.h.sampler(role='actor', store=PrivateFeatureState(self.h.root / 'actor-samples.json'))
        root = self.h.root / 'actor'; root.mkdir(mode=0o700); self.root = root
        sha = 'f' * 64
        path = root / SOURCE
        path.write_bytes(encode(dict(actorVersion=1, instance='e'*32, processId=456, configuredEpochMs=19900, scriptSha256=sha)))
        path.chmod(0o600)
        self.file_actor = actor_seams.FileActor(root); self.addCleanup(self.file_actor.close_all)
        self.clock = 0.; self.fd = -1; self.addCleanup(self.close); self.issued = 0; self.effect = 'accept'
        self.files = ChatActorFiles(root, PrivateFeatureState(self.h.root / 'files.json'), self.h.peer_binding,
            sha, lambda: True, self.released, component_only=True, clock_ms=lambda:20000,
            monotonic=lambda:self.clock, sleep=self.tick)
        self.addCleanup(self.files.detach)
        self.input = ChatPeerInput(self.files, PrivateFeatureState(self.h.root / 'input.json'), RUN)
        self.store = PrivateFeatureState(self.h.root / 'peer-send.json')
        self.owner = ChatPeerSend(self.input, self.h.samples, self.actor, self.store,
            monotonic=lambda:self.clock, sleep=lambda seconds:setattr(self, 'clock', self.clock+seconds))

    def close(self):
        if self.fd >= 0: os.close(self.fd); self.fd = -1

    def released(self, identity):
        if self.fd >= 0 and node(os.fstat(self.fd)) == identity: return False
        return self.file_actor.released(identity)

    def tick(self, seconds):
        self.clock += seconds
        import json
        request = json.loads((self.root / COMMAND).read_bytes())
        self.issued += 1
        temporary = self.root / '.receipt'
        fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        receipt = dict(actorFileVersion=1, commandNode=node((self.root/COMMAND).stat()), resultNode=node(os.fstat(fd)),
            native=dict(peerInputVersion=1, commandId=request['commandId'], runId=RUN, operation='send',
                instance='8'*32, sequence=self.issued, processId=456, capturedEpochMs=20000))
        os.write(fd, encode(receipt)); os.fsync(fd); os.replace(temporary, self.root / RECEIPT)
        self.close(); self.fd = fd
        if self.effect != 'none':
            self.h.accept(context(RUN)[request['textKey']], channel=request['channel'], local=self.effect=='echo')

    def send(self): return self.owner.send('domain', 'reply', 20000)

    def test_consumed_normal_send_requires_both_separately_queried_original_receivers_and_storage(self):
        observed = self.send()
        self.assertEqual('received', self.store.read()['attempts'][0]['phase'])
        self.assertEqual(1, self.issued)
        for state in observed: self.assertEqual([context(RUN)['reply']], state['state']['domainMessages'])
        refs = self.store.read()['attempts'][0]
        self.assertFalse(set(refs['before'][0]['queries']) & set(refs['after'][1]['queries']))
        self.assertTrue(self.input.store.path.exists()); self.assertTrue(self.store.path.exists())

    def rebuilt(self):
        self.input=ChatPeerInput(self.files,self.input.store,RUN)
        self.h.samples=self.h.sampler();self.actor=self.h.sampler(role='actor',store=self.actor.store)
        return ChatPeerSend(self.input,self.h.samples,self.actor,self.store,monotonic=lambda:self.clock,sleep=lambda seconds:setattr(self,'clock',self.clock+seconds))

    def test_rpc_reconstruction_uses_both_original_histories_and_full_consumption_without_query_or_send(self):
        self.send();before=self.issued;queries=[len(source.commands) for source in (self.h.primary,self.h.peer,self.h.view,self.h.native)]
        original=self.store.path.read_bytes();self.owner=self.rebuilt()
        self.assertEqual(original,self.store.path.read_bytes());self.assertEqual(before,self.issued)
        self.assertEqual(queries,[len(source.commands) for source in (self.h.primary,self.h.peer,self.h.view,self.h.native)])
        with self.assertRaises(NativeUIError):self.send()
        self.assertEqual(before,self.issued);self.assertEqual(original,self.store.path.read_bytes())
        self.owner.send('domain','hidden',20000);self.assertEqual(before+1,self.issued)
        self.assertEqual(['reply','hidden'],[row['textKey'] for row in self.store.read()['attempts']])
        self.assertEqual(2,len(self.rebuilt().previous['attempts']))

    def test_uncertain_old_rewritten_query_or_consumption_reference_never_reconstructs_or_sends(self):
        for fault in ('phase','old-v1','queries','input-index','false-channel'):
            with self.subTest(fault=fault):
                self.setUp();self.send();old=self.store.read();changed=deepcopy(old);before=self.issued
                if fault=='old-v1':changed['chatPeerSendVersion']=1
                elif fault=='phase':changed['attempts'][0]['phase']='observing'
                elif fault=='queries':changed['attempts'][0]['after'][1]['queries'][0]='f'*32
                elif fault=='input-index':changed['attempts'][0]['inputIndex']=2
                else:changed['attempts'][0]['channel']='local'
                self.store.write(changed,old);original=self.store.path.read_bytes()
                with self.assertRaises(NativeUIError):self.rebuilt()
                self.assertEqual(original,self.store.path.read_bytes());self.assertEqual(before,self.issued)

    def test_equivalent_lock_paths_without_the_same_original_instances_are_refused(self):
        from adapters.script_journey.lock import ScriptSourceLock
        self.actor.locks=tuple(ScriptSourceLock(lock.path) for lock in self.actor.locks)
        with self.assertRaises(NativeUIError):ChatPeerSend(self.input,self.h.samples,self.actor,self.store)
        self.assertEqual(0,self.issued)

    def test_final_durable_received_write_cannot_hide_a_native_clock_jump_under_frozen_host(self):
        original=self.store.write;delta=0
        for role in self.owner.roles:role.primary.clock_ms=lambda:20000+delta
        def late(value,previous):
            nonlocal delta
            original(value,previous)
            if value['attempts'][-1]['phase']=='received':delta=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.send()
        self.assertEqual('received',self.store.read()['attempts'][0]['phase']);self.assertEqual(1,self.issued)

    def test_consumption_without_reception_times_out_and_cannot_resend(self):
        self.effect = 'none'
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual('observing', self.store.read()['attempts'][0]['phase'])
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual(1, self.issued)

    def test_old_matching_arrival_cannot_prove_a_new_send_and_local_echo_is_not_remote(self):
        self.h.accept(context(RUN)['reply']); self.effect = 'none'
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual(1, self.issued)
        self.setUp(); self.effect = 'echo'
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual('observing', self.store.read()['attempts'][0]['phase'])

    def test_foreign_actual_actor_source_refuses_before_input(self):
        self.files.source['instance'] = '9'*32
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual(0, self.issued); self.assertFalse((self.root/COMMAND).exists())

    def test_failed_independent_source_or_intent_cannot_issue_input(self):
        self.h.view.source['storage']['unowned'] = 1; self.h.view.source['storage']['count'] = 1
        with self.assertRaises(NativeUIError): self.send()
        self.assertEqual(0, self.issued); self.assertFalse((self.root/COMMAND).exists())


if __name__ == '__main__': unittest.main()
