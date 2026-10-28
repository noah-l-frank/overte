"""Real UIKit128 copy WAL recovery; native producers/clocks remain models.

No three-prefix replay, UIKit129 acquisition, page result or whole feature is
claimed. All faults belong to newly created, independently owned test files.
"""
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
from ios.adapters import tablet_web_uikit_continuation as closed
from ios.adapters import tablet_web_uikit_original_link as own
from ios.adapters import tablet_web_uikit_segment as active
from ios.self_tests import test_ios_tablet_web_uikit_continuation as existing


class TabletUIKitCopyRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletUIKitContinuationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletUIKitContinuationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.build();self.f.freeze();self.owner=self.f.owner();self.s=self.f.source
        self.evidence=self.f.f;self.boundary=self.evidence.f.boundary;self.markers=[]

    def files(self,*,exclude_header=False):
        return {path.name:(closed.EmoteOriginalLease.signature(path.lstat()),hashlib.sha256(path.read_bytes()).hexdigest())
            for path in self.s.root.iterdir() if path.is_file() and (not exclude_header or path!=self.owner.store.path)}

    def native(self):
        return self.evidence.native_counts(),self.boundary.host,self.boundary.mono,self.boundary.epoch

    def reopen(self):self.owner=self.f.owner();return self.owner

    def interrupted_copy(self,phase):
        intent=self.owner.intent
        def lost(kind,value):
            if kind=='original' and phase=='complete' and value['phase']=='saved':
                self.markers.append(deepcopy(value));raise OSError('Complete UIKit copy before saved transition')
            answer=intent(kind,value)
            if kind=='original' and value['phase']==phase:
                self.markers.append(deepcopy(value));raise OSError('Lost actual UIKit copy transition return')
            return answer
        with patch.object(self.owner.copies,'intent',lost),self.assertRaises(OSError):self.owner.copy()
        self.assertEqual(1,len(self.markers));self.reopen()

    def blocked(self):
        before=self.files();native=self.native()
        with patch.object(OriginalFrameStore,'write',side_effect=AssertionError('No original creation')), \
                patch.object(OriginalFrameStore,'append',side_effect=AssertionError('No manifest creation')), \
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Blocked recovery wrote metadata')), \
                self.assertRaises(NativeUIError):self.owner.recover_copy()
        self.assertEqual(before,self.files());self.assertEqual(native,self.native())

    def test_complete_owned_copy_survives_lost_recovery_CAS_then_indexes_and_opens_without_query(self):
        self.interrupted_copy('complete');reference=deepcopy(self.owner.state['copyIntent'])
        self.assertEqual('opened',reference['phase']);self.assertEqual(self.owner.body(),self.owner.copies.read(reference))
        before=self.files(exclude_header=True);native=self.native();write=PrivateFeatureState.write;committed=[]
        def lost(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.owner.store.path and previous['copyIntent']['phase']=='opened' and value['copyIntent']['phase']=='saved':
                committed.append(deepcopy(value['copyIntent']));raise OSError('Lost successful UIKit copy recovery CAS return')
            return answer
        with patch.object(OriginalFrameStore,'write',side_effect=AssertionError('No original overwrite')), \
                patch.object(OriginalFrameStore,'append',side_effect=AssertionError('No new manifest during recovery')), \
                patch.object(PrivateFeatureState,'write',lost),self.assertRaises(OSError):self.owner.recover_copy()
        self.assertEqual(1,len(committed));self.reopen();self.assertEqual('saved',self.owner.state['copyIntent']['phase'])
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Idempotent recovery wrote metadata')):
            recovered=self.owner.recover_copy()
        self.assertEqual(reference['file'],dict(device=recovered['device'],inode=recovered['inode']))
        self.assertEqual(before,self.files(exclude_header=True));self.assertEqual(native,self.native())
        self.owner.index();self.assertEqual(128,self.owner.history()['globalIndex'])
        before=self.files();retained=[];read=OriginalFrameStore.read
        def inside(store,value):
            result=read(store,value);prefix=getattr(store.guard,'__self__',None)
            if type(prefix) is own._OriginalLinkPrefix and store.namespace=='tabletweb-uikit-packets' and not retained:
                retained.append(prefix);self.assertTrue(own.own_read_active())
                for operation in (self.owner.recover_copy,prefix.recover_copy):
                    with self.assertRaises(NativeUIError):operation()
            return result
        s=self.s
        with patch.object(OriginalFrameStore,'read',inside):
            result=own.read(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(1,len(retained));self.assertFalse(retained[0].alive);self.assertFalse(own.own_read_active())
        with self.assertRaises(NativeUIError):retained[0].recover_copy()
        self.assertEqual(128,result['globalIndex']);self.assertTrue(result['subgraphOnly']);self.assertFalse(result['peerAuthority'])
        self.assertEqual(before,self.files());self.assertEqual(native,self.native())
        # Existing initial-segment code consumes the recovered complete prefix.
        # This journals no query129 and supplies no native/whole authority.
        segment=active.open_initial_segment(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,lambda:True,
            monotonic=s.monotonic,epoch_ms=lambda:int(self.boundary.host+self.boundary.mono*1000))
        self.assertEqual(129,segment._next_index());self.assertEqual(129,segment.state['nextRaw'])
        self.assertEqual([],segment.state['records']);self.assertIsNone(segment.state['pending'])
        before=self.files()
        with self.assertRaises(NativeUIError):segment.closed.recover_copy()
        self.assertEqual(before,self.files());self.assertEqual(native,self.native())

    def test_planned_copy_stays_blocked_absent_and_with_complete_but_unowned_bytes(self):
        self.interrupted_copy('planned');reference=self.owner.state['copyIntent'];path=self.owner.copies.path(reference)
        self.assertEqual('planned',reference['phase']);self.assertIsNone(reference['file']);self.assertFalse(path.exists())
        self.blocked()
        body=dict(tabletWebClosedHeaderFrameVersion=1,kind='sources',binding=self.s.binding,
            runId=self.s.run,role=self.s.role,index=1,frame=self.owner.body())
        raw=canonical(body);self.assertEqual(reference['sha256'],hashlib.sha256(raw).hexdigest())
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self.blocked();self.assertIsNone(self.owner.state['copyIntent']['file'])

    def test_opened_empty_original_stays_owned_and_is_never_completed_by_recovery(self):
        self.interrupted_copy('opened');reference=self.owner.state['copyIntent'];path=self.owner.copies.path(reference)
        self.assertEqual(0,path.stat().st_size);self.assertEqual(reference['file']['inode'],path.stat().st_ino)
        self.blocked();self.assertEqual('opened',self.owner.state['copyIntent']['phase'])

    def test_truncated_owned_prefix_stays_partial_without_rewriting(self):
        self.interrupted_copy('complete');reference=self.owner.state['copyIntent'];path=self.owner.copies.path(reference)
        full=path.read_bytes();inode=path.stat().st_ino
        retention=self.enterContext(tempfile.TemporaryDirectory(prefix='tablet-uikit-copy-before-truncation-'))
        retained=Path(retention)/path.name;self.assertFalse(retained.is_relative_to(self.s.root))
        retained.write_bytes(full);retained.chmod(0o600)
        # Deliberate fault only to this test's new, not-yet-saved owned copy.
        with path.open('r+b') as stream:stream.truncate(len(full)//2)
        self.assertEqual(inode,path.stat().st_ino);self.assertGreater(path.stat().st_size,0)
        self.assertLess(path.stat().st_size,reference['bytes']);self.assertEqual(full,retained.read_bytes())
        self.blocked();self.assertEqual('opened',self.owner.state['copyIntent']['phase'])

    def test_equal_bytes_on_new_inode_cannot_replace_the_owned_original(self):
        self.interrupted_copy('complete');reference=self.owner.state['copyIntent'];path=self.owner.copies.path(reference)
        raw=path.read_bytes();inode=path.stat().st_ino;members=set(self.s.root.iterdir())
        retention=self.enterContext(tempfile.TemporaryDirectory(prefix='tablet-uikit-copy-old-inode-'))
        retained=Path(retention)/path.name;self.assertFalse(retained.is_relative_to(self.s.root))
        self.assertEqual(path.stat().st_dev,retained.parent.stat().st_dev)
        path.rename(retained);path.write_bytes(raw);path.chmod(0o600)
        self.assertEqual(inode,retained.stat().st_ino);self.assertNotEqual(inode,path.stat().st_ino)
        self.assertEqual(raw,path.read_bytes());self.assertEqual(members,set(self.s.root.iterdir()))
        self.blocked()

    def test_foreign_run_process_or_source_cannot_adopt_the_existing_copy(self):
        self.interrupted_copy('complete');expected=deepcopy(self.owner.expected)
        for field in ('run','process','source'):
            with self.subTest(field=field):
                changed=deepcopy(expected)
                if field=='run':changed['runId']='e'*32
                elif field=='process':changed['processId']=32;changed['binding']['processIdentity']='32'
                else:changed['binding']['sourceRevision']='e'*40
                self.owner.expected=changed;self.assertNotEqual(expected,self.owner.expected)
                try:self.blocked()
                finally:self.owner.expected=deepcopy(expected)

    def test_fully_owned_foreign_body_cannot_stand_in_for_the_literal_prefix(self):
        foreign=deepcopy(self.owner.body());foreign['scope']['runId']='e'*32
        foreign['scope']['processId']=32
        foreign['scope']['binding'].update(processIdentity='32',sourceRevision='e'*40)
        native=self.native()
        # Explicit lower-store fault: a real owned file and valid frame
        # envelope contain another scope, rather than this prefix's body.
        self.owner.copies.write(1,foreign);self.reopen()
        reference=self.owner.state['copyIntent'];self.assertEqual('saved',reference['phase'])
        self.assertEqual(foreign,self.owner.copies.read(reference))
        self.assertNotEqual(self.owner.body(),foreign);self.assertEqual(native,self.native())
        self.blocked()


if __name__=='__main__':unittest.main()
