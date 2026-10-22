"""Snapshot original-widget transport counterexamples, with synthetic native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_controls import PhoneSnapshotIO,validate,metadata
from appium_adapter import readonly_feature_command


class Boundary:
    def __init__(self):
        self.epoch=10000;self.clock=0.;self.sequence=0;self.commands=0;self.okay=True;self.ignore=False;self.fault=None
        self.raw='';self.calls=[];self.intents=[];self.reference_fault=None
        self.controls=[dict(id='snapshot.capture',token='a'*32,enabled=True,focused=False,inputReady=True)]
        self.instance='b'*32;self.generation='c'*32
    def send(self,value):
        self.calls.append(deepcopy(value));request=value['request']
        if self.ignore:return
        if request['action']=='observe':
            self.sequence+=1;self.epoch+=10
            packet=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance=self.instance,generation=self.generation,
                snapshotControlsVersion=1,sourceSequence=self.sequence,lastCommandSequence=self.commands,elapsedMs=int(self.clock*1000),
                capturedEpochMs=self.epoch,processId=31,ready=True,controls=deepcopy(self.controls))
            if self.fault:self.fault(packet)
        else:
            assert self.intents and self.intents[-1]['request']==request # Must be durable before delivery.
            self.commands+=1
            packet=dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],instance=self.instance,
                generation=self.generation,sequence=self.commands,processId=31,performed=True)
            # An ACK deliberately changes no actual capture, widget or file.
        self.raw=json.dumps(packet)
    def sleep(self,seconds):self.clock+=seconds
    def io(self):return PhoneSnapshotIO(self.send,lambda:self.raw,lambda:self.epoch,lambda:self.okay,31,
        intent=lambda row:self.intents.append(row),monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotControlsTests(unittest.TestCase):
    def test_ack_retains_original_intent_but_cannot_create_capture_or_export_effects(self):
        b=Boundary();io=b.io();original=io.capture();io.activate('snapshot.capture',reference=original)
        after=io.capture();self.assertEqual(original['controls'],after['controls']);self.assertEqual(1,after['lastCommandSequence'])
        self.assertEqual(original,b.intents[0]['original']);self.assertNotIn('files',after);self.assertNotIn('captured',after)
        self.assertEqual(1,len(b.intents))

    def test_capture_plan_persists_exact_original_intent_but_delivers_no_input(self):
        b=Boundary();io=b.io();reference=io.capture();request=io.plan_capture(reference=reference)
        self.assertEqual(1,len(b.intents));self.assertEqual(request,b.intents[0]['request'])
        self.assertEqual(reference,b.intents[0]['original']);self.assertEqual(0,b.commands)
        self.assertTrue(all(row['request']['action']=='observe' for row in b.calls))
        self.assertEqual('snapshot.capture',request['controlId']);self.assertEqual(reference['lastCommandSequence']+1,request['sequence'])

    def test_failed_intent_persistence_cannot_deliver_or_authorize_a_capture_plan(self):
        b=Boundary();io=b.io();io.intent=lambda *_:False
        with self.assertRaises(NativeUIError):io.plan_capture(reference=io.capture())
        self.assertEqual(0,b.commands)
        self.assertTrue(all(row['request']['action']=='observe' for row in b.calls))

    def test_old_foreign_missing_or_changed_widget_cannot_be_activated(self):
        for fault in ('stale','token','missing','generation','instance','disabled','input-ready','consumed'):
            with self.subTest(fault=fault):
                b=Boundary();io=b.io();original=io.capture()
                if fault=='stale':b.epoch+=2000
                elif fault=='token':b.controls[0]['token']='d'*32
                elif fault=='missing':b.controls=[]
                elif fault=='generation':b.generation='d'*32
                elif fault=='instance':b.instance='d'*32
                elif fault=='disabled':b.controls[0]['enabled']=False
                elif fault=='input-ready':b.controls[0]['inputReady']=False
                else:b.commands+=1
                with self.assertRaises(NativeUIError):io.activate('snapshot.capture',reference=original)
                self.assertEqual([],b.intents);self.assertTrue(all(row['request']['action']=='observe' for row in b.calls))

    def test_missing_stale_wrong_pid_or_incomplete_original_cannot_become_ready(self):
        for fault in ('ignore','old','pid','version','ambiguous','ready','expected'):
            with self.subTest(fault=fault):
                b=Boundary()
                if fault=='ignore':b.ignore=True
                else:
                    def mutate(v):
                        if fault=='old':v['capturedEpochMs']=1
                        elif fault=='pid':v['processId']=99
                        elif fault=='version':v['snapshotControlsVersion']=True
                        elif fault=='ambiguous':v['controls'].append(deepcopy(v['controls'][0]))
                        elif fault=='ready':v['ready']=False
                        else:v['expectedFiles']=1
                    b.fault=mutate
                with self.assertRaises(NativeUIError):b.io().capture()

    def test_exact_original_image_path_qualifies_the_dynamic_save_control(self):
        path='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/original.png'
        row=dict(id='snapshot.save.'+hashlib.sha256(path.encode()).hexdigest(),token='d'*32,enabled=True,focused=False,inputReady=True,path=path)
        metadata(row)
        for changed in ('/tmp/foreign.png',path.replace('original','../foreign'),path+'/'+'other.png'):
            with self.subTest(changed=changed),self.assertRaises((ValueError,RuntimeError)):metadata(row|dict(path=changed))

    def test_parameter_or_desired_state_injection_is_rejected_before_intent(self):
        b=Boundary();io=b.io();original=io.capture()
        for id,action,value in (('snapshot.capture','replace','success'),('snapshot.page','activate',None),
            ('snapshot.name','replace','\nexpected'),('snapshot.mode','select-index',True),('snapshot.scrollbar','scroll','sideways')):
            with self.subTest(id=id,action=action),self.assertRaises(NativeUIError):io.input(id,action,reference=original,value=value)
        self.assertEqual([],b.intents)

    def test_readonly_actor_can_observe_widgets_but_cannot_issue_snapshot_inputs(self):
        id='d'*32;request=dict(schemaVersion=1,commandId=id,action='phone-snapshot-ui',request=dict(schemaVersion=1,commandId=id,action='observe'))
        readonly_feature_command(request)
        for action in ('activate','replace','select-index','scroll'):
            with self.subTest(action=action),self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request|dict(request=request['request']|dict(action=action)))

    def test_probe_accepts_only_closed_actual_control_commands(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();start=source.index('    function validPhoneSnapshotRequest(')
        body=source[start:source.index('    var lastPhoneCreateRequest',start)]
        harness='''const assert=require('node:assert/strict');
function objectKeysMatch(value,keys){return JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());}
function phoneFileInteger(value,low,high){return Number.isInteger(value)&&value>=low&&value<=high;}
'''+body+'''
const id='a'.repeat(32),base={schemaVersion:1,commandId:id,action:'activate',instance:id,generation:id,sequence:1,observedElapsedMs:0,controlId:'snapshot.capture',controlToken:id};
assert.equal(validPhoneSnapshotRequest(base),true);
for(const controlId of ['snapshot.modeX','snapshotXmode','create.apply','snapshot.save.expected','../native'])assert.equal(validPhoneSnapshotRequest({...base,controlId}),false);
assert.equal(validPhoneSnapshotRequest({...base,expectedFiles:1}),false);
assert.equal(validPhoneSnapshotRequest({...base,action:'replace',controlId:'snapshot.name',text:'Owned photo'}),true);
assert.equal(validPhoneSnapshotRequest({...base,action:'replace',controlId:'snapshot.capture',text:'expected'}),false);
assert.equal(validPhoneSnapshotRequest({...base,action:'select-index',controlId:'snapshot.mode',index:1}),true);
assert.equal(validPhoneSnapshotRequest({...base,action:'select-index',controlId:'snapshotXmode',index:1}),false);
assert.equal(validPhoneSnapshotRequest({...base,action:'select-index',controlId:'snapshot.mode',index:8}),false);
'''
        subprocess.run(['node','-e',harness],check=True,timeout=10)


if __name__=='__main__':unittest.main()
