"""Original-axis/layer boundaries; no client, controller or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import lifecycle_gesture as gesture
from adapters.normal_ui import NativeUIError
RUN='a'*32
ROOT=Path(__file__).resolve().parents[3]


def sample(y=0,active=True):
    return dict(actionActive=active,raw=[0,y],mapped=[0,-y],mappedValid=True,changedSinceLastSync=True,lastChangeTimeNs='12345')


def native_status():
    return dict(schemaVersion=1,buildMarker='OVERTE_E2E_OPENXR_INPUT_V1',consumer='XR_APILAYER_OVERTE_e2e_input',
        profileId='overte-pico4-controller-v1',bindingProfileSha256='da7ef170275af8c058da53210c8a88aa6920e6315b5cdc0daaedf072dc1b3284',
        enabled=True,acceptedSequence=1,acceptedNonce='f'*64,activeCommandId='input-move-1',state='active',detail='vector-consumed',
        updatedEpochMs=20000,viewAppliedSequence=0,viewAppliedYawDegrees=0,viewAppliedPitchDegrees=0,vectorAppliedSequence=1,
        leftThumbstickAppliedX=0,leftThumbstickAppliedY=.8,booleanAppliedSequence=0,leftSecondaryApplied=False,rightSecondaryApplied=False)


def proof(status=None):
    raw=json.dumps(status or native_status())+'\n'
    return dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())


def event(kind,index=1,active='',y=0,stream=None):
    return dict(id=format(index,'032x'),eventSequence=index,kind=kind,gestureId=active,cause='axis-transition',frameSequence=index,
        occurredEpochMs=20000,elapsedMs=index-1,sample=sample(y),stream=stream or {})


class Boundary:
    def __init__(self):
        self.clock,self.sequence,self.value,self.alive,self.ignore=0.,0,None,True,False
        self.commands,self.mutate=[],None
        self.source=dict(backend='pico-openxr-left-thumbstick-publication',createdEpochMs=20000,frameSequence=1,frameEpochMs=20000,
            frameElapsedMs=0,known=True,current=sample(),activeGesture='',events=[event('neutral')])
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.value=dict(gestureObservationVersion=1,commandId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=123,capturedEpochMs=20000+round(self.clock*1000),source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value else ''
    def sleep(self,value):self.clock+=value
    def reader(self):return gesture.PicoLifecycleGesture(self.send,self.read,lambda:20000+round(self.clock*1000),lambda:self.alive,123,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def start(self):
        started=event('started',2,'c'*32,.8,proof());self.source.update(frameSequence=2,frameElapsedMs=1,current=sample(.8),
            activeGesture='c'*32);self.source['events'].append(started);return started


class LifecycleGestureTests(unittest.TestCase):
    def test_original_axis_history_and_intercepted_layer_bytes_join_exact_envelope(self):
        boundary=Boundary();reader=boundary.reader();baseline=reader.capture(RUN);started=boundary.start();current=reader.capture(RUN)
        envelope=dict(sessionNonce='f'*64,sequence=1,commands=[dict(id='input-move-1')])
        self.assertEqual(native_status(),gesture.consumed(current['source']['events'][-1],envelope))
        self.assertEqual(started['stream']['raw'],current['source']['events'][-1]['stream']['raw'])
        self.assertEqual(baseline['source']['events'],current['source']['events'][:1])
        self.assertEqual(boundary.read(),reader.last_raw)
        self.assertEqual(hashlib.sha256(reader.last_raw.encode()).hexdigest(),reader.last_sha256)
    def test_accepted_sequence_and_ack_without_actual_vector_consumption_never_count(self):
        boundary=Boundary();started=boundary.start();envelope=dict(sessionNonce='f'*64,sequence=1,commands=[dict(id='input-move-1')])
        faults=(dict(vectorAppliedSequence=0),dict(detail='accepted'),dict(enabled=False),dict(state='neutral'),
            dict(activeCommandId='foreign'),dict(acceptedNonce='e'*64),dict(acceptedSequence=2),
            dict(leftThumbstickAppliedY=-.8),dict(updatedEpochMs=18000))
        for fault in faults:
            value=deepcopy(started);status=native_status();status.update(fault);value['stream']=proof(status)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):gesture.consumed(value,envelope)
        for kind in ('changed','neutral','resumed'):
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):gesture.consumed(dict(started,kind=kind),envelope)
    def test_focus_unavailable_keeps_original_active_and_only_published_neutral_closes(self):
        boundary=Boundary();reader=boundary.reader();reader.capture(RUN);boundary.start();reader.capture(RUN)
        unknown=event('unavailable',3,'c'*32,.8);unknown['cause']='focus-out'
        boundary.source.update(frameSequence=3,frameElapsedMs=2,known=False);boundary.source['events'].append(unknown)
        self.assertEqual('c'*32,reader.capture(RUN)['source']['activeGesture'])
        boundary.source.update(frameSequence=4,frameElapsedMs=3,current=sample(),known=True,activeGesture='')
        boundary.source['events'].append(event('neutral',4,'c'*32))
        self.assertEqual('',reader.capture(RUN)['source']['activeGesture'])
    def test_unknown_is_not_neutral_and_inactive_or_inverted_mapping_is_not_known(self):
        faults=(lambda s:s['current'].update(actionActive=False),lambda s:s['current'].update(mapped=[0,.8]),
            lambda s:s.update(activeGesture=''),lambda s:s['events'][-1].update(kind='neutral'),
            lambda s:s.update(worldAttempts=1),lambda s:s.update(known=False))
        for fault in faults:
            boundary=Boundary();boundary.start();fault(boundary.source)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):boundary.reader().capture(RUN)
    def test_changed_or_removed_original_history_and_restarted_source_fail_closed(self):
        for fault in ('rewrite','truncate','instance','retime'):
            boundary=Boundary();reader=boundary.reader();reader.capture(RUN);boundary.start();original=reader.capture(RUN)
            if fault=='rewrite':boundary.source['events'][0]['cause']='action-published'
            if fault=='truncate':boundary.source['events']=boundary.source['events'][1:]
            if fault=='instance':boundary.mutate=lambda value:value.update(instance='d'*32)
            if fault=='retime':boundary.source['frameElapsedMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertEqual(original,reader.previous)
    def test_restore_keeps_native_instance_process_run_cursors_and_private_originals(self):
        boundary=Boundary();reader=boundary.reader();reader.capture(RUN);boundary.start();original=reader.capture(RUN)
        restored=boundary.reader();restored.restore(original)
        self.assertEqual(original['source']['events'],restored.capture(RUN)['source']['events'])
        boundary.mutate=lambda value:value.update(processId=124)
        with self.assertRaises(NativeUIError):restored.capture(RUN)
    def test_raw_status_digest_profile_duplicate_keys_and_boolean_schema_are_rejected(self):
        for fault in ('digest','profile','duplicate','schema'):
            boundary=Boundary();boundary.start();value=boundary.source['events'][-1]['stream']
            status=native_status()
            if fault=='digest':value['sha256']='0'*64
            if fault=='profile':status['profileId']='other';value.update(proof(status))
            if fault=='schema':status['schemaVersion']=True;value.update(proof(status))
            if fault=='duplicate':
                value['raw']=value['raw'].replace('"schemaVersion": 1','"schemaVersion": 1, "schemaVersion": 1')
                value['sha256']=hashlib.sha256(value['raw'].encode()).hexdigest()
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):boundary.reader().capture(RUN)
    def test_final_monotone_age_current_frame_age_and_no_reissue_are_enforced(self):
        boundary=Boundary();boundary.clock=2
        with self.assertRaises(NativeUIError):boundary.reader().capture(RUN)
        for late in ('accept','guard'):
            boundary=Boundary();reader=boundary.reader();reader.clock_ms=lambda:20000
            original=gesture.accept
            def slow(*args):
                result=original(*args);boundary.clock+=2;return result
            if late=='accept':
                with mock.patch.object(gesture,'accept',side_effect=slow),self.assertRaises(NativeUIError):reader.capture(RUN)
            else:
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==4:boundary.clock+=2
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertIsNone(reader.previous)
        boundary=Boundary();boundary.ignore=True
        with self.assertRaises(NativeUIError):boundary.reader().capture(RUN)
        self.assertEqual(1,len(boundary.commands))
        boundary=Boundary();reader=boundary.reader();reader.original=lambda:' '*262145
        with mock.patch.object(gesture,'decode') as decoder,self.assertRaises(NativeUIError):reader.capture(RUN)
        decoder.assert_not_called()


class LifecycleGestureProbeTests(unittest.TestCase):
    def test_original_probe_preserves_native_payload_and_current_command_deduplication(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();action=source.index('command.action === "feature-lifecycle-gesture-observe"')
        start=source.rfind('        if (command &&',0,action);end=source.index('        if (command &&',action)
        harness=r'''
const assert=require('node:assert/strict');let lastLifecycleGestureRequest='',saved=[],calls=[],result;
const objectKeysMatch=(value,keys)=>Object.keys(value).sort().join('|')===keys.sort().join('|');
const Test={featureLifecycleGestureObservation:value=>{calls.push(value);return result;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-lifecycle-gesture-observe'};
result={...command,original:true};apply(command);assert.strictEqual(saved[0].value,result);apply(command);assert.equal(calls.length,1);
apply({...command,commandId:'c'.repeat(32),expected:1});assert.equal(calls.length,1);
result=null;apply({...command,commandId:'c'.repeat(32)});assert.equal(saved[1].value.available,false);
assert.equal(saved[1].file,'feature-lifecycle-gesture.json');
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)


if __name__=='__main__':unittest.main()
