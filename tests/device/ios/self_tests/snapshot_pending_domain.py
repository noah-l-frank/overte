"""Connected actual owners with explicit Qt/script/native timer producers.

Effects follow actual ordinary input deliveries. Timer death is backed by real
Python weak lifetimes; no adapter submits a desired callback or absence result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import time
import uuid
import weakref
from unittest.mock import patch
from adapters.native_feature_observation import need
from feature_journeys.witness import Client
from ios.adapters import normal_input,snapshot_work,snapshot_pending_inputs,snapshot_pending_choices
from ios.adapters.snapshot_pending_runtime import IOSSnapshotPendingRuntime
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,BASE,RUN
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.test_ios_snapshot_work import packet as initial_work

REAL_TIME=time.time
REAL_MONOTONIC=time.monotonic
REAL_SLEEP=time.sleep


class Timer:
    pass


class SnapshotPendingDomain(SnapshotCaptureDomain):
    def __init__(self,case):
        super().__init__(case);self.mode_index=0;self.popup=False;self.name_focused=False;self.capturing=False;self.capture_count=0;self.cancel_count=0
        self.f.now=int(REAL_TIME()*1000);self.f.input_native.epoch=self.f.now
        native_producer=self.ctx.native.mutate
        def produced(value):self.advance();native_producer(value)
        self.ctx.native.mutate=produced
        self.choice_events=[];self.choice_sequence=0;self.lost_controls=set();self.ignored_controls=set();self.timers={};self.held=[];self.hold_timers=False
        self.work_template=initial_work();self.event_sequence=1;self.call_sequence=0;self.script_state=deepcopy(self.work_template['source']['workers'][0]['state'])
        self.script_events=deepcopy(self.work_template['source']['workers'][0]['events']);self.timer_records=[];self.pending_request=None
        self.initial_name='';self.f.input_native.name=self.initial_name;self.combo_id=str(uuid.uuid4());self.tokens={key:str(uuid.uuid4()) for key in (
            'snapshot.name','snapshot.mode','snapshot.capture','snapshot.cancel','snapshot.mode.animated','snapshot.mode.still')}
        base_observed=self.f.input_native.observed
        def observed():
            ui=base_observed();base=ui['controls'][0];ui.update(sampleEpochMs=self.epoch(),snapshotPendingControlsVersion=1);ui['controls']=[]
            base.update(snapshotMode=self.mode_index,snapshotCapturing=self.capturing,snapshotImageCount=0)
            for control in ('snapshot.capture','snapshot.name','snapshot.mode','snapshot.cancel'):
                row=deepcopy(base);enabled=self.capturing if control=='snapshot.cancel' else not self.capturing
                row.update(id=control,token=self.tokens[control],enabled=enabled,inputReady=enabled,focused=control=='snapshot.name' and self.name_focused)
                ui['controls'].append(row)
            if self.popup:
                for option in ('animated','still'):
                    control='snapshot.mode.'+option;meta=self.choice_metadata(option)
                    ui['controls'].append(dict(id=control,token=self.tokens[control],enabled=True,focused=False,frame=deepcopy(base['frame']),checked=meta['checked'],snapshotPendingChoice=meta))
            return ui
        self.f.input_native.observed=observed
        actual=patch.object(normal_input,'urlopen',self.input_post);actual.start();case.addCleanup(actual.stop)
        domain=self
        class Runtime(IOSSnapshotPendingRuntime):
            def _sources(self,_selector):return dict(binding=domain.ctx.binding,check=lambda:domain.good,observer=domain.ctx.feature,clock_source=domain.f.clock().native,native=domain.f.input_native.input())
            def existing_input_session(self,_selector):return nullcontext()
        self.runtime=Runtime(SimpleNamespace(state_path=lambda _:self.ctx.root/'session.json',_candidate_guard=lambda:True,_binding=lambda:None))
    def advance(self):self.f.now=max(self.f.now,self.f.input_native.epoch,int(REAL_TIME()*1000))+1
    def sleep(self,delay):REAL_SLEEP(delay);self.f.now+=round(delay*1000)
    def choice_metadata(self,option):
        return dict(snapshotPendingChoiceVersion=1,rootId='11111111-2222-4333-8444-777777777777',qmlSource='qrc:/scripts/system/snapshot/NativeSnapshotReview.qml',
            comboId=self.combo_id,option=option,selectedMode=self.mode_index,format='png',checked=self.mode_index==(1 if option=='animated' else 0),popupOpen=self.popup,inputReady=self.popup)
    def event(self,event,closure,call):
        self.advance();self.event_sequence+=1
        row=dict(sequence=self.event_sequence,callerSequence=self.event_sequence,capturedEpochMs=self.epoch(),invokedEpochMs=self.epoch(),
            event=event,closure=closure,call=call,state=deepcopy(self.script_state))
        self.script_events.append(row);return row
    def start(self):
        self.capture_count+=1;need(not self.capturing and self.mode_index==1);self.call_sequence+=1;call=self.call_sequence
        self.event('entry','takeSnapshot',call);self.pending_request='snap_'+str(self.epoch())+'_1';self.capturing=True
        self.script_state.update(captureId=self.pending_request,captureCounter=1,revision=self.script_state['revision']+1,mode='animated',timerHandles=[1,2],overlaysHidden=True)
        for handle,interval in ((1,350),(2,60000)):
            timer=Timer();row=dict(timerId=uuid.uuid4().hex,handle=handle,callerChain=['qrc:/scripts/system/snapshot.js'],createdEpochMs=self.epoch(),
                singleShot=True,intervalMs=interval,activeAtBirth=True,remainingAtBirthMs=interval,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,
                destroyedEpochMs=None,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
            def destroyed(_weak,row=row):self.advance();row['destroyedEpochMs']=self.epoch()
            self.timer_records.append((weakref.ref(timer,destroyed),row));self.timers[handle]=timer
        self.event('returned','takeSnapshot',call);self.event('finally','takeSnapshot',call)
    def cancel_effect(self):
        self.cancel_count+=1;need(self.capturing);self.call_sequence+=1;call=self.call_sequence;self.event('entry','cancelNativeCapture',call)
        self.capturing=False;self.script_state.update(captureId='',timerHandles=[],overlaysHidden=False,revision=self.script_state['revision']+1)
        if self.hold_timers:self.held.extend(self.timers.values())
        self.timers.clear();self.event('returned','cancelNativeCapture',call);self.event('finally','cancelNativeCapture',call)
    def input_post(self,request,timeout):
        query=json.loads(request.data);native=self.f.input_native;key=str(uuid.uuid4());control=None;self.advance()
        if query['operation']=='edit':
            controls=native.observed()['controls'];rows=[row for row in controls if row['token']==query['input']['fieldToken']];need(len(rows)==1)
            row=rows[0];control=row['id'];native.field=control
            root=deepcopy(row['snapshotPendingChoice']) if control in snapshot_pending_choices.IDS else dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])
            details=dict(outerCommandId=query['commandId'],command=query['input'],controlId=control,root=root)
            if control in snapshot_pending_choices.IDS:self.choice_event(key,'received',details)
            else:native.event(key,'received',details)
        result=Boundary.post(native,request,timeout)
        if control is not None:
            ignored=control in self.ignored_controls
            if not ignored:
                operation=query['input']['operation']
                if control=='snapshot.name':
                    self.name_focused=True
                    if operation=='replace':native.name=query['input']['text']
                elif control=='snapshot.mode':self.popup=True;self.name_focused=False
                elif control in snapshot_pending_choices.IDS:
                    self.mode_index=1 if control.endswith('animated') else 0;self.popup=False
                elif control=='snapshot.capture':self.start()
                else:need(control=='snapshot.cancel');self.cancel_effect()
            native.receipt['status']['sampleEpochMs']=max(int(native.receipt['status']['sampleEpochMs']),native.epoch)
            if control in snapshot_pending_choices.IDS:self.choice_event(key,'returned',native.receipt)
            else:native.event(key,'returned',native.receipt)
            self.advance()
            if control in self.lost_controls:self.lost_controls.remove(control);raise OSError('Declared lost ordinary '+control+' return')
        return result
    def choice_event(self,key,kind,details):
        self.choice_events.append(dict(sequence=len(self.choice_events)+1,eventId=str(uuid.uuid4()),inputId=key,kind=kind,clock=self.f.input_native.stamp(),details=deepcopy(details)))
    def work_packet(self,q):
        self.advance();self.work_sequence+=1;before=self.clock();value=deepcopy(self.work_template);self.event_sequence+=1
        row=value['source']['workers'][0];latest=dict(sequence=self.event_sequence,callerSequence=self.event_sequence,capturedEpochMs=self.epoch(),invokedEpochMs=self.epoch(),event='snapshot',closure='',call=0,state=deepcopy(self.script_state))
        row.update(events=deepcopy(self.script_events),state=deepcopy(self.script_state),latest=latest)
        value['source']['eventSequence']=self.event_sequence;value['source']['timerSources']['workers'][0]['timerWork']['timers']=sorted([deepcopy(row) for _weak,row in self.timer_records],key=lambda row:row['timerId'])
        value.update(requestId=q['commandId'],sequence=self.work_sequence,clockBefore=before,clockAfter=self.clock());return value
    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=snapshot_pending_inputs.ACTION:return super().post(request,timeout)
        self.advance();self.commands.append(deepcopy(query));self.choice_sequence+=1;before=self.clock()
        value=dict(iosNormalInputsVersion=1,profile='snapshot-pending',requestId=query['commandId'],runId=query['runId'],instance='9'*32,sequence=self.choice_sequence,
            processId=42,clockDomain='native-process-normal-inputs',clockBefore=before,clockAfter=self.clock(),source=dict(complete=True,events=deepcopy(self.choice_events)))
        self.raws[snapshot_pending_inputs.FILE]=json.dumps(value,indent=1)+'\n';self.ctx.files.echo=json.dumps(query).encode();return self.ctx.files
    def client(self):
        domain=self
        class Phase(Client):
            def request(self,_path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                domain.phase_sequence+=1;return dict(fixturePhaseVersion=1,instance='e'*32,sequence=domain.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',
                    capturedEpochMs=domain.epoch(),active=True,createdEpochMs=BASE-100,retiredEpochMs=None,
                    activations=[dict(sequence=1,ticket='f'*32,activatedEpochMs=BASE-90,stimulus=dict(verb='capture-cancel',inputs=dict(mode='animated',format='png')))])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.mono,sleep=self.sleep)
    def owner(self):return self.runtime.pending_owner('primary',RUN,self.client(),epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
