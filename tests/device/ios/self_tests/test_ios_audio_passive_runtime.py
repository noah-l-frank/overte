"""Actual host SDK ledger/directory births, explicitly modeled source transport.

No live InstalledAdapter/SDK/microphone is used. Pure historical admission must
precede the modeled source factory; source binding is a producer declaration,
not a measured native/device/acoustic fact. Original host files/WAL are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os,shutil,unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import collect
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.audio_passive_runtime import IOSAudioPassiveRuntime
from ios.self_tests.test_ios_audio_passive_owner import PassiveBoundary
from ios.self_tests.test_ios_audio_pcm_lease import PCMModel
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,BINDING,RUN

LEASE='4'*32
OTHER='5'*32


class DeclaredTransport:
    def __init__(self,boundary):
        self.boundary=boundary;self.remote='@declared-host-only:documents/results/source.json';self.before_send=None
    def send(self,query):
        if self.before_send is not None:self.before_send()
        return self.boundary.send(query)
    def original(self,**_fields):return self.boundary.read()


class RuntimeModel(IOSAudioPassiveRuntime):
    def __init__(self,fixture,boundary):
        self.f,self.boundary=fixture,boundary;self.adapter=SimpleNamespace(state_path=lambda _target:fixture.root/'session.json')
        self.calls=0;self.binding=deepcopy(BINDING);self.required_pure_reads=set();self.actual_reads=None
    def _sources(self,_selector):
        self.calls+=1
        if self.required_pure_reads:
            assert self.actual_reads is not None and self.required_pure_reads.issubset(self.actual_reads),'Fresh source preceded complete original historical admission'
        self.boundary.block=False
        native,_unused=PCMModel(self.f.model).reader();observer=DeclaredTransport(self.boundary)
        return dict(binding=deepcopy(self.binding),clock_source=native,observer=observer,check=self.f.model.guard)
    @contextmanager
    def existing_input_session(self,_selector):yield


class AudioPassiveRuntimeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.artifacts=self.f.root/'passive-artifacts';self.artifacts.mkdir(mode=0o700)
        self.boundary=PassiveBoundary(self.f.model);self.runtime=RuntimeModel(self.f,self.boundary)
    def owner(self,lease=LEASE):
        m=self.f.model
        return self.runtime.passive_owner('actor',RUN,lease,self.artifacts,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
    def ledger(self):return PrivateFeatureState(self.f.root/'ios-audio-passive-ledger.json')
    def test_selected_sdk_ledger_owns_actual_child_birth_before_native_start_and_preserves_sdk_root(self):
        with self.owner() as owner:
            value=self.ledger().read();row=value['leases'][0];info=owner.root.stat()
            self.assertEqual(str(self.f.root),value['sdkStateRoot']);self.assertEqual(str(self.artifacts),value['artifactRoot'])
            self.assertNotEqual(value['sdkStateRoot'],str(owner.root));self.assertEqual('opened',row['phase'])
            self.assertEqual(dict(device=info.st_dev,inode=info.st_ino),row['rootIdentity'])
            self.assertEqual([],self.boundary.commands);owner.start(6);owner.retire()
        self.assertTrue(self.ledger().path.exists());self.assertEqual(1,self.boundary.count('start'))
    def test_new_lease_refuses_live_prior_capture_before_any_fresh_source_constructor(self):
        with self.owner() as owner:owner.start(6)
        before=self.runtime.calls;commands=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError),self.owner(OTHER):pass
        self.assertEqual(before,self.runtime.calls);self.assertEqual(commands,self.boundary.commands)
        self.assertTrue(self.boundary.owned);self.assertEqual(1,len(self.ledger().read()['leases']))
    def test_reopening_types_every_original_file_before_source_and_does_not_adopt_new_native_capture(self):
        with self.owner() as owner:owner.start(6)
        self.boundary.finish()
        with self.owner() as owner:owner.capture();owner.retire();root=owner.root
        self.runtime.required_pure_reads={path for path in root.iterdir() if path.is_file()};self.boundary.block=True
        commands=self.boundary.count('start')
        with collect() as reads:
            self.runtime.actual_reads=reads
            with self.owner() as owner:self.assertTrue(owner.retired()['retired'])
        self.assertEqual(commands,self.boundary.count('start'));self.assertFalse(self.boundary.owned)
    def test_unknown_audio_duty_in_actual_sdk_root_blocks_before_source_even_when_active_child_is_valid(self):
        with self.owner() as owner:owner.start(6);owner.retire()
        unknown=PrivateFeatureState(self.f.root/'ios-audio-unparsed-duty.json');unknown.write(dict(declaredHostFault=True),None)
        before=self.runtime.calls;commands=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError),self.owner():pass
        self.assertEqual(before,self.runtime.calls);self.assertEqual(commands,self.boundary.commands);self.assertTrue(unknown.path.exists())
    def test_lost_directory_birth_return_remains_planned_and_cannot_adopt_created_same_path(self):
        original=os.mkdir;created=[]
        def lost(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if Path(path).name=='ios-audio-passive-'+LEASE:
                created.append(Path(path));raise OSError('Declared lost return after actual directory birth')
            return result
        with patch.object(os,'mkdir',lost),self.assertRaises(OSError),self.owner():pass
        self.assertEqual(1,len(created));self.assertTrue(created[0].is_dir())
        self.assertEqual('planned',self.ledger().read()['leases'][0]['phase']);self.assertEqual([],self.boundary.commands)
        before=self.runtime.calls
        with self.assertRaises(NativeUIError),self.owner():pass
        self.assertEqual(before,self.runtime.calls);self.assertTrue(created[0].is_dir())
    def test_same_body_replacement_child_inode_is_not_adopted_before_source(self):
        with self.owner() as owner:owner.start(6);owner.retire();child=owner.root
        original=self.f.root/'retained-original-child';child.rename(original);shutil.copytree(original,child);child.chmod(0o700)
        self.assertNotEqual(original.stat().st_ino,child.stat().st_ino)
        before=self.runtime.calls;commands=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError),self.owner():pass
        self.assertEqual(before,self.runtime.calls);self.assertEqual(commands,self.boundary.commands)
        self.assertEqual((original/'ios-audio-passive-owner.json').read_bytes(),(child/'ios-audio-passive-owner.json').read_bytes())
    def test_selected_existing_lease_refuses_foreign_fresh_binding_without_new_start_or_native_query(self):
        with self.owner() as owner:owner.start(6);owner.retire()
        self.runtime.binding['generation']+=1;before=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError),self.owner():pass
        self.assertEqual(before,self.boundary.commands);self.assertEqual(1,self.boundary.count('start'))
    def test_foreign_selected_lease_cannot_discharge_or_adopt_another_planned_birth(self):
        original=os.mkdir
        def refused(path,*args,**kwargs):
            if Path(path).name=='ios-audio-passive-'+LEASE:raise OSError('Declared mkdir refusal before directory birth')
            return original(path,*args,**kwargs)
        with patch.object(os,'mkdir',refused),self.assertRaises(OSError),self.owner():pass
        before=self.runtime.calls
        with self.assertRaises(NativeUIError),self.owner(OTHER):pass
        self.assertEqual(before,self.runtime.calls);self.assertEqual([],self.boundary.commands)
        self.assertEqual(LEASE,self.ledger().read()['leases'][0]['leaseId'])


if __name__=='__main__':unittest.main()
