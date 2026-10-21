"""Actual Pico navigation/token/Home composition at synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from adapters.pico4.graphics_surface import PicoGraphicsSurface
from adapters.pico4.navigation import PicoNavigation,NavigationError,validate_snapshot
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_script_ui import TokenScriptUI
from self_tests.test_pico_tablet_home import original as home_original
from self_tests.test_token_graphics_ui import GraphicsBoundary
from self_tests.test_vr_graphics_subject import Boundary as SubjectBoundary,RUN

URL='http://controlled.invalid/owned/graphics-scene.v1.json?location=/0,0,0/0,0,0,1'
IDENTITY=dict(schemaVersion=1,sourceRevision='a'*40,artifactSha256='b'*64,installedCandidateVerified=True)


class Boundary:
    def __init__(self):
        self.pid=31
        self.clock=0.;self.opened=False;self.page='home';self.page_number=1;self.focused=False;self.text='original'
        self.sequence=0;self.revision=0;self.inputs=[];self.events=[];self.intents=[];self.entered=[]
        self.bridge='11111111-1111-4111-8111-111111111111';self.generation='22222222-2222-4222-8222-222222222222'
        self.graph=GraphicsBoundary(generic=True);self.leases=dict(tablet=False,address=False,menu=False)
        self.okay=True;self.fault='';self.allowed={URL};self.authority_calls=0
    @property
    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds;self.graph.clock=self.clock
    def guard(self):
        if not self.okay:raise NavigationError()
        return True
    def bind_input(self):return self.guard()
    def snapshot(self):
        rows=[]
        if self.opened:
            if self.page=='home':
                rows=[dict(id='tablet.page.1'),dict(id='tablet.page.2')]
                if self.page_number==1:rows.append(dict(id='settings.entry',inputReady=True,viewport='visible'))
                else:rows.append(dict(id='navigation.goto'))
            elif self.page=='settings':rows=[dict(id='graphics.settings-entry',inputReady=True,viewport='visible')]
            elif self.page=='graphics':rows=deepcopy(self.graph.capture()['controls'])
            elif self.page=='address':rows=[dict(id='navigation.address',textSha256=hashlib.sha256(self.text.encode()).hexdigest(),
                textLength=len(self.text),inputReady=self.focused)]
        for row in rows:
            row.setdefault('enabled',True);row['focused']=row['id']=='navigation.address' and self.focused
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,str(self.revision)+json.dumps(row,sort_keys=True)))
        return dict(schemaVersion=1,bridgeId=self.bridge,generation=self.generation,processId=self.pid,elapsedMs=round(self.clock*1000),
            updatedEpochMs=self.epoch,lastCommandSequence=self.sequence,open=self.opened,ready=self.opened,
            featureControlsVersion=1,graphicsControlsVersion=1,navigationAddressVersion=1,controls=rows)
    def read(self):return self.snapshot(),self.epoch
    def controller(self,operation):
        self.guard();assert operation in ('tablet.open','tablet.close');self.events.append(operation)
        assert self.intents and self.intents[-1]['control']==operation
        self.opened=operation=='tablet.open';self.revision+=1
    def send(self,command):
        self.guard();original=next(row for row in self.snapshot()['controls'] if row['id']==command['controlId'])
        assert original['token']==command['controlToken'];assert command['sequence']==self.sequence+1
        self.sequence+=1;self.inputs.append(deepcopy(command));control=command['controlId'];action=command['action']
        assert self.intents and self.intents[-1]['control']==control
        self.events.append(control+':'+action)
        if self.fault=='lost-return':raise NavigationError()
        if control.startswith('tablet.page.'):self.page_number=int(control.rsplit('.',1)[1])
        elif control=='settings.entry':self.page='settings'
        elif control=='graphics.settings-entry':self.page='graphics'
        elif control=='navigation.goto':self.page='address'
        elif control=='navigation.address':
            if action=='activate':self.focused=True
            elif action=='replace':
                if self.fault!='ignored-address':self.text=command['text']
            elif action=='submit':self.entered.append(self.text);self.page='home';self.opened=False;self.focused=False
            else:raise AssertionError(action)
        elif control.startswith('graphics.'):
            token=next(row['token'] for row in self.graph.capture()['controls'] if row['id']==control)
            if action=='activate':self.graph.activate(control,token=token)
            elif action=='scroll':self.graph.scroll(control,command['direction'],token=token)
            elif action=='set-value':self.graph.set_value(control,command['value'],token=token)
            else:raise AssertionError(action)
        else:raise AssertionError(control)
        self.revision+=1
        return dict(schemaVersion=1,bridgeId=self.bridge,commandId=command['commandId'],sequence=command['sequence'],
            performed=True,error='',processId=self.pid,updatedEpochMs=self.epoch),self.epoch
    def intent(self,stage,subject,source,control):
        if self.fault=='intent':raise NavigationError()
        if self.fault=='candidate-intent':self.okay=False
        if self.fault=='revoke-address' and stage=='address-replace':self.allowed.clear()
        if self.fault=='revoke-submit' and stage=='address-go':self.allowed.clear()
        if self.fault=='change-submit' and stage=='address-go':self.text='http://foreign.invalid/late'
        self.intents.append(dict(stage=stage,subject=deepcopy(subject),source=deepcopy(source),control=control))
        self.events.append('intent:'+control)
        if source['kind']=='graphics' and control in ('graphics.resolution','graphics.haze','graphics.mirrors','graphics.scrollbar'):
            self.graph.intents.append((stage,control))
    def lease(self,field,value):self.leases[field]=value
    def allowed_url(self,url):self.authority_calls+=1;return url in self.allowed


class HomeSource:
    pid=31
    def __init__(self,native):self.native=native;self.sequence=0;self.pid=native.pid
    def guard(self):return self.native.guard()
    def clock_ms(self):return self.native.epoch
    def monotonic(self):return self.native.clock
    def sleep(self,value):self.native.sleep(value)
    def capture(self):
        self.sequence+=1;value=home_original()
        value.update(processId=self.pid,capturedEpochMs=self.native.epoch,sourceSequence=self.sequence,
            tabletShown=self.native.opened,onHomeScreen=self.native.page=='home')
        return value
    def stage(self,pose):
        self.guard();assert self.native.intents[-1]['control']=='tablet.home-ray'
        self.native.events.append('tablet.home-ray');self.native.page='home';self.native.focused=False;self.native.revision+=1


class PicoGraphicsSurfaceTests(unittest.TestCase):
    def surface(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        path=Path(temporary.name);path.chmod(0o700);native=Boundary()
        navigation=PicoNavigation(native,path/'navigation.json',IDENTITY,'31:original-start','http://controlled.invalid/scene.json',
            monotonic=lambda:native.clock,sleep=native.sleep)
        ui=TokenScriptUI(PicoScriptIO(navigation),monotonic=lambda:native.clock,sleep=native.sleep)
        boundary=SubjectBoundary();original_send=boundary.send
        def send(request):boundary.epoch=native.epoch;original_send(request)
        reader=boundary.reader(require_framework=True);reader.send=send;reader.clock_ms=lambda:native.epoch
        reader.guard=native.guard;reader.monotonic=lambda:native.clock;reader.sleep=native.sleep
        home=HomeSource(native)
        surface=PicoGraphicsSurface(ui,reader,PicoTabletHome(home,home.stage),RUN,native.intent,
            lambda field:native.leases[field],native.lease,native.allowed_url)
        return native,surface

    def test_absent_unowned_address_is_noop_before_ordinary_graphics_home_and_close(self):
        native,surface=self.surface();surface.open();before=list(native.events)
        surface.close_address();self.assertEqual(before,native.events);self.assertEqual('graphics',native.page)
        surface.close_tablet();self.assertEqual('home',native.page);self.assertFalse(native.opened)
        self.assertIn('tablet.home-ray',native.events)

    def test_generic_settings_native_readback_and_home_before_physical_close(self):
        native,surface=self.surface();surface.open();surface.set_resolution(.5);surface.toggle('graphics.haze',True)
        surface.toggle('graphics.mirrors',True);surface.set_resolution(.6);surface.toggle('graphics.haze',False)
        surface.toggle('graphics.mirrors',False);surface.close_tablet()
        self.assertFalse(native.opened);self.assertEqual('home',native.page);self.assertFalse(any(native.leases.values()))
        self.assertEqual(.6,native.graph.resolution);self.assertFalse(native.graph.haze);self.assertFalse(native.graph.mirrors)
        self.assertLess(native.events.index('tablet.home-ray'),native.events.index('tablet.close'))
        self.assertNotIn('settings.vr-render-resolution',json.dumps(native.inputs))
        for record in native.intents:self.assertEqual(3,record['subject']['source']['subjectVersion'])
        home=next(row for row in native.intents if row['source']['kind']=='home')
        self.assertEqual('Gizmo',home['source']['value']['entityType'])

    def test_normal_goto_submits_only_actual_original_field_hash_and_exact_registered_url(self):
        native,surface=self.surface();self.assertEqual({'performed':True},surface.navigate(URL))
        self.assertEqual([URL],native.entered);self.assertFalse(native.opened);self.assertFalse(any(native.leases.values()))
        self.assertEqual(1,sum(row['action']=='replace' for row in native.inputs))
        self.assertEqual(1,sum(row['action']=='submit' for row in native.inputs))
        self.assertNotIn('text',next(row['source']['value']['controls'][0] for row in native.intents if row['stage']=='address-go'))

    def test_ignored_field_replacement_never_submits_old_address_or_resends(self):
        native,surface=self.surface();native.fault='ignored-address'
        with self.assertRaises(RuntimeError):surface.navigate(URL)
        self.assertEqual([],native.entered);self.assertEqual(1,sum(row['action']=='replace' for row in native.inputs))
        self.assertFalse(any(row['action']=='submit' for row in native.inputs));self.assertTrue(native.leases['address'])
        replacement=next(row for row in native.inputs if row['action']=='replace')
        self.assertLessEqual(native.clock-replacement['observedElapsedMs']/1000,10.2)

    def test_out_of_scope_unsafe_and_revoked_urls_never_reach_replace_or_submit(self):
        for url in ('http://foreign.invalid/scene.json','https://user:secret@controlled.invalid/scene.json','file:///tmp/foreign','x\nurl'):
            native,surface=self.surface()
            with self.subTest(url=url),self.assertRaises((RuntimeError,ValueError)):surface.navigate(url)
            self.assertEqual([],native.inputs);self.assertEqual([],native.events)
        native,surface=self.surface();native.fault='revoke-address'
        with self.assertRaises(RuntimeError):surface.navigate(URL)
        self.assertFalse(any(row['action'] in ('replace','submit') for row in native.inputs));self.assertTrue(native.leases['address'])

    def test_late_field_change_or_scope_revocation_cannot_authorize_enter(self):
        for fault in ('revoke-submit','change-submit'):
            native,surface=self.surface();native.fault=fault
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):surface.navigate(URL)
            self.assertEqual([],native.entered);self.assertFalse(any(row['action']=='submit' for row in native.inputs))
            self.assertTrue(native.leases['address'])

    def test_navigation_scope_is_opt_in_replaces_default_and_is_rechecked_before_enter(self):
        native,surface=self.surface();navigation=surface.ui.io.navigation
        native.opened=True;native.page='address';native.focused=True
        configured=next(iter(navigation.urls))
        native.intents.append(dict(control='navigation.address'))
        with self.assertRaises(RuntimeError):navigation.input('navigation.address','replace',configured)
        self.assertEqual([],native.inputs)
        navigation.input('navigation.address','replace',URL);self.assertEqual(URL,native.text)
        calls=[]
        def revoked(url):calls.append(url);return len(calls)==1
        navigation.address_authority=revoked
        with self.assertRaises(RuntimeError):navigation.input('navigation.address','submit',expected_address=URL)
        self.assertEqual([URL,URL],calls);self.assertEqual([],native.entered)
        navigation.address_authority=None
        with self.assertRaises(RuntimeError):navigation.input('navigation.address','replace',URL)
        navigation.input('navigation.address','replace',configured);self.assertEqual(configured,native.text)

    def test_failed_durable_intent_and_candidate_loss_prevent_input(self):
        for fault in ('intent','candidate-intent'):
            native,surface=self.surface();native.fault=fault
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):surface.open()
            self.assertEqual([],native.inputs);self.assertFalse(native.opened)
        native,surface=self.surface();surface.open();native.okay=False;before=len(native.inputs)
        with self.assertRaises(RuntimeError):surface.set_resolution(.5)
        self.assertEqual(before,len(native.inputs));self.assertTrue(native.leases['tablet'])

    def test_lost_return_preserves_intent_lease_and_does_not_automatically_retry(self):
        native,surface=self.surface();native.fault='lost-return'
        with self.assertRaises(RuntimeError):surface.open()
        self.assertEqual(1,len(native.inputs));self.assertTrue(native.leases['tablet'])
        self.assertEqual('settings.entry',native.intents[-1]['control'])

    def test_hidden_owned_graphics_is_reopened_to_normal_home_before_retiring_lease(self):
        native,surface=self.surface();surface.open();native.opened=False;native.revision+=1
        surface.close_tablet()
        self.assertEqual('home',native.page);self.assertFalse(native.opened);self.assertFalse(native.leases['tablet'])
        self.assertEqual(2,native.events.count('tablet.open'));self.assertEqual(1,native.events.count('tablet.home-ray'))

    def test_foreign_open_or_retained_tablet_is_not_closed_or_adopted(self):
        native,surface=self.surface();native.opened=True;native.page='graphics'
        with self.assertRaises(RuntimeError):surface.open()
        self.assertEqual([],native.events)
        native.opened=False
        with self.assertRaises(RuntimeError):surface.close_tablet()
        self.assertEqual([],native.events)

    def test_slider_non_grid_values_and_wrong_camera_are_refused_without_product_setters(self):
        native,surface=self.surface();surface.open();before=len(native.inputs)
        with self.assertRaises(RuntimeError):surface.set_resolution(.65)
        self.assertEqual(before,len(native.inputs))
        self.assertEqual({'performed':False},surface.select_camera('first person'))
        with self.assertRaises(RuntimeError):surface.select_camera('first person look at')
        self.assertEqual(before,len(native.inputs))

    def test_optional_original_address_metadata_is_strict_and_legacy_reader_remains_explicit(self):
        native,surface=self.surface();native.opened=True;native.page='address';native.focused=True
        packet=native.snapshot();validate_snapshot(packet,31,native.epoch)
        for change in (dict(textLength=True),dict(textSha256='expected'),dict(focused=False),dict(inputReady=1)):
            value=deepcopy(packet);value['controls'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NavigationError):validate_snapshot(value,31,native.epoch)
        value=deepcopy(packet);value.pop('navigationAddressVersion')
        for key in ('textLength','textSha256','inputReady'):value['controls'][0].pop(key)
        validate_snapshot(value,31,native.epoch)
        value['navigationAddressVersion']=True
        with self.assertRaises(NavigationError):validate_snapshot(value,31,native.epoch)
