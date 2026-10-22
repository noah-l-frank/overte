"""Closed cancel transport, synthetic native producer; no product acceptance."""
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
from appium_adapter import readonly_feature_command
from overte_phone_snapshot_cancel import PhoneSnapshotCancel,command
from test_snapshot_source import Boundary as SnapshotBoundary

RUN='a'*32;JOB='b'*32
INPUT=dict(schemaVersion=1,commandId=JOB,action='activate',controlId='snapshot.capture',controlToken='c'*32,
    instance='d'*32,generation='e'*32,sequence=1,observedElapsedMs=0)


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=10000;self.sequence=0;self.raw='';self.calls=[];self.okay=True;self.ignore=False;self.fault=None
        snapshot=SnapshotBoundary();snapshot.reader().read(RUN);core=json.loads(snapshot.raw)['source']
        core.pop('review');core.pop('androidExport');core['phoneSnapshotObservationVersion']=1
        self.core=core
        self.review=dict(snapshotReviewObservationVersion=1,present=True,review=dict(
            componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml',visible=True,capturing=False,
            processing=False,loggedIn=False,canShare=False,canBlast=False,statusError=False,captureSettingsLoaded=True,
            statusText='',uploadPath='',exportTicket='',mode=1,format='webp',capabilities=['save','share'],
            exportBusy=False,exportError='',images=[]))
        self.before=dict(capturedEpochMs=10000,native=deepcopy(self.core),review=deepcopy(self.review))

    def send(self,request):
        self.calls.append(deepcopy(request))
        if self.ignore:return
        self.epoch+=10;self.sequence+=1
        state=dict(snapshotFastCancelVersion=1,instance='f'*32,job=JOB,runId=RUN,phase='capturing',error='',
            startedEpochMs=10000,completedEpochMs=0,observedEpochMs=self.epoch,timerActive=True,retired=False,request='',
            captureCommand=deepcopy(INPUT),captureInput={key:INPUT[key] for key in ('schemaVersion','commandId','instance','generation','sequence')}
                |dict(processId=31,performed=True),cancelCommand={},cancelInput={},before=deepcopy(self.before),pending={},
            cancelled={},retirement={},current=dict(capturedEpochMs=self.epoch,native=deepcopy(self.core),review=deepcopy(self.review)))
        packet=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance='8'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=state,
            jobs=[{key:state[key] for key in ('job','runId','instance','phase','timerActive','retired')}])
        if self.fault:self.fault(packet)
        self.raw=json.dumps(packet)

    def reader(self):return PhoneSnapshotCancel(self.send,lambda:self.raw,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=lambda seconds:setattr(self,'clock',self.clock+seconds))


