"""Real host weak owners and strict native capture codecs; no compiler/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
import uuid
import weakref

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_captures as source
from ios.self_tests import test_ios_create_transport as transport_tests
from ios.self_tests.test_ios_snapshot_work import packet as work_packet
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Capture:
    def __init__(self):self.state=0;self.announced=False


class Resource:
    def __init__(self,capture):self.capture=capture


class Native:
    def __init__(self):
        self.now=1700000000000;self.sequence=0;self.captures={};self.resources={};self.events=[]
        self.activity=dict(requests=0,secondaryCapturePresent=False,secondaryTimerActive=False,secondaryTaking=False,secondaryFramePending=False,
            animated=dict(capturePresent=False,encodingPresent=False,timerPresent=False,timerRunning=False,framePending=False,frames=0,delays=0))
    def tick(self):self.now+=1;return self.now
    def event(self,id_,kind,**detail):
        self.events.append(dict(sequence=len(self.events)+1,capture=id_,kind=kind,capturedEpochMs=self.tick(),detail=detail))
    def begin(self,request='snap_1700000000000_1'):
        cap=Capture();id_=uuid.uuid4().hex
        self.captures[id_]=(weakref.ref(cap),dict(instance=id_,requestId=request,bornEpochMs=self.tick()))
        self.event(id_,'begin');self.event(id_,'accepted');return cap,id_
    def resource(self,cap,id_):
        resource=Resource(cap);rid=uuid.uuid4().hex
        record=dict(instance=rid,capture=id_,kind='animated-timer',bornEpochMs=self.tick(),destroyedEpochMs=None)
        def destroyed(_weak):record['destroyedEpochMs']=self.tick()
        self.resources[rid]=(weakref.ref(resource,destroyed),record);return resource
    def finish(self,cap,id_):
        cap.state=2;cap.announced=True;self.event(id_,'status',phase='complete',hasPath=True,hasError=False)
    def cancel(self,cap,id_):
        self.event(id_,'cancel-requested');cap.state=1;self.event(id_,'cancelled')
        cap.announced=True;self.event(id_,'cancel-delivered')
    def clock(self):return dict(epochMs=self.tick(),monotonicMs=self.now-1700000000000)
    def read(self):
        before=self.clock();captures=[];resources=[];self.sequence+=1
        for weak,original in self.captures.values():
            held=weak();captures.append(dict(original,alive=held is not None,state=None if held is None else held.state,announced=None if held is None else held.announced))
        for weak,original in self.resources.values():resources.append(dict(original,alive=weak() is not None))
        return dict(iosSnapshotCapturesVersion=1,requestId='ios-'+uuid.uuid4().hex,runId=RUN,instance='b'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-snapshot-captures',clockBefore=before,clockAfter=self.clock(),
            source=dict(complete=True,captures=sorted(captures,key=lambda row:row['instance']),resources=sorted(resources,key=lambda row:row['instance']),
                        events=deepcopy(self.events),activity=deepcopy(self.activity)))


def query(value):return dict(schemaVersion=1,action=source.ACTION,commandId=value['requestId'],runId=RUN)


class Boundary(transport_tests.StateBoundary):
    def original(self):
        self.clock+=.001;before=self.clocks();self.sequence+=1;self.clock+=.001
        native=Native();value=native.read();value.update(requestId=self.requests[-1]['commandId'],sequence=self.sequence,clockBefore=before,clockAfter=self.clocks())
        self.last=deepcopy(value);return json.dumps(value)


class SnapshotCaptureTests(unittest.TestCase):
    def cancellation(self):
        n=Native();before=n.read();pending=work_packet();row=pending['source']['workers'][0];initial=deepcopy(row['state'])
        state=deepcopy(initial);state.update(captureId='snap_1700000000010_1',captureCounter=1,revision=1,timerHandles=[1,2],overlaysHidden=True)
        def event(seq,kind,name,call,state,offset):return dict(sequence=seq,callerSequence=seq,capturedEpochMs=1700000000000+offset,
            invokedEpochMs=1700000000000+offset,event=kind,closure=name,call=call,state=deepcopy(state))
        row['events'] += [event(2,'entry','takeSnapshot',1,initial,10),event(3,'returned','takeSnapshot',1,state,11),
                          event(4,'finally','takeSnapshot',1,state,12)]
        row['state']=state;row['latest']=event(5,'snapshot','',0,state,13);pending['source']['eventSequence']=5
        pending['clockBefore'].update(epochMs=1700000000014,monotonicMs=14);pending['clockAfter'].update(epochMs=1700000000015,monotonicMs=15)
        timers=[]
        for handle,interval in ((1,350),(2,60000)):
            timers.append(dict(timerId=str(handle)*32,handle=handle,callerChain=['qrc:/scripts/system/snapshot.js'],createdEpochMs=1700000000010,
                singleShot=True,intervalMs=interval,activeAtBirth=True,remainingAtBirthMs=interval,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,
                destroyedEpochMs=None,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None))
        pending['source']['timerSources']['workers'][0]['timerWork']['timers']=timers
        cancelled=deepcopy(pending);cancelled.update(sequence=2,requestId='ios-'+'f'*32)
        cancelled['clockBefore'].update(epochMs=1700000000030,monotonicMs=30);cancelled['clockAfter'].update(epochMs=1700000000031,monotonicMs=31)
        end=deepcopy(state);end.update(captureId='',timerHandles=[],overlaysHidden=False)
        row=cancelled['source']['workers'][0];row['events'] += [event(6,'entry','cancelNativeCapture',2,state,22),
            event(7,'returned','cancelNativeCapture',2,end,23),event(8,'finally','cancelNativeCapture',2,end,24)]
        row['state']=end;row['latest']=deepcopy(row['events'][-1]);cancelled['source']['eventSequence']=8
        for timer in cancelled['source']['timerSources']['workers'][0]['timerWork']['timers']:timer['destroyedEpochMs']=1700000000023
        n.now=1700000000040;return n,before,pending,cancelled,n.read()

    def test_joined_real_pending_delays_and_cancel_return_require_independent_native_begin_absence(self):
        n,before,pending,cancelled,after=self.cancellation()
        proof=source.pending_cancellation(before,pending,cancelled,after,'qrc:/scripts/')
        self.assertEqual(pending['source']['workers'][0]['state']['captureId'],proof['captureId'])
        self.assertTrue(proof['normalInputOwnerRequired']);self.assertTrue(proof['fileAbsenceRequired'])
        cap,id_=n.begin(proof['captureId']);n.finish(cap,id_);del cap
        with self.assertRaises(NativeUIError):source.pending_cancellation(before,pending,cancelled,n.read(),'qrc:/scripts/')

    def test_idle_ack_late_timer_and_foreign_process_cannot_become_early_cancellation(self):
        for fault in ('idle','timer','pid','throws'):
            n,before,pending,cancelled,after=self.cancellation()
            if fault=='idle':
                for event in cancelled['source']['workers'][0]['events']:
                    if event['event']=='entry' and event['closure']=='cancelNativeCapture':event['state']['captureId']=''
            elif fault=='timer':
                timer=pending['source']['timerSources']['workers'][0]['timerWork']['timers'][0]
                timer.update(fired=1,pendingDispatch=1,lastFiredEpochMs=1700000000012)
            elif fault=='pid':pending['processId']=cancelled['processId']=43
            else:
                row=cancelled['source']['workers'][0];row['events']=[event for event in row['events'] if event['sequence']!=7]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.pending_cancellation(before,pending,cancelled,after,'qrc:/scripts/')

    def test_actual_weak_worker_and_timer_lifetime_outlive_terminal_native_success(self):
        n=Native();source.drained(n.read());cap,id_=n.begin();timer=n.resource(cap,id_);n.finish(cap,id_)
        original=n.read();source.original(original)
        with self.assertRaises(NativeUIError):source.drained(original)
        del cap
        with self.assertRaises(NativeUIError):source.drained(n.read())
        del timer;gone=n.read();self.assertFalse(gone['source']['captures'][0]['alive'])
        source.validate(gone,query(gone),42,previous=original);source.drained(gone)

    def test_cancelled_request_cannot_retire_while_queued_callback_retains_it(self):
        n=Native();cap,id_=n.begin();n.cancel(cap,id_)
        callback=lambda retained=cap:retained.state
        del cap;self.assertEqual(1,callback())
        with self.assertRaises(NativeUIError):source.drained(n.read())
        del callback;source.drained(n.read())

    def test_native_active_flags_and_timer_clear_before_destruction_are_not_quiet(self):
        for fault in ('request','secondary','animation','encode','frame','timer-event-gap'):
            n=Native();value=n.read()
            if fault=='request':value['source']['activity']['requests']=1
            elif fault=='secondary':value['source']['activity']['secondaryTimerActive']=True
            elif fault=='animation':value['source']['activity']['animated']['capturePresent']=True
            elif fault=='encode':value['source']['activity']['animated']['encodingPresent']=True
            elif fault=='frame':value['source']['activity']['animated']['frames']=1
            else:
                cap,id_=n.begin();timer=n.resource(cap,id_);n.cancel(cap,id_);del cap,timer;value=n.read()
                value['source']['resources'][0]['destroyedEpochMs']=None
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.drained(value)

    def test_retained_original_history_birth_clock_and_pid_cannot_be_replaced(self):
        n=Native();cap,id_=n.begin();first=n.read();n.finish(cap,id_);second=n.read()
        source.validate(second,query(second),42,previous=first)
        for fault in ('pid','birth','nonce','clock','events','capture','identity','state'):
            value=deepcopy(second)
            if fault=='pid':value['processId']=43
            elif fault=='birth':value['instance']='f'*32
            elif fault=='nonce':value['requestId']=first['requestId']
            elif fault=='clock':value['clockBefore']['monotonicMs']=0
            elif fault=='events':value['source']['events'][0]['capturedEpochMs']+=1
            elif fault=='capture':value['source']['captures']=[]
            elif fault=='identity':value['source']['captures'][0]['requestId']='snap_1700000000000_2'
            else:value['source']['captures'][0]['state']=0
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query(value),42,previous=first)

    def test_expired_capture_and_qobject_destruction_cannot_revive(self):
        n=Native();cap,id_=n.begin();timer=n.resource(cap,id_);n.cancel(cap,id_);del cap,timer
        first=n.read();second=n.read();source.validate(second,query(second),42,previous=first)
        for category in ('captures','resources'):
            value=deepcopy(second);value['source'][category][0]['alive']=True
            if category=='captures':value['source'][category][0].update(state=1,announced=True)
            else:value['source'][category][0]['destroyedEpochMs']=None
            with self.subTest(category=category),self.assertRaises(NativeUIError):source.validate(value,query(value),42,previous=first)

    def test_fixture_and_actual_afc_factory_keep_original_query_and_native_clocks(self):
        value=Native().read();q=query(value);f=FixtureState();self.assertEqual(q,f.set_client_command(q))
        for extra in ({'expected':{}},{'requestId':'snap_1_1'},{'schemaVersion':True}):
            with self.assertRaises((ValueError,RuntimeError)):f.set_client_command(q|extra)
        seam=Boundary();harness=transport_tests.CreateTransportTests();harness.setUp()
        try:
            native,observer=harness.transport(seam,source.FILE);value=observer.snapshot_captures().read(RUN)
            self.assertEqual(seam.last,value)
            self.assertEqual(['feature-native-observe',source.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
        finally:harness.doCleanups()

    def test_actual_probe_reads_each_original_once_and_cannot_accept_a_requested_outcome(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const saved=[];let calls=0;const original={iosSnapshotCapturesVersion:1,requestId:'ios-'+'c'.repeat(32),actual:'untouched'};
const Test={featureIOSSnapshotCaptures:()=>{calls++;return original},saveObject:(v,name)=>saved.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:original.requestId,action:'feature-ios-snapshot-captures',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);if(calls!==1||saved[0].v!==original||saved[0].name!==c.action+'.json')throw Error('replaced or resent');
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32),expected:'cancelled'});if(calls!==1)throw Error('accepted outcome');
delete Test.featureIOSSnapshotCaptures;applyClientCommand({...c,commandId:'ios-'+'e'.repeat(32)});
if(saved.at(-1).v.status!=='unavailable')throw Error('missing source became success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_native_hooks_are_passive_weak_and_observe_actual_resource_destruction(self):
        root=Path(__file__).resolve().parents[4];header=(root/'tests/device/native/IOSSnapshotCaptureObservation.h').read_text()
        cpp=(root/'interface/src/ui/Snapshot.cpp').read_text();animated=(root/'interface/src/ui/SnapshotAnimated.cpp').read_text()
        self.assertIn('std::weak_ptr<SnapshotCaptureRequest>',header);self.assertIn('QPointer<QObject>',header)
        self.assertIn('&QObject::destroyed',header);self.assertIn('held->state.load()',header)
        self.assertIn('#define snapshotObserved(...) ((void)0)',cpp)
        self.assertIn('resource(capture,watcher,"secondary-watcher")',cpp)
        self.assertIn('resource(snapshotCapture,snapshotAnimatedTimer,"animated-timer")',animated)
        self.assertIn('resource(request,watcher,"animated-watcher")',animated)
        self.assertNotIn('QTimer::singleShot',header);self.assertNotIn('deleteLater()',header)


if __name__=='__main__':unittest.main()
