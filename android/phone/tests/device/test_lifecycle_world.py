"""Original input-attempt/motion sources remain distinct from requested effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_lifecycle_world import PhoneLifecycleWorldSource,validate,command
RUN='a'*32;GESTURE='b'*32


class Boundary:
    def __init__(self):
        self.epoch=100000;self.sequence=0;self.clock=0;self.last=None;self.sent=[];self.intents=[]
        self.source=dict(phoneLifecycleWorldInputVersion=1,instance='c'*32,sequence=0,commandId='',runId=RUN,capturedEpochMs=self.epoch,
            performed=False,pending=False,pendingRun='',pendingGesture='',elapsedMs=0,timerActive=False,gestures=[])
        self.motion=dict(phoneLifecycleMotionVersion=1,instance='d'*32,sequence=1,capturedEpochMs=self.epoch-1,keyboardPluginActive=True,upChannel=2067,
            upPressed=0,feetPosition=[0,0,4],effectiveDrive=[0,0,0],rawDrive=[0,0,0],grounded=True)
    def send(self,value):self.sent.append(deepcopy(value));self.last=deepcopy(value)
    def read(self):
        self.sequence+=1;self.source.update(sequence=self.sequence,commandId=self.last['commandId'],runId=self.last['runId'],capturedEpochMs=self.epoch)
        return json.dumps(dict(schemaVersion=1,requestId=self.last['commandId'],runId=RUN,instance='e'*32,sequence=self.sequence,processId=77,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=self.source,motion=self.motion))
    def reader(self,primary=False):
        return PhoneLifecycleWorldSource(self.send,self.read,lambda:self.epoch,lambda:True,77,
            intent=(lambda value:self.intents.append(deepcopy(value))) if primary else None,
            monotonic=lambda:self.clock,sleep=lambda value:setattr(self,'clock',self.clock+value))
    def press(self):
        row=dict(gestureId=GESTURE,runId=RUN,commandId='f'*32,createdEpochMs=self.epoch,pressEpochMs=self.epoch,
            releaseEpochMs=0,releaseReason='',pressObserved=True,releaseObserved=False)
        self.source.update(pending=True,pendingRun=RUN,pendingGesture=GESTURE,elapsedMs=1,timerActive=True,gestures=[row]);return row


class LifecycleWorldTests(unittest.TestCase):
    def test_real_attempt_inventory_and_current_effective_input_are_distinct_sources(self):
        b=Boundary();b.press();packet=b.reader().request(RUN)
        self.assertTrue(packet['source']['gestures'][0]['pressObserved']);self.assertEqual([0,0,0],packet['motion']['effectiveDrive'])
        self.assertEqual([0,0,4],packet['motion']['feetPosition']);self.assertFalse(packet['source']['performed'])
    def test_hold_input_ack_does_not_create_original_delivery_or_measured_movement(self):
        b=Boundary();reader=b.reader(True);reader.request(RUN);b.source['performed']=True
        packet=reader.request(RUN,'hold');self.assertTrue(packet['source']['performed']);self.assertEqual([],packet['source']['gestures'])
        self.assertEqual([0,0,0],packet['motion']['effectiveDrive']);self.assertEqual(b.sent[-1],b.intents[-1])
    def test_actor_cannot_hold_or_release_original_input(self):
        from appium_adapter import readonly_feature_command
        b=Boundary();reader=b.reader();reader.request(RUN);readonly_feature_command(b.sent[-1])
        for operation,gesture in (('hold',''),('release',GESTURE)):
            with self.assertRaises(NativeUIError):reader.request(RUN,operation,gesture)
            request=dict(schemaVersion=1,commandId='f'*32,action='phone-lifecycle-world-input',operation=operation,runId=RUN,gestureId=gesture)
            with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request)
        self.assertEqual(1,len(b.sent))
    def test_actual_original_press_and_release_history_cannot_be_dropped_or_retimed(self):
        for fault in ('drop','press-time','alias','timer'):
            b=Boundary();b.press();reader=b.reader();reader.request(RUN)
            if fault=='drop':b.source.update(gestures=[],pending=False,pendingRun='',pendingGesture='',timerActive=False,elapsedMs=0)
            elif fault=='press-time':b.source['gestures'][0]['pressEpochMs']-=1
            elif fault=='alias':b.source['gestures'][0]['gestureId']='9'*32;b.source['pendingGesture']='9'*32
            else:b.source['timerActive']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.request(RUN)
    def test_independently_sampled_motion_cannot_be_retimed_without_a_new_original_frame(self):
        for fault in ('position','drive','clock','instance','stale','nan'):
            b=Boundary();reader=b.reader();reader.request(RUN)
            if fault=='position':b.motion['feetPosition']=[1,0,4]
            elif fault=='drive':b.motion['effectiveDrive']=[0,0,1]
            elif fault=='clock':b.motion['capturedEpochMs']+=1
            elif fault=='instance':b.motion['instance']='9'*32
            elif fault=='stale':b.epoch+=1600
            else:b.motion['rawDrive']=[0,0,float('nan')]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.request(RUN)
    def test_restore_preserves_originals_and_new_sampling_cannot_drop_them(self):
        b=Boundary();b.press();reader=b.reader();frame=reader.request(RUN);restored=b.reader();restored.restore([frame]);restored.request(RUN)
        b.source['gestures'][0].update(releaseObserved=True,releaseEpochMs=b.epoch,releaseReason='explicit')
        b.source.update(pending=False,pendingRun='',pendingGesture='',timerActive=False,elapsedMs=0);after=restored.request(RUN)
        self.assertEqual(frame['source']['gestures'][0]['pressEpochMs'],after['source']['gestures'][0]['pressEpochMs'])
    def test_closed_grammar_excludes_caller_motion_counter_position_or_lease_extension(self):
        original=dict(schemaVersion=1,commandId='f'*32,action='phone-lifecycle-world-input',operation='hold',runId=RUN,gestureId='')
        for key in ('durationMs','feetPosition','effectiveDrive','attempts','expected'):
            with self.subTest(key=key),self.assertRaises(NativeUIError):command(original|{key:1})
    def test_probe_forwards_original_world_packet_and_missing_hook_stays_unavailable(self):
        raw=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();point=raw.index('&& command.action === "phone-lifecycle-world-input"')
        begin=raw.rfind('        if (command &&',0,point);end=raw.index('\n        if (command &&',point)
        code='''const assert=require('node:assert/strict');let lastPhoneLifecycleWorldRequest='',saved=[],calls=0;
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.slice().sort());}
let original={requestId:'1'.repeat(32),source:{original:true},motion:{originalFrame:true}};
const Test={phoneLifecycleWorldInput(){calls++;return original;},saveObject(v,f){saved.push([v,f]);}};
function apply(command){'''+raw[begin:end]+'''}
const request={schemaVersion:1,commandId:'1'.repeat(32),action:'phone-lifecycle-world-input',operation:'observe',runId:'a'.repeat(32),gestureId:''};
apply(request);apply(request);assert.equal(calls,1);assert.equal(saved[0][0],original);assert.equal(saved[0][1],'phone-lifecycle-world-input.json');
apply({...request,commandId:'2'.repeat(32),expected:1});assert.equal(calls,1);
delete Test.phoneLifecycleWorldInput;apply({...request,commandId:'3'.repeat(32)});assert.equal(saved[1][0].available,false);
'''
        subprocess.run(['node','-e',code],check=True,timeout=10)

if __name__=='__main__':unittest.main()
