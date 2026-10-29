"""Owned uneven source continuation; real files/JS, modeled native transport.

These cases do not supply screenshot33, WholeSourceReady, peer authority or a
full26 result. Every new packet still passes its ordinary production decoder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters.tablet_web_source_owner import ORDER,TabletWebSourceOwner
from ios.adapters.tablet_web_rotation_fence import TabletHeaderRotating
from ios.self_tests import test_ios_tablet_web_child_rotation as existing
from ios.self_tests.tablet_web_fresh_echo_boundary import FreshEchoBoundary


class TabletOwnedAggregateRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletChildRotationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletChildRotationTests();self.addCleanup(self.f.doCleanups)
        # The producer is declared BEFORE the inherited first Source capture.
        # Existing Boundary/default fixtures outside this construction stay literal.
        with patch.object(existing.existing,'Boundary',lambda original:FreshEchoBoundary(self,original)):
            self.f.setUp()
        self.source=self.f.source;self.boundary=self.f.f.boundary
        # Ordinary independent reads create genuine UNEQUAL current cursors.
        # Their original bytes are never edited or given a synthetic row128.
        self.boundary.epoch=self.boundary.host+int(self.boundary.mono*1000)
        self.source.children['dom'].capture(self.boundary.reader('dom'))
        self.source.children['buttons'].capture(self.boundary.reader('buttons'))
        self.source.children['buttons'].capture(self.boundary.reader('buttons'))
        self.counts={name:len(child.state['records']) for name,child in self.source.children.items()}
        self.f.freeze()
        self.canonical_paths=[self.source.store.path,*[child.store.path for child in self.source.children.values()]]
        self.canonical=self.pins(self.canonical_paths)

    @staticmethod
    def pins(paths):
        return {str(path):(path.stat().st_dev,path.stat().st_ino,path.read_bytes()) for path in paths}

    def arguments(self):
        s=self.source
        return s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,lambda:True

    def clocks(self):return dict(epoch_ms=lambda:int(self.boundary.host+self.boundary.mono*1000),monotonic=lambda:self.boundary.mono)

    def open(self):return aggregate.open_owned(*self.arguments(),**self.clocks())

    def historical(self):return aggregate.TabletWebAggregateRoot(*self.arguments(),**self.clocks(),historical=True)

    def capture(self,owner):
        # Declare only the NEXT native boundary clock before acquisition;
        # stored clocks and all native validation/freshness windows stay literal.
        self.boundary.epoch=self.boundary.host+int(self.boundary.mono*1000)+100
        return self.f.f.capture(owner)

    def test_actual_nine_query_join_uses_unequal_child_cursors_and_preserves_canonical_parent_and_headers(self):
        before=list(self.boundary.calls);owner=self.open();self.assertEqual(before,self.boundary.calls)
        self.assertEqual(2,owner._next_index());self.assertEqual((2,3),(self.counts['dom'],self.counts['buttons']))
        parts,row=self.capture(owner)
        self.assertEqual(list(ORDER),self.boundary.calls[len(before):]);self.assertEqual(2,row['index'])
        self.assertEqual({name:count+1 for name,count in self.counts.items()},
            {part['component']:part['index'] for part in row['components']})
        self.assertEqual(self.canonical,self.pins(self.canonical_paths))
        calls=list(self.boundary.calls);actual,frame,frames=self.historical().frame_at(owner.state['records'][0])
        self.assertEqual(row,actual);self.assertEqual(parts,frame);self.assertEqual(2,len(frames));self.assertEqual(calls,self.boundary.calls)
        frame['sources']['roots'].clear();self.assertEqual(parts,self.historical().frame_at(owner.state['records'][0])[1])
        # Legacy Source3 remains fenced, even after a real new root exists.
        with self.assertRaises(TabletHeaderRotating):
            TabletWebSourceOwner(*self.arguments(),**self.clocks(),historical=True)

    def test_same_bytes_new_canonical_child_inode_refuses_before_any_new_query(self):
        self.open();path=self.source.children['dom'].store.path;value=PrivateFeatureState(path).read()
        old=path.stat().st_ino;PrivateFeatureState(path).write(value,value)
        self.assertNotEqual(old,path.stat().st_ino);before=list(self.boundary.calls)
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(before,self.boundary.calls)

    def test_changed_actual_active_original_bytes_refuse_without_recapture(self):
        owner=self.open();self.capture(owner);child=owner.children['trace']
        path=child.originals.path(child.originals.expand(child.state['records'][0]))
        raw=path.read_bytes();before=list(self.boundary.calls)
        # Retained actual file, same inode; no outer header mismatch masks SHA.
        inode=path.stat().st_ino;path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'))
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.historical()
        self.assertEqual(before,self.boundary.calls);self.assertEqual(self.canonical,self.pins(self.canonical_paths))

    def test_lost_complete_new_parent_flush_recovers_same_original_global_index_without_new_query(self):
        owner=self.open();fsync=os.fsync;lost=[]
        def actual(descriptor):
            name=os.readlink('/proc/self/fd/'+str(descriptor))
            if not lost and 'tabletweb-acquisitions-frame-' in name:
                lost.append(name);raise OSError('Actual complete aggregate original flush return lost')
            return fsync(descriptor)
        with patch('os.fsync',side_effect=actual),self.assertRaises(OSError):self.capture(owner)
        self.assertEqual(1,len(lost));calls=list(self.boundary.calls);rebuilt=self.open();self.assertTrue(rebuilt.blocked)
        intent=deepcopy(rebuilt.state['intent']);self.assertEqual(2,intent['index']);self.assertEqual('opened',intent['phase'])
        path=rebuilt.originals.path(intent);pin=self.pins([path]);reference=rebuilt.recover_original()
        self.assertEqual(2,reference['index']);self.assertEqual(pin,self.pins([path]));self.assertEqual(calls,self.boundary.calls)
        self.assertEqual(reference,self.historical().state['records'][0]);self.assertEqual(self.canonical,self.pins(self.canonical_paths))

    def test_foreign_binding_cannot_reuse_an_existing_owned_root(self):
        self.open();args=list(self.arguments());args[1]=dict(args[1],generation=args[1]['generation']+1)
        before=list(self.boundary.calls)
        with self.assertRaises(NativeUIError):aggregate.open_owned(*args,**self.clocks())
        self.assertEqual(before,self.boundary.calls);self.assertEqual(self.canonical,self.pins(self.canonical_paths))

    def test_orphan_child_root_before_parent_refuses_without_new_parent_or_query(self):
        s=self.source;path=s.root/aggregate.child_name('dom',s.run,s.role)
        PrivateFeatureState(path).write(dict(orphanResponsibility=True),None);before=self.pins([path]);calls=list(self.boundary.calls)
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(before,self.pins([path]));self.assertEqual(calls,self.boundary.calls)
        self.assertFalse((s.root/aggregate.root_name(s.run,s.role)).exists())

    def test_lost_child_initialization_return_keeps_declared_root_closed_without_replay(self):
        write=PrivateFeatureState.write;lost=[]
        def actual(store,value,previous):
            result=write(store,value,previous)
            if not lost and '-aggregate-segment-' in store.path.name:
                lost.append(store.path);raise OSError('Actual saved initial child return lost')
            return result
        calls=list(self.boundary.calls)
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):self.open()
        self.assertEqual(1,len(lost));rootpath=self.source.root/aggregate.root_name(self.source.run,self.source.role)
        before=self.pins([rootpath,*lost])
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(before,self.pins([rootpath,*lost]));self.assertEqual(calls,self.boundary.calls)
        self.assertEqual(self.canonical,self.pins(self.canonical_paths))

    def test_boolean_parent_link_count_cannot_impersonate_the_actual_original_integer_signature(self):
        owner=self.open();before=list(self.boundary.calls);previous=owner.store.read()
        changed=deepcopy(previous);self.assertIs(type(changed['parent']['signature']['nlink']),int)
        self.assertEqual(1,changed['parent']['signature']['nlink']);changed['parent']['signature']['nlink']=True
        owner.store.write(changed,previous)
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(before,self.boundary.calls);self.assertEqual(self.canonical,self.pins(self.canonical_paths))


if __name__=='__main__':unittest.main()
