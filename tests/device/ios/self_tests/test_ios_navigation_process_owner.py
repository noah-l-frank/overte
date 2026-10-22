"""Actual private transfer journals and scene HTTP, with explicit native SDK seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_admission_owner import SOURCES
from ios.adapters.navigation_process_owner import NavigationProcessOwner
from ios.self_tests import test_ios_navigation_process_context as contexts


class Native(NativeFeatureObservation):
    def __init__(self,harness):
        self.h=harness;self.ios=True;self.pid=43;self.sequence=1;self.guard=lambda:harness.okay
        self.values=[harness.proof.after['clockJoin'][key] for key in ('nativeBefore','nativeAfter')]
    def read(self,after):
        self.h.reads.append('native');value=deepcopy(self.values.pop(0));self.sequence=value['sequence']
        self.h.advance(value['capturedEpochMs']);return value


class NavigationProcessOwnerTests(unittest.TestCase):
    def setUp(self):
        self.proof=contexts.NavigationProcessContextTests();self.proof.setUp();self.addCleanup(self.proof.doCleanups)
        self.root=self.proof.h.h.root;self.lock=self.proof.lock;self.fixture=self.proof.h.h.provider
        self.start=self.proof.after['clockJoin']['nativeBefore']['capturedEpochMs'];self.ms=0
        self.host=time.time()*1000;self.reads=[];self.okay=True;self.fault=None;self.native=Native(self);self.sources={}
        for name,kind in SOURCES.items():
            def read(_reader,run=None,name=name):
                self.reads.append(name)
                if self.fault==name:raise OSError('Synthetic lost source return')
                value=deepcopy(self.proof.after['originals'][name])
                stamp=value.get('sampleEpochMs',value.get('capturedEpochMs'))
                if stamp is None:stamp=value['clockAfter']['epochMs']
                self.advance(stamp);return value
            reader=type('ExplicitNewProcessSDK',(kind,),{'__init__':lambda _self:None,'read':read,'capture':read})()
            reader.pid=43;reader.ios=True;self.sources[name]=reader
    def advance(self,epoch):self.ms=max(self.ms,epoch-self.start)
    def epoch(self):return self.host+self.ms
    def mono(self):return 10.3+self.ms/1000
    def owner(self,*,historical=False,**changes):
        options=dict(store=PrivateFeatureState(self.root/'ios-navigation-process-context.json'),initial=self.proof.initial,
            before=self.proof.before,receipt=self.proof.receipt,owner_files=self.proof.owners,lock=self.lock,
            guard=lambda:self.okay,historical=historical,native=None if historical else self.native,
            sources=None if historical else self.sources,fixture=None if historical else self.fixture,
            epoch_ms=self.epoch,monotonic=self.mono)
        options.update(changes);return NavigationProcessOwner(**options)
    def take(self,owner):return owner.acquire(self.epoch()-1)

    def test_actual_new_originals_are_durable_and_historical_reconstruction_never_calls_sdk_or_http(self):
        with self.lock.held():
            owner=self.owner();basis=self.take(owner);self.assertEqual('43',basis['binding']['processIdentity'])
            self.assertEqual(['native',*SOURCES,'native'],self.reads);self.assertEqual('transferred',owner.state['phase'])
            raw=deepcopy(owner.store.read());reads=list(self.reads);self.okay=False
            self.fixture.scene=lambda:self.fail('Historical validation made HTTP call')
            self.assertEqual(owner.state['context'],self.owner(historical=True).archive())
            self.assertEqual(raw,owner.store.read());self.assertEqual(reads,self.reads)
            self.assertEqual(self.proof.initial['bookmarkBaseline'],basis['bookmarkBaseline'])

    def test_lost_middle_read_keeps_original_prefix_and_cannot_reacquire_or_recover_an_incomplete_group(self):
        with self.lock.held():
            self.fault='http';owner=self.owner()
            with self.assertRaises(OSError):self.take(owner)
            self.assertEqual({'inventory','navigation','bookmarks','model'},set(owner.state['originals']))
            self.assertIsNotNone(owner.state['nativeStart']);self.assertIsNone(owner.state['nativeEnd'])
            reads=list(self.reads);raw=deepcopy(owner.store.read());self.fault=None;again=self.owner()
            with self.assertRaises(NativeUIError):self.take(again)
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(reads,self.reads);self.assertEqual(raw,again.store.read())

    def test_complete_lost_return_recovers_old_originals_without_refreshing_the_input_deadline(self):
        with self.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['phase']=='transferred':raise OSError('Synthetic lost transfer return')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):self.take(owner)
            owner.store.write=write;again=self.owner();reads=list(self.reads)
            self.ms+=2000;again.recover();self.assertEqual('transferred',again.state['phase'])
            self.assertEqual(reads,self.reads);self.assertEqual(self.proof.after['originals'],again.archive()['after']['originals'])
            with self.assertRaises(NativeUIError):again.for_input()

    def test_changed_candidate_original_scope_or_external_journal_cannot_bypass_ownership(self):
        with self.lock.held():
            owner=self.owner();self.take(owner);reads=list(self.reads)
            changed=deepcopy(self.proof.receipt);changed['input']['newBinding']['sourceRevision']='f'*40
            with self.assertRaises(NativeUIError):self.owner(receipt=changed)
            changed=deepcopy(self.proof.before);changed['originals']['bookmarks']['loaded']['entries']={}
            with self.assertRaises(NativeUIError):self.owner(before=changed)
            saved=owner.store.read();changed=deepcopy(saved);changed['runId']='f'*32;owner.store.write(changed,saved)
            with self.assertRaises(NativeUIError):owner.archive()
            self.assertEqual(reads,self.reads)

    def test_rejected_new_scene_stays_owned_and_reconstruction_does_not_replace_its_read(self):
        with self.lock.held():
            self.proof.after['originals']['navigation']['source']['view']['mode']='third person';owner=self.owner()
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertEqual(set(SOURCES),set(owner.state['originals']));self.assertEqual('reading',owner.state['phase'])
            self.assertIsNotNone(owner.state['providerAfter']);reads=list(self.reads)
            with self.assertRaises(NativeUIError):self.owner().recover()
            self.assertEqual(reads,self.reads)

    def test_source_basis_validation_cannot_cross_the_original_input_deadline_after_the_last_check(self):
        from ios.adapters import navigation_process_context
        with self.lock.held():
            owner=self.owner();self.take(owner);original=navigation_process_context.source_basis;reads=list(self.reads)
            def late(value,files):
                basis=original(value,files);self.ms+=2000;return basis
            with patch.object(navigation_process_context,'source_basis',side_effect=late),self.assertRaises(NativeUIError):
                owner.for_input()
            self.assertEqual(reads,self.reads);self.assertEqual('transferred',owner.state['phase'])
