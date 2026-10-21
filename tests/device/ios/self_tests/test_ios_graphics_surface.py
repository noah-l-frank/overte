"""Ordinary iOS UI/AFC framing with a synthetic generic Qt/menu boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from adapters.token_graphics_ui import TokenGraphicsUI
from self_tests.test_token_graphics_ui import GraphicsBoundary
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_script_ui_inventory import inventory
from ios.adapters import normal_input
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.graphics_source import IOSGraphicsSource
from ios.adapters.graphics_surface import IOSGraphicsSurface
from ios.adapters.view_controls import LABELS,MODES
from ios.self_tests.test_ios_normal_input import Boundary as InputBoundary

RUN='b'*32;URL='https://controlled.invalid/original.json'


class Model(GraphicsBoundary):
    def original(self,identifier,token):
        rows=[row for row in self.capture()['controls'] if row['id']==identifier]
        if len(rows)!=1 or rows[0]['token']!=token or not rows[0]['inputReady']:raise NativeUIError('Retired widget token')


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__();self.model=Model(generic=True);self.stage='closed';self.camera='look at'
        self.focus=None;self.address='';self.url=URL;self.clicks=[];self.intents=[];self.refs={};self.fault=''
        self.leases=dict(tablet=False,address=False,menu=False)
        self.subject=SubjectBoundary();self.subject.edit=self.subject_packet
        self.subject.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,0,0],orientation=[0,0,0,1],modelScale=1))

    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds;self.model.clock=self.clock
    def subject_packet(self,value):
        value.update(processId=42,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        value['source']['view']['mode']=self.camera;value['source']['sceneUrl']=self.url

    def observed(self):
        value=super().observed();self.ui_sequence=getattr(self,'ui_sequence',0)+1
        shown=self.stage not in ('closed','address')
        def row(identifier,**fields):return dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),
            enabled=True,focused=self.focus==identifier,frame=dict(x=10,y=20,width=200,height=48),**fields)
        rows=[]
        if self.stage=='closed':rows=[row('hud.goto')]
        elif self.stage=='address':rows=[row(identifier) for identifier in ('address.field','address.go','address.cancel')]
        elif self.stage=='home':rows=[row('scripts.menu'),row('settings.entry',inputReady=True,viewport='visible')]
        elif self.stage=='settings':rows=[row('tablet.home'),row('graphics.settings-entry',inputReady=True,viewport='visible')]
        elif self.stage=='graphics':
            for item in self.model.capture()['controls']:
                item=deepcopy(item);item['token']=str(uuid.UUID(hex=item['token']));item['focused']=False
                item['frame']=None if item['viewport'] in ('above','below') else dict(x=10,y=20,width=100,height=40)
                rows.append(item)
        elif self.stage in ('menu','view'):
            ids=['view.menu'] if self.stage=='menu' else list(MODES.values())
            rows=[row(identifier,viewMenuSourceVersion=1,sourceType=2 if identifier=='view.menu' else 1,
                labelSha256=hashlib.sha256(LABELS[identifier].encode()).hexdigest(),
                checked=None if identifier=='view.menu' else MODES.get(self.camera)==identifier) for identifier in ids]
        value.update(sampleEpochMs=self.epoch(),elapsedMs=round(self.clock*1000),generation=self.instance if not shown else 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
            controls=rows,tabletShown=shown,featureControlsVersion=1,loginControlsVersion=2,graphicsControlsVersion=1,
            viewMenuControlsVersion=1,scriptObservationVersion=1,scriptSourceSequence=self.ui_sequence,
            scriptInventory=inventory(tabletShown=shown))
        return value

    def post(self,request,timeout):
        payload=json.loads(request.data);self.requests.append(deepcopy(payload));self.response=json.dumps(payload).encode()
        if payload['operation']=='observe':self.receipt=dict(schemaVersion=1,commandId=payload['commandId'],observation=self.observed())
        else:
            item=payload['input'];self.sequence=item['sequence'];token=item['fieldToken'].replace('-','')
            if item['operation']=='replace':self.address=item['text']
            elif item['operation']=='scroll':self.model.scroll('graphics.scrollbar',item['direction'],token=token)
            elif item['operation']=='set-value':self.model.set_value('graphics.resolution',item['value'],token=token)
            else:raise AssertionError('Unreviewed synthetic input')
            self.receipt=dict(schemaVersion=1,commandId=payload['commandId'],status=dict(schemaVersion=1,
                commandId=item['commandId'],instance=self.instance,sequence=self.sequence,performed=True,processId=42,sampleEpochMs=self.epoch()))
        return self

    def call(self,method,path,body=None):
        if path.endswith('/elements'):
            identifier=body['value'];name=identifier.removeprefix('OverteNavigation.')
            found=(identifier=='OverteTabletOpen' and self.stage=='closed' or identifier=='OverteTabletClose'
                and self.stage not in ('closed','address') or any(row['id']==name for row in self.observed()['controls']))
            if not found:return []
            key='node-'+str(len(self.refs));self.refs[key]=identifier;return [{W3C_ELEMENT:key}]
        identifier=self.refs[path.split('/element/')[1].split('/')[0]];name=identifier.removeprefix('OverteNavigation.')
        if path.endswith('/displayed') or path.endswith('/enabled'):return True
        if path.endswith('/attribute/value'):
            if self.fault=='retired':return 'ffffffff-ffff-4fff-8fff-ffffffffffff'
            return next(row['token'] for row in self.observed()['controls'] if row['id']==name)
        assert path.endswith('/click');self.clicks.append(identifier)
        if self.fault=='ignored' and name=='view.first-person':return
        if identifier=='OverteTabletOpen':self.stage='home'
        elif identifier=='OverteTabletClose':self.stage='closed'
        elif name=='scripts.menu':self.stage='menu'
        elif name=='view.menu':self.stage='view'
        elif name in MODES.values():self.camera=next(mode for mode,value in MODES.items() if value==name);self.stage='home'
        elif name=='settings.entry':self.stage='settings'
        elif name=='graphics.settings-entry':self.stage='graphics'
        elif name=='tablet.home':self.stage='home'
        elif name in ('graphics.haze','graphics.mirrors'):
            token=next(row['token'] for row in self.model.capture()['controls'] if row['id']==name)
            self.model.activate(name,token=token)
        elif name=='hud.goto':self.stage='address'
        elif name=='address.field':self.focus=name
        elif name=='address.go':self.url=self.address;self.focus=None;self.stage='closed'
        elif name=='address.cancel':self.focus=None;self.stage='closed'
        else:raise AssertionError('Unreviewed synthetic pointer')

    def flow(self):
        native=normal_input.NativeInput(self,'owned-session',self.target,self.process,native_epoch_ms=self.epoch,
            monotonic=lambda:self.clock,sleep=self.sleep)
        ui=NativeUI(self,'owned-session',native._check,monotonic=lambda:self.clock,sleep=self.sleep)
        original=IOSScriptIO(ui,native);source=IOSGraphicsSource(original,self.epoch,native._check,42,monotonic=lambda:self.clock)
        graphics=TokenGraphicsUI(source,lambda *_:None,monotonic=lambda:self.clock,sleep=self.sleep)
        subject=self.subject.reader(ios=True,native_clock_bound=True);subject.pid=42;subject.clock_ms=self.epoch
        def intent(*values):
            self.intents.append(deepcopy(values))
            if self.fault=='intent':raise NativeUIError('Synthetic failed durable intent')
        def lease(field,value):self.leases[field]=value
        return IOSGraphicsSurface(original,subject,graphics,RUN,intent,lambda field:self.leases[field],lease,lambda value:value==URL)


class IOSGraphicsSurfaceTests(unittest.TestCase):
    def test_generic_camera_uses_real_view_tokens_and_independent_original_mode(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):result=b.flow().select_camera('first person look at')
        self.assertEqual({'performed':True},result);self.assertEqual('first person look at',b.camera)
        self.assertIn('OverteNavigation.view.first-person',b.clicks);self.assertEqual('closed',b.stage)
        self.assertFalse(any(b.leases.values()));self.assertTrue(all(len(row)==4 for row in b.intents))

    def test_ignored_camera_and_retired_tokens_are_not_resent_or_reported_as_effects(self):
        for fault in ('ignored','retired'):
            b=Boundary();b.fault=fault
            with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow().select_camera('first person look at')
            self.assertEqual('look at',b.camera);self.assertLessEqual(b.clicks.count('OverteNavigation.view.first-person'),1)

    def test_generic_settings_can_open_scroll_set_toggle_close_and_reopen_on_original_generations(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            surface=b.flow();surface.open();surface.set_resolution(.5);surface.toggle('graphics.haze',True)
            surface.close_tablet();surface.open();surface.close_tablet()
        self.assertEqual(.5,b.model.resolution);self.assertTrue(b.model.haze)
        self.assertFalse(any(b.leases.values()));self.assertEqual('closed',b.stage)

    def test_navigation_uses_normal_address_ime_and_refuses_unowned_urls_before_input(self):
        b=Boundary();b.url='file:///original.json'
        with patch.object(normal_input,'urlopen',b.post):
            surface=b.flow()
            with self.assertRaises(NativeUIError):surface.navigate('https://foreign.invalid/world.json')
            self.assertEqual([],b.clicks);surface.navigate(URL)
        self.assertEqual(URL,b.url);self.assertEqual('closed',b.stage);self.assertFalse(any(b.leases.values()))
        self.assertEqual(1,sum(row['operation']=='edit' for row in b.requests))

    def test_failed_intent_prevents_ordinary_pointer_delivery(self):
        b=Boundary();b.fault='intent'
        with patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow().open()
        self.assertEqual([],b.clicks)

    def test_ignored_native_slider_ack_preserves_old_value_and_never_replays_input(self):
        b=Boundary();b.model.fault='resolution'
        with patch.object(normal_input,'urlopen',b.post):
            surface=b.flow();surface.open()
            with self.assertRaises(NativeUIError):surface.set_resolution(.5)
        self.assertEqual(.6,b.model.resolution);self.assertEqual(1,b.model.actions.count('resolution'))
        self.assertTrue(b.leases['tablet'])

    def test_foreign_view_label_wrong_source_kind_boolean_and_missing_hook_fail_before_input(self):
        for fault in ('label','kind','checked','version','extra'):
            b=Boundary();b.stage='view';original=b.observed
            def observed():
                value=original();row=value['controls'][0]
                if fault=='label':row['labelSha256']='f'*64
                elif fault=='kind':row['sourceType']=2
                elif fault=='checked':row['checked']=1
                elif fault=='version':value.pop('viewMenuControlsVersion')
                else:row['expectedMode']='first person look at'
                return value
            with self.subTest(fault=fault),patch.object(b,'observed',side_effect=observed), \
                 patch.object(normal_input,'urlopen',b.post),self.assertRaises(NativeUIError):b.flow()
            self.assertEqual([],b.clicks)


if __name__=='__main__':unittest.main()
