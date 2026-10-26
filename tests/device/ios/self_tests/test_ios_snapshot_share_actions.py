"""Actual Share input journals/files over declared WDA/native journal models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError,W3C_ELEMENT
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.snapshot_share_actions import SnapshotShareUIAction
from ios.adapters.snapshot_share_packets import ShareNativeSegments,SnapshotShareInputs,SnapshotShareExportsPacket
from ios.adapters.snapshot_photos_packets import PhotosSaveSegments,PhotosSaveInputs
from ios.adapters.snapshot_source_packet import SnapshotSourceSegments,SnapshotExportsPacket
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters import snapshot_share_original as source
from ios.self_tests.test_ios_snapshot_share_original import received
from ios.self_tests.test_ios_snapshot_inputs import Native,RUN
from ios.self_tests.snapshot_photos_domain import revision


BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='share-ui-session',generation=0,targetFingerprint='c'*64)


class ShareUIModel:
    def __init__(self,root):
        _native,_operation,_exports,self.record,raw=received();self.path=root/'actual-native-journal.json'
        file=root/'received-original.bytes';file.write_bytes(raw);file.chmod(0o600);stat=root.stat()
        root_id=hashlib.sha256(':'.join(map(str,(stat.st_dev,stat.st_ino,stat.st_mode,stat.st_uid,stat.st_gid))).encode()).hexdigest()
        self.record.update(iosSnapshotShareOriginalVersion=2,artifactRevision=revision(file),rootIdentity=root_id)
        self.fields={};self.output='';self.requests=[];self.clicks=[];self.loss=None;self.ignored_write=False;self.good=True
        self.elements={};self.identifiers={}
    def call(self,method,path,body=None):
        self.requests.append((method,path,deepcopy(body)));prefix='/session/'+BINDING['sessionId'];assert path.startswith(prefix)
        suffix=path[len(prefix):]
        if suffix=='/elements':
            name=body['value']
            if name not in self.elements:
                token='element-'+str(len(self.elements)+1);self.elements[name]=token;self.identifiers[token]=name
            return [{W3C_ELEMENT:self.elements[name]}]
        identifier=self.identifiers[suffix.split('/')[2]]
        if suffix.endswith(('/displayed','/enabled')):return True
        if suffix.endswith('/attribute/value'):return self.output
        if suffix.endswith('/text'):return self.fields.get(identifier,'')
        if suffix.endswith('/clear'):
            self.fields[identifier]=''
            if self.loss=='clear':self.loss=None;raise OSError('Declared lost native field clear return')
            return None
        if suffix.endswith('/value'):
            if not self.ignored_write:self.fields[identifier]=body['text']
            if self.loss=='value':self.loss=None;raise OSError('Declared lost native field write return')
            return None
        assert suffix.endswith('/click');self.clicks.append(identifier)
        if identifier=='snapshot.share.inspect':
            query=deepcopy(self.record['queries'][-1]);query['requestId']=self.fields['snapshot.share.query']
            query['clock']={key:value+1 for key,value in query['clock'].items()};self.record['queries'].append(query)
            self.path.write_text(json.dumps(self.record,indent=1)+'\n');self.path.chmod(0o600);self.output=self.path.read_bytes().decode('utf-8')
        if self.loss=='click':self.loss=None;raise OSError('Declared lost button return after actual delivery')
        return None


class SnapshotShareActionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.model=ShareUIModel(self.root)
    def plan(self,control='snapshot.share.inspect'):
        return dict(label='inspect',control=control,selector=None,fields=[['snapshot.share.query','ios-'+'a'*32]])
    def action(self,plan=None,*,historical=False):
        return SnapshotShareUIAction(self.root,self.lock,BINDING,RUN,1,self.plan() if plan is None else plan,lambda:self.model.good,
            client=self.model,session=BINDING['sessionId'],epoch_ms=lambda:time.time()*1000,historical=historical)
    def mutation_count(self,suffix):return sum(method=='POST' and path.endswith(suffix) for method,path,_body in self.model.requests)

    def test_actual_original_view_bytes_follow_normal_nonce_input_and_historical_read_never_touches_WDA(self):
        with self.lock.held():
            action=self.action();raw=action.execute();action.qualified();source.original(json.loads(raw));self.assertEqual(self.model.path.read_bytes(),raw)
            self.assertEqual('ios-'+'a'*32,json.loads(raw)['queries'][-1]['requestId']);calls=len(self.model.requests)
            self.assertEqual(raw,self.action(historical=True).original())
            with self.assertRaises(NativeUIError):self.action(historical=True).execute()
            self.assertEqual(calls,len(self.model.requests));self.assertEqual(raw,self.action().execute());self.assertEqual(calls,len(self.model.requests))
        self.assertEqual(['snapshot.share.inspect'],self.model.clicks)

    def test_lost_clear_write_and_button_returns_recover_without_second_mutation(self):
        for fault in ('clear','value','click'):
            with self.subTest(fault=fault):
                fixture=SnapshotShareActionTests();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.model.loss=fault
                with fixture.lock.held():
                    with self.assertRaises(NativeUIError):fixture.action().execute()
                    raw=fixture.action().execute();self.assertEqual(fixture.model.path.read_bytes(),raw)
                self.assertEqual(1,fixture.mutation_count('/clear'));self.assertEqual(1,fixture.mutation_count('/value'));self.assertEqual(1,fixture.mutation_count('/click'))

    def test_ignored_field_write_and_changed_scope_never_replay_or_reach_button(self):
        self.model.ignored_write=True
        with self.lock.held():
            for _ in range(2):
                with self.assertRaises(NativeUIError):self.action().execute()
        self.assertFalse(self.model.clicks);self.assertEqual(1,self.mutation_count('/value'))
        self.model.good=False;before=len(self.model.requests)
        with self.lock.held(),self.assertRaises(NativeUIError):self.action().execute()
        self.assertEqual(before,len(self.model.requests))

    def test_saved_source_before_parent_update_adopts_original_inode_and_bytes_without_UI_read(self):
        with self.lock.held():
            action=self.action();actual=action.files.intent
            def lost(kind,value):
                actual(kind,value)
                if value['phase']=='saved':raise OSError('Declared parent update interruption')
            action.files.intent=lost
            with self.assertRaises(OSError):action.execute()
            file=next(self.root.glob('share-normal-frame-*'));before=(file.stat().st_ino,file.stat().st_mtime_ns,file.read_bytes());calls=len(self.model.requests)
            self.assertEqual(self.model.path.read_bytes(),self.action().execute());self.assertEqual(calls,len(self.model.requests))
            self.assertEqual(before,(file.stat().st_ino,file.stat().st_mtime_ns,file.read_bytes()))

    def test_partial_original_is_owned_and_cannot_be_rewritten_or_reinspected(self):
        with self.lock.held():
            action=self.action();actual=action.files.intent
            def lost(kind,value):
                actual(kind,value)
                if value['phase']=='opened':raise OSError('Declared partial output')
            action.files.intent=lost
            with self.assertRaises(OSError):action.execute()
            file=next(self.root.glob('share-normal-frame-*'));inode=file.stat().st_ino;calls=len(self.model.requests)
            with self.assertRaises(NativeUIError):self.action()
            self.assertEqual(b'',file.read_bytes());self.assertEqual(inode,file.stat().st_ino);self.assertEqual(calls,len(self.model.requests))

    def test_system_click_ACK_requires_independent_effect_and_readonly_output_cannot_be_written(self):
        plan=dict(label='select',control='system-select',selector=dict(using='accessibility id',value='Actual configured receiver row'),fields=[])
        with self.lock.held():
            result=self.action(plan).execute();self.assertEqual(dict(deliveryKnown=True,independentOutcomeRequired=True),result)
            calls=len(self.model.requests);self.assertEqual(result,self.action(plan).execute());self.assertEqual(calls,len(self.model.requests))
            plan['fields']=[['snapshot.share.original','expected-success']]
            with self.assertRaises(NativeUIError):self.action(plan)
        self.assertEqual(1,len(self.model.clicks))


class SnapshotSharePacketTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
    def test_closed_share_raw_parts_cannot_substitute_Photos_or_Capture_profiles(self):
        raw=b'actual raw native exports';tag=hashlib.sha256(raw).hexdigest();old=[]
        for cls in (SnapshotSourceSegments,PhotosSaveSegments):
            source=cls(self.root,BINDING,RUN,'primary','exports',lambda:True,lambda _:True,monotonic=lambda:1);old.append((source,source.write('raw',tag,raw,1)))
        share=ShareNativeSegments(self.root,BINDING,RUN,'primary','exports',lambda:True,lambda _:True,monotonic=lambda:1);parent=share.write('raw',tag,raw,1)
        self.assertEqual(raw,share.read(parent));self.assertEqual('share-native-exports-parts',share.store.namespace)
        for reader,value in old:
            with self.assertRaises(NativeUIError):reader.read(parent)
            with self.assertRaises(NativeUIError):share.read(value)
        for subject in ('work','captures','primary'):
            with self.assertRaises(NativeUIError):ShareNativeSegments(self.root,BINDING,RUN,'primary',subject,lambda:True,lambda _:True,monotonic=lambda:1)
    def test_share_input_and_packet_names_do_not_adopt_existing_capture_or_Photos_journals(self):
        with self.lock.held():
            store=PrivateFeatureState(self.root/SnapshotShareInputs.store_name('primary'));owner=SnapshotShareInputs(store,self.lock,BINDING,RUN,'primary',Native().input(),lambda:True);owner.save()
            SnapshotShareInputs.history(store,self.lock,BINDING,RUN,'primary')
            for cls in (SnapshotInputOwner,PhotosSaveInputs):
                foreign=PrivateFeatureState(self.root/cls.store_name('primary'));foreign.write(store.read(),None)
                with self.assertRaises(NativeUIError):cls.history(foreign,self.lock,BINDING,RUN,'primary')
            with self.assertRaises(NativeUIError):owner.reserve('snapshot.save.0',{})
            for cls,name in ((SnapshotShareExportsPacket,'ios-snapshot-primary-native-exports-0001.json'),(SnapshotExportsPacket,'snapshot-share-primary-native-exports-0001.json')):
                with self.assertRaises(NativeUIError):cls.history(PrivateFeatureState(self.root/name),self.lock,BINDING,RUN,'primary',1)


if __name__=='__main__':unittest.main()
