"""Normal W3C page recipe; actual private intent journal, Qt/UIKit modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from ios.adapters.audio_page_inputs import AudioPageInputs,PRIMARY
from ios.adapters.normal_audio import IOSAudioIO
from ios.adapters.normal_input import observation


class PageModel:
    def __init__(self,root):
        self.route='closed';self.page=0;self.pages=2;self.audio_page=1;self.clock=1.;self.sequence=0
        self.instance=str(uuid.uuid4());self.launcher=str(uuid.uuid4());self.tokens={};self.elements={}
        self.actions=[];self.settings=False;self.ignore=None;self.lost=None;self.change=False;self.ambiguous=False
        self.store=PrivateFeatureState(root/'audio-page-input-intents.json');self.previous=None;self.journal={}
        self.guard=lambda:not self.change
        self.native=NativeUI(SimpleNamespace(call=self.call),'owned-audio-session',self.guard,monotonic=lambda:self.clock,sleep=self.sleep)
        self.io=IOSAudioIO(SimpleNamespace(capture=self.capture));self.input=AudioPageInputs(self.io,self.native,self.intent,monotonic=lambda:self.clock,sleep=self.sleep)
    def sleep(self,seconds):self.clock+=seconds
    def row(self,id_,**extra):
        key=(self.route,self.page,id_);token=self.tokens.setdefault(key,str(uuid.uuid4()))
        return dict(id=id_,token=token,enabled=True,focused=False,frame=dict(x=10,y=20,width=100,height=40),**extra)
    def capture(self):
        if not self.guard():raise NativeUIError('Declared lost foreground/candidate continuity')
        self.clock+=.001;rows=[];extra={}
        if self.route=='closed':rows=[self.row('hud.tablet')]
        elif self.route=='launcher':
            selected=dict(tabletLauncherControlVersion=1,launcherRootId=self.launcher,
                launcherQmlSource='qrc:/qml/hifi/tablet/TabletHome.qml',launcherCurrentIndex=self.page,
                launcherPageCount=self.pages,inputReady=True)
            rows=[self.row('snapshot.entry',**selected,launcherControlIndex=-1)]
            if self.pages>1:rows.extend(self.row('tablet.page.'+str(i+1),**selected,launcherControlIndex=i) for i in range(self.pages))
            if self.page==self.audio_page:rows.append(self.row('settings.entry' if self.settings else 'audio.entry',inputReady=True))
            rows.append(self.row('tablet.close'));extra['tabletLauncherControlsVersion']=1
        elif self.route=='settings':rows=[self.row('audio.settings-entry',inputReady=True),self.row('tablet.home'),self.row('tablet.close')]
        elif self.route=='audio':
            rows=[self.row('audio.page',inputReady=False,mode=0,nativeHmd=False,uiHmd=False,cycle=0),
                self.row('tablet.home'),self.row('tablet.close')]
        value=dict(schemaVersion=1,instance=self.instance,frameSpace='qt-window-logical',processId=42,
            sampleEpochMs=20000+round(self.clock*1000),elapsedMs=round(self.clock*1000),lastSequence=self.sequence,
            tabletShown=self.route!='closed',ready=True,controls=rows,audioControlsVersion=1,**extra)
        return observation(value,42,value['sampleEpochMs'])
    def intent(self,label,control,value,element):
        if label in self.journal:raise NativeUIError('The original page input remains owned; do not resend')
        value=deepcopy(value);self.journal[label]=dict(control=control,ui=value,element=element)
        packet=dict(intents=deepcopy(self.journal));self.store.write(packet,self.previous);self.previous=deepcopy(packet)
        return True
    def call(self,method,path,body=None):
        if path.endswith('/elements'):
            rows=self.capture()['controls'];matches=[]
            for row in rows:
                if body['value']==PRIMARY.get(row['id'],'OverteNavigation.'+row['id']):
                    element='element-'+row['token'];self.elements[element]=(row['id'],row['token'])
                    matches.append({W3C_ELEMENT:element})
            if self.ambiguous and matches:matches.append({W3C_ELEMENT:'foreign-duplicate'})
            return matches
        prefix='/session/owned-audio-session/element/';assert path.startswith(prefix)
        element,operation=path[len(prefix):].split('/',1);id_,token=self.elements[element]
        row=next((row for row in self.capture()['controls'] if row['id']==id_ and row['token']==token),None)
        if row is None:raise NativeUIError('Actual original UIKit element retired')
        if method=='GET':return token if operation=='attribute/value' else True
        assert method=='POST' and operation=='click' and body=={}
        assert any(value['control']==id_ and value['element']=='/element/'+element for value in self.store.read()['intents'].values())
        self.actions.append(id_);self.sequence+=1
        if id_!=self.ignore:
            if id_=='hud.tablet' or id_=='tablet.home':self.route='launcher'
            elif id_=='tablet.close':self.route='closed'
            elif id_.startswith('tablet.page.'):self.page=int(id_.rsplit('.',1)[1])-1
            elif id_=='audio.entry' or id_=='audio.settings-entry':self.route='audio'
            elif id_=='settings.entry':self.route='settings'
            else:raise AssertionError(id_)
        if id_==self.lost:self.lost=None;raise NativeUIError('Declared lost native click return after actual modeled UI effect')


class AudioPageInputTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.m=PageModel(self.root)
    def test_normal_direct_open_and_original_launcher_restore_use_real_source_tokens(self):
        m=self.m;opened=m.input.open();self.assertEqual('audio',m.input.route(opened['ui']))
        self.assertEqual(0,opened['launcher']['launcherCurrentIndex']);closed=m.input.close(opened['launcher'])
        self.assertEqual('closed',m.input.route(closed));self.assertEqual(0,m.page)
        self.assertEqual(['hud.tablet','tablet.page.2','audio.entry','tablet.home','tablet.page.1','tablet.close'],m.actions)
        self.assertEqual(len(m.actions),len(m.journal))
    def test_settings_fallback_uses_actual_settings_category_without_handler_calls(self):
        m=self.m;m.settings=True;opened=m.input.open()
        self.assertEqual('audio',m.input.route(opened['ui']));self.assertIn('settings.entry',m.actions);self.assertIn('audio.settings-entry',m.actions)
        m.input.close(opened['launcher']);self.assertEqual('closed',m.route)
    def test_already_open_page_is_only_observed_without_new_input(self):
        m=self.m;m.route='audio';opened=m.input.open();self.assertIsNone(opened['launcher']);self.assertEqual([],m.actions)
    def test_ignored_page_change_remains_owned_and_cannot_be_repeated(self):
        m=self.m;m.ignore='tablet.page.2'
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertEqual(1,m.actions.count('tablet.page.2'));m.ignore=None
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertEqual(1,m.actions.count('tablet.page.2'))
    def test_lost_audio_click_return_is_retained_and_fresh_ui_read_never_resends_it(self):
        m=self.m;m.lost='audio.entry'
        with self.assertRaises(NativeUIError):m.input.open()
        before=deepcopy(m.actions);opened=m.input.open();self.assertEqual('audio',m.input.route(opened['ui']));self.assertEqual(before,m.actions)
        self.assertIn('open-audio',m.store.read()['intents'])
    def test_failed_intent_and_foreground_guard_prevent_actual_click(self):
        m=self.m
        def reject(*_):raise NativeUIError('Declared original WAL failure')
        m.input.intent=reject
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertEqual([],m.actions);m.input.intent=m.intent;m.change=True
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertEqual([],m.actions)
    def test_ambiguous_real_element_is_refused_before_intent_and_input(self):
        m=self.m;m.ambiguous=True
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertEqual({},m.journal);self.assertEqual([],m.actions)
    def test_unobserved_audio_entry_exhausts_actual_pages_without_guessing_another_control(self):
        m=self.m;m.audio_page=10
        with self.assertRaises(NativeUIError):m.input.open()
        self.assertNotIn('audio.entry',m.actions);self.assertNotIn('settings.entry',m.actions)
