"""Actual normal observer factory and genuine full unequal native prefix.

Loopback SDK/native/UIKit/clock endpoints are explicit host models. The real
installed-source admission, Source/WAL/9 joins/bytes execute; no physical,
independent Actor or whole26 qualification follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters import tablet_web_child_rotation as closed
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,ORDER
from ios.adapters.tablet_web_rotation_fence import TabletHeaderRotating
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletOwnedFactoryActivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=PairedTabletFixture(self);self.primary=self.fixture.primary
        self.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))

    @staticmethod
    def pins(paths):
        return {str(path):(path.stat().st_dev,path.stat().st_ino,path.stat().st_size,
            path.stat().st_mtime_ns,path.stat().st_ctime_ns,path.read_bytes()) for path in paths}

    def full_original_dom(self):
        # Every row is acquired by the actual existing native reader over
        # loopback HTTP; no duplicated refs/edited headers/synthetic row128.
        with self.primary.parts() as runtime:
            source=runtime.observer.source;self.assertIs(type(source),TabletWebSourceOwner)
            child=source.children['dom']
            while len(child.state['records'])<128:child.capture(runtime.observer.readers['dom'])
            self.assertEqual(128,len(child.state['records']))
            self.assertTrue(all(child.originals.read(child.originals.expand(ref))['status']=='returned' for ref in child.state['records']))
            self.legacy=source;self.counts={name:len(part.state['records']) for name,part in source.children.items()}
            self.assertTrue(any(count<128 for count in self.counts.values()))
            self.children=self.pins([part.store.path for part in source.children.values()])
            self.global_index=source._next_index()
        return source

    def assert_normal_new_join(self,runtime):
        owner=runtime.observer.source;self.assertIs(type(owner),aggregate.TabletWebAggregateRoot)
        parent=owner.root/('tabletweb-source-owner-'+RUN+'-primary.json');pinned=self.pins([parent])
        original=runtime.tail_source();calls=deepcopy(self.fixture.sdk.calls)
        historical=aggregate.source_owner(owner.root,owner.binding,owner.run,owner.role,owner.fixture,owner.pid,owner.lock,
            lambda:True,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic,historical=True)
        self.assertTrue(historical.historical);row,frame,_frames=historical.frame_at(original['observation']['reference'])
        self.assertEqual(calls,self.fixture.sdk.calls)
        self.assertEqual(self.global_index,row['index']);self.assertEqual(list(ORDER),[part['component'] for part in row['components']])
        self.assertEqual({name:count+1 for name,count in self.counts.items()},
            {part['component']:part['index'] for part in row['components']})
        self.assertEqual(129,next(part['index'] for part in row['components'] if part['component']=='dom'))
        self.assertEqual(2,frame['state']['iosTabletWebStateVersion'])
        self.assertEqual(self.children,self.pins([owner.root/value.split('/')[-1] for value in self.children]))
        self.assertEqual(pinned,self.pins([parent]))
        # Old constructors remain actually closed at the canonical Source3.
        with self.assertRaises(TabletHeaderRotating):
            TabletWebSourceOwner(owner.root,owner.binding,owner.run,owner.role,owner.fixture,owner.pid,owner.lock,
                lambda:True,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic,historical=True)

    def test_normal_factory_under_capacity_keeps_literal_owner_without_root_or_closed_copy(self):
        with self.primary.parts() as runtime:
            source=runtime.observer.source;self.assertIs(type(source),TabletWebSourceOwner)
            self.assertFalse((source.root/aggregate.root_name(source.run,source.role)).exists())
            self.assertFalse(any(path.name.startswith('tabletweb-closed-headers-') for path in source.root.iterdir()))
            runtime.tail_source();self.assertIs(type(runtime.observer.source),TabletWebSourceOwner)
        self.assertEqual([],self.fixture.sdk.errors)

    def test_actual_native128_then_normal_factory_lost_complete_copy_return_recovers_same_copy_and_joins_dom129(self):
        self.full_original_dom();write=OriginalFrameStore.write;copies=[]
        def actual(store,index,frame):
            result=write(store,index,frame)
            if store.namespace=='tabletweb-closed-headers':
                copies.append((store.path(store.expand(result)),deepcopy(result)))
                if len(copies)==1:raise OSError('Actual successful closed-copy local return lost')
            return result
        with patch.object(OriginalFrameStore,'write',actual):
            with self.assertRaises(OSError):
                with self.primary.parts():self.fail('Lost original copy return must interrupt before new capture')
            self.assertEqual(1,len(copies));copy_path=copies[0][0];copy_pin=self.pins([copy_path])
            self.assertEqual(self.children,self.pins([part.store.path for part in self.legacy.children.values()]))
            head=self.legacy.store.read();self.assertEqual('saved',head['copyIntent']['phase'])
            with self.primary.parts() as runtime:self.assert_normal_new_join(runtime)
            self.assertEqual(1,len(copies));self.assertEqual(copy_pin,self.pins([copy_path]))
        self.assertEqual([],self.fixture.sdk.errors)

    def test_actual_saved_Source3_CAS_without_copy_receipt_remains_fenced_and_never_rewrites_or_recaptures(self):
        self.full_original_dom();write=PrivateFeatureState.write;lost=[]
        def actual(store,value,previous):
            result=write(store,value,previous)
            if store.path==self.legacy.store.path and value.get('tabletWebSourceOwnerVersion')==3 and not lost:
                lost.append(True);raise OSError('Actual Source3 CAS return lost before copy intent')
            return result
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):
            with self.primary.parts():self.fail('Unknown original CAS return must interrupt')
        self.assertEqual([True],lost);head=self.legacy.store.read();closed.decode(head,aggregate.fence.scope(
            self.legacy.binding,self.legacy.run,self.legacy.role,self.legacy.fixture,self.legacy.pid))
        self.assertIsNone(head['copyIntent']);parent=self.pins([self.legacy.store.path])
        for _attempt in range(2):
            with self.assertRaises(NativeUIError):
                with self.primary.parts():self.fail('No second canonical CAS/copy/query permitted')
            self.assertEqual(parent,self.pins([self.legacy.store.path]))
            self.assertEqual(self.children,self.pins([part.store.path for part in self.legacy.children.values()]))
            self.assertFalse((self.legacy.root/aggregate.root_name(RUN,'primary')).exists())
            self.assertFalse(any(path.name.startswith('tabletweb-closed-headers-') for path in self.legacy.root.iterdir()))
        self.assertEqual([],self.fixture.sdk.errors)


if __name__=='__main__':unittest.main()
