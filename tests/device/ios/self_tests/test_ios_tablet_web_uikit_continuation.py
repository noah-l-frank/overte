"""UIKit original closure; host-model contacts are never physical release proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from unittest.mock import patch
import zlib

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
        s=self.source
        self.parts=TabletWebSourceSegments(s.root,s.binding,s.run,s.role,'uikit',lambda:True,self.intent,monotonic=s.monotonic)
        self.originals=OriginalFrameStore(s.root,s.binding,s.run,s.role,lambda:True,lambda kind,value:self.intent(dict(kind=kind,value=value)),
            namespace='tabletweb-uikit-packets',schema_prefix='tabletWebSourcePacket',monotonic=s.monotonic)

    def intent(self,value):
        self.fixture.write(value,self.fixture_state);self.fixture_state=deepcopy(value)

    def build(self):
        child=self.uikit
        refs=deepcopy(child.state['records']);cursor=child.state['nextRaw']
        for index in range(2,129):
            reference,_packet=self.model_row(index,cursor);refs.append(reference);cursor+=1
        previous=deepcopy(child.state);child.state.update(records=refs,nextRaw=cursor);child.store.write(child.state,previous)
        child.saved=deepcopy(child.state);child.history();self.flow.bound();self.dom=self.flow.open()
        self.dom.capture(self.f.f.boundary.reader('dom'));return self

    def model_row(self,index,raw_index):
        s=self.source;before=self.uikit.stamp();self.intent(dict(phase='modeled-query',index=index))
        packet=self.f.f.boundary.reader('uikit').read(s.run,s.fixture);query=deepcopy(self.f.f.boundary.sent['uikit'])
        raw=self.f.f.boundary.raw['uikit'].encode();parent=self.parts.write('uikit',sha(canonical(query)),raw,raw_index);after=self.uikit.stamp()
        row=dict(tabletWebSourcePacketVersion=2,index=index,before=before,after=after,query=query,sendReturned=True,status='returned',
            raws=[dict(before=before,after=after,segments=parent,inspection=self.parts.inspect(parent),outcome='accepted')],
            unsafe=[],resultSha256=sha(canonical(packet)),readbacks=[])
        return self.originals.write(index,row),packet

    def owner(self):
        s=self.source
        return closed.TabletUIKitClosedPrefix(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def freeze(self):
        value=closed.prepare(self.source);closed.install(self.source,value);return value

    def complete(self):
        self.freeze();owner=self.owner();owner.copy();owner.index();return owner

    def test_original129_lost_successful_binding_reopens_exact_successor_without_query_or_release(self):
        self.build();owner=self.complete();old=closed.decode(owner.state,owner.expected)[0];body=deepcopy(owner.body())
        reference,packet=self.model_row(129,129);before=self.f.originals();inventory=self.f.inventory();counts=self.f.native_counts()
        write=PrivateFeatureState.write;lost=[]
        def actual(store,value,previous):
            result=write(store,value,previous)
            if store.path==owner.store.path and value.get('tabletWebUIKitContinuationVersion')==2:
                lost.append(True);raise OSError('Modeled lost successful UIKit129 binding return')
            return result
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):owner.bind_successor(reference)
        self.assertEqual([True],lost);saved=owner.store.read();self.assertEqual(reference,saved['successor'])
        with self.assertRaises(NativeUIError):owner.bind_successor(reference)
        reopened=self.owner();actual=reopened.adopted()
        self.assertEqual((129,130,130),(actual['globalIndex'],actual['nextIndex'],actual['nextRaw']))
        self.assertEqual(packet,actual['nativeFloor']);self.assertTrue(actual['historicalOnly']);self.assertEqual('rotating',actual['phase'])
        for key in ('objects','targets','contacts','dispatches','pendingDispatches'):self.assertEqual(packet[key],actual['nativeFloor'][key])
        self.assertEqual(old,closed.decode(saved,reopened.expected)[0]);self.assertEqual(body,reopened.body())
        self.assertEqual(body,reopened.copies.read(reopened.state['copyIntent']));self.assertEqual(before,self.f.originals())
        self.assertEqual(counts,self.f.native_counts());self.assertEqual(saved,reopened.store.read())
        self.assertEqual({name:value for name,value in inventory.items() if name!=owner.store.path.name},
            {name:value for name,value in self.f.inventory().items() if name!=owner.store.path.name})
        with self.assertRaises(NativeUIError):reopened.bind_successor(reference)
        with self.assertRaises(NativeUIError):self.dom.history()

    def test_original129_native_sequence_regression_cannot_be_replaced_by_storage_index(self):
        self.build();owner=self.complete();self.f.f.boundary.frame['touches']['sequence']=0
        reference,packet=self.model_row(129,129);self.assertEqual(128,packet['sequence'])
        before=owner.store.path.read_bytes();counts=self.f.native_counts();inventory=self.f.inventory()
        with self.assertRaises(NativeUIError):owner.bind_successor(reference)
        self.assertEqual(before,owner.store.path.read_bytes());self.assertEqual(counts,self.f.native_counts())
        self.assertEqual(inventory,self.f.inventory());self.assertEqual(1,owner.state['tabletWebUIKitContinuationVersion'])

    def test_original129_cannot_drop_contacts_and_dispatches_from_actual_prefix(self):
        self.build();owner=self.complete();native=self.f.f.boundary.frame['touches']
        self.assertTrue(native['contacts']);self.assertTrue(native['dispatches'])
        native.update(contacts=[],dispatches=[],pendingDispatches=[],dispatchSequence=0)
        reference,packet=self.model_row(129,129);self.assertEqual(129,packet['sequence'])
        before=owner.store.path.read_bytes();counts=self.f.native_counts();inventory=self.f.inventory()
        with self.assertRaises(NativeUIError):owner.bind_successor(reference)
        self.assertEqual(before,owner.store.path.read_bytes());self.assertEqual(counts,self.f.native_counts())
        self.assertEqual(inventory,self.f.inventory());self.assertEqual(1,owner.state['tabletWebUIKitContinuationVersion'])

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


class TabletUIKitContinuationMetadataTests(unittest.TestCase):
    """Syntax compatibility grants no file, contact or native authority."""
    def value(self,version,legacy):
        value,expected,raw=existing.TabletDOMSegmentMetadataTests().value(1,legacy)
        old=json.loads(raw);old['component']='uikit';raw=(json.dumps(old,indent=1)+'\n').encode()
        value.pop('tabletWebDOMContinuationVersion');value['tabletWebUIKitContinuationVersion']=version;value['profile']=closed.PROFILE
        prior=value['previousHeader'];prior.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            data=base64.b64encode(zlib.compress(raw)).decode());prior['signature']['bytes']=len(raw)
        if version==2:value['successor']=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=129)
        return value,expected,raw

    def test_literal_metadata1_and_bound2_preserve_exact_Packet1_and2_predecessors(self):
        for version in (1,2):
            for legacy in (1,2):
                with self.subTest(version=version,legacy=legacy):
                    value,expected,raw=self.value(version,legacy);before=deepcopy(value)
                    with patch.object(OriginalFrameStore,'__init__',side_effect=AssertionError('No store from metadata syntax')):
                        actual,old=closed.decode(value,expected)
                    self.assertEqual(raw,actual);self.assertEqual(legacy,old['tabletWebPacketsVersion']);self.assertEqual(before,value)

    def test_metadata1_stays_literal_and_metadata2_requires_exact_nonnull_global129(self):
        for kind in ('extra-v1','null','reset','later','missing-identity'):
            with self.subTest(kind=kind):
                value,expected,_raw=self.value(1 if kind=='extra-v1' else 2,2)
                if kind=='extra-v1':value['successor']=None
                elif kind=='null':value['successor']=None
                elif kind=='reset':value['successor']['index']=1
                elif kind=='later':value['successor']['index']=130
                else:value['successor'].pop('inode')
                with self.assertRaises(NativeUIError):closed.decode(value,expected)


if __name__=='__main__':unittest.main()
