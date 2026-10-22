"""Original private input/independent source joins with synthetic product effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
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
