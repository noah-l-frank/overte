"""Actual Script Window call on the existing normal Combined upload fixture.

Qt queues/V8/native ledgers remain models. The actual Script/request.js GET,
actual callback's Window invocation, existing normal native-job constructor,
private PNG and protected backend bytes drive the modeled source events.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import uuid
import weakref
from adapters.native_feature_observation import need
from ios.self_tests.snapshot_combined_consumer_domain import CombinedConsumerDomain,ConsumerBoundary
from ios.self_tests.snapshot_combined_work_fixture import caller
from ios.self_tests.snapshot_upload_script_domain import OriginalUploadScript
from ios.self_tests.snapshot_upload_flow_domain import RUN,BASE


class QueueLease:pass


class CausalConsumerBoundary(ConsumerBoundary):
    trace_calls=True
    def trace(self,event):
        if event['kind']=='window-share':
            self.trace_events.append(deepcopy(event));self.domain.window_called(event['details']);return
        if event['kind']=='window-return':
            self.trace_events.append(deepcopy(event));self.domain.window_returned();return
        super().trace(event)


class CausalDispatchDomain(CombinedConsumerDomain):
    def __init__(self,case):
        super().__init__(case);self.http=CausalConsumerBoundary(self);self.script=OriginalUploadScript(case,self.backend,self.http)
        self.causal_instance=uuid.uuid4().hex;self.causal_sequence=0;self.calls=[];self.lease=None;self.lease_ref=None
        self.hold_dispatch=False;self.held=[]
    def window_called(self,parameters):
        need(self.lease is None)
        # This event arrives only from the actual running Window function in
        # the Node edge, between actual text-read and callback-leave events.
        model=self.work_template['source']['workers'][0];raw_stack,_modules=caller(('system/snapshot.js','modules/request.js'),BASE)
        observed=dict(callerVersion=1,method='shareSnapshot',sequence=len(self.calls)+1,invokedEpochMs=self.epoch(),
            manager=deepcopy(model['manager']),code=deepcopy(model['code']),snapshotCombinedSources=deepcopy(model['codeSources']),snapshotCombinedStack=raw_stack)
        events={row['kind']:row for row in self.http.events};link=dict(httpInstance=self.http.instance,
            clockDomain='native-process-snapshot-combined-preflight-http',xhrId=self.http.xhr,replyId=self.http.reply,
            **{key:deepcopy(events[kind]) for key,kind in (('created','created'),('sent','sent'),('finished','reply-finished'),('entered','callback-enter'),('read','text-read'))})
        self.advance();name=Path(parameters['path']).name
        row=dict(instance=uuid.uuid4().hex,bornEpochMs=self.epoch(),file=dict(privateName=True,name=name,nameSha256=hashlib.sha256(name.encode()).hexdigest()),
            caller=observed,http=link,hops=[],upload=None,associatedEpochMs=None,releasedEpochMs=None)
        self.calls.append(row);lease=QueueLease()
        def released(_weak):self.advance();row['releasedEpochMs']=self.epoch()
        self.lease_ref=weakref.ref(lease,released);self.lease=lease;self.entered('window')
    def entered(self,stage):
        self.advance();self.calls[-1]['hops'].append(dict(instance=uuid.uuid4().hex,stage=stage,enteredEpochMs=self.epoch(),leftEpochMs=None))
    def left(self,stage):
        self.advance();matches=[row for row in self.calls[-1]['hops'] if row['stage']==stage and row['leftEpochMs'] is None]
        need(len(matches)==1);matches[0]['leftEpochMs']=self.epoch()
    def window_returned(self):
        if self.calls:self.left('window')
    def new_upload(self):
        need(self.lease is not None);self.entered('application');self.entered('snapshot')
        upload=super().new_upload();self.advance();self.calls[-1].update(upload=upload.upload['instance'],associatedEpochMs=self.epoch())
        self.left('snapshot');self.left('application')
        if self.hold_dispatch:self.held.append(self.lease)
        self.lease=None;return upload
    def causal_packet(self,query):
        self.advance();self.causal_sequence+=1;before=self.clock();self.advance();after=self.clock()
        rows=deepcopy(self.calls)
        for row in rows:row['leaseAlive']=self.lease_ref is not None and self.lease_ref() is not None
        return dict(iosSnapshotCausalDispatchVersion=1,requestId=query['commandId'],runId=RUN,instance=self.causal_instance,
            sequence=self.causal_sequence,processId=42,clockDomain='native-process-snapshot-causal-dispatch',clockBefore=before,clockAfter=after,
            source=dict(complete=True,calls=rows))
