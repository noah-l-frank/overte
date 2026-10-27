"""UIKit original closure; host-model contacts are never physical release proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from ios.adapters import tablet_web_uikit_continuation as closed
from ios.adapters.tablet_web_segments import TabletWebSourceSegments,sha
from ios.self_tests import test_ios_tablet_web_dom_segment as existing


class TabletUIKitContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletDOMSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.f=self.flow.f;self.source=self.f.source;self.uikit=self.source.children['uikit']
        self.fixture=PrivateFeatureState(self.f.f.root/'uikit-boundary-fixture.json');self.fixture_state=None

    def intent(self,value):
        self.fixture.write(value,self.fixture_state);self.fixture_state=deepcopy(value)

    def build(self):
        s=self.source;child=self.uikit
        parts=TabletWebSourceSegments(s.root,s.binding,s.run,s.role,'uikit',lambda:True,self.intent,monotonic=s.monotonic)
        originals=OriginalFrameStore(s.root,s.binding,s.run,s.role,lambda:True,lambda kind,value:self.intent(dict(kind=kind,value=value)),
            namespace='tabletweb-uikit-packets',schema_prefix='tabletWebSourcePacket',monotonic=s.monotonic)
        refs=deepcopy(child.state['records']);cursor=child.state['nextRaw']
        for index in range(2,129):
            before=child.stamp();self.intent(dict(phase='modeled-query',index=index))
            packet=self.f.f.boundary.reader('uikit').read(s.run,s.fixture);query=deepcopy(self.f.f.boundary.sent['uikit'])
            raw=self.f.f.boundary.raw['uikit'].encode();parent=parts.write('uikit',sha(canonical(query)),raw,cursor);after=child.stamp()
            row=dict(tabletWebSourcePacketVersion=2,index=index,before=before,after=after,query=query,sendReturned=True,status='returned',
                raws=[dict(before=before,after=after,segments=parent,inspection=parts.inspect(parent),outcome='accepted')],
                unsafe=[],resultSha256=sha(canonical(packet)),readbacks=[])
            refs.append(originals.write(index,row));cursor+=1
        previous=deepcopy(child.state);child.state.update(records=refs,nextRaw=cursor);child.store.write(child.state,previous)
        child.saved=deepcopy(child.state);child.history();self.flow.bound();self.dom=self.flow.open()
        self.dom.capture(self.f.f.boundary.reader('dom'));return self

    def owner(self):
        s=self.source
        return closed.TabletUIKitClosedPrefix(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def freeze(self):
        value=closed.prepare(self.source);closed.install(self.source,value);return value

    def test_original_UIKit128_tail_keeps_every_contact_object_dispatch_and_global_raw_cursor(self):
        self.build();packet=self.uikit.history()[-1];old=self.uikit.store.path.read_bytes();before=self.f.originals();self.freeze()
        counts=self.f.native_counts();owner=self.owner();owner.copy();owner.index();after=self.f.originals();actual=owner.history()
        self.assertEqual(old,closed.decode(owner.state,owner.expected)[0]);self.assertEqual(packet,actual['nativeFloor'])
        self.assertEqual((128,129,129),(actual['globalIndex'],actual['nextIndex'],actual['nextRaw']))
        for key in ('objects','targets','contacts','dispatches','pendingDispatches'):self.assertEqual(packet[key],actual['nativeFloor'][key])
        self.assertTrue(actual['historicalOnly']);self.assertEqual('rotating',actual['phase'])
        self.assertEqual(before,{name:value for name,value in after.items() if name in before});self.assertEqual(counts,self.f.native_counts())
        with self.assertRaises(NativeUIError):self.dom.history()
        with self.assertRaises(NativeUIError):closed.read_barrier(owner.state,self.source.binding,self.source.run,self.source.role,self.source.fixture,self.source.pid,'uikit')

    def test_lost_successful_UIKit_CAS_stays_owned_and_never_restores_lower_writer(self):
        self.build();value=closed.prepare(self.source);write=PrivateFeatureState.write;lost=[];counts=self.f.native_counts()
        def actual(store,current,previous):
            result=write(store,current,previous)
            if store.path==self.uikit.store.path and current.get('tabletWebUIKitContinuationVersion')==1:
                lost.append(True);raise OSError('Modeled lost UIKit fence CAS return')
            return result
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):closed.install(self.source,value)
        self.assertEqual([True],lost);self.assertEqual(value,self.uikit.store.read());owner=self.owner()
        with self.assertRaises(NativeUIError):owner.history()
        with self.assertRaises(NativeUIError):closed.install(self.source,value)
        self.assertEqual(value,self.uikit.store.read());self.assertEqual(counts,self.f.native_counts())

    def test_changed_DOM_identity_invalidates_copy_scope_before_file_creation(self):
        self.build();self.freeze();owner=self.owner();old=self.dom.store.read();self.dom.store.write(old,old)
        counts=self.f.native_counts();inventory=self.f.inventory()
        with self.assertRaises(NativeUIError):owner.copy()
        self.assertEqual(inventory,self.f.inventory());self.assertEqual(counts,self.f.native_counts())
        self.assertIsNone(self.uikit.store.read()['copyIntent'])


if __name__=='__main__':unittest.main()
