"""Original Python origin selection and Home ray; native Qt/VR simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
import uuid
from adapters.navigation_origin import NavigationOrigin
from adapters.normal_ui import NativeUIError
from adapters.pico4.tablet_home import PicoTabletHome
from self_tests import test_navigation_origin as legacy
from self_tests.test_pico_tablet_home import original


class Ray:
    def __init__(self,fixture):
        self.fixture=fixture;self.model=fixture.model;self.sequence=0;self.gestures=[];self.ignore=False;self.lose=False;self.edit=None
        self.home=PicoTabletHome(SimpleNamespace(pid=123,capture=self.capture,guard=self.model.guard,clock_ms=self.model.epoch,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep),self.stage)
        raw=self.model.raw
        def actual():
            value=raw();value['controls']=[r for r in value['controls'] if r['id']!='tablet.home'];return value
        self.model.raw=actual
    def capture(self):
        self.sequence+=1
        value=original()|dict(commandId=uuid.uuid4().hex,processId=123,sourceSequence=self.sequence,elapsedMs=100+round(self.model.clock*1000),
            capturedEpochMs=self.model.epoch(),tabletShown=True,onHomeScreen=not self.model.login)
        if self.edit:self.edit(value)
        return value
    def stage(self,pose):
        disk=json.loads(self.fixture.path.read_text());pending=disk['operation']['pending']
        assert pending['control']=='tablet.home-ray' and pending['token'] is None and disk['operation']['homeBefore'] is not None
        self.gestures.append(deepcopy(pose))
        if not self.ignore:self.model.login=False;self.model.focus='';self.model.generation=str(uuid.uuid4())
        if self.lose:raise NativeUIError('Synthetic applied Home ray result lost')


class NavigationOriginRayTests(unittest.TestCase):
    def setUp(self):
        self.fixture=legacy.NavigationOriginTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=self.fixture.model;self.ray=Ray(self.fixture)
    def owner(self):
        f=self.fixture
        return NavigationOrigin(f.io,self.model.reader(),f.path,legacy.RUN,f.binding,self.model.guard,home=self.ray.home,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
    def select(self):return self.owner().select(legacy.TICKET,legacy.OWNED)
    def test_actual_home_entity_closes_selected_and_restored_original_endpoint_without_a_qml_home_control(self):
        self.assertEqual(dict(performed=True),self.select());state=self.owner().state
        self.assertEqual('ray',state['homeMode']);self.assertEqual(3,len(self.model.calls));self.assertEqual(1,len(self.ray.gestures))
        self.assertTrue(state['operation']['homeAfter']['observation']['onHomeScreen'])
        self.assertEqual(state['operation']['homeBefore']['original']['ui']['sequence'],state['last']['ui']['sequence'])
        self.assertEqual(7,len(state['operation']['quiet']));self.assertFalse(self.model.login)
        self.select();self.assertEqual(1,len(self.ray.gestures))
        self.model.reopen();self.owner().select(legacy.RESTORE,legacy.OWNED,restoring=True)
        self.assertEqual(legacy.ORIGINAL,self.model.selected);self.assertEqual(6,len(self.model.calls));self.assertEqual(2,len(self.ray.gestures))
    def test_lost_ray_recovers_original_geometry_and_effect_without_another_gesture(self):
        self.ray.lose=True
        with self.assertRaises(NativeUIError):self.select()
        self.assertEqual('tablet.home-ray',self.owner().state['operation']['pending']['control'])
        self.ray.lose=False;self.select();self.assertEqual(1,len(self.ray.gestures));self.assertEqual(3,len(self.model.calls))
    def test_ignored_home_foreign_entity_or_extra_qt_input_cannot_pass_or_repeat_the_gesture(self):
        for fault in ('ignore','identity','input'):
            self.setUp()
            if fault=='ignore':self.ray.ignore=True
            else:
                stage=self.ray.home.stage
                def changed(pose):
                    stage(pose)
                    if fault=='input':self.model.sequence+=1
                    else:self.ray.edit=lambda p:p.update(homeId='8'*32)
                self.ray.home.stage=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.select()
            with self.assertRaises(NativeUIError):self.select()
            self.assertEqual(1,len(self.ray.gestures));self.assertEqual(3,len(self.model.calls))
    def test_changed_saved_home_source_or_missing_archive_refuses_recreation(self):
        for fault in ('source','pid','query','archive'):
            self.setUp();self.ray.lose=True
            with self.assertRaises(NativeUIError):self.select()
            disk=json.loads(self.fixture.path.read_text());before=disk['operation']['homeBefore']
            if fault=='source':before['observation']['onHomeScreen']=True
            elif fault=='pid':before['observation']['processId']=124
            elif fault=='query':disk['queries'].remove(before['observation']['commandId'])
            else:self.owner().packet_store(before['original']['sha256']).path.unlink()
            self.fixture.path.write_text(json.dumps(disk));self.fixture.path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(1,len(self.ray.gestures))
    def test_closed_v1_qml_history_remains_readable_but_cannot_be_retargeted_to_the_real_ray(self):
        self.setUp();old=legacy.NavigationOriginTests.owner(self.fixture)
        # Legacy boundary has its original synthetic QML control solely for
        # migration coverage; the real current Pico factory always binds a ray.
        raw=self.model.raw;token=str(uuid.uuid4())
        def with_home():
            value=raw();value['controls'].append(dict(id='tablet.home',token=token,enabled=True,focused=False));return value
        self.model.raw=with_home
        old.select(legacy.TICKET,legacy.OWNED);disk=json.loads(self.fixture.path.read_text())
        disk['navigationOriginVersion']=1;disk.pop('homeMode');disk['operation'].pop('homeBefore');disk['operation'].pop('homeAfter')
        self.fixture.path.write_text(json.dumps(disk));self.fixture.path.chmod(0o600)
        self.assertEqual('qml',self.owner().state['homeMode'])
        with self.assertRaises(NativeUIError):self.select()
        self.assertFalse(self.ray.gestures)
    def test_extra_input_during_independent_quiet_keeps_completed_ray_owned(self):
        sleep=self.model.sleep
        def changed(seconds):
            sleep(seconds)
            if self.ray.gestures:self.model.sequence+=1
        self.model.sleep=changed
        with self.assertRaises(NativeUIError):self.select()
        self.assertFalse(self.owner().state['operation']['quiet']);self.assertEqual(1,len(self.ray.gestures))
        with self.assertRaises(NativeUIError):self.select()
        self.assertEqual(1,len(self.ray.gestures));self.assertEqual(3,len(self.model.calls))
    def test_missing_or_unusable_original_home_geometry_never_issues_a_ray(self):
        for fault in ('hidden','already-home','geometry','epoch'):
            self.setUp()
            def edit(value):
                if fault=='hidden':value['tabletShown']=False
                elif fault=='already-home':value['onHomeScreen']=True
                elif fault=='geometry':value['sensorToWorld'][0]=0
                else:value['capturedEpochMs']-=1600
            self.ray.edit=edit
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.select()
            self.assertFalse(self.ray.gestures);self.assertEqual(3,len(self.model.calls))
    def test_full_original_account_history_stays_in_hash_bound_archives_with_home_originals(self):
        for index in range(1,65):
            legacy.append(self.model.acct,legacy.event(sequence=index,kind='profile-changed',epoch=20000,generation=1))
        self.select();state=self.owner().state
        self.assertEqual(64,len(state['original']['account']['observation']['events']))
        self.assertLess(self.fixture.path.stat().st_size,65536);self.assertEqual(1,len(self.ray.gestures))
    def test_pending_v1_qml_owner_keeps_original_cas_and_never_resends_the_lost_field_input(self):
        fixture=legacy.NavigationOriginTests();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.model.lose_stage=1
        with self.assertRaises(NativeUIError):fixture.owner().select(legacy.TICKET,legacy.OWNED)
        disk=json.loads(fixture.path.read_text());disk['navigationOriginVersion']=1;disk.pop('homeMode')
        disk['operation'].pop('homeBefore');disk['operation'].pop('homeAfter');fixture.path.write_text(json.dumps(disk));fixture.path.chmod(0o600)
        owner=fixture.owner();self.assertEqual(disk,owner.disk_state);self.assertEqual(1,owner.state['operation']['pending']['stage'])
        fixture.model.lose_stage=None;owner.select(legacy.TICKET,legacy.OWNED)
        self.assertEqual(4,len(fixture.model.calls));self.assertEqual(2,json.loads(fixture.path.read_text())['navigationOriginVersion'])


if __name__=='__main__':unittest.main()
