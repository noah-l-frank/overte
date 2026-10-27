"""Real old Source/DOM tails and closed copies; native producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_child_rotation as rotation,tablet_web_rotation_fence as base
from ios.adapters.tablet_web_source_owner import ORDER,TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_source_owner as existing


class TabletChildRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletWebSourceOwnerTests.setUpClass()
    def setUp(self):
        self.f=existing.TabletWebSourceOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source=self.f.prepare();self.parts,self.record=self.f.capture(self.source)
        self.expected=base.scope(self.source.binding,self.source.run,self.source.role,self.source.fixture,self.source.pid)
        self.head=self.source.store
        self.copies=OriginalFrameStore(self.f.root,self.source.binding,self.source.run,self.source.role,
            self.guard,self.intent,namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader')

    def guard(self):rotation.decode(self.head.read(),self.expected);return True
    def intent(self,kind,value):
        previous=self.head.read();current=rotation.with_copy_intent(previous,kind,value,self.expected)
        self.head.write(current,previous)
    def freeze(self):
        fence=rotation.make(self.source);self.head.write(fence,self.source.saved)
        self.copies.write(1,rotation.copy_body(fence,self.expected));return self.head.read()
    def restore(self):
        s=self.source
        return rotation.restore(self.f.root,s.binding,s.run,s.role,s.fixture,s.pid,self.f.lock)
    def native_counts(self):return list(self.f.boundary.calls),self.f.boundary.native_count,self.f.boundary.posts
    def originals(self):
        return {path.name:(path.stat().st_dev,path.stat().st_ino,hashlib.sha256(path.read_bytes()).hexdigest())
            for path in self.f.root.glob('*frame-*.json')}

    def test_independent_input_DOM_tail_is_preserved_beyond_the_aggregate_reference(self):
        # A later input-channel query can observe disappearance while the
        # last full aggregate still holds ready DOM. Only the NEW native
        # producer changes; the stored aggregate/JS bytes remain untouched.
        self.f.boundary.frame['document']['status']='unavailable'
        self.f.boundary.frame['document']['source']={}
        dom=self.source.children['dom'];latest=dom.capture(self.f.boundary.reader('dom'))
        self.assertEqual(1,self.record['components'][2]['index']);self.assertEqual(2,len(dom.state['records']))
        self.assertEqual(2,latest['sequence']);self.assertEqual('unavailable',latest['status'])
        self.assertEqual('ready',self.parts['document']['status']);before=self.originals();self.freeze();counts=self.native_counts()
        actual=self.restore();self.assertTrue(actual['historicalOnly']);self.assertEqual('rotating',actual['phase'])
        self.assertEqual(1,actual['globalIndex']);self.assertEqual(latest,actual['children']['dom'])
        self.assertEqual(self.record['nativeAfter'],actual['nativeFloor'])
        self.assertEqual(self.record['phaseAfter'],actual['phaseFloor'])
        self.assertEqual(before,{name:value for name,value in self.originals().items() if name in before})
        self.assertEqual(counts,self.native_counts())
        with self.assertRaises(base.TabletHeaderRotating):base.read_barrier(self.head.read(),self.expected)

    def test_all_nine_actual_heads_are_fixed_before_CAS_and_have_exact_last_references(self):
        fence=rotation.make(self.source)
        self.assertEqual(list(ORDER),[row['component'] for row in fence['children']])
        for row in fence['children']:
            child=self.source.children[row['component']]
            self.assertEqual(child.state['records'][-1],row['lastRecord'])
            self.assertEqual(child.store.path.stat().st_ino,row['signature']['inode'])
            self.assertEqual(hashlib.sha256(child.store.path.read_bytes()).hexdigest(),row['sha256'])
        for change in ('missing','duplicate','foreign-name'):
            with self.subTest(change=change):
                value=deepcopy(fence)
                if change=='missing':value['children'].pop()
                elif change=='duplicate':value['children'][1]=deepcopy(value['children'][0])
                else:value['children'][0]['headerName']='foreign.json'
                with self.assertRaises(NativeUIError):rotation.decode(value,self.expected)

    def test_existing_unbound_Source3_fence_cannot_be_enriched_or_restored(self):
        raw,signature=rotation._raw(self.head.path);legacy=base.make(raw,signature,self.expected)
        self.head.write(legacy,self.source.saved)
        with self.assertRaises(NativeUIError):rotation.make(self.source)
        with self.assertRaises(NativeUIError):self.restore()
        with self.assertRaises(base.TabletHeaderRotating):base.read_barrier(self.head.read(),self.expected)
        self.assertEqual(raw,base.decode(self.head.read(),self.expected))

    def test_unresolved_child_query_or_app_ownership_prevents_new_fence(self):
        child=self.source.children['dom'];old=deepcopy(child.state)
        changed=deepcopy(old);changed['pending']=dict(unresolved=True);child.store.write(changed,old)
        before=self.head.path.read_bytes();counts=self.native_counts()
        with self.assertRaises(NativeUIError):rotation.make(self.source)
        self.assertEqual(before,self.head.path.read_bytes());self.assertEqual(counts,self.native_counts())

    def test_child_head_replacement_and_newer_same_scope_packet_never_lower_or_refresh_floor(self):
        self.freeze();child=self.source.children['dom'];old=child.store.read()
        child.store.write(old,old);counts=self.native_counts()
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(counts,self.native_counts());self.assertEqual('rotating',self.head.read()['phase'])

    def test_mid_read_child_inode_change_is_detected_with_all_originals_retained(self):
        self.freeze();child=self.source.children['trace'];read=OriginalFrameStore.read;changed=[]
        def actual(store,value):
            result=read(store,value)
            if not changed:
                old=child.store.read();child.store.write(old,old);changed.append(True)
            return result
        counts=self.native_counts()
        with patch.object(OriginalFrameStore,'read',actual),self.assertRaises(NativeUIError):self.restore()
        self.assertEqual([True],changed);self.assertEqual(counts,self.native_counts())

    def test_readonly_snapshot_and_foreign_binding_have_no_capture_or_write_permission(self):
        fence=self.freeze();raw=rotation.decode(fence,self.expected);state=base._legacy(raw,self.expected)
        counts=self.native_counts();s=self.source
        historical=TabletWebSourceOwner._closed_snapshot(self.f.root,s.binding,s.run,s.role,s.fixture,s.pid,self.f.lock,state)
        with self.assertRaises(NativeUIError):historical.bound()
        with self.assertRaises(NativeUIError):historical.save()
        changed=deepcopy(s.binding);changed['generation']+=1
        with self.assertRaises(NativeUIError):
            rotation.restore(self.f.root,changed,s.run,s.role,s.fixture,s.pid,self.f.lock)
        self.assertEqual(counts,self.native_counts())


if __name__=='__main__':unittest.main()
