"""DOM128/129 codec boundary with modeled native producers and real originals.

The bounded fixture writes independent query replies through the unchanged
raw/frame stores, not 128 full Journey captures. No runtime capacity, native
clock, input admission or physical-device qualification is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from ios.adapters import tablet_web_child_rotation as parent,tablet_web_dom_continuation as continuation
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters.tablet_web_segments import TabletWebSourceSegments,sha
from ios.self_tests import test_ios_tablet_web_child_rotation as existing


class TabletDOMContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletChildRotationTests.setUpClass()

    def setUp(self):
        fixture=existing.TabletChildRotationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.f,self.source,self.expected,self.head=fixture.f,fixture.source,fixture.expected,fixture.head
        self.freeze,self.originals,self.native_counts=fixture.freeze,fixture.originals,fixture.native_counts

    def build(self,count=128,*,last_status='returned'):
        self.dom=self.source.children['dom'];self.f.boundary.frame['document'].update(status='unavailable',source={})
        self.fixture_intent=PrivateFeatureState(self.f.root/'dom-boundary-fixture.json')
        self.fixture_state=None
        self.parts_store=TabletWebSourceSegments(self.f.root,self.source.binding,self.source.run,self.source.role,'dom',
            lambda:True,self.write_intent,monotonic=self.source.monotonic)
        self.rows_store=OriginalFrameStore(self.f.root,self.source.binding,self.source.run,self.source.role,lambda:True,
            lambda kind,value:self.write_intent(dict(kind=kind,value=value)),
            namespace='tabletweb-dom-packets',schema_prefix='tabletWebSourcePacket',monotonic=self.source.monotonic)
        records=deepcopy(self.dom.state['records']);cursor=self.dom.state['nextRaw']
        for index in range(2,count+1):
            reference,packet=self.model_row(index,cursor,status=last_status if index==count else 'returned');records.append(reference);cursor+=1
        previous=deepcopy(self.dom.state);self.dom.state.update(records=records,nextRaw=cursor)
        self.dom.store.write(self.dom.state,previous);self.dom.saved=deepcopy(self.dom.state)
        self.dom.history();self.freeze();return self

    def write_intent(self,value):
        self.fixture_intent.write(value,self.fixture_state);self.fixture_state=deepcopy(value)

    def model_row(self,index,raw_index,*,status='returned'):
        before=self.dom.stamp();self.write_intent(dict(phase='model-query',index=index))
        value=self.f.boundary.reader('dom').read(self.source.run,self.source.fixture)
        query=deepcopy(self.f.boundary.sent['dom']);raw=self.f.boundary.raw['dom'].encode()
        parts=self.parts_store.write('dom',sha(canonical(query)),raw,raw_index)
        after=self.dom.stamp()
        row=dict(tabletWebSourcePacketVersion=2,index=index,before=before,after=after,query=query,
            sendReturned=True,status=status,raws=[dict(before=before,after=after,segments=parts,
                inspection=self.parts_store.inspect(parts),outcome='accepted')],unsafe=[],
            resultSha256=sha(canonical(value)) if status=='returned' else None,readbacks=[])
        return self.rows_store.write(index,row),value

    def prefix(self):
        s=self.source
        return continuation.TabletDOMClosedPrefix(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def inventory(self):
        return {path.name:(path.stat().st_dev,path.stat().st_ino,path.stat().st_mtime_ns,path.stat().st_ctime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest()) for path in self.f.root.iterdir() if path.is_file()}

    def complete(self):
        fence=continuation.prepare(self.source);continuation.install(self.source,fence)
        owner=self.prefix();owner.copy();owner.index();return owner

    def test_128_to_129_uses_actual_global_raw_cursor_and_independent_native_DOM_tail(self):
        self.build();old=self.originals();old_header=self.dom.store.path.read_bytes()
        owner=self.complete();counts=self.native_counts();actual=owner.history()
        self.assertEqual((128,129,129),(actual['globalIndex'],actual['nextIndex'],actual['nextRaw']))
        self.assertEqual(128,actual['nativeFloor']['sequence']);self.assertEqual('unavailable',actual['nativeFloor']['status'])
        self.assertEqual(old_header,continuation.decode(owner.state,self.expected)[0]);self.assertEqual(counts,self.native_counts())
        ref,packet=self.model_row(129,129);before=self.originals();inventory=self.inventory();counts=self.native_counts()
        next_=owner.successor(ref)
        self.assertEqual((129,130,130),(next_['globalIndex'],next_['nextIndex'],next_['nextRaw']))
        self.assertEqual(packet,next_['nativeFloor']);self.assertEqual('rotating',next_['phase'])
        self.assertTrue(next_['historicalOnly']);self.assertEqual(counts,self.native_counts());self.assertEqual(before,self.originals())
        self.assertEqual(inventory,self.inventory())
        self.assertEqual(old,{name:value for name,value in before.items() if name in old})
        self.assertEqual(3,self.head.read()['tabletWebSourceOwnerVersion'])
        self.assertEqual('rotating',self.head.read()['phase'])

    def test_native_sequence_regression_is_not_replaced_by_storage_row129(self):
        self.build();owner=self.complete();self.f.boundary.frame['document']['sequence']=0
        reference,packet=self.model_row(129,129);self.assertEqual(128,packet['sequence']);counts=self.native_counts()
        with self.assertRaises(NativeUIError):owner.successor(reference)
        self.assertEqual(counts,self.native_counts());self.assertEqual(3,self.dom.store.read()['tabletWebPacketsVersion'])

    def test_raw_gap_even_with_valid_native_sequence_fails(self):
        self.build();owner=self.complete();reference,packet=self.model_row(129,130)
        self.assertEqual(129,packet['sequence']);counts=self.native_counts()
        with self.assertRaises(NativeUIError):owner.successor(reference)
        self.assertEqual(counts,self.native_counts())

    def test_lost_successful_CAS_is_discovered_without_lower_head_or_query_resend(self):
        self.build();fence=continuation.prepare(self.source);write=PrivateFeatureState.write;lost=[]
        def actual(store,value,previous):
            result=write(store,value,previous)
            if store.path==self.dom.store.path and value.get('tabletWebPacketsVersion')==3:
                lost.append(True);raise OSError('Modeled lost CAS return after actual replacement')
            return result
        counts=self.native_counts()
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):continuation.install(self.source,fence)
        self.assertEqual([True],lost);self.assertEqual(fence,self.dom.store.read());self.assertEqual(counts,self.native_counts())
        owner=self.prefix()
        with self.assertRaises(NativeUIError):owner.history()
        with self.assertRaises(NativeUIError):continuation.install(self.source,fence)
        self.assertEqual(fence,self.dom.store.read());self.assertEqual(counts,self.native_counts())

    def test_lost_manifest_return_retains_one_owned_intent_without_append_retry(self):
        self.build();continuation.install(self.source,continuation.prepare(self.source));owner=self.prefix();owner.copy()
        original=owner.intent
        def lost(kind,value):
            original(kind,value)
            if kind=='manifest' and value['phase']=='saved':raise OSError('Modeled lost manifest return')
        owner.records.intent=lost;counts=self.native_counts()
        with self.assertRaises(OSError):owner.index()
        reopened=self.prefix();intent=deepcopy(reopened.state['manifestIntent'])
        self.assertEqual('saved',intent['phase']);self.assertEqual([],reopened.state['manifests'])
        self.assertEqual(self.dom.state['records'][:1],reopened.records.manifest(intent['reference']))
        with self.assertRaises(NativeUIError):reopened.index()
        with self.assertRaises(NativeUIError):reopened.history()
        self.assertEqual(intent,reopened.store.read()['manifestIntent']);self.assertEqual(counts,self.native_counts())

    def test_early_Ctor_barrier_precedes_original_or_raw_storage_construction(self):
        self.build();continuation.install(self.source,continuation.prepare(self.source));s=self.source;counts=self.native_counts()
        changed=deepcopy(self.expected);changed['binding']['generation']+=1
        with self.assertRaises(NativeUIError):continuation.decode(self.dom.store.read(),changed)
        changed=self.dom.store.read();changed['nativeFloor']=dict(sequence=129)
        with self.assertRaises(NativeUIError):continuation.decode(changed,self.expected)
        with patch('ios.adapters.tablet_web_packets.OriginalFrameStore',side_effect=AssertionError('No frame factory')), \
             patch('ios.adapters.tablet_web_packets.TabletWebSourceSegments',side_effect=AssertionError('No raw factory')):
            with self.assertRaises(NativeUIError):
                TabletWebPackets(s.root,s.binding,s.run,s.role,s.fixture,s.pid,'dom',lambda:True,historical=True)
        self.assertEqual(counts,self.native_counts())

    def test_short_prefix_cannot_manufacture_boundary_row129(self):
        self.build(127);before=self.dom.store.path.read_bytes();counts=self.native_counts()
        with self.assertRaises(NativeUIError):continuation.prepare(self.source)
        self.assertEqual(before,self.dom.store.path.read_bytes());self.assertEqual(counts,self.native_counts())

    def test_failed_archived_query_cannot_disappear_behind_new_native_tail(self):
        self.build(last_status='failed');before=self.dom.store.path.read_bytes();counts=self.native_counts()
        with self.assertRaises(NativeUIError):continuation.prepare(self.source)
        self.assertEqual(before,self.dom.store.path.read_bytes());self.assertEqual(counts,self.native_counts())

    def test_original_inode_change_during_historical_replay_blocks_the_suffix(self):
        self.build();owner=self.complete();read=OriginalFrameStore.read;changed=[]
        def actual(store,value):
            result=read(store,value)
            if store.namespace=='tabletweb-dom-packets' and not changed:
                path=store.path(value);raw=path.read_bytes();replacement=path.with_name('replacement-original.json')
                replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path);changed.append(True)
            return result
        counts=self.native_counts()
        with patch.object(OriginalFrameStore,'read',actual),self.assertRaises(NativeUIError):owner.history()
        self.assertEqual([True],changed);self.assertEqual(counts,self.native_counts());self.assertEqual('rotating',owner.store.read()['phase'])

    def test_memory_header_mutation_cannot_substitute_a_different_literal_predecessor(self):
        self.build();continuation.install(self.source,continuation.prepare(self.source));owner=self.prefix();counts=self.native_counts()
        before=owner.store.path.read_bytes();owner.old['records'].pop(0)
        with self.assertRaises(NativeUIError):owner.copy()
        self.assertEqual(before,owner.store.path.read_bytes());self.assertEqual(counts,self.native_counts())

    def test_reentry_actually_reads_the_parent_copy_and_rejects_its_new_inode(self):
        self.build();continuation.install(self.source,continuation.prepare(self.source));parent_head=self.head.read()
        path=self.copied_parent_path(parent_head['copyIntent']);raw=path.read_bytes();replacement=path.with_name('replacement-parent-copy.json')
        replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path);counts=self.native_counts()
        with self.assertRaises(NativeUIError):self.prefix()
        self.assertEqual(counts,self.native_counts());self.assertEqual(3,self.dom.store.read()['tabletWebPacketsVersion'])

    def copied_parent_path(self,reference):
        s=self.source
        store=OriginalFrameStore(s.root,s.binding,s.run,s.role,lambda:True,lambda *_:False,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader')
        return store.path(reference)


if __name__=='__main__':unittest.main()
