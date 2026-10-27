"""Actual original-file DOM5/native peer composition, modeled native clocks.

Explicit independent prefix replies are not full Journey steps or native
timing qualification. No129 file is precreated by the prefix builder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom_continuation as dom_closed,tablet_web_dom_segment as dom
from ios.adapters import tablet_web_dom_original_link as dom_own
from ios.adapters import tablet_web_native_child_continuation as native,tablet_web_child_rotation as parent
from ios.self_tests import test_ios_tablet_web_native_child_continuation as existing
from ios.self_tests import test_ios_tablet_web_source_owner as source_fixture


class RetainedDirectory:
    """Keep this new multi-prefix scope's originals on pass, error or timeout."""
    def __init__(self):
        root=Path(__file__).resolve().parents[4]/'.ios-host-tmp'
        self.name=tempfile.mkdtemp(prefix='continuation5-dom-native-',dir=root)
    def cleanup(self):pass


class TabletNativePeerDOMFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletNativeChildContinuationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletNativeChildContinuationTests()
        with patch.object(source_fixture,'tempfile',SimpleNamespace(TemporaryDirectory=RetainedDirectory)):
            self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s,self.boundary=self.f.s,self.f.boundary
        print('Retained original scope: '+str(self.s.root),flush=True)

    def dom_arguments(self):
        s=self.s
        return s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,self.f.current_guard

    def dom_reader(self):return dom.TabletDOMSegment(*self.dom_arguments(),**self.f.clocks())

    def own_dom(self):
        s=self.s
        return dom_own.read(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def start(self):
        # Both native/DOM literal128 predecessors exist before the same nine
        # original descriptors freeze. The model supplies unavailable DOM
        # content, never a fabricated ready page or a product effect.
        self.boundary.frame['document'].update(status='unavailable',source={})
        self.f.build(['sources','dom'])
        value=dom_closed.prepare(self.s);dom_closed.install(self.s,value)
        prefix=dom_closed.TabletDOMClosedPrefix(*self.dom_arguments()[:-1],monotonic=self.s.monotonic)
        prefix.copy();prefix.index()
        first=dom.open_initial_segment(*self.dom_arguments(),**self.f.clocks())
        self.assertEqual(5,first.closed.state['tabletWebDOMContinuationVersion'])
        first_value=first.capture(self.boundary.reader('dom'));self.assertEqual(129,first_value['sequence'])
        self.f.complete('sources');source=self.f.open('sources')
        self.assertIsNone(source.closed.state['firstRecord']);self.assertEqual([],source.state['records'])
        source_value=source.capture(self.boundary.reader('sources'));self.assertEqual(129,source_value['sequence'])
        return first,source,first_value,source_value

    def test_actual_DOM5_and_sources129_require_independent_original_proof_then_fence_mutation_and_unknown_peer(self):
        first,source,first_value,source_value=self.start()
        counts=self.f.fixture.native_counts();originals=self.f.fixture.originals()
        with self.assertRaises(NativeUIError):first.history()
        proof=native.read_own;seen=[]
        def actual(*args,**kwargs):
            result=proof(*args,**kwargs);seen.append(deepcopy(result));return result
        with patch.object(native,'read_own',actual):current=self.dom_reader()
        self.assertEqual(1,len(seen));self.assertEqual('sources',seen[0]['component'])
        self.assertTrue(seen[0]['historicalOnly']);self.assertTrue(seen[0]['subgraphOnly']);self.assertFalse(seen[0]['peerAuthority'])
        self.assertEqual(source_value,seen[0]['nativeFloor']);self.assertEqual(first_value,current.history()[-1])
        self.assertEqual(counts,self.f.fixture.native_counts());self.assertEqual(originals,self.f.fixture.originals())
        with self.assertRaises(TypeError):current.closed.native_peers['sources']['sha256']='a'*64
        pins=current.closed.native_peers;current.closed.native_peers={}
        with self.assertRaises(NativeUIError):current.history()
        current.closed.native_peers=pins
        later=current.capture(self.boundary.reader('dom'));self.assertEqual(130,later['sequence'])
        s=self.s;counts=self.f.fixture.native_counts();originals=self.f.fixture.originals()
        historical=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(later,historical['children']['dom']);self.assertEqual(source_value,historical['children']['sources'])
        self.assertEqual(1,historical['globalIndex']);self.assertEqual(1,historical['frames'][0]['document']['sequence'])
        self.assertEqual(1,historical['frames'][0]['sources']['sequence'])
        self.assertEqual(counts,self.f.fixture.native_counts());self.assertEqual(originals,self.f.fixture.originals())
        # Read the real complete Sources graph first, then replace only its
        # mutable header with identical bytes at a different inode.
        mutations=[]
        def mutate(*args,**kwargs):
            result=proof(*args,**kwargs)
            before=parent._raw(source.store.path);value=source.store.read();source.store.write(value,value)
            after=parent._raw(source.store.path)
            self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['inode'],after[1]['inode'])
            mutations.append(True);return result
        with patch.object(native,'read_own',mutate),self.assertRaises(NativeUIError):self.dom_reader()
        self.assertEqual([True],mutations)
        with self.assertRaises(NativeUIError):current.history()
        admitted=self.dom_reader();self.assertEqual(later,admitted.history()[-1])
        self.assertEqual(counts,self.f.fixture.native_counts());self.assertEqual(originals,self.f.fixture.originals())
        # A fresh source reader independently follows DOM130. Losing the
        # issued130 CAS return leaves an unknown exact query before send.
        source=self.f.reopen('sources');write=PrivateFeatureState.write;issued=[]
        def lost(store,value,previous):
            result=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==source.store.path and pending is not None and pending['status']=='issued' and not issued:
                issued.append(deepcopy(pending));raise OSError('Modeled lost successful Sources130 issued CAS return')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises((OSError,NativeUIError)):
            source.capture(self.boundary.reader('sources'))
        self.assertEqual(1,len(issued));self.assertEqual(130,issued[0]['index']);self.assertFalse(issued[0]['sendReturned'])
        self.assertEqual(counts,self.f.fixture.native_counts())
        with self.assertRaises(NativeUIError):self.dom_reader()
        with patch.object(native,'read_own',side_effect=AssertionError('No native peer authority from an own DOM graph')):
            own=self.own_dom()
        self.assertEqual(later,own['nativeFloor']);self.assertTrue(own['subgraphOnly']);self.assertFalse(own['peerAuthority'])
        self.assertEqual(counts,self.f.fixture.native_counts());self.assertEqual(originals,self.f.fixture.originals())


if __name__=='__main__':unittest.main()
