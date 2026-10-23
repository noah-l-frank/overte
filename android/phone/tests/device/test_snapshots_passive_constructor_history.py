"""Actual Documents/Share scopes admit immutable history, never current facts.

The unchanged SDK26 public fixture owns a separate original Java provider and
real private files. Native/SDK/render signals remain explicit host producers;
these counters establish neither Android integration nor device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import copy,deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshot_documents_journey_boundary as documents
import test_snapshots_constructor_history_pass as foreground
import test_snapshots_feature_journey as harness
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_constructor_history import SnapshotConstructorHistoryPass
from overte_phone_snapshots_role import PhoneSnapshotsRole
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshot_documents_ui import SnapshotDocumentContext
from overte_phone_snapshot_system_context import SnapshotSystemContext


class SnapshotPassiveConstructorHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('PassiveConstructorFixture',(documents.SnapshotDocumentsCommonJourneyTests,),{})
        cls.fixture_type.setUpClass()
        # Compile unchanged Java only into this test's fresh owned output. No
        # prepared product object, APK, foreign build or package is adopted.
        build_root=harness.ROOT/'build/snapshot-passive-constructor-contract'
        build_root.mkdir(parents=True,exist_ok=True)
        cls.build=Path(tempfile.mkdtemp(prefix='check-',dir=build_root))
        compiler=documents.OriginalDocumentsProcess.compile
        cls.compiler_patch=patch.object(documents.OriginalDocumentsProcess,'compile',
            classmethod(lambda _cls,_requested:compiler(cls.build)))
        cls.compiler_patch.start()
    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:
            cls.compiler_patch.stop();cls.fixture_type.doClassCleanups()
    def setUp(self):
        self.fixture=self.fixture_type('test_normal_public_document_picker_open_cancel_and_success_acquires_original')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        fixture=self.fixture;fixture.client.activate('c'*32)
        first=self.observe(0)
        fixture.act('open');fixture.act('capture',dict(mode='still',format='png'))
        captured=self.observe(first['sequence']);self.assertEqual(1,captured['state']['files'])
        fixture.act('save-picker-open');self.measured=self.observe(captured['sequence'])
        self.assertTrue(self.measured['state']['saveSheet'])
        self.assertEqual('document-picker',self.measured['state']['saveBackend'])

    def observe(self,after):
        return self.fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=after))

    @contextmanager
    def prepared(self):
        fixture=self.fixture;feature=fixture.adapter._snapshots_feature('test-only-appium',harness.RUN)
        with ExitStack() as disposals,ExitStack() as session:
            with feature.lock.held():
                session.enter_context(feature.adapter.existing_input_session(feature.selector))
                feature.load();token=SnapshotConstructorHistoryPass.prepare(feature,'primary',passive=True)
                self.assertIsNotNone(token)
            try:yield feature,token,disposals
            finally:token.close()

    def construct(self,feature,token,disposals,*,current=True):
        with feature.lock.held():
            token.before_load();feature.load();token.after_load()
            role=PhoneSnapshotsRole(feature,'primary',expected_previous=token.role_header,
                _observe_disposals=disposals,_history_pass=token)
            token.before_read(role)
            if current:return role.read(self.measured['sequence'])
            return role

    def reject(self,feature,token,disposals):
        calls=[]
        def forbidden(*_args,**_kwargs):
            calls.append(True);raise AssertionError('Invalid passive history reached current source acquisition')
        with patch.object(PhoneSnapshotsRole,'read',forbidden),patch.object(PhoneSnapshotsRole,'batch',forbidden):
            with self.assertRaises(NativeUIError):self.construct(feature,token,disposals)
        self.assertEqual([],calls);self.assertTrue(token.closed)

    @contextmanager
    def passive_factories(self):
        forbidden=[];passive=[];adapter=self.fixture.adapter
        with ExitStack() as stack:
            for name in ('_snapshot_measurements','_native_feature_observer','_avatar_render_observer',
                    '_graphics_subject_observer','_touch_state_observer','_create_fixture_observer',
                    '_snapshot_readbacks','_snapshot_upload_source','_snapshot_platform'):
                def deny(*_args,_name=name,**_kwargs):
                    forbidden.append(_name);raise AssertionError('Foreground factory escaped passive history')
                stack.enter_context(patch.object(adapter,name,side_effect=deny))
            for name in ('_snapshot_handoff_source','_snapshot_system_platform','_snapshot_system_files'):
                original=getattr(adapter,name)
                def actual(*args,_name=name,_original=original,**kwargs):
                    passive.append(_name);return _original(*args,**kwargs)
                stack.enter_context(patch.object(adapter,name,side_effect=actual))
            yield forbidden,passive
        self.assertEqual([],forbidden)

    def test_actual_document_scope_full_role_and_input_replay_is_unlocked_before_passive_current_read(self):
        with self.prepared() as (feature,token,disposals),self.passive_factories() as (forbidden,passive):
            self.assertIs(type(feature._system_scope),SnapshotDocumentContext)
            with feature.lock.held():
                self.assertIsNone(SnapshotConstructorHistoryPass.prepare(feature,'primary'))
                self.assertIsNone(SnapshotConstructorHistoryPass.prepare(feature,'actor',passive=True))
                with self.assertRaises(NativeUIError):SnapshotConstructorHistoryPass.prepare(feature,'primary',passive=True,cleanup=True)
            failure=AssertionError('Unlocked immutable replay attempted current target authority')
            original=SnapshotsOriginals.file;entered=[];child=[]
            def during_actual_file(engine,path,descriptor,value):
                result=original(engine,path,descriptor,value)
                self.assertIsNone(feature.lock._owner)
                self.assertEqual(path.stat().st_ino,os.fstat(descriptor).st_ino)
                entered.append(True)
                if not child:
                    process=subprocess.run([sys.executable,'-c',foreground.LOCK_CHILD,json.dumps(sys.path),str(feature.lock.path)],
                        capture_output=True,text=True,check=True,timeout=3)
                    packet=json.loads(process.stdout);self.assertNotEqual(os.getpid(),packet['pid'])
                    self.assertTrue(packet['held']);child.append(packet)
                return result
            with patch.object(feature,'bound',side_effect=failure),patch.object(feature.phase,'status',side_effect=failure),\
                    patch.object(PhoneSnapshotsRole,'read',side_effect=failure),patch.object(PhoneSnapshotsRole,'batch',side_effect=failure),\
                    patch.object(SnapshotsOriginals,'file',during_actual_file):token.read()
            self.assertTrue(entered);self.assertTrue(child);self.assertEqual([],passive)
            self.assertTrue(any(p.name.startswith('emote-frame-snapshots-input-') for p in token.files))
            self.assertTrue(any(p.name.startswith('emote-index-snapshots-input-') for p in token.files))
            self.assertTrue(any(p.name.startswith('emote-frame-snapshots-') and not p.name.startswith('emote-frame-snapshots-input-') for p in token.files))
            self.assertTrue(any(p.suffix=='.png' for p in token.files));self.assertTrue(any(p.suffix=='.bin' for p in token.files))
            role=self.construct(feature,token,disposals,current=False)
            self.assertTrue(role.system);self.assertIsNotNone(role.handoff)
            with feature.lock.held():
                value=role.read(self.measured['sequence'])
                self.assertTrue(value['state']['saveSheet']);self.assertGreater(value['sequence'],self.measured['sequence'])
            self.assertTrue(passive);self.assertEqual([],forbidden)

    def test_actual_normal_share_uses_exact_share_scope_without_document_or_foreground_adoption(self):
        self.fixture.act('save-picker-cancel');closed=self.observe(self.measured['sequence'])
        self.fixture.act('share-open');self.measured=self.observe(closed['sequence'])
        self.assertTrue(self.measured['state']['shareSheet'])
        with self.prepared() as (feature,token,disposals),self.passive_factories():
            self.assertIs(type(feature._system_scope),SnapshotSystemContext)
            token.read();value=self.construct(feature,token,disposals)
            self.assertTrue(value['state']['shareSheet'])

    def test_missing_foreign_and_identical_rewritten_actual_headers_never_reach_current(self):
        for kind in ('feature-aba','role-aba','role-missing','role-foreign'):
            with self.subTest(kind=kind),self.prepared() as (feature,token,disposals):
                token.read();store=feature.store if kind.startswith('feature') else token.role_store
                header=deepcopy(store.read());changed=None
                try:
                    if kind=='role-missing':store.path.unlink()
                    elif kind=='role-foreign':changed=dict(header,role='actor');store.write(changed,header)
                    else:store.write(header,header)
                    self.reject(feature,token,disposals)
                    if kind=='role-missing':self.assertFalse(store.path.exists())
                    elif changed is not None:self.assertEqual(changed,store.read())
                finally:
                    if store.path.exists():store.write(header,store.read())
                    else:store.write(header,None)

    def test_scope_configuration_binding_or_handoff_replacement_is_red_before_current(self):
        for kind in ('scope','configuration','binding','handoff','factory','late-scope','rebound-clock'):
            with self.subTest(kind=kind),self.prepared() as (feature,token,disposals):
                token.read()
                if kind=='scope':feature._system_scope=copy(feature._system_scope)
                elif kind=='configuration':feature.config=deepcopy(feature.config);feature.config['domainId']='foreign'
                elif kind=='binding':feature.binding=deepcopy(feature.binding);feature.binding['processIdentity']='32:foreign'
                elif kind=='handoff':
                    feature.state=deepcopy(feature.state);feature.state['handoff']['id']='e'*32
                elif kind=='factory':
                    factory=feature.adapter._snapshot_system_context
                    with patch.object(feature.adapter,'_snapshot_system_context',side_effect=factory):self.reject(feature,token,disposals)
                    continue
                elif kind=='rebound-clock':
                    after_load=token.after_load
                    def clock_before_rebind():
                        old_clock=token.system_scope.last_clock
                        self.assertIsNotNone(old_clock)
                        feature._system_scope.monotonic=lambda:old_clock-1
                        return after_load()
                    token.after_load=clock_before_rebind
                else:
                    before=token.before_read;changed=[]
                    def last_callback(role):
                        bound=feature.bound
                        def change_after_query():
                            value=bound()
                            if not changed:
                                scope=feature._system_scope;callback=scope.current_component
                                scope.current_component=lambda:callback();changed.append(True)
                            return value
                        with patch.object(feature,'bound',side_effect=change_after_query):return before(role)
                    token.before_read=last_callback
                self.reject(feature,token,disposals)
                if kind=='late-scope':self.assertEqual([True],changed)
        # Admission must pin the pre-callback host/SDK owner, rather than learn
        # a formally valid replacement after its last actual native query.
        for kind in ('input-references','sdk-scope'):
            with self.subTest(admission=kind),ExitStack() as session:
                feature=self.fixture.adapter._snapshots_feature('test-only-appium',harness.RUN)
                with feature.lock.held():
                    session.enter_context(feature.adapter.existing_input_session(feature.selector));feature.load()
                    status=feature.phase.status;old_scope=feature.adapter._existing_input_scope;changed=[];forbidden=[]
                    def change_after_phase(*args,**kwargs):
                        value=status(*args,**kwargs)
                        if not changed:
                            if kind=='input-references':
                                # Select a real earlier manifest, not a caller-
                                # invented reference or expected observation.
                                current=feature.state['inputs'][-1];older=[]
                                for path in feature.root.glob('emote-index-snapshots-input-'+harness.RUN+'-primary-*.json'):
                                    raw=path.read_bytes();body=json.loads(raw)
                                    if body['block']==current['block'] and len(body['entries'])==current['count']-1:
                                        older.append(dict(block=body['block'],count=len(body['entries']),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
                                self.assertTrue(older)
                                feature.state=deepcopy(feature.state);feature.state['inputs'][-1]=older[0]
                                feature.state['inputSequence']-=1
                            else:feature.adapter._existing_input_scope=deepcopy(old_scope)
                            changed.append(True)
                        return value
                    def invalid_read(*_args,**_kwargs):forbidden.append(True);raise AssertionError('Admission reached current Role IO')
                    try:
                        with patch.object(feature.phase,'status',side_effect=change_after_phase),patch.object(PhoneSnapshotsRole,'read',invalid_read):
                            with self.assertRaises(NativeUIError):SnapshotConstructorHistoryPass.prepare(feature,'primary',passive=True)
                        self.assertEqual([True],changed);self.assertEqual([],forbidden)
                    finally:feature.adapter._existing_input_scope=old_scope

    def test_real_new_phase_or_fixture_close_cannot_turn_passive_replay_into_current_authority(self):
        with self.prepared() as (feature,token,disposals):
            token.read();self.fixture.client.activate('d'*32,'share-open',{})
            self.reject(feature,token,disposals)
        with self.prepared() as (feature,token,disposals):
            token.read();self.fixture.client.close();self.reject(feature,token,disposals)

    def test_actual_old_input_role_file_metadata_and_late_attached_graph_mutations_are_red(self):
        for kind in ('input-body','manifest','mode','late-graph'):
            with self.subTest(kind=kind),self.prepared() as (feature,token,disposals):
                token.read();original=None;path=None;changed=[]
                try:
                    if kind!='late-graph':
                        path=next(p for p in token.files if
                            (p.name.startswith('emote-frame-snapshots-input-') if kind=='input-body' else
                             p.name.startswith('emote-index-') if kind=='manifest' else p.suffix=='.png'))
                        original=(path.read_bytes(),path.stat().st_mode&0o777)
                        if kind=='mode':path.chmod(0o640)
                        else:path.write_bytes(original[0]+b' ')
                    else:
                        before=token.before_read
                        def final_native(role):
                            bound=feature.bound
                            def actual_then_change():
                                value=bound()
                                if not changed:
                                    role.frames=deepcopy(role.frames);role.frames[0]['unqualifiedPassiveGraphChange']=True;changed.append(True)
                                return value
                            with patch.object(feature,'bound',side_effect=actual_then_change):return before(role)
                        token.before_read=final_native
                    self.reject(feature,token,disposals)
                    if kind=='late-graph':self.assertEqual([True],changed)
                    elif kind=='mode':self.assertEqual(0o640,path.stat().st_mode&0o777)
                    else:self.assertEqual(original[0]+b' ',path.read_bytes())
                finally:
                    if original is not None:path.write_bytes(original[0]);path.chmod(original[1])

    def test_failed_or_closed_token_never_reuses_passive_constructor_authority(self):
        with self.prepared() as (feature,token,disposals):
            token.read();token.close();self.assertIsNone(token.frames)
            with self.assertRaises(NativeUIError):token.read()
            self.reject(feature,token,disposals)
        with self.prepared() as (feature,token,disposals):
            token.read()
            with feature.lock.held(),patch.object(feature,'bound',side_effect=NativeUIError('Controlled actual guard failure')):
                with self.assertRaises(NativeUIError):token.before_load()
            self.assertTrue(token.closed);self.reject(feature,token,disposals)

    def test_public_os_observe_uses_actual_passive_history_and_closes_its_one_use_token(self):
        actual=SnapshotConstructorHistoryPass.read;passes=[];constructed=[];ctor=PhoneSnapshotsRole.__init__
        def replay(token):
            self.assertIsNone(token.feature.lock._owner);passes.append(token);return actual(token)
        def construct(role,*args,**kwargs):
            constructed.append(kwargs.get('_history_pass'));return ctor(role,*args,**kwargs)
        with self.passive_factories(),patch.object(SnapshotConstructorHistoryPass,'read',replay),patch.object(PhoneSnapshotsRole,'__init__',construct):
            value=self.observe(self.measured['sequence'])
        self.assertTrue(value['state']['saveSheet']);self.assertEqual(1,len(passes))
        self.assertIn(passes[0],constructed);self.assertTrue(passes[0].closed)


if __name__=='__main__':unittest.main()
