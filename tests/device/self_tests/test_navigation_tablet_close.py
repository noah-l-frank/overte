"""Original normal controller route and journals; Qt/VR/native are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.token_script_ui import TokenScriptUI
from adapters.script_journey.history import pack,unpack
from self_tests import test_navigation_ray_transit as ray_tests
from self_tests.test_navigation_transit import SELECT


class NavigationTabletCloseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ray_tests.NavigationRayTransitTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.start();self.world=f.world;self.shown=True;self.controllers=[];self.ignore=False;self.lose=False;self.edit=None
        raw=f.widgets.raw
        def current():
            value=raw();value.update(open=self.shown,ready=self.shown,featureControlsVersion=1)
            if not self.shown:value['controls']=[]
            return value
        f.widgets.raw=current
        self.normal=TokenScriptUI(PicoScriptIO(f.navigation),monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        self.transit=f.owner();self.transit.act(SELECT,'bookmark')
        capture=f.ray.source.capture
        def home():
            value=capture();value['tabletShown']=self.shown;return value
        f.ray.source.capture=home
        def controller(operation):
            self.assertEqual('tablet.close',operation)
            saved=unpack(json.loads(self.path.read_text())['payload'])[0]
            self.assertEqual('closing',saved['phase']);self.assertTrue(saved['before']['home']['tabletShown'])
            self.controllers.append(operation)
            if not self.ignore:
                self.shown=False;f.widgets.generation=str(uuid.uuid4());f.ray.panel_boundary.open=False
            if self.edit:self.edit()
            if self.lose:raise NativeUIError('Synthetic applied controller close lost reply')
        f.widgets.controller=controller;self.path=self.world.root/'tablet-close.json'
        write=self.world.ui.write
        def graphics(*args):
            self.world.ui.shown=self.shown;self.world.ui.clock=self.world.clock;self.world.ui.epoch=self.world.epoch();return write(*args)
        self.world.ui.write=graphics
    def source(self):
        source=self.world.ui.source();source.clock_ms=self.world.epoch;source.monotonic=lambda:self.world.clock;source.sleep=self.world.sleep;return source
    def owner(self):
        return NavigationTabletClose(self.transit,self.normal,self.source(),self.path,self.world.guard,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
    def act(self):return self.owner().close(SELECT)
    def test_normal_controller_close_has_original_intent_effect_and_three_seconds_independent_quiet(self):
        self.assertEqual(dict(performed=True),self.act());state=self.owner().state
        self.assertEqual(['tablet.close'],self.controllers);self.assertEqual(7,len(state['quiet']))
        self.assertTrue(state['before']['home']['tabletShown']);self.assertFalse(state['last']['home']['tabletShown'])
        self.assertEqual(state['before']['transit']['ui']['scope']['sequence'],state['last']['transit']['ui']['scope']['sequence'])
        self.assertNotEqual(state['before']['transit']['ui']['scope']['generation'],state['last']['transit']['ui']['scope']['generation'])
        self.assertFalse(state['last']['graphics']['tabletShown']);self.assertEqual('closed',state['phase'])
        self.act();self.assertEqual(['tablet.close'],self.controllers)
    def test_applied_lost_controller_result_resumes_original_close_without_another_toggle(self):
        self.lose=True
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual('closing',self.owner().state['phase']);self.lose=False;self.act();self.assertEqual(1,len(self.controllers))
    def test_ignored_close_or_conflicting_home_graphics_or_qt_counter_does_not_finish_or_replay(self):
        for fault in ('ignored','home','graphics','qt-input','generation'):
            self.setUp()
            if fault=='ignored':self.ignore=True
            elif fault=='home':self.edit=lambda:setattr(self.fixture.ray,'home_edit',lambda v:v.update(onHomeScreen=False))
            elif fault=='graphics':self.edit=lambda:setattr(self.world.ui,'edit',lambda v:v.update(tabletShown=True))
            elif fault=='qt-input':self.edit=lambda:setattr(self.fixture.widgets,'sequence',self.fixture.widgets.sequence+1)
            else:
                original=self.fixture.widgets.generation;self.edit=lambda:setattr(self.fixture.widgets,'generation',original)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            with self.assertRaises(NativeUIError):self.act()
            self.assertEqual(1,len(self.controllers));self.assertFalse(self.owner().state['quiet'])
    def test_keyboard_editor_or_retained_foreign_root_refuses_before_controller_input(self):
        for fault in ('keyboard','editor','root'):
            self.setUp()
            if fault=='keyboard':self.world.ui.keyboard=True
            elif fault=='editor':self.world.ui.focused=True
            else:self.world.ui.roots=[dict(id='d'*32,profile='tablet-menu-v1',visible=False,inCurrentTree=False,callbackRunning=True,callbackItemPresent=True)]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertFalse(self.controllers);self.assertIsNone(self.owner().state)
    def test_replacement_home_entity_cannot_adopt_the_original_owned_tablet_close(self):
        self.fixture.ray.home_edit=lambda value:value.update(homeId='8'*32)
        with self.assertRaises(NativeUIError):self.act()
        self.assertFalse(self.controllers);self.assertIsNone(self.owner().state)
    def test_changed_bookmarks_or_frozen_original_home_clock_during_quiet_retains_owned_close(self):
        for fault in ('storage','clock','new-panel'):
            self.setUp();sleep=self.world.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='storage':self.fixture.widgets.map['Foreign']='hifi://foreign.invalid';self.fixture.widgets.persist()
                elif fault=='clock':self.fixture.ray.home_edit=lambda v:v.update(capturedEpochMs=23000,elapsedMs=3100)
                else:
                    self.fixture.ray.extra_roots=[dict(rootId='8'*32,profile='pico-address-v1',sourceSha256='7'*64,
                        firstObservedEpochMs=self.world.epoch(),alive=True,inCurrentTree=False,visible=False)]
            self.world.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertEqual(1,len(self.controllers));self.assertFalse(self.owner().state['quiet'])
    def test_altered_saved_intent_or_unknown_scope_refuses_recreation_without_reclosing(self):
        for fault in ('origin','counter','phase','query'):
            self.setUp();self.lose=True
            with self.assertRaises(NativeUIError):self.act()
            disk=json.loads(self.path.read_text());state=unpack(disk['payload'])[0]
            if fault=='origin':disk['transitOriginalSha256']='8'*64
            elif fault=='counter':state['before']['transit']['ui']['scope']['sequence']+=1
            elif fault=='phase':state['phase']='closed'
            else:state['queries'].pop()
            disk['payload']=pack([state]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(1,len(self.controllers))
    def test_actual_private_factory_pins_existing_manager_binding_and_same_world_lock(self):
        from pathlib import Path
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as n
        fixture=n.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);adapter=fixture.instance()
        adapter._scripts=lambda target:SimpleNamespace(ui=self.normal,binding=self.world.binding)
        adapter._native_feature_observer=lambda target:SimpleNamespace(guard=self.world.guard,monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        adapter._graphics_ui_observer=lambda target:self.source()
        def lock(_self,target,provided):self.assertEqual('owned',target);self.assertIs(self.world.lock,provided);return provided
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock):
            owner=adapter._navigation_tablet_close('owned',self.path,self.transit,source_lock=self.world.lock)
            with self.assertRaises(NativeUIError):owner.close(SELECT)
            self.assertFalse(self.controllers)
            with self.world.lock.held():self.assertEqual(dict(performed=True),owner.close(SELECT))
        self.assertEqual(1,len(self.controllers))


if __name__=='__main__':unittest.main()
