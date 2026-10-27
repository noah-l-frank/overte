"""Original combined-manager work on the existing ordinary upload boundary.

Qt/V8/SDK are declared models. Input delivery, original PNG/body descriptors,
host clocks, quiet windows and durable file owners use the existing paths.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from ios.adapters import snapshot_combined_work as work
from ios.self_tests.snapshot_combined_work_fixture import packet,entry
from ios.self_tests.snapshot_upload_flow_domain import SnapshotUploadFlowDomain,RUN,BASE,REAL_TIME,REAL_MONOTONIC


class CombinedUploadDomain(SnapshotUploadFlowDomain):
    def __init__(self,case):
        super().__init__(case)
        self.work_template=packet(BASE)
        self.script_events=deepcopy(self.work_template['source']['workers'][0]['events'])

    def event(self,event,closure,call):
        row=super().event(event,closure,call);row['callerStackId']='c'*32;return row

    def work_packet(self,query):
        self.advance();self.work_sequence+=1;before=self.clock();value=deepcopy(self.work_template);self.event_sequence+=1
        row=value['source']['workers'][0]
        row.update(events=deepcopy(self.script_events),state=deepcopy(self.script_state),latest=dict(sequence=self.event_sequence,
            callerSequence=self.event_sequence,capturedEpochMs=self.epoch(),invokedEpochMs=self.epoch(),event='snapshot',closure='',call=0,
            state=deepcopy(self.script_state),callerStackId='d'*32))
        value['source']['eventSequence']=self.event_sequence;timers=value['source']['timerSources']['workers'][0]['timerWork']
        for _weak,original in sorted(self.timer_records,key=lambda item:item[1]['timerId']):
            observed={key:deepcopy(item) for key,item in original.items() if key!='callerChain'}
            observed['callerStackId']='f'*32;timers['timers'].append(observed)
        if timers['timers']:timers['callerStacks']=[entry('f'*32,('system/snapshot.js','system/snapshot/featureSnapshotWork.js','defaultScripts.js'),BASE)]
        value.update(requestId=query['commandId'],sequence=self.work_sequence,clockBefore=before,clockAfter=self.clock());return value

    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=work.ACTION:return super().post(request,timeout)
        self.commands.append(deepcopy(query));self.raws[work.FILE]=json.dumps(self.work_packet(query),indent=1)+'\n'
        self.ctx.files.echo=json.dumps(query).encode();return self.ctx.files

    @contextmanager
    def capture_owner(self):
        with self.runtime.capture_owner('primary',RUN,self.client(),combined=True) as owner:
            owner.epoch_ms=lambda:int(REAL_TIME()*1000);owner.monotonic=REAL_MONOTONIC;owner.sleep=self.sleep
            owner.phase.epoch_ms=owner.epoch_ms;owner.phase.monotonic=REAL_MONOTONIC;yield owner

    def upload_owner(self,*,combined=True):
        return self.runtime.upload_owner('primary',RUN,self.client(),combined=combined,
            epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
