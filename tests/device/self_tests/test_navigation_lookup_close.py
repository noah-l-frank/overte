"""Real lookup/dismissal/close owners; native/Qt/OS sources remain host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.navigation_lookup_close import NavigationDismissedLookup
from adapters.script_journey.history import unpack
from self_tests import test_navigation_lookup_recovery as recovery

DISMISS=recovery.DISMISS


class NavigationLookupCloseTests(unittest.TestCase):
    def setUp(self):
        self.flow=recovery.NavigationLookupRecoveryTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.flow.lookup();self.flow.dismiss()
        self.fixture=self.flow.fixture;self.native=self.flow.source;self.world=self.fixture.world
        self.path=self.world.root/'lookup-tablet-close.json';self.inputs=[];self.ignore=self.lose=False
        self.edit=None;self.world.ui.roots=[]
        def controller(operation):
            self.assertEqual('tablet.close',operation)
            from adapters.normal_feature_state import PrivateFeatureState
            actual=unpack(PrivateFeatureState(self.path).read()['payload'])[0]
            self.assertEqual('closing',actual['phase']);self.assertTrue(actual['before']['home']['tabletShown'])
            self.inputs.append(operation)
            if not self.ignore:self.native.opened=False;self.native.generation=str(uuid.uuid4())
            if self.edit:self.edit()
            if self.lose:raise NativeUIError('Synthetic lost applied final controller response')
        self.native.controller=controller
        write=self.world.ui.write
        def graphics(*args):
            self.world.ui.shown=self.native.opened;self.world.ui.clock=self.world.clock;self.world.ui.epoch=self.world.epoch()
            return write(*args)
        self.world.ui.write=graphics
    def owner(self):
        context=NavigationDismissedLookup(self.fixture.owner(),self.flow.dismissal())
        graphics=self.world.ui.source();graphics.clock_ms=self.world.epoch
        graphics.monotonic=lambda:self.world.clock;graphics.sleep=self.world.sleep
        return NavigationTabletClose(context,self.fixture.normal,graphics,self.path,self.world.guard,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
    def close(self):return self.owner().close(DISMISS)
    def test_normal_lookup_ok_and_final_close_preserve_originals_and_three_second_quiet(self):
        headers=(self.fixture.owner().disk,self.flow.dismissal().disk);qml=deepcopy(self.native.inputs)
        self.assertEqual(dict(performed=True),self.close());owner=self.owner()
        self.assertEqual('dismissed-lookup',owner.disk['sourceKind']);self.assertEqual('closed',owner.state['phase'])
        self.assertEqual(7,len(owner.state['quiet']));self.assertEqual(['tablet.close'],self.inputs)
        self.assertFalse(self.native.opened);self.assertEqual(qml,self.native.inputs)
        self.assertEqual(headers,(self.fixture.owner().disk,self.flow.dismissal().disk))
        self.close();self.assertEqual(['tablet.close'],self.inputs)
    def test_lost_final_close_reobserves_without_replay(self):
        self.lose=True
        with self.assertRaises(NativeUIError):self.close()
        self.lose=False;self.assertEqual(dict(performed=True),self.close());self.assertEqual(['tablet.close'],self.inputs)
    def test_ignored_close_never_replays_and_keeps_original_ownership(self):
        self.ignore=True
        with self.assertRaises(NativeUIError):self.close()
        with self.assertRaises(NativeUIError):self.close()
        self.assertEqual(['tablet.close'],self.inputs);self.assertEqual('closing',self.owner().state['phase'])
    def test_current_modal_root_bookmark_or_keyboard_change_cannot_authorize_close(self):
        for fault in ('modal','panel','bookmark','keyboard'):
            self.setUp()
            if fault=='modal':self.native.modal.records[0]['rootAlive']=True
            elif fault=='panel':
                self.native.extra_roots=[dict(rootId='8'*32,profile='pico-places-v1',sourceSha256='6'*64,
                    firstObservedEpochMs=self.native.epoch,alive=True,inCurrentTree=False,visible=False)]
            elif fault=='bookmark':self.native.book.map['Foreign']='hifi://foreign.invalid';self.native.book.persist()
            else:self.world.ui.keyboard=True
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,RuntimeError)):self.close()
            self.assertEqual([],self.inputs);self.assertFalse(self.path.exists())

    def test_parent_ram_original_or_source_kind_change_never_adopts_close(self):
        lookup,dismissal=self.fixture.owner(),self.flow.dismissal()
        lookup.state['submitEpochMs']+=1
        with self.assertRaises(RuntimeError):NavigationDismissedLookup(lookup,dismissal)
        owner=self.owner();owner.transit.dismissal.state['ticket']='f'*32
        with self.assertRaises((RuntimeError,NativeUIError)):owner.close(DISMISS)
        self.assertFalse(self.inputs)
        self.close();disk=self.owner().store.read();changed=deepcopy(disk);changed['sourceKind']='transit'
        self.owner().store.write(changed,disk)
        with self.assertRaises(RuntimeError):self.owner()
        self.assertEqual(['tablet.close'],self.inputs)

    def test_transit_legacy_v1_stays_readable_without_relabeling_or_another_close(self):
        from self_tests import test_navigation_tablet_close as transit_tests
        f=transit_tests.NavigationTabletCloseTests();f.setUp();self.addCleanup(f.doCleanups);f.act()
        owner=f.owner();old=deepcopy(owner.disk);old.pop('sourceKind');old['navigationTabletCloseVersion']=1
        owner.store.write(old,owner.disk);cold=f.owner()
        self.assertEqual(old,cold.disk);self.assertEqual('transit',cold.source_kind)
        self.assertEqual(['tablet.close'],f.controllers)

    def test_closed_lookup_publishes_new_original_stereo_through_existing_owner(self):
        from self_tests import test_navigation_frames as frames
        self.close();harness=frames.NavigationFramesTests();harness.world=self.world
        harness.closed=self.owner();harness.path=self.world.root/'lookup-frames.json'
        self.assertEqual(frames.RUN,self.fixture.owner().run);self.world.active=DISMISS
        harness.prepare_sources()
        with self.world.lock.held():
            actual=harness.owner().read(DISMISS,0)
            image,metadata=[self.world.artifacts/row['name'] for row in actual['artifacts']]
            measured,_=frames.observation(image.read_bytes(),metadata.read_bytes(),frames.RUN,DISMISS,
                self.world.client.url+'/runs/'+frames.RUN+'/',frames.POLICY,harness.sample(actual))
        self.assertEqual('B',measured['location']);self.assertEqual(['tablet.close'],self.inputs)
        self.assertIsNone(self.world.owner_store('primary').read())
        self.assertEqual([],list(self.world.native_root.iterdir()))

    def test_actual_private_factory_requires_the_original_shared_lock_and_binding(self):
        from pathlib import Path
        from types import SimpleNamespace
        from copy import copy
        from unittest.mock import patch
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native
        f=native.NativeExecutionBindingTest();f.setUp();self.addCleanup(f.doCleanups);adapter=f.instance()
        fresh=copy(self.fixture.normal);fresh.io=copy(fresh.io);fresh.io.navigation=copy(fresh.io.navigation)
        self.assertIsNot(fresh.io.navigation,self.fixture.normal.io.navigation)
        manager=SimpleNamespace(ui=fresh,binding=self.world.binding)
        adapter._scripts=lambda target:manager
        adapter._native_feature_observer=lambda target:SimpleNamespace(guard=self.world.guard,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        adapter._graphics_ui_observer=lambda target:self.owner().graphics
        adapter._navigation_replies=lambda target:self.native.replies()
        adapter._navigation_modals=lambda target:self.native.modals()
        def lock(_self,target,provided):
            self.assertEqual('owned',target);self.assertIs(self.world.lock,provided);return provided
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock):
            with self.assertRaises((RuntimeError,ValueError)):
                adapter._navigation_lookup_close('owned',self.path,self.fixture.owner(),self.flow.dismissal(),source_lock=self.world.lock)
            with self.world.lock.held():
                lookup=self.fixture.owner()
                manager.binding={**self.world.binding,'artifactSha256':'f'*64}
                with self.assertRaises(ValueError):
                    adapter._navigation_lookup_dismissal('owned',self.flow.path,lookup,source_lock=self.world.lock)
                self.assertEqual([],self.inputs);manager.binding=self.world.binding
                dismissal=adapter._navigation_lookup_dismissal('owned',self.flow.path,lookup,source_lock=self.world.lock)
                self.assertIs(lookup.navigation,dismissal.ui.io.original.navigation)
                actual=adapter._navigation_lookup_close('owned',self.path,lookup,dismissal,source_lock=self.world.lock)
                self.assertIs(lookup.navigation,actual.normal.io.navigation)
                self.assertEqual(dict(performed=True),actual.close(DISMISS))
        self.assertEqual(['tablet.close'],self.inputs)


if __name__=='__main__':unittest.main()
