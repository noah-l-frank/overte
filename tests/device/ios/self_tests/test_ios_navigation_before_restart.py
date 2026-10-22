"""Real retained journals/loopback scene; app and SDK are explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters.navigation_before_restart import NavigationBeforeRestart
from ios.self_tests.test_ios_navigation_process_context import NavigationProcessContextTests


class Native(NativeFeatureObservation):
    def __init__(self,h):
        self.h=h;self.ios=True;self.pid=42;self.sequence=2
        self.guard=lambda:True
        self.values=[deepcopy(h.proof.before['clockJoin'][key]) for key in ('nativeBefore','nativeAfter')]
    def read(self,after):
        value=self.values.pop(0);self.sequence=value['sequence'];self.h.reads.append('native')
        self.h.clock(value['capturedEpochMs']);return value


class NavigationBeforeRestartTests(unittest.TestCase):
    def setUp(self):
        self.proof=NavigationProcessContextTests();self.proof.setUp();self.addCleanup(self.proof.doCleanups)
        self.h=self.proof.h.h;self.reads=[]
        raw=self.proof.before['originals'];self.admission=self.proof.h.admission
        self.first=self.proof.before['clockJoin']['nativeBefore']['capturedEpochMs']
        self.h.ms=self.first-self.h.native_first
        self.h.fixture.harness.provider.clock_ms=lambda:int(self.h.epoch())
        self.h.provider.epoch_ms=lambda:int(self.h.epoch())
        for name,reader in self.admission.sources.items():
            def read(run=None,name=name):
                self.reads.append(name);value=deepcopy(raw[name])
                self.clock(value.get('sampleEpochMs',value.get('capturedEpochMs',value.get('clockAfter',{}).get('epochMs'))))
                return value
            if name=='ui':reader.capture=read
            else:reader.read=read
        self.admission.native=Native(self)

    def clock(self,epoch):self.h.advance(epoch)

    @contextmanager
    def held(self):
        # ScriptSourceLock deliberately wraps its body; surface the original
        # test assertion instead of hiding failures under a lock error.
        fault=None
        with self.h.lock.held():
            try:yield
            except BaseException as exc:fault=exc
        if fault is not None:raise fault

    def owner(self):
        return NavigationBeforeRestart(PrivateFeatureState(self.h.root/'ios-navigation-before-restart.json'),
            self.admission,epoch_ms=self.h.epoch,monotonic=self.h.mono)

    def test_fresh_eight_originals_keep_actual_root_bookmark_and_static_admission(self):
        with self.held():
            original=deepcopy(self.admission.previous);owner=self.owner();group=owner.acquire()
            self.assertEqual(['native',*self.admission.sources,'native'],self.reads)
            self.assertEqual(self.proof.before['originals'],group['originals'])
            self.assertEqual(self.proof.before['addressOwner'],group['addressOwner'])
            self.assertEqual(original,self.admission.previous);self.assertEqual(group,owner.for_input())
            self.assertEqual('observed',owner.state['phase']);self.assertNotIn('restarted',owner.state)
            saved=deepcopy(owner.store.read());reads=list(self.reads)
            self.admission.sources['ui'].capture=lambda:self.fail('Historical archive read SDK')
            self.h.provider.scene=lambda:self.fail('Historical archive read provider')
            self.assertEqual(group,NavigationBeforeRestart.archive(saved,self.proof.initial))
            self.assertEqual(reads,self.reads)

    def test_lost_middle_read_preserves_prefix_and_cannot_reacquire(self):
        with self.held():
            self.admission.sources['http'].read=lambda run:(_ for _ in ()).throw(OSError('Synthetic lost HTTP original'))
            owner=self.owner()
            with self.assertRaises(OSError):owner.acquire()
            again=self.owner();saved=deepcopy(again.store.read());reads=list(self.reads)
            self.assertEqual({'inventory','navigation','bookmarks','model'},set(again.state['originals']))
            self.assertIsNotNone(again.state['nativeStart']);self.assertIsNone(again.state['nativeEnd'])
            with self.assertRaises(NativeUIError):again.acquire()
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(saved,again.store.read());self.assertEqual(reads,self.reads)

    def test_runtime_factory_requires_same_actual_selector_binding_and_directory(self):
        from ios.adapters.navigation_runtime import IOSNavigationRuntime
        with self.held():
            runtime=object.__new__(IOSNavigationRuntime)
            source=dict(binding=deepcopy(self.admission.binding))
            runtime._sources=lambda selector:source
            runtime.state_path=lambda selector:self.h.root/'ios-state.json'
            owner=runtime._navigation_before_restart('existing-only',self.admission)
            self.assertIs(self.admission,owner.admission);self.assertIsNone(owner.store.read())
            self.assertEqual([],self.reads)
            source['binding']['processIdentity']='43'
            with self.assertRaises(NativeUIError):runtime._navigation_before_restart('existing-only',self.admission)
            source['binding']=deepcopy(self.admission.binding)
            runtime.state_path=lambda selector:self.h.root/'foreign'/'ios-state.json'
            with self.assertRaises(NativeUIError):runtime._navigation_before_restart('existing-only',self.admission)

    def test_lost_final_result_recovers_only_original_group_without_new_deadline(self):
        with self.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['phase']=='observed':raise OSError('Synthetic lost final write')
                return write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):owner.acquire()
            again=self.owner();reads=list(self.reads);self.h.ms+=2000
            self.assertEqual(self.proof.before['originals'],again.recover()['originals'])
            self.assertEqual(reads,self.reads)
            with self.assertRaises(NativeUIError):again.for_input()

    def test_changed_root_or_foreign_scene_refuses_and_retains_full_originals(self):
        for fault in ('root','scene','preferences'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                raw=self.proof.before['originals']
                if fault=='root':raw['ui']['navigationInventory']['roots'][0]['rootId']='00000000-0000-4000-8000-000000000099'
                elif fault=='scene':raw['navigation']['source']['sceneUrl']='hifi://unowned-scene'
                else:raw['model']['preferences']['metaverseOrigin']='http://unowned.invalid'
                with self.held():
                    owner=self.owner()
                    with self.assertRaises((NativeUIError,ValueError)):owner.acquire()
                    self.assertEqual(8,len(owner.state['originals']));self.assertEqual('reading',owner.state['phase'])
                    reads=list(self.reads)
                    with self.assertRaises((NativeUIError,ValueError)):self.owner().recover()
                    self.assertEqual(reads,self.reads)

    def test_retained_archive_cannot_rewrite_source_join_or_original_binding(self):
        with self.held():
            owner=self.owner();owner.acquire();original=owner.store.read()
            for fault in ('source','clock','admission','binding'):
                value=deepcopy(original);state=unpack(value['payload'])[0]
                if fault=='source':state['originals']['ui']['sampleEpochMs']+=1
                elif fault=='clock':state['nativeEnd']['nativeAfter']['sequence']+=1
                elif fault=='admission':value['initialAdmissionSha256']='0'*64
                else:value['binding']['processIdentity']='43'
                value['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                    NavigationBeforeRestart.archive(value,self.proof.initial)


if __name__=='__main__':unittest.main()