class SnapshotCancelTests(unittest.TestCase):
    def test_input_delivery_and_running_local_recipe_are_not_a_capture_cancel_verdict(self):
        b=Boundary();reader=b.reader();first=reader.request(RUN,JOB,'start',INPUT)
        self.assertEqual('capturing',first['source']['phase']);self.assertEqual({},first['source']['cancelled'])
        self.assertTrue(first['source']['captureInput']['performed'])
        first['source']['before']['native']['storageRoot']='foreign'
        self.assertNotEqual(first['source']['before'],reader.request(RUN,JOB,'observe')['source']['before'])

    def test_wrong_pid_foreign_stale_or_missing_originals_and_hidden_work_are_rejected(self):
        for fault in ('pid','run','nonce','old','missing','future','version','retired','hidden','desired'):
            with self.subTest(fault=fault):
                b=Boundary()
                def mutate(value):
                    if fault=='pid':value['processId']=99
                    elif fault=='run':value['runId']='9'*32
                    elif fault=='nonce':value['requestId']='9'*32
                    elif fault=='old':value['capturedEpochMs']=1
                    elif fault=='missing':value['source']['current']={}
                    elif fault=='future':value['source']['current']['capturedEpochMs']=value['capturedEpochMs']+1
                    elif fault=='version':value['source']['snapshotFastCancelVersion']=True
                    elif fault=='retired':value['source']['retired']=True
                    elif fault=='hidden':value['jobs']=[]
                    else:value['source']['expectedCancelled']=True
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().request(RUN,JOB,'start',INPUT)
                self.assertEqual(1,len(b.calls))

    def test_historical_original_replacement_is_rejected_after_fresh_read(self):
        for key in ('before','captureInput','captureCommand'):
            with self.subTest(key=key):
                b=Boundary();reader=b.reader();reader.request(RUN,JOB,'start',INPUT)
                def replace(value):
                    if key=='before':value['source'][key]['native']['history']['instance']='9'*32
                    elif key=='captureInput':value['source'][key]['performed']=False
                    else:value['source'][key]['controlToken']='9'*32
                b.fault=replace
                with self.assertRaises(NativeUIError):reader.request(RUN,JOB,'observe')

    def test_a_different_original_job_cannot_disappear_or_change_identity_between_fresh_reads(self):
        for fault in ('missing','identity','phase','retirement'):
            with self.subTest(fault=fault):
                b=Boundary();reader=b.reader()
                other=dict(job='9'*32,runId=RUN,instance='7'*32,phase='complete',timerActive=False,retired=True)
                b.fault=lambda packet:packet['jobs'].insert(0,deepcopy(other))
                reader.request(RUN,JOB,'start',INPUT)
                if fault=='missing':b.fault=None
                elif fault=='identity':other['instance']='6'*32
                elif fault=='phase':other['phase']='failed'
                else:other['retired']=False
                with self.assertRaises(NativeUIError):reader.request(RUN,JOB,'observe')

    def test_missing_reply_or_lost_guard_never_replays_a_mutating_input(self):
        b=Boundary();b.ignore=True
        with self.assertRaises(NativeUIError):b.reader().request(RUN,JOB,'start',INPUT)
        self.assertEqual(1,len(b.calls));self.assertLessEqual(b.clock,5.1)
        b=Boundary();b.okay=False
        with self.assertRaises(NativeUIError):b.reader().request(RUN,JOB,'start',INPUT)
        self.assertEqual([],b.calls)

    def test_readonly_actor_can_only_observe_the_original_local_recipe(self):
        request=dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-cancel',runId=RUN,jobId=JOB,operation='observe',request={})
        readonly_feature_command(request)
        for change in (dict(operation='retire'),dict(operation='start',request=INPUT),dict(expectedCancelled=True)):
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request|change)

    def test_closed_command_rejects_foreign_job_expected_state_or_non_capture_input(self):
        request=dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-cancel',runId=RUN,jobId=JOB,operation='start',request=INPUT)
        command(request)
        for change in (dict(jobId='9'*32),dict(request=INPUT|dict(controlId='snapshot.cancel-capture')),
                dict(request=INPUT|dict(expectedCancelled=True)),dict(operation='observe'),dict(operation='reset')):
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError)):command(request|change)

    def test_probe_dispatch_executes_only_closed_commands_and_never_replays_start(self):
        raw=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=raw.index('    function applyClientCommand(command) {')
        block=raw[start:raw.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-readback"',start)]+'\n}'
        first=raw.index('    function validPhoneSnapshotRequest(')
        grammar=raw[first:raw.index('    var lastPhoneCreateRequest',first)]
        script='''const assert=require('node:assert/strict');
function objectKeysMatch(value,keys){return value&&JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.slice().sort());}
function phoneFileInteger(value,low,high){return Number.isInteger(value)&&value>=low&&value<=high;}
let lastPhoneSnapshotCancelRequest='',calls=[],saved=[];
const Test={phoneSnapshotCancel(c){calls.push(c);return {requestId:c.commandId};},saveObject(v,f){saved.push(f);}};
'''+grammar+block+'\nconst request='+json.dumps(dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-cancel',runId=RUN,jobId=JOB,operation='start',request=INPUT))+''';
applyClientCommand(request);applyClientCommand(request);assert.equal(calls.length,1);
for(const change of [{expectedCancelled:true},{request:{...request.request,controlId:'snapshot.cancel-capture'}},{jobId:'9'.repeat(32)}])
 applyClientCommand({...request,commandId:'e'.repeat(32),...change});
assert.equal(calls.length,1);assert.deepEqual(saved,['phone-snapshot-cancel.json']);
applyClientCommand({...request,commandId:'f'.repeat(32),operation:'observe',request:{}});assert.equal(calls.length,2);
'''
        subprocess.run(['node','-e',script],check=True,timeout=10)


if __name__=='__main__':unittest.main()
