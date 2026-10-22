"""Original Python transit/VR Home journals; native Qt/OpenXR are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.navigation_transit import NavigationTransit
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.token_places_ui import TokenPlacesUI
from adapters.script_journey.history import pack,unpack
from self_tests import test_navigation_transit as transit


class NavigationRayTransitTests(unittest.TestCase):
    setUp=transit.NavigationTransitTests.setUp
    witness=transit.NavigationTransitTests.witness
    def owner(self):
        return NavigationTransit(lambda intent:TokenPlacesUI(PicoPlacesIO(self.original),intent,transit.RUN,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep),self.world.arrival(),self.widgets.reader(),self.widgets.bookmarks(),
            lambda ticket:self.world.stereo(self.world.root/('navigation-stereo-'+ticket+'.json')),
            self.path,transit.RUN,self.world.binding,transit.SCENE,self.world.guard,
            home=self.ray.home,panels=self.ray.panels(),monotonic=lambda:self.world.clock,sleep=self.world.sleep)
    def act(self):return self.owner().act(transit.SELECT,'bookmark')
    def start(self):self.ray=transit.RayBoundary(self)
    def test_actual_home_ray_uses_original_geometry_intent_and_separate_native_root_retirement(self):
        self.start();original=self.widgets.storage();self.assertEqual(dict(performed=True),self.act())
        state=self.owner().state;self.assertEqual('ray',state['homeMode']);self.assertEqual(1,len(self.ray.gestures))
        self.assertEqual(['places.tab.1','places.bookmark.visit.'+transit.sha(transit.context(transit.RUN)['renamed'])],
                         [c['controlId'] for c in self.widgets.calls])
        self.assertEqual(state['homeBefore']['original']['ui']['scope']['sequence'],state['last']['ui']['scope']['sequence'])
        self.assertTrue(state['homeAfter']['onHomeScreen']);self.assertFalse(state['last']['panels']['roots'][0]['alive'])
        self.assertEqual(7,len(state['quiet']));self.assertEqual(original,self.widgets.storage())
        self.act();self.assertEqual(1,len(self.ray.gestures));self.assertEqual(1,len(self.world.gpu.commands))
    def test_applied_lost_ray_receipt_recovers_by_original_effect_without_another_gesture(self):
        self.start();self.ray.lose=True
        with self.assertRaises(NativeUIError):self.act()
        self.assertTrue(self.owner().state['pending']['home']);self.assertEqual(1,len(self.ray.gestures))
        self.assertFalse(self.world.gpu.commands);self.ray.lose=False
        self.act();self.assertEqual(1,len(self.ray.gestures));self.assertEqual(1,len(self.world.gpu.commands))
    def test_ignored_home_retained_places_or_foreign_input_cannot_borrow_acknowledgment(self):
        for fault in ('ignored','retained','extra-input','new-home'):
            self.setUp();self.start()
            if fault=='ignored':self.ray.ignore=True
            elif fault=='retained':self.widgets.retained_root=True
            else:
                stage=self.ray.stage
                def changed(pose):
                    stage(pose)
                    if fault=='extra-input':self.widgets.sequence+=1
                    else:self.ray.home_edit=lambda v:v.update(homeId='3'*32)
                self.ray.home.stage=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            with self.assertRaises(NativeUIError):self.act()
            self.assertEqual(1,len(self.ray.gestures));self.assertFalse(self.world.gpu.commands)
    def test_unknown_address_root_or_false_native_places_identity_refuses_before_input(self):
        for fault in ('address','source','old-root'):
            self.setUp();self.start()
            if fault=='address':
                self.ray.extra_roots=[dict(rootId='8'*32,profile='pico-address-v1',sourceSha256='7'*64,
                    firstObservedEpochMs=20000,alive=True,inCurrentTree=False,visible=False)]
            else:self.ray.panel_edit=lambda v:v['roots'][0].update(**({'sourceSha256':'8'*64} if fault=='source' else {'rootId':'8'*32}))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertFalse(self.widgets.calls);self.assertFalse(self.ray.gestures)
    def test_disappeared_history_and_replacement_root_during_quiet_keep_owner_unresolved(self):
        for fault in ('drop','new-root','resurrect'):
            self.setUp();self.start();sleep=self.world.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='drop':self.ray.panel_edit=lambda v:v.update(roots=[])
                elif fault=='resurrect':self.ray.panel_edit=lambda v:v['roots'][0].update(alive=True)
                else:
                    self.ray.extra_roots=[dict(rootId='8'*32,profile='pico-address-v1',sourceSha256='7'*64,
                        firstObservedEpochMs=self.world.epoch(),alive=True,inCurrentTree=False,visible=False)]
            self.world.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertEqual([],self.owner().state['quiet']);self.assertEqual(1,len(self.ray.gestures))
    def test_foreign_retained_address_appearing_after_arrival_refuses_before_home_gesture(self):
        self.start();send=self.widgets.send
        def changed(command):
            result=send(command)
            if command['controlId'].startswith('places.bookmark.visit.'):
                self.ray.extra_roots=[dict(rootId='8'*32,profile='pico-address-v1',sourceSha256='7'*64,
                    firstObservedEpochMs=self.world.epoch(),alive=True,inCurrentTree=False,visible=False)]
            return result
        self.widgets.send=changed
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual('A',self.world.position);self.assertFalse(self.ray.gestures);self.assertFalse(self.world.gpu.commands)
    def test_changed_home_original_and_wrong_version_journal_cannot_authorize_another_input(self):
        for fault in ('clock','storage','query','legacy-injection'):
            self.setUp();self.start();self.ray.lose=True
            with self.assertRaises(NativeUIError):self.act()
            disk=json.loads(self.path.read_text());state=unpack(disk['payload'])[0]
            if fault=='clock':state['homeBefore']['observation']['capturedEpochMs']-=2000
            elif fault=='storage':state['homeBefore']['original']['bookmarks']['storage']['file']['sha256']='8'*64
            elif fault=='query':state['queries'].remove(state['homeBefore']['observation']['commandId'])
            else:disk['navigationTransitVersion']=1
            disk['payload']=pack([state]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(1,len(self.ray.gestures))
    def test_closed_legacy_journal_reads_history_but_never_retargets_uncertain_qml_home_to_ray(self):
        legacy=transit.NavigationTransitTests.owner(self);self.widgets.lost='tablet.home'
        with self.assertRaises(NativeUIError):legacy.act(transit.SELECT,'bookmark')
        disk=json.loads(self.path.read_text());state=unpack(disk['payload'])[0]
        for key in ('homeMode','homeBefore','homeAfter'):state.pop(key)
        disk['navigationTransitVersion']=1;disk['payload']=pack([state]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
        self.start();self.widgets.lost=None
        # The archive remains readable; new independent sources cannot be
        # silently spliced into the old uncertain QML input history.
        self.assertEqual('qml',self.owner().state['homeMode']);calls=len(self.widgets.calls)
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(calls,len(self.widgets.calls));self.assertFalse(self.ray.gestures)


if __name__=='__main__':unittest.main()
