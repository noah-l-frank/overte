"""Real Pico normal Navigation input; original SDK/Home/controller effects are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
import time
import uuid
import json
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.browser_entry import PicoBrowserScriptIO,PicoBrowserEntry
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from self_tests.test_pico_tablet_home import Source as HomeSource
import test_pico_browser_apps as app_seams

RUN='a'*32;TICKET='b'*32


class Fence(PhaseInputFence):
    def __init__(self,source,lock):
        super().__init__(source);self.lock=lock;self.expected=source.status()
    def original(self):
        self.lock.assert_held();need(not self.failed);return self.expected


class PicoBrowserEntryTests(unittest.TestCase):
    def setUp(self):
        self.h=app_seams.PicoBrowserAppTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.epoch=int(time.time()*1000);self.host=0.;self.inputs=[];self.disk=None;self.slow=False;self.native_jump=False;self.owned=True
        self.lock=self.h.lock;self.adapter=self.h.adapter;self.target=self.h.native.target
        self.require_page=self.paged=self.ignore_page=False
        original_snapshot=self.h.snapshot
        def snapshot():
            value=original_snapshot()
            if not value['open']:value['controls']=[]
            elif self.require_page and not self.paged:
                value['controls']=[dict(id='tablet.page.2',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'page2')),enabled=True,focused=False)]
            return value
        change=patch.object(self.h.native,'snapshot',side_effect=snapshot)
        change.start();self.addCleanup(change.stop)
        change=patch.object(self.h.native,'epoch_milliseconds',side_effect=lambda target:self.epoch)
        change.start();self.addCleanup(change.stop)
        original_write=self.h.native.write_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if path!='files/overte-e2e/navigation-ui-command.json' or command.get('controlId')!='tablet.page.2':
                return original_write(target,package,path,raw)
            self.h.native.inputs.append(deepcopy(command));self.h.native.sequence=command['sequence']
            self.h.native.status=dict(schemaVersion=1,bridgeId=self.h.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.epoch)
            if not self.ignore_page:self.paged=True
        change=patch.object(self.h.native,'write_debug_app_file',side_effect=write)
        change.start();self.addCleanup(change.stop)
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('tablet-web')
        self.journal.activate(RUN,TICKET)
        client=Client('http://controlled.invalid/feature-fixture/v1','r'*64)
        client.request=lambda path,**kw:self.journal.phase(RUN,kw['phase_nonce'])
        source=PhaseFixtureReader(client,RUN,'tablet-web',epoch_ms=lambda:self.epoch,monotonic=lambda:self.host)
        self.fence=Fence(source,self.lock);self.fence.stream_intent=self.envelope
        self.store=PrivateFeatureState(self.lock.path.with_name('browser-inputs-test.json'))
        self.home_source=HomeSource();self.home_source.pid=123
        self.home_source.value.update(processId=123,capturedEpochMs=self.epoch)
        self.home_source.clock_ms=lambda:self.epoch;self.home_source.monotonic=lambda:self.host
        self.home_source.sleep=lambda seconds:setattr(self,'host',self.host+seconds)
        self.ignore_home=False;self.lost_home=False
    def save(self):
        value=dict(inputs=deepcopy(self.inputs));self.store.write(value,self.disk);self.disk=deepcopy(value)
        if self.slow:self.host+=2
        if self.native_jump:self.epoch+=2000
    def begin(self,original):
        self.fence.mark();self.inputs.append(dict(original=deepcopy(original),complete=False,envelope=None));self.save()
    def done(self):self.inputs[-1]['complete']=True;self.save()
    def envelope(self,value):self.inputs[-1]['envelope']=deepcopy(value);self.save()
    def lease(self,value):self.owned=value
    def home_stage(self,pose,*,intent,before_publish):
        envelope=dict(operation='pointer.gesture',pose=deepcopy(pose))
        intent(envelope);before_publish(envelope)
        if not self.ignore_home:self.home_source.value['onHomeScreen']=True
        if self.lost_home:raise NativeUIError('Original Home delivery return lost')
    def controller(self,operation):
        self.fence.before_controller(operation);envelope=dict(operation=operation)
        self.fence.stage_intent(envelope);self.fence.before_publish(envelope)
        self.h.native.opened=operation=='tablet.open'
        return {'performed':True}
    def entry(self):
        normal,_observe,_binding=self.adapter._script_runtime(self.target)
        io=PicoBrowserScriptIO(normal.io,self.fence,self.begin,self.done)
        normal=TokenScriptUI(io,monotonic=lambda:self.host,sleep=lambda seconds:setattr(self,'host',self.host+seconds))
        # The normal QML path remains original. Only the existing OpenXR/SDK
        # actuator effect is replaced; held-envelope admission still executes.
        io.navigation.io.controller=self.controller
        apps=self.adapter._browser_app_controls(self.target,source_lock=self.lock,read_only=False)
        home=PicoTabletHome(self.home_source,self.home_stage)
        return PicoBrowserEntry(normal,apps,home,self.fence,self.begin,self.done,lambda:self.owned,self.lease)
    def test_normal_actual_home_ray_then_original_app_tile_and_normal_tablet_close(self):
        with self.lock.held():
            entry=self.entry();entry.open('browser-app.web',initial=False);entry.close()
        self.assertEqual(1,self.h.effect);self.assertFalse(self.owned);self.assertFalse(self.h.native.opened)
        self.assertTrue(all(row['complete'] for row in self.inputs));self.assertEqual(3,len(self.inputs))
        self.assertEqual('home-ray',self.inputs[0]['original']['kind']);self.assertIsNotNone(self.inputs[0]['envelope'])
    def test_initial_normal_controller_open_and_observed_page_before_original_app(self):
        self.owned=False;self.h.native.opened=False;self.require_page=True
        with self.lock.held():self.entry().open('browser-app.web',initial=True)
        self.assertTrue(self.owned);self.assertTrue(self.paged);self.assertEqual(1,self.h.effect)
        self.assertEqual(['tablet.page.2','browser-app.web'],[row['controlId'] for row in self.h.native.inputs])
        self.assertTrue(all(row['complete'] for row in self.inputs))

    def test_page_ack_without_actual_app_is_observed_once_and_never_reclicked(self):
        self.require_page=True;self.ignore_page=True
        with self.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.entry().open('browser-app.web',initial=False)
        self.assertEqual(0,self.h.effect);self.assertFalse(self.paged)
        self.assertEqual(['tablet.page.2'],[row['controlId'] for row in self.h.native.inputs])

    def test_ignored_or_lost_home_cannot_become_app_activation_and_is_not_resent(self):
        for lost in (False,True):
            with self.subTest(lost=lost):
                self.ignore_home=not lost;self.lost_home=lost;self.host=0.;self.inputs=[];self.fence.failed=False
                self.home_source.value['onHomeScreen']=False
                with self.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.entry().open('browser-app.web',initial=False)
                self.assertEqual(0,self.h.effect);self.assertEqual(1,len(self.inputs));self.assertFalse(self.inputs[0]['complete'])
    def test_slow_original_host_cas_or_native_clock_jump_refuses_before_actual_home_publish(self):
        for native in (False,True):
            with self.subTest(native=native):
                self.slow=not native;self.native_jump=native;self.host=0.;self.inputs=[];self.fence.failed=False
                with self.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.entry().open('browser-app.web',initial=False)
                self.assertEqual(0,self.h.effect);self.assertEqual(1,len(self.inputs));self.assertIsNone(self.inputs[0]['envelope'])
    def test_fixture_change_after_durable_input_intent_prevents_native_app_pointer(self):
        self.home_source.value['onHomeScreen']=True;original=self.save
        def save():
            original();self.journal.activate(RUN,'c'*32,'open',{})
        self.save=save
        with self.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.entry().open('browser-app.web',initial=False)
        self.assertEqual(0,self.h.effect);self.assertEqual([],self.h.native.inputs);self.assertFalse(self.inputs[-1]['complete'])


if __name__=='__main__':unittest.main()
