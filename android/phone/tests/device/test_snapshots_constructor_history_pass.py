"""Actual private constructor history is never current measurement authority.

These host counters use the guarded public fixture, original TLS/journals and
real JSON/manifest/PNG/binary files. Native/SDK/render signals are explicit host
producers. No Android compiler, OS integration or device result is implied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as harness
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_constructor_history import SnapshotConstructorHistoryPass
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_role import PhoneSnapshotsRole


LOCK_CHILD=r'''
import json,os,sys
sys.path[:0]=json.loads(sys.argv[1])
from snapshots_journey_producers import HostOnlyBoundary
with HostOnlyBoundary():
    from overte_phone_script_lock import PhoneScriptSourceLock
    with PhoneScriptSourceLock(sys.argv[2],timeout=.1).held():
        print(json.dumps(dict(pid=os.getpid(),held=True)),flush=True)
'''


class SnapshotConstructorHistoryPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('ConstructorHistoryFixture',(harness.SnapshotJourneyTests,),{})
        cls.fixture_type.setUpClass()
    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:cls.fixture_type.doClassCleanups()
    def setUp(self):
        self.fixture=self.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.client.activate('c'*32)
        first=f.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
        f.act('open');f.act('capture',dict(mode='still',format='png'))
        self.observed=f.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=first['sequence']))
        self.assertEqual(1,self.observed['state']['files'])

    @contextmanager
    def prepared(self):
        f=self.fixture.adapter._snapshots_feature('test-only-appium',harness.RUN)
        # Disposal is outermost, just as in the real observation operation.
        with ExitStack() as disposals,ExitStack() as session:
            with f.lock.held():
                session.enter_context(f.adapter.existing_input_session(f.selector))
                f.load();token=SnapshotConstructorHistoryPass.prepare(f,'primary')
                self.assertIsNotNone(token)
            try:yield f,token,disposals
            finally:token.close()

    def reconstruct(self,f,token,disposals,*,current=True):
        with f.lock.held():
            token.before_load();f.load();token.after_load()
            role=PhoneSnapshotsRole(f,'primary',expected_previous=token.role_header,
                _history_pass=token,_observe_disposals=disposals)
            token.before_read(role)
            if current:return role.read(self.observed['sequence'])
            return role

    def reject_before_current(self,f,token,disposals):
        forbidden=[]
        def current(*_args,**_kwargs):
            forbidden.append(True)
            raise AssertionError('Invalid historical pass reached current acquisition')
        with patch.object(PhoneSnapshotsRole,'read',current),patch.object(PhoneSnapshotsRole,'batch',current):
            with self.assertRaises(NativeUIError):self.reconstruct(f,token,disposals)
        self.assertEqual([],forbidden)

    def test_actual_full_files_are_unlocked_while_separate_process_acquires_source_lock(self):
        with self.prepared() as (f,token,disposals):
            original=SnapshotsOriginals.file;entered=[];child=[]
            def during_actual_file(engine,path,descriptor,value):
                self.assertIsNone(f.lock._owner)
                result=original(engine,path,descriptor,value)
                # The original file engine has actually opened its descriptor.
                # The child runs while that read's normal metadata checks are
                # active, rather than during an artificial pre-read sleep.
                actual=os.fstat(descriptor);self.assertEqual(path.stat().st_ino,actual.st_ino)
                entered.append(True)
                if not child:
                    process=subprocess.run([sys.executable,'-B','-c',LOCK_CHILD,json.dumps(sys.path),str(f.lock.path)],
                        capture_output=True,text=True,timeout=3,check=True)
                    packet=json.loads(process.stdout);self.assertNotEqual(os.getpid(),packet['pid'])
                    self.assertTrue(packet['held']);child.append(packet)
                return result
            forbidden=AssertionError('Historical replay requested current target authority')
            with patch.object(f,'bound',side_effect=forbidden),patch.object(f.phase,'status',side_effect=forbidden),\
                    patch.object(PhoneSnapshotsRole,'read',side_effect=forbidden),patch.object(PhoneSnapshotsRole,'batch',side_effect=forbidden),\
                    patch.object(SnapshotsOriginals,'file',during_actual_file):
                token.read()
            self.assertTrue(entered);self.assertTrue(child)
            self.assertTrue(any(path.name.startswith('emote-frame-') for path in token.files))
            self.assertTrue(any(path.name.startswith('emote-index-') for path in token.files))
            self.assertTrue(any(path.suffix=='.png' for path in token.files))
            self.assertTrue(any(path.suffix=='.bin' for path in token.files))
            value=self.reconstruct(f,token,disposals)
            self.assertGreater(value['sequence'],self.observed['sequence'])
            self.assertEqual(1,value['state']['files'])

    def test_actual_file_and_manifest_changes_after_replay_never_reach_current_read(self):
        for kind in ('json','manifest','png-mode','binary-link','missing','same-bytes-new-inode'):
            with self.subTest(kind=kind),self.prepared() as (f,token,disposals):
                token.read()
                path=next(path for path in token.files if
                    (path.name.startswith('emote-index-') if kind=='manifest' else
                     path.suffix==('.png' if kind=='png-mode' else '.bin' if kind=='binary-link' else '.json')))
                raw=path.read_bytes();mode=path.stat().st_mode&0o777;other=path.with_name(path.name+'.counter-owned')
                try:
                    if kind in ('json','manifest'):path.write_bytes(raw+b' ')
                    elif kind=='png-mode':path.chmod(0o640)
                    elif kind=='binary-link':os.link(path,other)
                    else:
                        path.rename(other)
                        if kind=='same-bytes-new-inode':path.write_bytes(raw);path.chmod(mode)
                    self.reject_before_current(f,token,disposals)
                finally:
                    if kind in ('json','manifest'):path.write_bytes(raw)
                    elif kind=='png-mode':path.chmod(mode)
                    elif kind=='binary-link':other.unlink()
                    else:
                        if path.exists():path.unlink()
                        other.rename(path)

    def test_same_payload_feature_and_role_header_rewrites_are_detected_as_aba(self):
        for owner in ('feature','role'):
            with self.subTest(owner=owner),self.prepared() as (f,token,disposals):
                token.read();store=f.store if owner=='feature' else PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
                actual=deepcopy(store.read());store.write(actual,actual)
                self.assertEqual(actual,store.read())
                self.reject_before_current(f,token,disposals)
                self.assertEqual(actual,store.read())

    def test_formally_valid_changed_headers_are_not_adopted_by_constructor(self):
        for owner in ('feature','role'):
            with self.subTest(owner=owner),self.prepared() as (f,token,disposals):
                token.read();store=f.store if owner=='feature' else PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
                previous=deepcopy(store.read());state=unpack(previous['payload'])[0]
                if owner=='feature':state['cleanupStages']['controlled-foreign-stage']='e'*32
                else:state['phase']='retired'
                foreign=dict(previous,payload=pack([state]));store.write(foreign,previous)
                try:
                    self.reject_before_current(f,token,disposals)
                    self.assertEqual(foreign,store.read())
                finally:store.write(previous,foreign)

    def test_replaced_scope_or_changed_configuration_cannot_supply_authority(self):
        for kind in ('scope-object','scope-content','configuration'):
            with self.subTest(kind=kind),self.prepared() as (f,token,disposals):
                token.read();scope=f.adapter._existing_input_scope;contents=deepcopy(scope);config=deepcopy(f.config)
                try:
                    if kind=='scope-object':f.adapter._existing_input_scope=deepcopy(scope)
                    elif kind=='scope-content':scope['generation']+=1
                    else:f.config['imageExtent'][0]+=1
                    self.reject_before_current(f,token,disposals)
                finally:
                    f.adapter._existing_input_scope=scope;scope.clear();scope.update(contents);f.config=config

    def test_actual_native_pid_change_after_host_replay_is_red_before_current(self):
        with self.prepared() as (f,token,disposals):
            token.read();native=self.fixture.setup.f.native;original=native.identity
            try:
                native.identity='32:foreign-original-start'
                self.reject_before_current(f,token,disposals)
            finally:native.identity=original

    def test_actual_new_phase_cannot_be_adopted_after_unlocked_replay(self):
        with self.prepared() as (f,token,disposals):
            token.read();self.fixture.client.activate('e'*32,'upload',{})
            self.reject_before_current(f,token,disposals)

    def test_closed_original_phase_does_not_turn_constructor_into_finalizer(self):
        with self.prepared() as (f,token,disposals):
            token.read();self.fixture.client.close()
            self.reject_before_current(f,token,disposals)

    def test_only_memory_graph_changes_are_rejected_before_current(self):
        with self.prepared() as (f,token,disposals):
            token.read();self.assertTrue(token.frames)
            frames=deepcopy(token.frames);frames[-1]['controlled-memory-change']=True;token.frames=frames
            self.reject_before_current(f,token,disposals)

    def test_graph_changed_during_final_native_guard_cannot_reach_current(self):
        with self.prepared() as (f,token,disposals):
            token.read();bound=f.bound;changed=[]
            def actual_guard_then_change():
                result=bound()
                if not changed:
                    frames=deepcopy(token.frames);frames[-1]['changed-during-real-guard']=True
                    token.frames=frames;changed.append(True)
                return result
            with patch.object(f,'bound',side_effect=actual_guard_then_change):
                self.reject_before_current(f,token,disposals)
            self.assertEqual([True],changed)

    def test_sealed_receipts_cannot_be_erased_and_token_cannot_be_reused(self):
        with self.prepared() as (f,token,disposals):
            token.read();self.assertTrue(token.files);token.files.clear()
            self.reject_before_current(f,token,disposals)
        with self.prepared() as (f,token,disposals):
            token.read();role=self.reconstruct(f,token,disposals,current=False)
            with f.lock.held():role.read(self.observed['sequence'])
            with self.assertRaises(NativeUIError):token.read()
            with self.assertRaises(NativeUIError):token.guard()
            with f.lock.held(),self.assertRaises(NativeUIError):token.before_read(role)

    def test_another_actual_thread_cannot_read_the_live_pass(self):
        with self.prepared() as (f,token,disposals):
            errors=[]
            def foreign():
                try:token.read()
                except NativeUIError:errors.append(True)
            thread=threading.Thread(target=foreign);thread.start();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual([True],errors)
            self.assertTrue(token.closed)

    def test_actor_falls_through_but_known_removed_primary_owner_is_not_adopted(self):
        with self.prepared() as (f,token,_disposals):
            token.close()
            with f.lock.held():
                self.assertIsNone(SnapshotConstructorHistoryPass.prepare(f,'actor'))
                store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
                path=store.path;other=path.with_name(path.name+'.counter-owned');previous=deepcopy(store.read())
                self.assertEqual(previous,token.role_header);path.rename(other)
                try:
                    forbidden=[]
                    def current(*_args,**_kwargs):
                        forbidden.append(True);raise AssertionError('Missing owner reached current measurement')
                    with patch.object(PhoneSnapshotsRole,'read',current),patch.object(PhoneSnapshotsRole,'batch',current):
                        with self.assertRaises(NativeUIError):
                            SnapshotConstructorHistoryPass.prepare(f,'primary',expected_role=previous)
                    self.assertEqual([],forbidden);self.assertFalse(path.exists())
                finally:other.rename(path)


if __name__=='__main__':unittest.main()
