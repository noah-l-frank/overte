"""UIKit-only original authority, modeled native producers and real files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_uikit_original_link as link,tablet_web_child_rotation as parent
from ios.self_tests import test_ios_tablet_web_uikit_segment as existing


class TabletUIKitOriginalLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletUIKitSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletUIKitSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.s=self.flow.source;self.evidence=self.flow.evidence

    def read(self,*,binding=None):
        s=self.s
        return link.read(s.root,s.binding if binding is None else binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_closed_bound_and_active_originals_survive_independent_peer_heads_without_exporting_authority(self):
        self.flow.base.build();prefix=self.flow.base.complete()
        counts=self.evidence.native_counts();originals=self.evidence.originals();inventory=self.evidence.inventory()
        closed=self.read();self.assertEqual((128,129,129),(closed['globalIndex'],closed['nextIndex'],closed['nextRaw']))
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(originals,self.evidence.originals())
        self.assertEqual(inventory,self.evidence.inventory())
        reference,packet129=self.flow.base.model_row(129,129);prefix.bind_successor(reference)
        bound=self.read();self.assertEqual(packet129,bound['nativeFloor']);self.assertEqual(129,bound['globalIndex'])
        owner=self.flow.open();packet130=owner.capture(self.flow.boundary.reader('uikit'))
        peer=self.s.children['trace'];previous=peer.store.read();before=parent._raw(peer.store.path)
        peer.store.write(previous,previous);after=parent._raw(peer.store.path)
        self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['inode'],after[1]['inode'])
        counts=self.evidence.native_counts();originals=self.evidence.originals();inventory=self.evidence.inventory()
        with self.assertRaises(NativeUIError):owner.history()
        s=self.s
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        retained=[];constructor=link._OriginalLinkPrefix.__init__
        def actual(scope,*args,**kwargs):
            try:return constructor(scope,*args,**kwargs)
            finally:retained.append(scope)
        with patch.object(link._OriginalLinkPrefix,'__init__',actual):result=self.read()
        self.assertEqual(packet130,result['nativeFloor']);self.assertEqual((130,131,131),
            (result['globalIndex'],result['nextIndex'],result['nextRaw']))
        for key in ('objects','targets','contacts','dispatches','pendingDispatches'):
            self.assertEqual(packet130[key],result['nativeFloor'][key])
        self.assertEqual('uikit',result['component']);self.assertTrue(result['historicalOnly']);self.assertTrue(result['subgraphOnly'])
        self.assertFalse(result['peerAuthority']);self.assertEqual('rotating',result['phase'])
        self.assertEqual(1,len(retained));scope=retained[0];self.assertFalse(scope.alive)
        for operation in (scope.guard,scope.history,scope.adopted,scope.copy,scope.index,lambda:scope.save({}),lambda:scope.bind_successor({})):
            with self.assertRaises(NativeUIError):operation()
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(originals,self.evidence.originals())
        self.assertEqual(inventory,self.evidence.inventory())
        # A foreign constructor also expires its scope before returning an
        # error. No partial reader may retain authority after failed entry.
        changed=deepcopy(s.binding);changed['generation']+=1
        with patch.object(link._OriginalLinkPrefix,'__init__',actual),self.assertRaises(NativeUIError):self.read(binding=changed)
        self.assertEqual(2,len(retained));self.assertFalse(retained[-1].alive)
        with self.assertRaises(NativeUIError):retained[-1].guard()
        # Change a peer only after a real own original has been opened.
        read=OriginalFrameStore.read;altered=[]
        def mutate(store,value):
            answer=read(store,value)
            if store.namespace=='tabletweb-uikit-packets' and not altered:
                old=peer.store.read();peer.store.write(old,old);altered.append(True)
            return answer
        with patch.object(link._OriginalLinkPrefix,'__init__',actual),patch.object(OriginalFrameStore,'read',mutate),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([True],altered);self.assertFalse(retained[-1].alive)
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(originals,self.evidence.originals())
        with self.assertRaises(NativeUIError):owner.history()
        # Own actual originals still need their original inode and bytes;
        # identical source metadata or a current peer census cannot repair it.
        ref=owner.originals.expand(owner.state['records'][-1]);path=owner.originals.path(ref)
        data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual('rotating',owner.store.read()['phase'])


if __name__=='__main__':unittest.main()
