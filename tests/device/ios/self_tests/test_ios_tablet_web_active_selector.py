"""Historical selection of actual active DOM originals, no live SourceReady.

Native/SDK boundaries are explicit models; private files and the existing
query/record/copy/read validators execute. No native timing is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_child_rotation as rotation,tablet_web_dom_segment as active
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_dom_segment as existing


class TabletActiveSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletDOMSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.f=self.flow.f

    def current(self):
        self.flow.bound();owner=self.flow.open();packet=owner.capture(self.f.f.boundary.reader('dom'))
        return owner,packet

    def restore(self):
        s=self.f.source
        return rotation.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_all_nine_actual_tails_select_active_DOM130_with_global_old_refs_and_existing_record_cache(self):
        owner,packet=self.current();f=self.f;s=f.source
        aggregate=s.originals.read(s.originals.expand(s.state['records'][-1]));counts=f.native_counts();inventory=f.inventory()
        with scope(TabletRecordCache()):
            actual=self.restore();again=self.restore()
        self.assertEqual(actual,again);self.assertEqual(list(s.children),list(actual['children']))
        self.assertEqual(packet,actual['children']['dom']);self.assertEqual(130,actual['children']['dom']['sequence'])
        self.assertEqual('ready',actual['frames'][0]['document']['status']);self.assertEqual(1,actual['frames'][0]['document']['sequence'])
        self.assertEqual(aggregate['nativeAfter'],actual['nativeFloor']);self.assertEqual(aggregate['phaseAfter'],actual['phaseFloor'])
        self.assertEqual(1,actual['globalIndex']);self.assertTrue(actual['historicalOnly']);self.assertEqual('rotating',actual['phase'])
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())
        with self.assertRaises(NativeUIError):
            TabletWebSourceOwner(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,lambda:True,historical=True)

    def test_forced_historical_segment_never_calls_current_guard_or_clock_and_cannot_mutate(self):
        owner,packet=self.current();f=self.f
        def forbidden():raise AssertionError('No SDK/current clock from historical selector')
        arguments=list(self.flow.arguments());arguments[-1]=forbidden
        reader=active.TabletDOMSegment(*arguments,monotonic=f.source.monotonic,epoch_ms=forbidden,historical=True)
        counts=f.native_counts();inventory=f.inventory();self.assertEqual(packet,reader.history()[-1])
        self.assertEqual(f.source.children['dom'].state['records'][0],reader.reference(1))
        self.assertEqual(owner.state['records'][0],reader.reference(129));self.assertEqual(owner.state['records'][1],reader.reference(130))
        for operation in (reader.save,reader.stamp,reader.recover_record,reader.archive_pending,
                lambda:reader.capture(f.f.boundary.reader('dom')),lambda:reader.reconcile(f.f.boundary.reader('dom'))):
            with self.assertRaises(NativeUIError):operation()
        s=f.source;actual_reference,actual_history=reader.reference,reader.history
        def inject():
            return TabletWebSourceOwner._closed_snapshot(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,s.state,
                monotonic=s.monotonic,closed_dom_reader=reader)
        reader.reference=lambda _index:deepcopy(owner.state['records'][0])
        with self.assertRaises(NativeUIError):inject()
        reader.reference=actual_reference;reader.history=lambda:[]
        with self.assertRaises(NativeUIError):inject()
        reader.history=actual_history;reader.pid=32
        with self.assertRaises(NativeUIError):inject()
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())

    def test_unknown_active_query_refuses_parent_before_snapshot_and_never_returns_lower129(self):
        owner,_packet=self.current();f=self.f;f.f.boundary.lost='dom'
        with self.assertRaises(NativeUIError):owner.capture(f.f.boundary.reader('dom'))
        pending=deepcopy(owner.state['pending']);counts=f.native_counts();inventory=f.inventory()
        with patch.object(TabletWebSourceOwner,'_closed_snapshot',side_effect=AssertionError('No unresolved snapshot')):
            with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(pending,owner.state['pending']);self.assertEqual(131,pending['index'])
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())

    def test_unknown_non_DOM_original_stays_owned_and_blocks_new_all_nine_selector(self):
        f=self.f;child=f.source.children['trace'];f.f.boundary.lost='trace'
        with self.assertRaises(NativeUIError):child.capture(f.f.boundary.reader('trace'))
        unknown=child.archive_pending(abandon=True);f.f.boundary.lost=None
        owner,_packet=self.current();row=child.originals.read(child.originals.expand(unknown))
        counts=f.native_counts();inventory=f.inventory()
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(row,child.originals.read(child.originals.expand(unknown)));self.assertEqual('abandoned',row['status'])
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())


if __name__=='__main__':unittest.main()
