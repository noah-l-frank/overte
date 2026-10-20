"""Separate native receive/source seams with real private ownership journals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.independent_chat_receiver import IndependentChatReceiver
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from self_tests.test_native_chat_observation import Boundary,RUN,BINDING,SELF,PEER


class IndependentChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);os.chmod(self.temp.name,0o700)
        root=Path(self.temp.name)
        self.primary=Boundary();self.primary.present=True;self.primary.opened=20000
        self.native=Boundary();self.clock=0
        self.peer_store=PrivateFeatureState(root/'peer.json');self.store=PrivateFeatureState(root/'receiver.json')
        self.binding=BINDING|{'processIdentity':'456','targetFingerprint':'d'*64}
        self.mixer='d'*64
        def mutate(value):value.update(instance='e'*32,processId=456);value['source'].update(selfSha256=PEER,mixerSha256=self.mixer if self.native.mixer else '')
        self.native.mutate=mutate
        reader=self.native.reader();reader.pid=456
        self.peer=OwnedChatCapture(reader,ChatCaptureOwner(self.peer_store,self.binding,self.native.guard,component_only=True),RUN)
        self.receiver=IndependentChatReceiver(self.primary.reader(),BINDING,self.peer,self.store,component_only=True,monotonic=lambda:self.clock)

    def test_actual_peer_reception_order_multiplicity_and_channels_exclude_echoes_and_acks(self):
        self.assertEqual([],self.receiver.sample()['peerMessages'])
        self.native.event(sender=SELF,channel='local');self.native.event(sender=PEER)
        self.native.event(sender=SELF,local=True);self.native.event(sender='f'*64)
        self.native.event(sender=SELF,text=context(RUN)['retry']);self.native.event(sender=SELF,text=context(RUN)['retry'])
        value=self.receiver.sample()
        self.assertEqual([context(RUN)['unicode'],context(RUN)['retry'],context(RUN)['retry']],value['peerMessages'])
        self.assertEqual(SELF,value['primary']['source']['selfSha256']);self.assertEqual(PEER,value['peer']['source']['selfSha256'])
        self.assertIsNotNone(self.store.read());self.assertIsNotNone(self.peer_store.read())
        self.receiver.retire();self.receiver.retire()
        self.assertTrue(self.primary.present);self.assertFalse(any(c['operation']=='retire' for c in self.primary.commands))
        self.assertIsNone(self.store.read());self.assertIsNone(self.peer_store.read())

    def test_same_target_process_binding_same_native_source_and_other_mixer_refuse(self):
        with self.assertRaises(NativeUIError):IndependentChatReceiver(self.primary.reader(),BINDING,self.peer,self.store)
        for changes in ({'processIdentity':'457'},{'targetFingerprint':BINDING['targetFingerprint']}):
            self.peer.owner.binding=self.binding|changes
            with self.assertRaises(NativeUIError):IndependentChatReceiver(self.primary.reader(),BINDING,self.peer,self.store,component_only=True)
        self.peer.owner.binding=self.binding
        for mode in ('same-instance','same-self','wrong-mixer'):
            primary=Boundary();primary.present=True;primary.opened=20000;native=Boundary()
            def mutate(value):
                value.update(instance='c'*32 if mode=='same-instance' else 'e'*32,processId=456)
                value['source'].update(selfSha256=SELF if mode=='same-self' else PEER,
                    mixerSha256='f'*64 if mode=='wrong-mixer' else 'd'*64)
            native.mutate=mutate;reader=native.reader();reader.pid=456
            store=PrivateFeatureState(Path(self.temp.name)/('peer-'+mode+'.json'))
            pair=PrivateFeatureState(Path(self.temp.name)/('pair-'+mode+'.json'))
            peer=OwnedChatCapture(reader,ChatCaptureOwner(store,self.binding,native.guard,component_only=True),RUN)
            receiver=IndependentChatReceiver(primary.reader(),BINDING,peer,pair,component_only=True,monotonic=lambda:0)
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):receiver.sample()
            self.assertTrue(native.present);self.assertIsNotNone(store.read());self.assertIsNone(pair.read())
            receiver.retire();self.assertFalse(native.present);self.assertTrue(primary.present)

    def test_mixer_replacement_requires_both_original_sources_to_have_seen_absence(self):
        self.receiver.sample();self.mixer='f'*64
        self.primary.mutate=lambda value:value['source'].update(mixerSha256='f'*64 if self.primary.mixer else '')
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.primary.mixer=False;self.native.mixer=False
        self.assertEqual([],self.receiver.sample()['peerMessages'])
        self.assertTrue(self.store.read()['primaryAbsent']);self.assertTrue(self.store.read()['peerAbsent'])
        self.primary.mixer=True;self.native.mixer=True;self.receiver.sample()
        self.assertEqual('f'*64,self.store.read()['mixerSha256'])
        self.assertFalse(self.store.read()['primaryAbsent']);self.assertFalse(self.store.read()['peerAbsent'])

    def test_old_matching_mixer_nodes_after_actual_absence_do_not_establish_recovery(self):
        self.receiver.sample();self.primary.mixer=False;self.native.mixer=False;self.receiver.sample()
        self.primary.mixer=True;self.native.mixer=True
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertTrue(self.store.read()['primaryAbsent']);self.assertTrue(self.store.read()['peerAbsent'])
        self.mixer='f'*64;self.primary.mutate=lambda value:value['source'].update(mixerSha256='f'*64)
        self.receiver.sample();self.assertEqual('f'*64,self.store.read()['mixerSha256'])
        self.assertFalse(self.store.read()['primaryAbsent']);self.assertFalse(self.store.read()['peerAbsent'])

    def test_missing_primary_cache_or_unavailable_peer_cannot_be_a_received_ledger(self):
        self.primary.present=False;self.primary.opened=0
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertEqual([],self.native.commands)
        self.primary.present=True;self.primary.opened=20000;self.native.ignored=True
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertIsNotNone(self.peer_store.read())

    def test_old_or_modified_peer_events_dropped_history_and_changed_sources_fail(self):
        self.receiver.sample();self.native.event(sender=SELF);self.receiver.sample()
        original=self.native.mutate
        self.native.events[0]['text']=context(RUN)['retry']
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.native.events[0]['text']=context(RUN)['unicode']
        for key,value in [('instance','f'*32),('processId',999)]:
            def mutate(row):original(row);row[key]=value
            self.native.mutate=mutate
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.receiver.sample()
        self.native.mutate=original
        for _ in range(128):self.native.event(sender=SELF)
        def dropped(value):
            original(value);value['source']['events']=value['source']['events'][-128:]
            value['source']['droppedEvents']=1
        self.native.mutate=dropped
        with self.assertRaises(NativeUIError):self.receiver.sample()

    def test_failed_pair_journal_write_keeps_native_owner_and_prevents_returning_success(self):
        original=self.store.write
        def fail(*_):raise NativeUIError('private write failed')
        self.store.write=fail
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertTrue(self.native.present);self.assertIsNotNone(self.peer_store.read())
        self.store.write=original;self.receiver.retire();self.assertFalse(self.native.present)

    def test_incomplete_retirement_or_foreign_owner_keeps_journals(self):
        self.receiver.sample();self.native.ignore_retire=True
        with self.assertRaises(NativeUIError):self.receiver.retire()
        self.assertIsNotNone(self.store.read());self.assertIsNotNone(self.peer_store.read())
        self.native.ignore_retire=False
        prior=self.store.read();self.store.write(prior|{'peerBinding':self.binding|{'generation':True}},prior)
        with self.assertRaises(NativeUIError):self.receiver.retire()
        self.assertTrue(self.native.present)

    def test_partial_retirement_requires_fresh_original_fence_after_peer_sidecar_is_gone(self):
        self.receiver.sample();original=self.store.discard
        def failed(_):raise NativeUIError('receiver sidecar removal unavailable')
        self.store.discard=failed
        with self.assertRaises(NativeUIError):self.receiver.retire()
        self.assertIsNone(self.peer_store.read());self.assertIsNotNone(self.store.read())
        self.store.discard=original
        self.native.retired=False;self.native.present=True;self.native.opened=20000
        with self.assertRaises(NativeUIError):self.receiver.retire()
        self.assertIsNotNone(self.store.read())
        self.native.retired=True;self.native.present=False;self.native.opened=0
        self.receiver.retire();self.assertIsNone(self.store.read());self.assertTrue(self.primary.present)
        self.assertEqual(1,sum(c['operation']=='retire' for c in self.native.commands))

    def test_read_deadline_and_monotonic_clock_are_actual_acquisition_limits(self):
        original=self.native.send
        def send(request):original(request);self.clock+=1
        self.native.send=send;self.peer.reader.send=send
        with self.assertRaises(NativeUIError):self.receiver.sample()
        self.assertIsNone(self.store.read());self.assertIsNotNone(self.peer_store.read())
        self.clock=-1
        with self.assertRaises(NativeUIError):self.receiver.sample()


if __name__=='__main__':unittest.main()
