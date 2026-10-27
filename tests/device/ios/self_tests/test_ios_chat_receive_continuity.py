"""Real private journals and codec; native receive/SDK boundaries are models.

Reopening a reader must retain the actual receive prefix, including duplicate
events. No modeled receive event proves a product send or physical peer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.independent_chat_receiver import IndependentChatReceiver
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import context
from self_tests.test_native_chat_observation import Boundary,RUN,SELF,PEER


class IOSChatReceiveContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);os.chmod(self.root,0o700)
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,
            processIdentity='123',sessionId='primary-owned',generation=1,targetFingerprint='c'*64)
        self.peer_binding=self.binding|dict(processIdentity='456',sessionId='peer-owned',targetFingerprint='d'*64)
        self.primary,self.native=Boundary(),Boundary();self.primary.present=True;self.primary.opened=20000
        def mutate(value):
            value.update(instance='e'*32,processId=456);value['source']['selfSha256']=PEER
        self.native.mutate=mutate
        self.peer_store=PrivateFeatureState(self.root/'peer.json');self.store=PrivateFeatureState(self.root/'receiver.json')
        self.receiver=self.reopen()
    def reopen(self,*,retain=True):
        reader=self.native.reader(ios=True);reader.pid=456
        peer=OwnedChatCapture(reader,ChatCaptureOwner(self.peer_store,self.peer_binding,self.native.guard),RUN)
        return IndependentChatReceiver(self.primary.reader(ios=True),self.binding,peer,self.store,
            retain_originals=retain,monotonic=lambda:0.)
    def census(self):
        return {p.name:(p.stat().st_ino,p.read_bytes()) for p in self.root.iterdir() if p.is_file()}
    def test_reopened_pair_restores_exact_original_prefix_without_queries_or_writes(self):
        self.receiver.sample();self.native.event(sender=SELF);self.native.event(sender=SELF)
        value=self.receiver.sample();files=self.census();commands=deepcopy((self.primary.commands,self.native.commands))
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No constructor write')):
            reopened=self.reopen()
        self.assertEqual(files,self.census());self.assertEqual(commands,(self.primary.commands,self.native.commands))
        raw=unpack(self.store.read()['originals']);self.assertEqual([dict(primary=value['primary'],peer=value['peer'])],raw)
        result=reopened.sample();self.assertEqual([context(RUN)['unicode']]*2,result['peerMessages'])
        self.assertGreater(result['peer']['sequence'],value['peer']['sequence'])
        self.assertNotEqual(result['peer']['commandId'],value['peer']['commandId'])
    def test_reopening_cannot_adopt_rewritten_peer_events(self):
        self.receiver.sample();self.native.event(sender=SELF);self.receiver.sample()
        old=deepcopy(self.native.events[0]);original=self.store.read()
        for change in (dict(text=context(RUN)['retry']),dict(localOnly=True),dict(channel='local'),dict(senderSha256='f'*64)):
            self.native.events[0]=old|change;receiver=self.reopen()
            with self.subTest(change=change),self.assertRaises(NativeUIError):receiver.sample()
            self.assertEqual(original,self.store.read())
        self.native.events[0]=old;self.assertEqual([context(RUN)['unicode']],self.reopen().sample()['peerMessages'])
    def test_reopening_cannot_adopt_rewritten_primary_originals(self):
        self.receiver.sample();self.primary.event(sender=PEER);self.receiver.sample()
        self.primary.events[0]['text']=context(RUN)['hidden'];before=len(self.native.commands)
        with self.assertRaises(NativeUIError):self.reopen().sample()
        self.assertEqual(before,len(self.native.commands))
    def test_lost_pair_cas_return_is_adopted_only_by_reopening_from_actual_saved_originals(self):
        self.receiver.sample();self.native.event(sender=SELF);write=self.store.write
        def lost(value,previous):write(value,previous);raise OSError('Declared lost pair CAS return')
        with patch.object(self.store,'write',side_effect=lost),self.assertRaises(NativeUIError):self.receiver.sample()
        commands=deepcopy(self.native.commands)
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertEqual(commands,self.native.commands)
        reopened=self.reopen();self.assertEqual([context(RUN)['unicode']],reopened.sample()['peerMessages'])
        self.assertEqual(1,len(self.native.events));self.assertTrue(self.native.present)
    def test_explicit_profile_refuses_cross_adoption_and_corrupt_packed_original(self):
        self.receiver.sample();files=self.census()
        with self.assertRaises(NativeUIError):self.reopen(retain=False).owned()
        self.assertEqual(files,self.census())
        before=self.store.read();value=deepcopy(before);value['originals']['sha256']='f'*64;self.store.write(value,before)
        commands=deepcopy((self.primary.commands,self.native.commands))
        with self.assertRaises(NativeUIError):self.reopen()
        self.assertEqual(commands,(self.primary.commands,self.native.commands))
    def test_reopened_retirement_fences_only_owned_peer_cache_and_keeps_primary(self):
        self.receiver.sample();self.native.event(sender=SELF);self.receiver.sample();receiver=self.reopen()
        receiver.retire();self.assertIsNone(self.store.read());self.assertIsNone(self.peer_store.read())
        self.assertTrue(self.primary.present);self.assertTrue(self.native.retired)
        self.assertFalse(any(row['operation']=='retire' for row in self.primary.commands))
    def test_restore_rejects_foreign_pid_nonce_and_non_pristine_reader_before_io(self):
        value=self.receiver.sample()['peer'];reader=self.native.reader(ios=True);reader.pid=456
        for change in (dict(processId=123),dict(commandId='f'*32)):
            commands=deepcopy(self.native.commands)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.restore(value|change)
            self.assertEqual(commands,self.native.commands)
        reader.restore(value)
        with self.assertRaises(NativeUIError):reader.restore(value)
    def test_literal_one_cannot_be_adopted_by_retained_profile_before_queries(self):
        self.reopen(retain=False).sample();commands=deepcopy((self.primary.commands,self.native.commands));files=self.census()
        with self.assertRaises(NativeUIError):self.reopen()
        self.assertEqual(commands,(self.primary.commands,self.native.commands));self.assertEqual(files,self.census())
    def test_full_original_limit_is_retained_and_dropped_history_is_never_admitted(self):
        self.receiver.sample()
        for _ in range(128):self.native.event(sender=SELF);self.primary.event(sender=PEER)
        value=self.receiver.sample();self.assertEqual(128,len(value['peerMessages']))
        self.assertEqual(value['peer'],unpack(self.store.read()['originals'])[0]['peer'])
        receiver=self.reopen();original=self.native.mutate
        def dropped(value):
            original(value);source=value['source'];source.update(eventSequence=129,droppedEvents=1)
            for index,event in enumerate(source['events'],2):event['sequence']=index
        self.native.mutate=dropped;files=self.census()
        with self.assertRaises(NativeUIError):receiver.sample()
        self.assertEqual(files,self.census())
    def test_original_mixer_absence_and_replacement_survive_reconstruction(self):
        self.receiver.sample();self.primary.mixer=False;self.native.mixer=False;self.reopen().sample()
        self.assertTrue(self.store.read()['primaryAbsent']);self.assertTrue(self.store.read()['peerAbsent'])
        self.primary.mixer=True;self.native.mixer=True
        with self.assertRaises(NativeUIError):self.reopen().sample()
        native_mutate=self.native.mutate
        self.primary.mutate=lambda value:value['source'].update(mixerSha256='f'*64)
        def replacement(value):native_mutate(value);value['source']['mixerSha256']='f'*64
        self.native.mutate=replacement;receiver=self.reopen();receiver.sample()
        self.assertEqual('f'*64,self.store.read()['mixerSha256']);self.assertFalse(self.store.read()['peerAbsent'])


if __name__=='__main__':unittest.main()
