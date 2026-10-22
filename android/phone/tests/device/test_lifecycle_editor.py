"""Closed independent reader/intent/cursor/context counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_lifecycle_editor import PhoneLifecycleEditorSource,source,command
from adapters.normal_ui import NativeUIError
RUN='a'*32


class Boundary:
    def __init__(self):
        self.epoch=100000;self.sequence=0;self.time=0;self.calls=[];self.saved=[];self.last=None;self.ok=True
        urls=dict(create='file:///owned/scripts/system/create/qml/NativeCreate.qml',chat='file:///owned/scripts/communityScripts/armored-chat/armored_chat.qml',scripts='file:///owned/qml/hifi/dialogs/TabletRunningScripts.qml')
        context=dict(editor='scripts',token='b'*32,fieldToken='c'*32,sourceUrl=urls['scripts'],createdEpochMs=self.epoch-1,retiredEpochMs=0,alive=True,attached=True,active=True)
        self.body=dict(phoneLifecycleEditorVersion=1,instance='d'*32,sequence=0,capturedEpochMs=self.epoch,canonicalSources=urls,
            current=dict(status='ready',**{key:context[key] for key in ('editor','token','fieldToken','sourceUrl')},text='',focused=False,frame=[1,2,300,48]),
            contexts=[context],osKeyboardVisible=False)
    def send(self,value):self.calls.append(deepcopy(value));self.last=deepcopy(value)
    def read(self):
        self.sequence+=1;self.body.update(sequence=self.sequence,capturedEpochMs=self.epoch)
        return json.dumps(dict(schemaVersion=1,requestId=self.last['commandId'],runId=RUN,instance='e'*32,sequence=self.sequence,processId=77,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,performed=self.last['action'].endswith('input'),source=self.body))
    def reader(self,primary=False):
        return PhoneLifecycleEditorSource(self.send,self.read,lambda:self.epoch,lambda:self.ok,77,
            intent=(lambda value:self.saved.append(deepcopy(value))) if primary else None,monotonic=lambda:self.time,sleep=lambda seconds:setattr(self,'time',self.time+seconds))


class LifecycleEditorTests(unittest.TestCase):
    def test_actual_none_ready_source_and_input_receipt_does_not_invent_text_focus_keyboard(self):
        b=Boundary();reader=b.reader(True);before=reader.request(RUN);after=reader.request(RUN,'focus')
        self.assertTrue(after['performed']);self.assertFalse(after['source']['current']['focused']);self.assertFalse(after['source']['osKeyboardVisible']);self.assertEqual('',after['source']['current']['text'])
        self.assertEqual(b.calls[1],b.saved[0]);self.assertEqual(before['source']['current']['fieldToken'],b.calls[1]['fieldToken'])
    def test_readonly_actor_grammar_cannot_send_any_input(self):
        from appium_adapter import readonly_feature_command
        b=Boundary();reader=b.reader();reader.request(RUN);readonly_feature_command(b.calls[0])
        for operation in ('focus','type'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):reader.request(RUN,operation)
        request=b.calls[0]|dict(action='phone-lifecycle-editor-input',operation='focus',fieldToken='c'*32,observationSequence=1)
        command(request)
        with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request)
        self.assertEqual(1,len(b.calls))
    def test_stale_and_expected_result_packets_cannot_supply_current_editor(self):
        for fault in ('source','text','active','keyboard','missing','epoch'):
            b=Boundary()
            if fault=='source':b.body['current']['sourceUrl']='file:///foreign/TabletRunningScripts.qml'
            elif fault=='text':b.body['current']['text']='private unrelated draft'
            elif fault=='active':b.body['contexts'][0]['active']=False
            elif fault=='keyboard':b.body['osKeyboardVisible']='requested'
            elif fault=='missing':b.body['contexts']=[]
            else:b.body['contexts'][0]['createdEpochMs']=b.epoch+1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().request(RUN)
    def test_actual_context_retirement_is_immutable_and_no_dead_identity_can_revive(self):
        for fault in ('drop','retime','revive','alias'):
            b=Boundary();reader=b.reader();b.body['contexts'][0].update(active=False,retiredEpochMs=b.epoch,alive=False,attached=False);b.body['current']={'status':'none'};reader.request(RUN)
            if fault=='drop':b.body['contexts']=[]
            elif fault=='retime':b.body['contexts'][0]['retiredEpochMs']-=1
            elif fault=='revive':b.body['contexts'][0]['alive']=True
            else:b.body['contexts'][0]['fieldToken']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.request(RUN)
    def test_missing_native_reply_or_lost_final_guard_never_repeats_input(self):
        b=Boundary();reader=b.reader(True);reader.request(RUN);reader.read=lambda:''
        with self.assertRaises(NativeUIError):reader.request(RUN,'focus')
        self.assertEqual(2,len(b.calls));self.assertLessEqual(b.time,5.1)
        b=Boundary();reader=b.reader(True);reader.request(RUN);b.ok=False
        with self.assertRaises(NativeUIError):reader.request(RUN,'type')
        self.assertEqual(1,len(b.calls));self.assertFalse(b.saved)
    def test_probe_transfers_only_original_packets_and_missing_hook_is_unavailable(self):
        raw=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();point=raw.index('&& (command.action === "phone-lifecycle-editor-observe"')
        begin=raw.rfind('        if (command &&',0,point);end=raw.index('\n        if (command &&',point)
        code='''const assert=require('node:assert/strict');
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.slice().sort());}
let lastPhoneLifecycleEditorRequest='',saved=[],called=0;
let original={requestId:'1'.repeat(32),performed:true,source:{original:true}};
const Test={phoneLifecycleEditor(){called++;return original;},saveObject(v,f){saved.push([v,f]);}};
function apply(command){'''+raw[begin:end]+'''}
let request={schemaVersion:1,commandId:'1'.repeat(32),action:'phone-lifecycle-editor-observe',runId:'a'.repeat(32)};
apply(request);apply(request);assert.equal(called,1);assert.equal(saved[0][0],original);assert.equal(saved[0][1],'phone-lifecycle-editor.json');
apply({...request,commandId:'2'.repeat(32),text:'expected'});assert.equal(called,1);
delete Test.phoneLifecycleEditor;apply({...request,commandId:'3'.repeat(32)});
assert.deepEqual(saved[1][0],{schemaVersion:1,requestId:'3'.repeat(32),available:false});
'''
        subprocess.run(['node','-e',code],check=True,timeout=10)
    def test_schema_disallows_caller_text_url_generation_keyboard_and_fake_outcomes(self):
        value=dict(schemaVersion=1,commandId='f'*32,action='phone-lifecycle-editor-observe',runId=RUN)
        for field in ('text','sourceUrl','generation','keyboard','expected'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(value|{field:'foreign'})
        for field,other in (('schemaVersion',True),('runId','foreign'),('action','reset')):
            with self.assertRaises(NativeUIError):command(value|{field:other})

if __name__=='__main__':unittest.main()
