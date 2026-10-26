"""Actual Pending→PNG→conditional file cleanup over explicit native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import uuid
import weakref
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.snapshot_journey_files_runtime import IOSSnapshotJourneyFilesRuntime
from ios.adapters.snapshot_remove_owner import RECEIPT
from ios.self_tests.snapshot_pending_domain import SnapshotPendingDomain,Timer,BASE,RUN,REAL_TIME,REAL_MONOTONIC


class SnapshotJourneyFilesDomain(SnapshotPendingDomain):
    def __init__(self,case):
        super().__init__(case);self.png_count=0;self.image_count=0;self.activations=[dict(sequence=1,ticket='f'*32,activatedEpochMs=BASE-90,stimulus=dict(verb='capture-cancel',inputs=dict(mode='animated',format='png')))]
        current=self.runtime;self.runtime=IOSSnapshotJourneyFilesRuntime(current.adapter);self.runtime._sources=current._sources;self.runtime.existing_input_session=current.existing_input_session
        observed=self.f.input_native.observed
        def actual():
            value=observed()
            for row in value['controls']:
                if 'snapshotCaptureControlVersion' in row:row['snapshotImageCount']=self.image_count
            return value
        self.f.input_native.observed=actual
        self.lose_remove=False;self.trace=[];execute=self.ctx.files.execute
        def actual_file(session,operation,values):
            if values['remotePath'].endswith('/'+RECEIPT):
                self.trace.append('original-remove-receipt')
                if RECEIPT not in self.raws:raise NativeUIError('Declared missing original remove receipt')
            return execute(session,operation,values)
        self.ctx.files.execute=actual_file
    def start(self):
        if self.mode_index==1:return super().start()
        need(not self.capturing and self.mode_index==0);self.capture_count+=1;self.png_count+=1;self.call_sequence+=1;call=self.call_sequence
        self.event('entry','takeSnapshot',call);counter=self.script_state['captureCounter']+1;self.f.request='snap_'+str(self.epoch())+'_'+str(counter);self.capturing=True
        self.script_state.update(captureId=self.f.request,captureCounter=counter,revision=self.script_state['revision']+1,mode='still',timerHandles=[3,4],overlaysHidden=True)
        for handle,interval in ((3,350),(4,60000)):
            timer=Timer();row=dict(timerId=uuid.uuid4().hex,handle=handle,callerChain=['qrc:/scripts/system/snapshot.js'],createdEpochMs=self.epoch(),singleShot=True,
                intervalMs=interval,activeAtBirth=True,remainingAtBirthMs=interval,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,
                destroyedEpochMs=None,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
            def destroyed(_weak,row=row):self.advance();row['destroyedEpochMs']=self.epoch()
            self.timer_records.append((weakref.ref(timer,destroyed),row));self.timers[handle]=timer
        del timer
        self.event('returned','takeSnapshot',call);self.event('finally','takeSnapshot',call);self.advance()
        self.sleep(.35);fired=next(row for _weak,row in self.timer_records if row['handle']==3)
        fired.update(fired=1,entered=1,left=1,lastFiredEpochMs=self.epoch(),lastCallbackEpochMs=self.epoch(),lastDispatchEpochMs=self.epoch());del self.timers[3]
        cap,identifier=self.native.begin(self.f.request);self.capture_instance=identifier
        self.f.f.h.path=self.f.f.h.path.with_name(self.f.f.h.prefix+'-'+self.f.request+'.png');self.f.f.h.path.write_bytes(self.f.bytes);self.f.f.h.path.chmod(0o600)
        self.native.finish(cap,identifier);self.image_count=1;self.capturing=False;self.call_sequence+=1;call=self.call_sequence
        self.event('entry','onNativeCaptureStatus',call);self.timers.clear();self.script_state.update(captureId='',timerHandles=[],overlaysHidden=False)
        self.event('returned','onNativeCaptureStatus',call);self.event('finally','onNativeCaptureStatus',call)
    def post(self,request,timeout):
        query=json.loads(request.data);self.trace.append(query['action']);result=super().post(request,timeout)
        if query['action']=='snapshot-files' and query['operation']=='list':
            packet=self.ctx.files.value
            if not any(row['prefix']==query['prefix'] for row in self.owned.prefixes):
                self.owned.prefixes.append(dict(prefix=query['prefix'],query=deepcopy(query),sampleEpochMs=packet['sampleEpochMs'],initiallyEmpty=not packet['files']))
            for row in self.owned.files.values():
                if row['manifestQuery']['commandId']==query['commandId']:
                    row['capture']['pathObservedEpochMs']=packet['sampleEpochMs'];row['observedEpochMs']=packet['sampleEpochMs']
        if query['action']=='feature-ios-snapshot-file-remove' and self.lose_remove:
            self.lose_remove=False;raise NativeUIError('Declared lost actual conditional-remove return')
        return result
    def client(self):
        domain=self
        class Phase(Client):
            def request(self,_path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                domain.phase_sequence+=1;return dict(fixturePhaseVersion=1,instance='e'*32,sequence=domain.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',
                    capturedEpochMs=domain.epoch(),active=True,createdEpochMs=BASE-100,retiredEpochMs=None,activations=deepcopy(domain.activations))
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=REAL_MONOTONIC,sleep=self.sleep)
    def complete_pending(self):
        with self.owner() as owner:result=owner.cancel('f'*32)
        self.advance();self.activations.append(dict(sequence=2,ticket='c'*32,activatedEpochMs=self.epoch(),stimulus=dict(verb='capture',inputs=dict(mode='still',format='png'))))
        return result
    @contextmanager
    def capture_owner(self):
        with self.runtime.capture_owner('primary',RUN,self.client()) as owner:
            owner.epoch_ms=lambda:int(REAL_TIME()*1000);owner.monotonic=REAL_MONOTONIC;owner.sleep=self.sleep
            owner.phase.epoch_ms=owner.epoch_ms;owner.phase.monotonic=REAL_MONOTONIC;yield owner
    def files_owner(self):return self.runtime.journey_files_owner('primary',RUN,self.client(),epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
