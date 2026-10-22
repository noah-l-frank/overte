"""Passive handoff counterexamples; explicit synthetic native/VM/OS boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError

from self_tests.test_native_account_observation import account
from test_snapshot_measurements import Boundary as Measurements,RUN
from overte_phone_snapshot_handoff import PhoneSnapshotHandoff,PhoneSnapshotHandoffControl,command,control,bound,original,continuity

HANDOFF='b'*32


class Boundary:
    def __init__(self):
        self.native=Measurements();self.epoch=20000;self.time=0.;self.okay=True;self.seq=0;self.commands=[];self.control_seq=0;self.mutate=lambda value:None
        self.owner=dict(snapshotHandoffBindingVersion=1,runId=RUN,handoffId=HANDOFF,instance='a'*32,sourceInstance='f'*32,processId=31,startedEpochMs=20000,deadlineEpochMs=80000)
        self.group=self.native.group()
        self.packet=self.frame()
    def frame(self,retired=False):
        self.seq+=1
        group=deepcopy(self.group)
        for index,key in enumerate(('rootsBefore','script','snapshot','rootsAfter')):
            row=group[key];row['sequence']=self.seq*10+index
            row['commandId' if 'commandId' in row else 'requestId']=uuid.uuid4().hex
        def envelope(body):
            return dict(schemaVersion=1,requestId=uuid.uuid4().hex,runId=RUN,instance='a'*32,sequence=self.seq,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=body)
        readbacks=envelope(dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True)))
        files=envelope(dict(phoneSnapshotCaptureFilesVersion=1,instance='3'*32,complete=True,sequence=self.seq,capturedEpochMs=self.epoch,rows=[],captures=[],plans=[]));files['accepted']=True
        upload=envelope(dict(snapshotUploadObservationVersion=1,instance='4'*32,complete=True,capturedEpochMs=self.epoch,sequence=0,events=[],jobs=[]))
        batch=dict(context=dict(snapshotHandoffContextVersion=1,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,lifecycle=dict(backgrounds=0,activations=1,launches=1),account=account()),group=group,readbacks=readbacks,captureFiles=files,upload=upload)
        source=dict(snapshotHandoffVersion=1,instance='f'*32,runId=RUN,handoffId=HANDOFF,processId=31,sequence=self.seq,startedEpochMs=20000,deadlineEpochMs=80000,capturedEpochMs=self.epoch,complete=True,error='',retired=retired,timerActive=not retired,readActive=False,source=batch)
        job={key:source[key] for key in ('runId','handoffId','instance','retired','timerActive','readActive','complete')}
        return dict(snapshotHandoffSourceVersion=1,instance='a'*32,processId=31,publishedEpochMs=self.epoch,source=source,jobs=[job])
    def raw(self):
        value=deepcopy(self.packet);self.mutate(value);return json.dumps(value)
    def reader(self):return PhoneSnapshotHandoff(self.raw,lambda:self.epoch,lambda:self.okay,self.owner,monotonic=lambda:self.time,sleep=self.sleep)
    def sleep(self,value):self.time+=value
    def send(self,request):
        self.commands.append(request);self.control_seq+=1
        self.packet=self.frame(retired=request['operation']=='retire')
        self.result=dict(snapshotHandoffControlVersion=1,requestId=request['commandId'],runId=RUN,handoffId=HANDOFF,instance='a'*32,processId=31,sequence=self.control_seq,capturedEpochMs=self.epoch,source=self.packet['source'],jobs=self.packet['jobs'])
    def controller(self):return PhoneSnapshotHandoffControl(self.send,lambda:json.dumps(self.result),lambda:self.epoch,lambda:self.okay,31,monotonic=lambda:self.time,sleep=self.sleep)


class SnapshotHandoffTests(unittest.TestCase):
    def test_foreground_control_and_passive_reader_keep_originals_and_independent_sequences(self):
        b=Boundary();owner=b.controller().request(RUN,'start',HANDOFF)
        self.assertEqual(b.owner,bound(owner));reader=b.reader();first=reader.read()
        self.assertEqual(b.packet['source']['source'],first)
        self.assertEqual(19000,first['group']['snapshot']['source']['scriptHistory']['events'][0]['capturedEpochMs'])
        b.packet=b.frame();reader.read();self.assertEqual(1,len(b.commands))
        self.assertEqual({'context','group','readbacks','captureFiles','upload'},set(first))
        first['upload']['source']['complete']=False;self.assertTrue(b.packet['source']['source']['upload']['source']['complete'])
    def test_actual_source_control_retirement_and_no_revival_are_required(self):
        b=Boundary();controller=b.controller();controller.request(RUN,'start',HANDOFF)
        reader=b.reader();reader.read();controller.request(RUN,'retire',HANDOFF);reader.read()
        self.assertTrue(reader.last['source']['retired']);self.assertFalse(reader.last['source']['timerActive'])
        with self.assertRaises(NativeUIError):reader.read()
        b.packet=b.frame();
        with self.assertRaises(NativeUIError):reader.read()
    def test_ignored_input_ack_cannot_create_a_passive_source(self):
        b=Boundary();reader=b.reader();b.raw=lambda:'{}'
        reader.original=lambda:json.dumps(dict(accepted=True))
        with self.assertRaises(NativeUIError):reader.read()
        ignored=PhoneSnapshotHandoffControl(lambda _request:None,lambda:'{}',lambda:20000,lambda:True,31,monotonic=lambda:b.time,sleep=b.sleep)
        with self.assertRaises(NativeUIError):ignored.request(RUN,'start',HANDOFF)
        self.assertLessEqual(b.time,5.1)
    def test_foreign_or_missing_sources_and_failed_partial_retirement_stay_red(self):
        faults=[lambda v:v.update(instance='c'*32),lambda v:v.update(processId=32),
            lambda v:v['source'].update(runId='c'*32),lambda v:v['source'].update(handoffId='c'*32),
            lambda v:v['source'].update(instance='c'*32),lambda v:v['source'].update(complete=False,error='lease-expired'),
            lambda v:v['source'].update(timerActive=False),lambda v:v['source'].update(readActive=True),
            lambda v:v['source']['source'].pop('upload'),lambda v:v['source']['source']['captureFiles']['source'].update(complete=False),
            lambda v:v['source']['source']['group']['snapshot'].update(processId=32),
            lambda v:v['source']['source']['context']['account']['observation'].update(instance='bad'),
            lambda v:v['source']['source']['context'].update(lifecycle=dict(backgrounds=0,activations=1,launches=0)),
            lambda v:v['jobs'].append(dict(v['jobs'][0],handoffId='d'*32,instance='d'*32)),
            lambda v:v['source'].update(retired=True,timerActive=True)]
        for index,fault in enumerate(faults):
            b=Boundary();b.mutate=fault
            with self.subTest(index=index),self.assertRaises(NativeUIError):b.reader().read()
    def test_fresh_publication_cannot_retime_old_native_or_nested_originals(self):
        for target in ('outer','context','roots','readbacks','files','upload','expired'):
            b=Boundary()
            if target=='outer':b.packet['publishedEpochMs']=18000
            elif target=='expired':b.epoch=80000
            elif target=='context':b.packet['source']['source']['context']['requestedEpochMs']=18000
            elif target=='roots':b.packet['source']['source']['group']['rootsBefore']['requestedEpochMs']=18000
            else:
                key={'readbacks':'readbacks','files':'captureFiles','upload':'upload'}[target]
                b.packet['source']['source'][key]['capturedEpochMs']=18000
            with self.subTest(target=target),self.assertRaises(NativeUIError):b.reader().read()
    def test_replayed_frame_and_clock_regression_cannot_advance_observation(self):
        b=Boundary();reader=b.reader();reader.read()
        with self.assertRaises(NativeUIError):reader.read()
        b=Boundary();reader=b.reader();reader.read();b.packet=b.frame();b.time=-1
        with self.assertRaises(NativeUIError):reader.read()
    def test_cross_acquisition_history_rollback_and_changed_originals_are_rejected(self):
        for target in ('lifecycle','account','capture','vm'):
            b=Boundary();before=b.frame();after=b.frame()
            if target=='lifecycle':before['source']['source']['context']['lifecycle']['backgrounds']=1
            elif target=='account':after['source']['source']['context']['account']['observation']['instance']='9'*32
            elif target=='capture':after['source']['source']['captureFiles']['source']['instance']='9'*32
            else:after['source']['source']['group']['snapshot']['source']['scriptHistory']['events'][0]['capturedEpochMs']=18999
            with self.subTest(target=target),self.assertRaises(NativeUIError):continuity(before,after)
    def test_closed_command_no_readonly_start_and_duplicate_json_keys(self):
        b=Boundary();controller=b.controller();controller.request(RUN,'start',HANDOFF);request=b.commands[0]
        from appium_adapter import readonly_feature_command
        from artifact_identity import IdentityError
        readonly_feature_command(dict(request,operation='observe'))
        for operation in ('start','retire'):
            with self.subTest(operation=operation),self.assertRaises((IdentityError,NativeUIError)):readonly_feature_command(dict(request,operation=operation))
        for field in ('expected','duration','uri','source'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(dict(request,**{field:'green'}))
        reader=b.reader();reader.original=lambda:'{"snapshotHandoffSourceVersion":1,"snapshotHandoffSourceVersion":1}'
        with self.assertRaises(NativeUIError):reader.read()
    def test_actual_probe_closed_route_forwards_original_once_and_never_synthesizes_source(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=source.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-handoff"')
        block=source[start:source.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-settings"',start)]
        script='''const assert=require('node:assert/strict');
function objectKeysMatch(value,keys){return JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.slice().sort());}
let lastPhoneSnapshotHandoffRequest='',calls=[],saved=[];
let Test={phoneSnapshotHandoff(c){calls.push(c);return {requestId:c.commandId,originalNative:{sequence:5}};},saveObject(v,f){saved.push([v,f]);}};
function apply(command){'''+block+'''}
let command={schemaVersion:1,commandId:'a'.repeat(32),action:'phone-snapshot-handoff',runId:'b'.repeat(32),handoffId:'c'.repeat(32),operation:'start'};
apply(command);apply(command);assert.equal(calls.length,1);assert.deepEqual(saved[0],[{requestId:command.commandId,originalNative:{sequence:5}},'phone-snapshot-handoff-result.json']);
for(let key of ['expected','uri','source','duration'])apply({...command,commandId:'d'.repeat(32),[key]:true});
assert.equal(calls.length,1);delete Test.phoneSnapshotHandoff;apply({...command,commandId:'e'.repeat(32)});
assert.deepEqual(saved[1][0],{available:false,requestId:'e'.repeat(32)});
'''
        subprocess.run(['node','-e',script],check=True,timeout=10)

    def test_guard_loss_after_acquisition_and_slow_transport_cannot_publish(self):
        for fault in ('guard','slow'):
            b=Boundary();reader=b.reader()
            def read():
                result=b.raw()
                if fault=='guard':b.okay=False
                else:b.time+=5
                return result
            reader.original=read
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read()


if __name__=='__main__':unittest.main()
