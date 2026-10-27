"""Existing Tablet copy/index WAL recovery; native and acquisition clocks are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from ios.adapters import tablet_web_native_child_continuation as closed,tablet_web_child_rotation as parent
from ios.self_tests import test_ios_tablet_web_native_child_continuation as existing


class TabletNativeChildStorageRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletNativeChildContinuationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletNativeChildContinuationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.build(['sources']);self.s=self.f.s;self.faults=[]
        value=closed.prepare(self.s,'sources');closed.install(self.s,'sources',value);self.owner=self.f.prefix('sources')

    def files(self,*,exclude_header=False):
        return {path.name:(closed.EmoteOriginalLease.signature(path.lstat()),hashlib.sha256(path.read_bytes()).hexdigest())
            for path in self.s.root.iterdir() if path.is_file() and (not exclude_header or path!=self.owner.store.path)}

    def counts(self):return self.f.fixture.native_counts()

    def loss(self,*,copy=None,manifest=None,count=3):
        intent=self.owner.intent
        def actual(kind,value):
            if kind=='original' and value['phase']==copy:
                intent(kind,value);self.faults.append(deepcopy(value));raise OSError('Modeled lost persisted copy transition return')
            if kind=='original' and copy=='saved-before' and value['phase']=='saved':
                self.faults.append(deepcopy(value));raise OSError('Modeled complete copy before saved transition')
            if kind=='manifest' and value['reference']['count']==count and manifest is not None:
                if manifest=='planned-complete' and value['phase']=='saved':
                    self.faults.append(deepcopy(value));raise OSError('Modeled complete manifest before saved transition')
                if manifest==value['phase']:
                    intent(kind,value);self.faults.append(deepcopy(value));raise OSError('Modeled lost persisted manifest transition return')
            return intent(kind,value)
        return actual

    def copy_saved(self):self.owner.copy();return self.owner.state['copyIntent']

    def interrupted_index(self,kind='saved',count=3):
        self.copy_saved()
        with patch.object(self.owner.records,'intent',self.loss(manifest=kind,count=count)),self.assertRaises(OSError):self.owner.index()
        self.assertEqual(1,len(self.faults));self.owner=self.f.prefix('sources')
        self.assertEqual(count,self.owner.state['manifestIntent']['reference']['count'])
        self.assertEqual(count-1,self.owner.state['manifests'][0]['count'])

    def unchanged_failure(self,operation,error=NativeUIError):
        before=self.files();counts=self.counts()
        with patch.object(OriginalFrameStore,'write',side_effect=AssertionError('Recovery attempted original creation')), \
             patch.object(OriginalFrameStore,'append',side_effect=AssertionError('Recovery attempted manifest creation')), \
             patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Blocked recovery attempted metadata write')), \
             self.assertRaises(error):operation()
        self.assertEqual(before,self.files());self.assertEqual(counts,self.counts())

    def test_complete_owned_copy_and_saved_manifest_adopt_only_existing_files_across_lost_CAS_returns(self):
        with patch.object(self.owner.copies,'intent',self.loss(copy='saved-before')),self.assertRaises(OSError):self.owner.copy()
        self.assertEqual(1,len(self.faults));self.assertEqual('opened',self.owner.state['copyIntent']['phase'])
        opened=deepcopy(self.owner.state['copyIntent']);self.owner=self.f.prefix('sources');before=self.files(exclude_header=True);counts=self.counts()
        write=PrivateFeatureState.write;lost=[]
        def committed(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.owner.store.path and previous['copyIntent']['phase']=='opened' and value['copyIntent']['phase']=='saved':
                lost.append(True);raise OSError('Modeled lost successful copy-recovery CAS return')
            return answer
        with patch.object(PrivateFeatureState,'write',committed),self.assertRaises(OSError):self.owner.recover_copy()
        self.assertEqual([True],lost);self.owner=self.f.prefix('sources');self.assertEqual('saved',self.owner.state['copyIntent']['phase'])
        recovered=self.owner.recover_copy();self.assertEqual(opened['file'],dict(device=recovered['device'],inode=recovered['inode']))
        self.assertEqual(before,self.files(exclude_header=True));self.assertEqual(counts,self.counts())
        self.faults=[]
        with patch.object(self.owner.records,'intent',self.loss(manifest='saved',count=17)),self.assertRaises(OSError):self.owner.index()
        self.assertEqual(1,len(self.faults));self.owner=self.f.prefix('sources')
        pending=deepcopy(self.owner.state['manifestIntent']);self.assertEqual('saved',pending['phase']);self.assertEqual(17,pending['reference']['count'])
        before=self.files(exclude_header=True);lost=[]
        def adopted(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.owner.store.path and previous['manifestIntent'] is not None and value['manifestIntent'] is None:
                lost.append(True);raise OSError('Modeled lost successful existing-manifest adoption CAS return')
            return answer
        with patch.object(PrivateFeatureState,'write',adopted),self.assertRaises(OSError):self.owner.recover_index()
        self.assertEqual([True],lost);self.owner=self.f.prefix('sources')
        self.assertIsNone(self.owner.state['manifestIntent']);self.assertEqual(pending['reference'],self.owner.recover_index())
        self.assertEqual(before,self.files(exclude_header=True));self.assertEqual(counts,self.counts())
        with self.assertRaises(NativeUIError):self.f.open('sources')
        self.assertEqual(counts,self.counts());self.owner.index();self.assertEqual(128,self.owner.history()['globalIndex'])
        before=self.files();self.assertEqual(self.owner.state['manifests'][0],self.owner.recover_index());self.assertEqual(before,self.files())
        read=OriginalFrameStore.read;attempts=[];retained=[]
        def pure(store,value):
            answer=read(store,value)
            if store.namespace=='tabletweb-sources-packets' and not attempts:
                attempts.append(True);prefix=closed._OWN_READ.get().prefix;retained.append(prefix)
                for operation in (self.owner.recover_copy,self.owner.recover_index,prefix.recover_copy,prefix.recover_index):
                    with self.assertRaises(NativeUIError):operation()
            return answer
        before=self.files()
        with patch.object(OriginalFrameStore,'read',pure):self.assertEqual(128,self.f.own()['globalIndex'])
        self.assertEqual([True],attempts);self.assertFalse(retained[0].alive)
        for operation in (retained[0].recover_copy,retained[0].recover_index):
            with self.assertRaises(NativeUIError):operation()
        self.assertEqual(before,self.files());self.assertEqual(counts,self.counts())
        # These are the first new native query and its actual file129, after
        # metadata-only recovery has completely left its boundary.
        active=self.f.open('sources');packet=active.capture(self.f.boundary.reader('sources'));self.assertEqual(129,packet['sequence'])
        before=self.files();counts=self.counts()
        for operation in (active.closed.recover_copy,active.closed.recover_index):
            with self.assertRaises(NativeUIError):operation()
        own=self.f.own();self.assertEqual(packet,own['nativeFloor']);self.assertFalse(own['peerAuthority'])
        result=parent.restore(self.s.root,self.s.binding,self.s.run,self.s.role,self.s.fixture,self.s.pid,self.s.lock,monotonic=self.s.monotonic)
        self.assertEqual(packet,result['children']['sources']);self.assertEqual(1,result['globalIndex'])
        self.assertEqual(before,self.files());self.assertEqual(counts,self.counts())

    def test_planned_copy_remains_blocked_both_absent_and_with_exact_foreign_file_without_owned_inode(self):
        with patch.object(self.owner.copies,'intent',self.loss(copy='planned')),self.assertRaises(OSError):self.owner.copy()
        self.assertEqual(1,len(self.faults));self.owner=self.f.prefix('sources');ref=self.owner.state['copyIntent']
        self.assertIsNone(ref['file']);path=self.owner.copies.path(ref);self.assertFalse(path.exists())
        self.unchanged_failure(self.owner.recover_copy)
        body=dict(tabletWebClosedHeaderFrameVersion=1,kind='sources',binding=self.s.binding,runId=self.s.run,role=self.s.role,index=1,frame=self.owner.body())
        raw=canonical(body);self.assertEqual(ref['sha256'],hashlib.sha256(raw).hexdigest())
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self.unchanged_failure(self.owner.recover_copy);self.assertEqual('planned',self.owner.state['copyIntent']['phase'])

    def test_known_opened_empty_copy_stays_partial_without_rewrite(self):
        with patch.object(self.owner.copies,'intent',self.loss(copy='opened')),self.assertRaises(OSError):self.owner.copy()
        self.assertEqual(1,len(self.faults));self.owner=self.f.prefix('sources');ref=self.owner.state['copyIntent'];path=self.owner.copies.path(ref)
        self.assertEqual(0,path.stat().st_size);self.assertEqual(ref['file']['inode'],path.stat().st_ino)
        self.unchanged_failure(self.owner.recover_copy)

    def test_known_opened_copy_missing_file_stays_owned_without_recreation(self):
        with patch.object(self.owner.copies,'intent',self.loss(copy='opened')),self.assertRaises(OSError):self.owner.copy()
        self.assertEqual(1,len(self.faults));self.owner=self.f.prefix('sources');path=self.owner.copies.path(self.owner.state['copyIntent'])
        path.unlink()  # Explicit fault to this test's newly owned copy only.
        self.unchanged_failure(self.owner.recover_copy,FileNotFoundError)

    def test_saved_copy_wrong_body_cannot_be_adopted_even_with_valid_owned_envelope_and_inode(self):
        body=self.owner.body();body['component']='trace';self.owner.copies.write(1,body)
        self.assertEqual('saved',self.owner.state['copyIntent']['phase'])
        self.assertEqual(body,self.owner.copies.read(self.owner.state['copyIntent']))
        self.faults.append(deepcopy(self.owner.state['copyIntent']));self.assertEqual(1,len(self.faults))
        self.unchanged_failure(self.owner.recover_copy)

    def test_saved_copy_same_bytes_new_inode_cannot_replace_the_owned_original(self):
        ref=self.copy_saved();path=self.owner.copies.path(ref);raw=path.read_bytes();old=path.stat().st_ino
        self.assertEqual(self.owner.body(),self.owner.copies.read(ref))
        descriptor,temp=tempfile.mkstemp(dir=self.s.root)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path);self.faults.append(path.stat().st_ino);self.assertEqual(1,len(self.faults))
        self.assertNotEqual(old,self.faults[0])
        self.unchanged_failure(self.owner.recover_copy)

    def test_planned_manifest_complete_file_is_not_reclassified_as_saved(self):
        self.interrupted_index('planned-complete');intent=deepcopy(self.owner.state['manifestIntent'])
        self.assertEqual('planned',intent['phase'])
        self.assertEqual(self.owner.old['records'][:3],self.owner.records.manifest(intent['reference']))
        self.unchanged_failure(self.owner.recover_index);self.assertEqual(intent,self.owner.state['manifestIntent'])

    def test_saved_manifest_foreign_membership_is_rejected_without_discovering_the_other_complete_file(self):
        self.interrupted_index();known=deepcopy(self.owner.state['manifestIntent']['reference'])
        original=PrivateFeatureState(self.owner.records.manifest_path(known)).read();foreign=deepcopy(original)
        foreign['entries'][-1]['inode']+=1;raw=canonical(foreign);ref=dict(known,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        PrivateFeatureState(self.owner.records.manifest_path(ref)).write(foreign,None)
        changed=deepcopy(self.owner.state);changed['manifestIntent']['reference']=ref;self.owner.save(changed)
        self.assertEqual(foreign['entries'],self.owner.records.manifest(ref))
        self.unchanged_failure(self.owner.recover_index)
        self.assertEqual(ref,self.owner.state['manifestIntent']['reference'])
        self.assertTrue(self.owner.records.manifest_path(known).is_file())

    def test_saved_manifest_missing_file_cannot_be_recreated(self):
        self.interrupted_index();path=self.owner.records.manifest_path(self.owner.state['manifestIntent']['reference']);path.unlink()
        self.unchanged_failure(self.owner.recover_index)

    def test_saved_manifest_partial_file_cannot_be_completed_from_expected_membership(self):
        self.interrupted_index();path=self.owner.records.manifest_path(self.owner.state['manifestIntent']['reference'])
        with path.open('r+b') as stream:stream.truncate(1)
        self.unchanged_failure(self.owner.recover_index)


if __name__=='__main__':unittest.main()
