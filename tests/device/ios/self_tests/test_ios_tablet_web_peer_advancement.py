"""Independent actual DOM/UIKit query ownership across mutable peer heads.

Prefix builders model native producers and own real original files. This is
not a physical input, real-time deadline or whole SourceReady qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom_segment as dom,tablet_web_uikit_segment as uikit
from ios.adapters import tablet_web_dom_original_link as dom_link,tablet_web_uikit_original_link as ui_link
from ios.adapters import tablet_web_child_rotation as parent
from ios.self_tests import test_ios_tablet_web_uikit_continuation as existing


class TabletPeerAdvancementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletUIKitContinuationTests.setUpClass()

    def setUp(self):
        self.fixture=existing.TabletUIKitContinuationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.s=self.fixture.source;self.dom_fixture=self.fixture.f;self.flow=self.fixture.flow
        self.boundary=self.dom_fixture.f.boundary;self.current_guard=self.flow.current_guard

    def arguments(self):
        s=self.s
        return s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,self.current_guard

    def clocks(self):return self.flow.clocks()
    def dom(self):return dom.TabletDOMSegment(*self.arguments(),**self.clocks())
    def uikit(self):return uikit.TabletUIKitSegment(*self.arguments(),**self.clocks())

    def start(self):
        # UIKit128 must exist before the DOM builder freezes the parent's
        # nine literal child descriptors. Neither builder creates row129.
        child=self.fixture.uikit;refs=deepcopy(child.state['records']);cursor=child.state['nextRaw']
        for index in range(2,129):
            reference,_packet=self.fixture.model_row(index,cursor);refs.append(reference);cursor+=1
        previous=deepcopy(child.state);child.state.update(records=refs,nextRaw=cursor)
        child.store.write(child.state,previous);child.saved=deepcopy(child.state);child.history()
        self.dom_fixture.build();self.dom_fixture.complete()
        first_dom=dom.open_initial_segment(*self.arguments(),**self.clocks())
        dom129=first_dom.capture(self.boundary.reader('dom'))
        self.fixture.complete()
        first_ui=uikit.open_initial_segment(*self.arguments(),**self.clocks())
        ui129=first_ui.capture(self.boundary.reader('uikit'))
        return first_dom,first_ui,dom129,ui129

    def test_both_real129_queries_then_independent130_and_mid_proof_mutation_unknown131_keep_authority_separate(self):
        first_dom,first_ui,dom129,ui129=self.start()
        self.assertEqual((129,129),(dom129['sequence'],ui129['sequence']))
        self.assertEqual(5,first_dom.closed.state['tabletWebDOMContinuationVersion'])
        self.assertEqual(5,first_ui.closed.state['tabletWebUIKitContinuationVersion'])
        counts=self.dom_fixture.native_counts();originals=self.dom_fixture.originals()
        with self.assertRaises(NativeUIError):first_dom.history()
        prove=ui_link.read;seen=[]
        def actual(*args,**kwargs):
            result=prove(*args,**kwargs);seen.append(deepcopy(result));return result
        with patch.object(ui_link,'read',actual):second_dom=self.dom()
        self.assertEqual(1,len(seen));self.assertTrue(seen[0]['subgraphOnly']);self.assertFalse(seen[0]['peerAuthority'])
        self.assertEqual(ui129,seen[0]['nativeFloor']);self.assertIsNotNone(second_dom.closed.uikit_peer)
        self.assertEqual(counts,self.dom_fixture.native_counts());self.assertEqual(originals,self.dom_fixture.originals())
        dom130=second_dom.capture(self.boundary.reader('dom'));self.assertEqual(130,dom130['sequence'])
        with self.assertRaises(NativeUIError):first_ui.history()
        second_ui=self.uikit();ui130=second_ui.capture(self.boundary.reader('uikit'))
        self.assertEqual(130,ui130['sequence'])
        for key in ('objects','targets','contacts','dispatches','pendingDispatches'):
            self.assertEqual(ui130[key],second_ui.history()[-1][key])
        with self.assertRaises(NativeUIError):second_dom.history()
        fresh=self.dom();self.assertEqual(dom130,fresh.history()[-1])
        counts=self.dom_fixture.native_counts();originals=self.dom_fixture.originals();inventory=self.dom_fixture.inventory()
        s=self.s;proof=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(dom130,proof['children']['dom']);self.assertEqual(ui130,proof['children']['uikit'])
        self.assertEqual(1,proof['globalIndex']);self.assertEqual(1,proof['frames'][0]['document']['sequence'])
        self.assertEqual(1,proof['frames'][0]['touches']['sequence'])
        self.assertEqual(counts,self.dom_fixture.native_counts());self.assertEqual(originals,self.dom_fixture.originals())
        self.assertEqual(inventory,self.dom_fixture.inventory())
        # A proof cannot adopt a different head born during that same read,
        # even when the actual replacement bytes are identical.
        changed=[]
        def mutate(*args,**kwargs):
            result=prove(*args,**kwargs)
            previous=second_ui.store.read();before=parent._raw(second_ui.store.path)
            second_ui.store.write(previous,previous);after=parent._raw(second_ui.store.path)
            self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['inode'],after[1]['inode'])
            changed.append(True);return result
        with patch.object(ui_link,'read',mutate),self.assertRaises(NativeUIError):self.dom()
        self.assertEqual([True],changed);self.assertEqual(counts,self.dom_fixture.native_counts())
        with self.assertRaises(NativeUIError):fresh.history()
        # At a new entry a complete known graph is independently proved;
        # no old reader's stored identity is silently refreshed in place.
        admitted=self.dom();self.assertEqual(dom130,admitted.history()[-1])
        self.assertEqual(counts,self.dom_fixture.native_counts());self.assertEqual(originals,self.dom_fixture.originals())
        # An issued query remains unknown after a lost successful CAS. It
        # cannot become peer admission merely because DOM's graph is valid.
        write=PrivateFeatureState.write;lost=[]
        def issued(store,value,previous):
            result=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==second_ui.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost UIKit131 issued CAS return before send')
            return result
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            second_ui.capture(self.boundary.reader('uikit'))
        self.assertEqual(1,len(lost));self.assertEqual(131,lost[0]['index'])
        self.assertEqual(counts,self.dom_fixture.native_counts())
        with self.assertRaises(NativeUIError):self.dom()
        # The own historical link never invokes the peer admission hook.
        # It may report original DOM130, with no claim about UIKit131.
        inventory=self.dom_fixture.inventory()
        with patch.object(ui_link,'read',side_effect=AssertionError('No peer proof from an own DOM link')):
            own=dom_link.read(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(dom130,own['nativeFloor']);self.assertFalse(own['peerAuthority']);self.assertTrue(own['subgraphOnly'])
        self.assertEqual(counts,self.dom_fixture.native_counts());self.assertEqual(originals,self.dom_fixture.originals())
        self.assertEqual(inventory,self.dom_fixture.inventory())


if __name__=='__main__':unittest.main()
