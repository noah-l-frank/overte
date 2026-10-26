"""Ordinary source-bound W3C request shapes and independent ACK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from ios.adapters.tablet_web_native_input import TabletWebNativeInput
from ios.self_tests.tablet_web_dom_fixture import packet as envelope
from ios.self_tests.test_ios_tablet_web_packets import BINDING

REPO=Path(__file__).resolve().parents[4]


class SDK:
    def __init__(self):self.calls=[];self.value='';self.rect=dict(x=20.,y=64.,width=200.,height=40.);self.kind='XCUIElementTypeTextField';self.label='Owned Tablet text';self.fail=False;self.after=None;self.active='actual-owned-field';self.displayed=True;self.enabled=True;self.ignore_clear=False
    def call(self,method,path,body=None):
        self.calls.append((method,path,deepcopy(body)))
        if method in ('POST','DELETE'):
            if self.fail and method=='POST':raise OSError('Actual touch return lost')
            if method=='POST' and path.endswith('/clear') and not self.ignore_clear:self.value=''
            if method=='POST' and path.endswith('/value'):self.value=body['text']
            if self.after:self.after(method,path)
            return None
        if path.endswith('/element/active'):return {W3C_ELEMENT:self.active}
        if path.endswith('/attribute/type'):return self.kind
        if path.endswith('/attribute/label'):return self.label
        if path.endswith('/rect'):return deepcopy(self.rect)
        if path.endswith('/displayed'):return self.displayed
        if path.endswith('/enabled'):return self.enabled
        if path.endswith('/attribute/value'):return self.value
        raise AssertionError('Unreviewed native request')


class TabletWebNativeInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        program='''const page=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page;
let result=[];for(const text of ['', 'old fixture text']){const p=page();p.nodes.get('text').value=text;
p.doc.activeElement=p.nodes.get('text');p.event('text','focusin');result.push(p.read('ios-'+(1).toString(16).padStart(32,'0')));}
process.stdout.write(JSON.stringify(result));'''
        run=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
        if run.returncode:raise AssertionError(run.stderr)
        cls.bodies=json.loads(run.stdout)
    def setUp(self):
        self.client=SDK();self.events=[];self.current=True;self.clock=100100
        self.input=TabletWebNativeInput(self.client,BINDING,lambda:self.clock,lambda:self.current,self.intent)
    def intent(self,phase,value):self.events.append((phase,deepcopy(value)))
    def document(self,nonempty=False):
        value=envelope(self.bodies[int(nonempty)])
        for key in ('presentationBefore','presentationAfter'):value['source'][key]['responders']=['8'*32]
        return value
    def mutations(self):return [row for row in self.client.calls if row[0] in ('POST','DELETE')]
    def test_actual_touch_uses_integer_viewport_point_once_and_retains_original_source(self):
        original=self.document();before=deepcopy(original);owner=self.input.tap(original,'bridge')
        calls=self.mutations();self.assertEqual(['POST','DELETE'],[row[0] for row in calls])
        actions=calls[0][2]['actions'][0];self.assertEqual('touch',actions['parameters']['pointerType'])
        point=actions['actions'][0];self.assertEqual([120,84],[point['x'],point['y']]);self.assertIs(type(point['x']),int)
        self.assertEqual(['issued','returned','issued','returned'],[phase for phase,_ in self.events])
        self.assertEqual(original['source']['nativeView'],owner['nativeView']);self.assertEqual(before,original)
        self.assertNotIn('delivered',owner);self.assertNotIn('effect',owner)
    def test_unknown_touch_return_releases_once_without_repeating_or_claiming_delivery(self):
        self.client.fail=True
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual(['POST','DELETE'],[row[0] for row in self.mutations()]);self.assertEqual(3,len(self.events))
        self.assertEqual(['touch','release','release'],[value['kind'] for _,value in self.events])
    def test_owned_release_keeps_original_transport_session_and_intent_after_alias_change(self):
        foreign=SDK();old_base=self.input.ui.base
        def changed(method,path):
            if method=='POST':
                self.current=False;self.input.ui=NativeUI(foreign,'foreign-session',lambda:True)
                self.input.intent=lambda *_:(_ for _ in ()).throw(AssertionError('Foreign callback used'))
        self.client.after=changed
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual(['POST','DELETE'],[method for method,_path,_body in self.mutations()])
        self.assertTrue(all(path==old_base+'/actions' for _method,path,_body in self.mutations()))
        self.assertEqual([],foreign.calls);self.assertEqual(['touch','touch','release','release'],[value['kind'] for _,value in self.events])
    def test_changed_original_transport_endpoint_cannot_retarget_owned_release(self):
        def changed(method,path):
            if method=='POST':self.client.server_url='changed-private-endpoint'
        self.client.after=changed
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual(['POST'],[method for method,_path,_body in self.mutations()])
        self.assertEqual(['touch','touch','release'],[value['kind'] for _,value in self.events])

    def test_rejected_journal_or_expired_original_before_touch_never_releases_unowned_actions(self):
        self.input.intent=lambda phase,value:False
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual([],self.client.calls)
        self.input.intent=self.intent;self.clock=102000
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual([],self.client.calls)
    def test_current_owned_field_unicode_and_clear_are_separate_once_requests(self):
        self.client.value='old fixture text';document=self.document(True);before=deepcopy(document)
        owner=self.input.replace(document,'text','Überte 🙂')
        self.assertEqual(before,document);self.assertEqual('Überte 🙂',self.client.value)
        self.assertEqual(2,len([path for _,path,_ in self.client.calls if path.endswith('/element/active')]))
        calls=self.mutations();self.assertEqual(2,len(calls));self.assertTrue(calls[0][1].endswith('/actual-owned-field/clear'))
        self.assertTrue(calls[1][1].endswith('/actual-owned-field/value'));self.assertEqual('Überte 🙂',calls[1][2]['text'])
        self.assertEqual(list('Überte 🙂'),calls[1][2]['value']);self.assertEqual('text',owner['field'])
        self.assertEqual(['clear','clear','text','text'],[value['kind'] for _,value in self.events])
    def test_clear_return_without_independently_empty_native_value_never_types(self):
        self.client.value='old fixture text';self.client.ignore_clear=True
        with self.assertRaises(NativeUIError):self.input.replace(self.document(True),'text','Überte 🙂')
        self.assertEqual(['clear'],[path.rsplit('/',1)[-1] for _,path,_ in self.mutations()])
        self.assertEqual(['clear','clear'],[value['kind'] for _,value in self.events])
        self.assertEqual('old fixture text',self.client.value)
    def test_changed_active_reference_after_clear_stops_before_unissued_text_or_other_field_read(self):
        self.client.value='old fixture text'
        def changed(method,path):
            if path.endswith('/clear'):self.client.active='actual-other-field'
        self.client.after=changed
        with self.assertRaises(NativeUIError):self.input.replace(self.document(True),'text','Überte 🙂')
        self.assertEqual(['clear'],[path.rsplit('/',1)[-1] for _,path,_ in self.mutations()])
        self.assertFalse(any('/element/actual-other-field/' in path for _,path,_ in self.client.calls))
        self.assertEqual(2,len([path for _,path,_ in self.client.calls if path.endswith('/element/active')]))
    def test_same_reference_changed_secure_hidden_label_or_rect_after_clear_never_types(self):
        for fault in ('secure','hidden','disabled','label','rect'):
            self.setUp();self.client.value='old fixture text'
            def changed(method,path):
                if not path.endswith('/clear'):return
                if fault=='secure':self.client.kind='XCUIElementTypeSecureTextField'
                elif fault=='hidden':self.client.displayed=False
                elif fault=='disabled':self.client.enabled=False
                elif fault=='label':self.client.label='Unrelated actual field'
                else:self.client.rect['x']+=20
            self.client.after=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.input.replace(self.document(True),'text','Überte 🙂')
            self.assertEqual(['clear'],[path.rsplit('/',1)[-1] for _,path,_ in self.mutations()])
            if fault=='secure':self.assertEqual(1,len([path for _,path,_ in self.client.calls if path.endswith('/attribute/value')]))
    def test_unknown_clear_return_never_issues_text_or_another_clear(self):
        self.client.value='old fixture text';self.client.fail=True
        with self.assertRaises(NativeUIError):self.input.replace(self.document(True),'text','Überte 🙂')
        self.assertEqual(['clear'],[path.rsplit('/',1)[-1] for _,path,_ in self.mutations()])
        self.assertEqual(['clear'],[value['kind'] for _,value in self.events])

    def test_wrong_active_type_rect_value_pid_or_dom_focus_never_mutates(self):
        for fault in ('type','rect','label','value','pid','focus','responder','private','webdriver-key'):
            document=self.document();self.client.calls.clear();self.client.kind='XCUIElementTypeTextField';self.client.label='Owned Tablet text';self.client.rect['x']=20.;self.client.value=''
            text='owned';field='text'
            if fault=='type':self.client.kind='XCUIElementTypeSecureTextField'
            elif fault=='rect':self.client.rect['x']=300.
            elif fault=='label':self.client.label='Different native sheet field'
            elif fault=='value':self.client.value='different unowned field'
            elif fault=='pid':document['processId']=42
            elif fault=='focus':document['source']['dom']['editor']['focused']=False;next(row for row in document['source']['dom']['elements'] if row['id']=='text')['focused']=False
            elif fault=='responder':
                for key in ('presentationBefore','presentationAfter'):document['source'][key]['responders']=[]
            elif fault=='private':field='password'
            else:text='\ue007'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.input.replace(document,field,text)
            self.assertEqual([],self.mutations())
            if fault in ('type','rect'):self.assertFalse(any(path.endswith('/attribute/value') for _,path,_ in self.client.calls))
    def test_slow_issued_journal_fails_last_freshness_and_owned_release_survives_guard_loss(self):
        def slow(phase,value):
            self.intent(phase,value)
            if phase=='issued':self.clock=102000
        self.input.intent=slow
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual([],self.client.calls)
        self.input.intent=self.intent;self.clock=100100
        def lost(method,path):
            if method=='POST':self.current=False
        self.client.after=lost
        with self.assertRaises(NativeUIError):self.input.tap(self.document(),'bridge')
        self.assertEqual(['POST','DELETE'],[row[0] for row in self.mutations()])


if __name__=='__main__':unittest.main()
