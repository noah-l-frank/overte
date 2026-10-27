"""Normal capture boundary with separately produced combined-manager work.

Qt/V8/capture/SDK are declared host models; normal input, immutable files and
the actual production coordinator execute. No retained separate packet is
relabeled or changed, and this does not qualify native Script execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from ios.adapters import snapshot_combined_work as work
from ios.self_tests.snapshot_combined_work_fixture import packet,entry
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,ClockedOwner,RUN
from ios.self_tests.test_ios_snapshot_completion import BASE


class CombinedCaptureDomain(SnapshotCaptureDomain):
    def work_packet(self,query):
        # Reuse only the declared model's ordinary input-driven state machine.
        # Construct this producer's identities and submitted-code originals
        # independently, before any AFC/journal persistence.
        before,after=self.f.work();model=(after if self.captured else before)['source']['workers'][0]
        value=packet(BASE);self.work_sequence+=1
        value.update(requestId=query['commandId'],sequence=self.work_sequence,clockBefore=self.clock(),clockAfter=self.clock())
        row=value['source']['workers'][0]
        row.update(state=deepcopy(model['state']),calls=deepcopy(model['calls']),ended=model['ended'])
        row['events']=[dict(deepcopy(event),callerStackId='c'*32) for event in model['events']]
        last=row['events'][-1];row['latest']=deepcopy(last)
        if self.work_sequence>1:
            sequence=last['sequence']+self.work_sequence
            row['latest']=dict(sequence=sequence,callerSequence=sequence,capturedEpochMs=self.f.now,invokedEpochMs=self.f.now,
                event='snapshot',closure='',call=0,state=deepcopy(row['state']),callerStackId='d'*32)
        value['source']['eventSequence']=row['latest']['sequence']
        native=value['source']['timerSources']['workers'][0]['timerWork']
        for modeled in (after if self.captured else before)['source']['timerSources']['workers'][0]['timerWork']['timers']:
            timer={key:deepcopy(item) for key,item in modeled.items() if key!='callerChain'}
            timer['callerStackId']='f'*32;native['timers'].append(timer)
        if native['timers']:native['callerStacks']=[entry('f'*32,('system/snapshot.js','system/snapshot/featureSnapshotWork.js','defaultScripts.js'),BASE)]
        return value

    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=work.ACTION:return super().post(request,timeout)
        self.commands.append(deepcopy(query));self.raws[work.FILE]=json.dumps(self.work_packet(query),indent=1)+'\n'
        self.ctx.files.echo=json.dumps(query).encode();return self.ctx.files

    def owner(self,*,combined=True):
        return ClockedOwner(self.runtime.capture_owner('primary',RUN,self.client(),combined=combined),self)
