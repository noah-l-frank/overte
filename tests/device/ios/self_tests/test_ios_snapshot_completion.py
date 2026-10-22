"""Actual input/file/artifact owners joined over explicitly modeled native work."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,snapshot_capture_controls as controls,snapshot_completion as source,snapshot_chunks
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.self_tests import test_ios_snapshot_original_file as files_fixture
from ios.self_tests import test_ios_snapshot_work as work_fixture
from ios.self_tests import test_ios_snapshot_captures as capture_fixture
from ios.self_tests.test_ios_snapshot_inputs import Native as InputNative

BASE=1700000000000
RUN=work_fixture.RUN


class SnapshotCompletionTests(unittest.TestCase):
    def setUp(self):
        self.f=files_fixture.SnapshotOriginalFileTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ctx=self.f.f;self.now=BASE-50;self.bytes=self.f.h.path.read_bytes();self.f.h.path.unlink()
        self.request='snap_'+str(BASE+20)+'_1'
        self.f.h.path=self.f.h.path.with_name(self.f.h.prefix+'-'+self.request+'.png')
        self.f.h.epoch_ms=lambda:self.now
        self.f.jobs.tick=lambda:self.now;self.f.jobs.clock=lambda:dict(epochMs=self.now,monotonicMs=self.now-BASE+1000)
        def producer(value):
            def clocks(node):
                if type(node) is dict:
                    for key,item in node.items():
                        if key.endswith('EpochMs'):node[key]=self.now
                        else:clocks(item)
                elif type(node) is list:
                    for item in node:clocks(item)
            clocks(value);value['processId']=42
        self.ctx.native.mutate=producer
        self.ctx.new_clock=self.clock;self.ctx.clock=self.clock()
        actual_time=patch('time.time',lambda:self.now/1000);actual_time.start();self.addCleanup(actual_time.stop)
        self.input_native=InputNative();self.input_native.name=self.f.h.prefix;observed=self.input_native.observed
        def observation():
            value=observed();value['controls'][0].update(snapshotMode=0,snapshotFormat='png');return value
        self.input_native.observed=observation
        actual_input=patch.object(normal_input,'urlopen',self.input_native.post);actual_input.start();self.addCleanup(actual_input.stop)

    def clock(self):
        native=self.ctx.native
        reader=NativeFeatureObservation(native.send,native.original,lambda:self.now,native.guard,42,ios=True,
            monotonic=lambda:native.clock,sleep=native.sleep)
        return NativeClockAcquisition(reader,epoch_ms=lambda:self.now,monotonic=lambda:native.clock)

    def manifest(self,index):
        owner=SnapshotManifest(PrivateFeatureState(self.ctx.root/('ios-snapshot-primary-manifest-'+format(index,'04d')+'.json')),
            self.ctx.lock,self.ctx.binding,RUN,'primary',index,self.ctx.feature,self.clock(),lambda:True)
        owner.reserve('still-png');owner.send(self.now);owner.recover();return owner

    def work(self):
        before=work_fixture.packet();after=deepcopy(before);after.update(requestId='ios-'+'e'*32,sequence=2)
        after['clockBefore'].update(epochMs=BASE+1120,monotonicMs=1121)
        after['clockAfter'].update(epochMs=BASE+1121,monotonicMs=1122)
        row=after['source']['workers'][0];idle=deepcopy(row['state']);pending=deepcopy(idle)
        pending.update(revision=1,captureCounter=1,captureId=self.request,timerHandles=[1,2],overlaysHidden=True)
        finished=deepcopy(pending);finished.update(captureId='',timerHandles=[],overlaysHidden=False)
        def event(sequence,kind,closure,call,state,offset):
            return dict(sequence=sequence,callerSequence=sequence,capturedEpochMs=BASE+offset,invokedEpochMs=BASE+offset,
                event=kind,closure=closure,call=call,state=deepcopy(state))
        row['events'] += [event(2,'entry','takeSnapshot',1,idle,20),event(3,'returned','takeSnapshot',1,pending,21),
            event(4,'finally','takeSnapshot',1,pending,22),event(5,'entry','onNativeCaptureStatus',2,pending,1101),
            event(6,'returned','onNativeCaptureStatus',2,finished,1102),event(7,'finally','onNativeCaptureStatus',2,finished,1103)]
        row['latest']=deepcopy(row['events'][-1]);row['state']=finished;after['source']['eventSequence']=7
        timers=[]
        for handle,interval,created,fired in ((1,350,20,370),(2,60000,20,None),(3,500,370,870)):
            timer=dict(timerId=str(handle)*32,handle=handle,callerChain=['qrc:/scripts/system/snapshot.js'],createdEpochMs=BASE+created,
                singleShot=True,intervalMs=interval,activeAtBirth=True,remainingAtBirthMs=interval,fired=int(fired is not None),
                entered=int(fired is not None),left=int(fired is not None),depth=0,pendingDispatch=0,
                destroyedEpochMs=BASE+(1102 if fired is None else fired),lastFiredEpochMs=None if fired is None else BASE+fired,
                lastCallbackEpochMs=None if fired is None else BASE+fired+1,lastDispatchEpochMs=None if fired is None else BASE+fired+2)
            timers.append(timer)
        after['source']['timerSources']['workers'][0]['timerWork']['timers']=timers
        return before,after

    def prepared(self):
        first=self.manifest(1);native=capture_fixture.Native();native.tick=lambda:self.now
        native.clock=lambda:dict(epochMs=self.now,monotonicMs=self.now-BASE+1000)
        self.now=BASE-40;before_native=native.read();before_work,after_work=self.work()
        self.now=BASE+10
        inputs=SnapshotInputOwner(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-inputs.json'),self.ctx.lock,
            self.ctx.binding,RUN,'primary',self.input_native.input(),lambda:True)
        inputs.reserve('snapshot.capture',controls.project(inputs.native.capture()));inputs.send()
        self.now=BASE+1000;capture,identifier=native.begin(self.request)
        self.now=BASE+1100;self.f.h.path.write_bytes(self.bytes);self.f.h.path.chmod(0o600);native.finish(capture,identifier);del capture
        self.now=BASE+1122;after_native=native.read()
        self.now=BASE+1130;start=self.manifest(2);chunks=[]
        for index,offset in enumerate(range(0,len(self.bytes),snapshot_chunks.CHUNK_BYTES),1):
            owner=self.f.h.owner(index);owner.reserve_original(start,self.f.h.path.name,offset);owner.send(self.now);owner.recover();chunks.append(owner)
        finish=self.manifest(3);self.f.callbacks.clear();work=self.f.jobs.read()
        artifact=SnapshotArtifact(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-artifact-0001.json'),
            self.ctx.lock,self.ctx.binding,RUN,'primary',1,lambda:True);artifact.capture(start,finish,chunks,work)
        return inputs,1,before_work,after_work,before_native,after_native,first,artifact,'qrc:/scripts/'

    def test_normal_input_native_status_and_actual_original_artifact_join_without_export_or_image_claim(self):
        with self.ctx.lock.held():
            args=self.prepared();result=source.completed(*args)
            self.assertEqual(self.request,result['captureId']);self.assertEqual(len(self.bytes),result['file']['size'])
            self.assertTrue(result['decodedImageRequired']);self.assertTrue(result['destinationOutcomeRequired'])
            self.assertTrue(result['independentWitnessRequired']);self.assertTrue(result['quietWindowRequired'])
            self.assertEqual(1,len([query for query in self.input_native.requests if query['operation']=='edit']))
            self.assertEqual(6,len(self.ctx.files.commands))

    def test_ignored_wrong_request_cancelled_or_failed_native_effect_cannot_pass_from_input_ACK(self):
        with self.ctx.lock.held():
            args=self.prepared()
            for fault in ('missing','request','error','path','held','foreign','work-callback','timeout'):
                values=list(args);values[3]=deepcopy(args[3]);values[5]=deepcopy(args[5]);native=values[5]['source']
                if fault=='missing':native['captures']=[];native['events']=[]
                elif fault=='request':native['captures'][0]['requestId']='snap_1700000000020_2'
                elif fault=='error':native['events'][-1]['detail'].update(phase='error',hasError=True)
                elif fault=='path':native['events'][-1]['detail']['hasPath']=False
                elif fault=='held':native['captures'][0].update(alive=True,state=2,announced=True)
                elif fault=='foreign':values[5]['processId']=43
                elif fault=='work-callback':
                    row=values[3]['source']['workers'][0];row['events']=[entry for entry in row['events'] if entry['sequence']!=6]
                else:
                    timer=values[3]['source']['timerSources']['workers'][0]['timerWork']['timers'][1]
                    timer.update(fired=1,entered=1,left=1,lastFiredEpochMs=BASE+1100,lastCallbackEpochMs=BASE+1101,lastDispatchEpochMs=BASE+1102)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.completed(*values)

    def test_missing_actual_artifact_bytes_cannot_be_replaced_with_native_complete_status(self):
        with self.ctx.lock.held():
            args=self.prepared();args[7].path().write_bytes(b'')
            with self.assertRaises(NativeUIError):source.completed(*args)


if __name__=='__main__':unittest.main()
