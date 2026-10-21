"""Original VR UI/root lifetime seams; no native toolkit or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_source import PicoGraphicsSource,resources,validate,COMMAND,FILE
from self_tests.test_token_graphics_ui import GraphicsBoundary
from self_tests.test_login_ui_inventory import loads,component


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.sample=None;self.okay=True
        self.requests=[];self.partial=0;self.ignore=False;self.edit=None
        self.roots=[dict(id='d'*32,profile='graphics-generic-v1',visible=True,inCurrentTree=True,
            callbackRunning=True,callbackItemPresent=False)]
        self.retired=[];self.qml=loads();self.shown=True;self.focused=False;self.keyboard=False
        self.controls=GraphicsBoundary(generic=True).capture()['controls']
        for row in self.controls:row['focused']=False
    def write(self,target,package,path,raw):
        assert (target,package,path)==('synthetic','org.overte.pico',COMMAND)
        request=json.loads(raw);assert set(request)=={'schemaVersion','commandId','action'} and request['action']=='observe'
        self.requests.append(request)
        if self.ignore:return
        self.sequence+=1
        self.sample=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance='a'*32,
            generation='b'*32,sourceSequence=self.sequence,lastCommandSequence=0,elapsedMs=round(self.clock*1000),
            capturedEpochMs=self.epoch,processId=31,graphicsControlsVersion=1,graphicsObservationVersion=1,
            tabletShown=self.shown,editorFocused=self.focused,ready=True,controls=deepcopy(self.controls),
            graphicsInventory=dict(inventoryVersion=1,complete=True,roots=deepcopy(self.roots),retiredRoots=sorted(self.retired),
                qmlLoads=deepcopy(self.qml),keyboard3D=dict(raised=self.keyboard,enabled=True)))
        if self.edit:self.edit(self.sample)
    def read(self,target,package,path,**options):
        assert (target,package,path)==('synthetic','org.overte.pico','files/overte-e2e/'+FILE) and options=={'attempts':1}
        if self.partial:self.partial-=1;return '{'
        return json.dumps(self.sample) if self.sample else ''
    def sleep(self,seconds):self.clock+=seconds
    def source(self):
        native=SimpleNamespace(guard=lambda:self.okay,clock_ms=lambda:self.epoch,pid=31,
            monotonic=lambda:self.clock,sleep=self.sleep)
        adapter=SimpleNamespace(adb=SimpleNamespace(write_debug_app_file=self.write,read_debug_app_file=self.read))
        return PicoGraphicsSource(adapter,'synthetic',native)


class PicoGraphicsSourceTests(unittest.TestCase):
    def test_actual_generic_controls_timer_and_root_are_preserved_with_nonce_only_read(self):
        boundary=Boundary();reader=boundary.source();value=reader.capture()
        self.assertEqual(boundary.sample,value);self.assertEqual(boundary.roots,value['graphicsInventory']['roots'])
        self.assertTrue(value['graphicsInventory']['roots'][0]['callbackRunning'])
        self.assertEqual(['panel:graphics','panel:graphics-tablet'],resources(value))
        self.assertEqual({'schemaVersion','commandId','action'},set(boundary.requests[0]))

    def test_hidden_retained_root_and_original_finished_component_cannot_become_empty_cleanup(self):
        boundary=Boundary();reader=boundary.source();reader.capture()
        boundary.shown=False;boundary.roots[0].update(visible=False,inCurrentTree=False,callbackRunning=False);boundary.controls=[]
        value=reader.capture();self.assertEqual(['panel:graphics'],resources(value))
        boundary.roots=[];boundary.retired=['d'*32];boundary.qml=loads([component(phase='finished')])
        value=reader.capture();self.assertEqual(['connection:graphics-qml-load'],resources(value))
        boundary.qml=loads(retired=['d'*32]);self.assertEqual([],resources(reader.capture()))

    def test_keyboard_focus_and_retained_menu_are_actual_resources_without_a_graphics_page(self):
        boundary=Boundary();boundary.controls=[];boundary.roots=[dict(id='d'*32,profile='tablet-menu-v1',visible=False,
            inCurrentTree=False,callbackRunning=True,callbackItemPresent=True)]
        boundary.shown=False;boundary.keyboard=True;boundary.focused=True
        self.assertEqual(['connection:graphics-menu','input:graphics-editor','input:graphics-keyboard'],resources(boundary.source().capture()))

    def test_disappeared_unretired_root_or_changed_root_profile_is_not_adopted(self):
        for change in ('omitted','profile','rewound'):
            boundary=Boundary();reader=boundary.source();reader.capture();boundary.controls=[]
            if change=='omitted':boundary.roots=[]
            elif change=='profile':boundary.roots[0]['profile']='tablet-menu-v1'
            else:boundary.qml['retiredComponents']=['f'*32];reader.capture();boundary.qml=loads()
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.capture()

    def test_foreign_phone_profile_missing_lifetime_and_inconsistent_current_root_fail(self):
        edits=[lambda v:v['controls'][0].update(profile='phone-immediate-v1'),lambda v:v.pop('graphicsInventory'),
            lambda v:v['graphicsInventory']['roots'][0].update(visible=False),
            lambda v:v['graphicsInventory']['roots'][0].update(profile='graphics-phone-v1'),
            lambda v:v['graphicsInventory']['roots'][0].update(callbackItemPresent=True),
            lambda v:v['graphicsInventory']['qmlLoads'].update(complete=False)]
        for edit in edits:
            boundary=Boundary();boundary.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):boundary.source().capture()

    def test_input_and_inherited_delivery_cannot_reach_the_observation_transport(self):
        boundary=Boundary();reader=boundary.source();value=reader.capture();count=len(boundary.requests)
        with self.assertRaises(NativeUIError):reader.input('graphics.haze','activate')
        with self.assertRaises(NativeUIError):reader.deliver(dict(schemaVersion=1,commandId='f'*32,action='activate'),value)
        self.assertEqual(count,len(boundary.requests))

    def test_candidate_loss_and_ignored_command_never_send_a_second_read_or_invent_empty_ui(self):
        boundary=Boundary();reader=boundary.source();reader.capture();boundary.okay=False
        with self.assertRaises(NativeUIError):reader.capture()
        self.assertEqual(1,len(boundary.requests))
        boundary=Boundary();boundary.ignore=True
        with self.assertRaises(NativeUIError):boundary.source().capture()
        self.assertEqual(1,len(boundary.requests))

    def test_partial_original_file_only_retries_reads_and_reused_cursor_or_native_birth_fails(self):
        boundary=Boundary();boundary.partial=2;reader=boundary.source();value=reader.capture()
        self.assertEqual(20000,value['capturedEpochMs']);self.assertEqual(1,len(boundary.requests))
        boundary.edit=lambda value:value.update(sourceSequence=1)
        with self.assertRaises(NativeUIError):reader.capture()
        boundary.edit=lambda value:value.update(instance='f'*32)
        with self.assertRaises(NativeUIError):reader.capture()

    def test_durable_original_history_never_supplies_a_current_read_or_forgets_a_retained_root(self):
        boundary=Boundary();first=boundary.source().capture();reader=boundary.source();reader.restore_inventory(first)
        self.assertEqual(1,len(boundary.requests));self.assertEqual(1,reader.sequence)
        boundary.controls=[];boundary.roots=[]
        with self.assertRaises(NativeUIError):reader.capture()
        boundary.retired=['d'*32];self.assertEqual(['panel:graphics-tablet'],resources(reader.capture()))
        with self.assertRaises(NativeUIError):reader.restore_inventory(first)

    def test_slow_final_guard_or_inventory_validation_cannot_bypass_current_freshness(self):
        boundary=Boundary();reader=boundary.source();original=reader.clock_ms
        calls=[]
        def clock():
            calls.append(True)
            if len(calls)>2:boundary.clock+=2
            return original()
        reader.clock_ms=clock
        with self.assertRaises(NativeUIError):reader.capture()
        boundary=Boundary();reader=boundary.source()
        with patch('adapters.pico4.graphics_source.accept_inventory',side_effect=lambda *a,**k:boundary.sleep(6)):
            with self.assertRaises(NativeUIError):reader.capture()


if __name__=='__main__':unittest.main()
