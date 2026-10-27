"""DOM-only archive authority; changed peers are never SourceReady evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_dom_original_link as link,tablet_web_child_rotation as parent
from ios.self_tests import test_ios_tablet_web_dom_segment as existing


class TabletDOMOriginalLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletDOMSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.f=self.flow.f;self.flow.bound();self.owner=self.flow.open()
        self.packet=self.owner.capture(self.f.f.boundary.reader('dom'))

    def read(self,*,binding=None):
        s=self.f.source
        return link.read(s.root,s.binding if binding is None else binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_DOM_subgraph_remains_original_while_changed_peer_stays_unqualified_and_scope_expires(self):
        peer=self.f.source.children['uikit'];previous=peer.store.read()
        peer.store.write(previous,previous);counts=self.f.native_counts();inventory=self.f.inventory()
        with self.assertRaises(NativeUIError):self.owner.history()
        s=self.f.source
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        constructor=link._OriginalLinkPrefix.__init__;retained=[]
        def actual(owner,*args,**kwargs):
            constructor(owner,*args,**kwargs);retained.append(owner)
        with patch.object(link._OriginalLinkPrefix,'__init__',actual):result=self.read()
        self.assertEqual(self.packet,result['nativeFloor']);self.assertEqual(130,result['globalIndex'])
        self.assertEqual('dom',result['component']);self.assertTrue(result['historicalOnly']);self.assertTrue(result['subgraphOnly'])
        self.assertFalse(result['peerAuthority']);self.assertEqual('rotating',result['phase'])
        self.assertEqual(1,len(retained));scope=retained[0];self.assertFalse(scope.alive)
        for operation in (scope.guard,scope.history,scope.copy,scope.index,lambda:scope.save({}),lambda:scope.bind_successor({})):
            with self.assertRaises(NativeUIError):operation()
        with self.assertRaises(NativeUIError):self.owner.history()
        self.assertEqual(counts,self.f.native_counts());self.assertEqual(inventory,self.f.inventory())

    def test_mid_read_peer_identity_change_and_foreign_binding_refuse_without_native_query(self):
        changed=deepcopy(self.f.source.binding);changed['generation']+=1;counts=self.f.native_counts()
        with self.assertRaises(NativeUIError):self.read(binding=changed)
        read=OriginalFrameStore.read;peer=self.f.source.children['uikit'];altered=[]
        def actual(store,value):
            result=read(store,value)
            if store.namespace=='tabletweb-dom-packets' and not altered:
                old=peer.store.read();peer.store.write(old,old);altered.append(True)
            return result
        with patch.object(OriginalFrameStore,'read',actual),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([True],altered);self.assertEqual(counts,self.f.native_counts())
        self.assertEqual('rotating',self.f.head.read()['phase'])


if __name__=='__main__':unittest.main()
