"""Public SDK26 constructor continuity; host producers do not qualify devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_passive_constructor_history as passive
import test_snapshots_feature_journey as harness
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_constructor_history import SnapshotConstructorHistoryPass
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_role import PhoneSnapshotsRole


class SnapshotCleanupConstructorScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):passive.SnapshotPassiveConstructorHistoryTests.setUpClass()
    @classmethod
    def tearDownClass(cls):passive.SnapshotPassiveConstructorHistoryTests.tearDownClass()

    @contextmanager
    def cleanup_fixture(self):
        fixture=passive.SnapshotPassiveConstructorHistoryTests.fixture_type('test_normal_public_document_picker_open_cancel_and_success_acquires_original')
        fixture.setUp()
        try:
            fixture.client.activate('c'*32)
            first=fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
            fixture.act('open');fixture.act('capture',dict(mode='still',format='png'))
            captured=fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=first['sequence']))
            self.assertEqual('document-picker',captured['state']['saveBackend'])
            fixture.client.activate('f'*32,'cleanup')
            fixture.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
            yield fixture,captured['sequence']
        finally:self.assertTrue(fixture.doCleanups(),'Owned SDK26 cleanup fixture cleanup failed')

    @contextmanager
    def monitored_feature(self,fixture):
        factory=fixture.adapter._snapshots_feature;features=[];loads=[];native=[]
        def create(*args,**kwargs):
            f=factory(*args,**kwargs);features.append(f);load=f.load;bound=f.bound
            def actual_load():loads.append(f);return load()
            def actual_bound():native.append(f);return bound()
            f.load=actual_load;f.bound=actual_bound;return f
        with patch.object(fixture.adapter,'_snapshots_feature',create):yield features,loads,native

    @staticmethod
    def observe(fixture,sequence):
        return fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=sequence))

    def test_public_cleanup_keeps_initial_load_full_files_and_fresh_current_qualification(self):
        with self.cleanup_fixture() as (fixture,sequence),self.monitored_feature(fixture) as (features,loads,native):
            read=SnapshotConstructorHistoryPass.read;file=SnapshotsOriginals.file;passes=[];opened=[];after=[];current=[]
            actual_current=PhoneSnapshotsRole.read
            def actual_replay(token):
                self.assertTrue(token.cleanup);self.assertFalse(token.passive)
                self.assertTrue(token.feature._scope_ready);self.assertIsNone(token.feature._system_scope)
                before=len(native);result=read(token);passes.append(token);after.append(len(native))
                self.assertEqual(before,len(native));return result
            def actual_file(owner,path,descriptor,value):
                result=file(owner,path,descriptor,value)
                if features and features[-1].lock._owner is None:
                    self.assertEqual(path.stat().st_ino,os.fstat(descriptor).st_ino);opened.append(path)
                return result
            def actual_read(role,*args,**kwargs):
                current.append(True);self.assertGreater(len(native),after[-1]);return actual_current(role,*args,**kwargs)
            with patch.object(SnapshotConstructorHistoryPass,'read',actual_replay),patch.object(SnapshotsOriginals,'file',actual_file),patch.object(PhoneSnapshotsRole,'read',actual_read):
                value=self.observe(fixture,sequence)
            self.assertEqual(1,len(features));self.assertEqual([features[0]],loads)
            self.assertEqual([True],current);self.assertEqual(1,len(passes));self.assertTrue(passes[0].closed)
            self.assertTrue(any(p.name.startswith('emote-frame-snapshots-input-') for p in opened))
            self.assertTrue(any(p.name.startswith('emote-frame-snapshots-') and '-input-' not in p.name for p in opened))
            self.assertTrue(any(p.suffix=='.png' for p in passes[0].files));self.assertTrue(any(p.suffix=='.bin' for p in passes[0].files))
            self.assertGreater(value['sequence'],sequence);self.assertEqual([],value['resources']);self.assertEqual(0,value['state']['files'])

    def mutate(self,kind,token,restores,fixture):
        f=token.feature
        if kind in ('guard','runtime-guard'):
            name='guard' if kind=='guard' else '_runtime_guard';old=getattr(f,name)
            setattr(f,name,lambda *args,**kwargs:old(*args,**kwargs))
        elif kind=='factory':
            old=f.adapter.normal_feature_runtime
            restores.enter_context(patch.object(f.adapter,'normal_feature_runtime',lambda *args,**kwargs:old(*args,**kwargs)))
        elif kind=='sdk-scope':
            old=f.adapter._existing_input_scope;replacement=deepcopy(old);f.adapter._existing_input_scope=replacement
            def restore_scope():
                if f.adapter._existing_input_scope is replacement:f.adapter._existing_input_scope=old
            restores.callback(restore_scope)
        elif kind=='system-scope':f._system_scope=object()
        elif kind=='scope-ready':f._scope_ready=False
        elif kind=='ram':f.state['cleanupStages']['controlled-private-graph']='e'*32
        elif kind=='input-file':
            path=next(p for p in token.files if p.name.startswith('emote-frame-snapshots-input-'))
            backup=path.with_name(path.name+'.controlled-missing');path.rename(backup);restores.callback(backup.rename,path)
        elif kind=='installed':
            adb=fixture.setup.f.fixture.adb;old=adb.digest;adb.digest='f'*64;restores.callback(setattr,adb,'digest',old)
        elif kind=='session':
            old=f.adapter.read_session(f.selector)
            restores.enter_context(patch.object(f.adapter,'read_session',return_value=dict(old,sessionId='foreign-session')))
        elif kind=='pid':
            native=fixture.setup.f.native;old=native.identity;native.identity='32:foreign-original-start';restores.callback(setattr,native,'identity',old)
        else:
            role=kind.startswith('role-');store=token.role_store if role else f.store
            previous=deepcopy(store.read());value=previous
            if kind.endswith('foreign'):
                state=unpack(previous['payload'])[0]
                if role:state['phase']='retired'
                else:state['cleanupStages']['controlled-foreign-owner']='e'*32
                value=dict(previous,payload=pack([state]))
            store.write(value,previous)
            restores.callback(lambda:store.write(previous,store.read()))

    def test_changed_context_prepare_callbacks_and_mid_replay_owners_never_reach_current(self):
        after_kinds=('guard','runtime-guard','factory','sdk-scope','system-scope','scope-ready','ram','input-file','installed','session','pid')
        cases=[('after',kind) for kind in after_kinds]
        cases += [('during',kind) for kind in ('feature-aba','feature-foreign','role-aba','role-foreign')]
        cases += [('prepare',kind) for kind in ('ram','feature-foreign')]
        with self.cleanup_fixture() as (fixture,sequence):
            for stage,kind in cases:
                with self.subTest(stage=stage,kind=kind),ExitStack() as restores,self.monitored_feature(fixture) as (_features,loads,_native):
                    read=SnapshotConstructorHistoryPass.read;file=SnapshotsOriginals.file;prepare=SnapshotConstructorHistoryPass.prepare
                    seen=[];changed=[];active=[];forbidden=[]
                    def invalid_current(*_args,**_kwargs):
                        forbidden.append(True);raise AssertionError('Invalid cleanup preparation reached current acquisition')
                    def actual_replay(token):
                        active[:]=[token];seen.append(token)
                        result=read(token)
                        if stage=='after':self.mutate(kind,token,restores,fixture);changed.append(True)
                        return result
                    def actual_file(owner,path,descriptor,value):
                        result=file(owner,path,descriptor,value)
                        if stage=='during' and active and not changed:
                            self.assertIsNone(active[0].feature.lock._owner)
                            self.assertEqual(path.stat().st_ino,os.fstat(descriptor).st_ino)
                            self.mutate(kind,active[0],restores,fixture);changed.append(True)
                        return result
                    def actual_prepare(cls,f,role,**kwargs):
                        if stage!='prepare':return prepare(f,role,**kwargs)
                        bound=f.bound
                        def native_then_change():
                            result=bound()
                            if not changed:
                                # The real preparation guard runs before the
                                # mutation. No historical token exists yet.
                                if kind=='ram':f.state['cleanupStages']['controlled-admission-graph']='e'*32
                                else:
                                    previous=deepcopy(f.store.read());state=unpack(previous['payload'])[0]
                                    state['cleanupStages']['controlled-admission-owner']='e'*32
                                    f.store.write(dict(previous,payload=pack([state])),previous)
                                    restores.callback(lambda:f.store.write(previous,f.store.read()))
                                changed.append(True)
                            return result
                        with patch.object(f,'bound',native_then_change):return prepare(f,role,**kwargs)
                    with patch.object(SnapshotConstructorHistoryPass,'read',actual_replay),patch.object(SnapshotsOriginals,'file',actual_file),\
                            patch.object(SnapshotConstructorHistoryPass,'prepare',classmethod(actual_prepare)),\
                            patch.object(PhoneSnapshotsRole,'read',invalid_current),patch.object(PhoneSnapshotsRole,'batch',invalid_current):
                        with self.assertRaises((NativeUIError,FileNotFoundError)):self.observe(fixture,sequence)
                    self.assertEqual([True],changed);self.assertEqual([],forbidden)
                    self.assertEqual(1,len(loads)) # A reload cannot repair the invalid context.
                    self.assertIsNone(fixture.adapter._existing_input_scope)
                    if stage=='prepare':self.assertEqual([],seen)
                    else:self.assertEqual(1,len(seen));self.assertTrue(seen[0].closed)

    def test_existing_public_passive_case_keeps_reload_and_distinct_os_scope(self):
        component=passive.SnapshotPassiveConstructorHistoryTests('test_public_os_observe_uses_actual_passive_history_and_closes_its_one_use_token')
        component.setUp()
        try:
            actual=SnapshotConstructorHistoryPass.after_load;scopes=[]
            def actual_after_load(token):
                self.assertTrue(token.passive);self.assertFalse(token.cleanup)
                before=token.system_scope;new=token.feature._system_scope
                self.assertIsNot(before,new);result=actual(token)
                self.assertIs(token.system_scope,new);scopes.append((before,new));return result
            with self.monitored_feature(component.fixture) as (features,loads,_native),patch.object(SnapshotConstructorHistoryPass,'after_load',actual_after_load):
                component.test_public_os_observe_uses_actual_passive_history_and_closes_its_one_use_token()
            self.assertEqual(1,len(features));self.assertEqual([features[0],features[0]],loads);self.assertEqual(1,len(scopes))
        finally:
            inner=component.fixture.doCleanups();outer=component.doCleanups()
            self.assertTrue(inner and outer,'Owned passive SDK26 fixture cleanup failed')


if __name__=='__main__':unittest.main()
