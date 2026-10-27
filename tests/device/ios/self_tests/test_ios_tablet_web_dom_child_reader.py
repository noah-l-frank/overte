"""Bound historical DOM successor, modeled producers and real native originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_child_rotation as parent,tablet_web_dom_continuation as dom
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_dom_continuation as existing


class TabletDOMChildReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMContinuationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletDOMContinuationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def restore(self):
        s=self.f.source
        return parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_bound_original129_replays_parent_without_changing_its_original_native_or_phase_floors(self):
        f=self.f.build();owner=f.complete();ref,packet=f.model_row(129,129)
        with self.assertRaises(NativeUIError):self.restore()
        aggregate=f.source.originals.read(f.source.originals.expand(f.source.state['records'][-1]))
        owner.bind_successor(ref);inventory=f.inventory();counts=f.native_counts();actual=self.restore()
        self.assertEqual(packet,actual['children']['dom']);self.assertEqual(1,actual['globalIndex'])
        self.assertEqual(aggregate['nativeAfter'],actual['nativeFloor'])
        self.assertEqual(aggregate['phaseAfter'],actual['phaseFloor']);self.assertEqual(129,actual['children']['dom']['sequence'])
        self.assertTrue(actual['historicalOnly']);self.assertEqual('rotating',actual['phase'])
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())
        s=f.source
        with self.assertRaises(NativeUIError):
            TabletWebSourceOwner(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,lambda:True,historical=True)
        self.assertEqual(counts,f.native_counts())

    def test_unbound_v2_and_literal_v1_stay_blocked_before_parent_snapshot_construction(self):
        f=self.f.build();value=dom.prepare(f.source);legacy=deepcopy(value)
        legacy['tabletWebDOMContinuationVersion']=1;legacy.pop('successor')
        counts=f.native_counts();dom.install(f.source,value)
        with patch.object(TabletWebSourceOwner,'_closed_snapshot',side_effect=AssertionError('No parent snapshot')):
            with self.assertRaises(NativeUIError):self.restore()
        # Isolated legacy fixture: both formats are Packets3/rotating. No
        # production path downgrades the canonical head or writes Packet2.
        f.dom.store.write(legacy,value);dom.decode(legacy,f.expected)
        with patch.object(TabletWebSourceOwner,'_closed_snapshot',side_effect=AssertionError('No legacy parent snapshot')):
            with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(3,f.dom.store.read()['tabletWebPacketsVersion']);self.assertEqual(counts,f.native_counts())

    def test_lost_successful_successor_CAS_retains_exact_ref_and_never_binds_again(self):
        f=self.f.build();owner=f.complete();ref,packet=f.model_row(129,129)
        write=PrivateFeatureState.write;lost=[];counts=f.native_counts()
        def actual(store,value,previous):
            result=write(store,value,previous)
            if store.path==f.dom.store.path and value.get('successor')==ref:
                lost.append(True);raise OSError('Modeled lost successor CAS return after real persistence')
            return result
        with patch.object(PrivateFeatureState,'write',actual),self.assertRaises(OSError):owner.bind_successor(ref)
        self.assertEqual([True],lost);reopened=f.prefix();inventory=f.inventory()
        self.assertEqual(ref,reopened.state['successor']);self.assertEqual(packet,reopened.adopted()['nativeFloor'])
        with self.assertRaises(NativeUIError):reopened.bind_successor(ref)
        self.assertEqual(packet,self.restore()['children']['dom']);self.assertEqual(counts,f.native_counts())
        self.assertEqual(inventory,f.inventory())

    def test_bound_successor_inode_replacement_cannot_fall_back_to_old_DOM128(self):
        f=self.f.build();owner=f.complete();ref,packet=f.model_row(129,129);owner.bind_successor(ref)
        path=owner.records.path(owner.records.expand(ref));raw=path.read_bytes();replacement=path.with_name('replacement-DOM129.json')
        replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path);counts=f.native_counts()
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(ref,f.dom.store.read()['successor']);self.assertEqual(counts,f.native_counts())
        self.assertEqual('rotating',f.head.read()['phase']);self.assertEqual('rotating',f.dom.store.read()['phase'])

    def test_complete_literal_v1_copy_remains_original_when_bound_by_v2(self):
        f=self.f.build();legacy=dom.prepare(f.source);legacy['tabletWebDOMContinuationVersion']=1;legacy.pop('successor')
        dom.decode(legacy,f.expected);f.dom.store.write(legacy,f.dom.saved)
        owner=f.prefix();owner.copy();owner.index();counts=f.native_counts()
        self.assertEqual(128,owner.history()['nativeFloor']['sequence']);self.assertEqual(counts,f.native_counts())
        with self.assertRaises(NativeUIError):self.restore()
        copied=deepcopy(owner.state['copyIntent']);self.assertEqual(1,owner.copies.read(copied)['tabletWebDOMClosedBodyVersion'])
        reference,packet=f.model_row(129,129);before=f.originals();counts=f.native_counts();owner.bind_successor(reference)
        self.assertEqual(2,owner.state['tabletWebDOMContinuationVersion']);self.assertEqual(copied,owner.state['copyIntent'])
        self.assertEqual(packet,self.restore()['children']['dom']);self.assertEqual(before,f.originals())
        self.assertEqual(counts,f.native_counts());self.assertEqual(1,owner.copies.read(copied)['tabletWebDOMClosedBodyVersion'])


if __name__=='__main__':unittest.main()
