"""Native lifetime host model driven by original executing Node/V8 events.

Only V8 source/stack and Script/reference JavaScript execute for real. Qt API,
queues and their weak holder objects are explicit Python models, not devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
import weakref


class Holder:pass


class EmissionOriginals:
    def __init__(self,sdk):
        self.sdk=sdk;self.instance=uuid.uuid4().hex;self.sequence=0;self.events=0;self.native=0
        self.objects=[];self.calls=[];self.queues=[];self.sinks=[];self.weak={};self.strong={};self.returns={}
    def stamp(self,epoch):return dict(epochMs=epoch,monotonicMs=epoch-self.sdk.base_epoch)
    def observe(self,result,trace,indices):
        for event in result['emissionEvents'][self.events:]:
            call=event['call'];at=self.stamp(event['epoch'])
            if event['kind']=='api-enter':
                holder=Holder();key=uuid.uuid4().hex;self.strong[call]=holder;self.weak[key]=weakref.ref(holder)
                self.objects.append(dict(id=key,born=at,expired=None,alive=True))
                self.calls.append(dict(id=call,sequence=len(self.calls)+1,object=key,surface='world',target=event['target'],message=event['message'],
                    caller=deepcopy(event['caller']),entered=at,returned=None,**{'finally':None}))
            else:
                row=next(row for row in self.calls if row['id']==call)
                row['returned' if event['kind']=='api-return' else 'finally']=at
                if event['kind']=='api-finally':self.strong.pop(call)
        self.events=len(result['emissionEvents'])
        # Actual Node event IDs map to the independently retained native trace,
        # not to an inferred message/count match.
        for ordinal,event in enumerate(result['nativeEvents'][self.native:],self.native+1):
            if event['kind']=='signal-return':
                self.returns[event['detail']['entry']]=self.stamp(event['epoch']);continue
            call=event.get('emissionCall')
            if call is None:continue
            assert event['kind'] in ('script-event-slot','page-reply')
            actual=trace[indices[ordinal]-1];assert actual['kind']==event['kind']
            at=self.stamp(event['epoch']);key=uuid.uuid4().hex
            self.sinks.append(dict(id=key,sequence=len(self.sinks)+1,kind=event['kind'],call=call,identity=deepcopy(actual['identity']),
                message=event['detail']['message'],entered=at,returned=None,**{'finally':None},node=ordinal))
        self.native=len(result['nativeEvents'])
        for row in self.sinks:
            ended=self.returns.get(row['node'])
            if ended is not None:row['returned']=deepcopy(ended);row['finally']=deepcopy(ended)
        # The modeled synchronous QtAuto receiver holder spans the real paired
        # native slot enter/return. An external Python holder can keep it alive.
        for call in self.calls:
            if any(row['call']==call['id'] for row in self.queues):continue
            sinks=[row for row in self.sinks if row['call']==call['id']]
            if not sinks:continue
            holder=Holder();key=uuid.uuid4().hex;self.weak[key]=weakref.ref(holder)
            ended=sinks[0]['finally']
            self.queues.append(dict(id=key,sequence=len(self.queues)+1,call=call['id'],route='world-surface',created=deepcopy(call['entered']),
                entered=deepcopy(sinks[0]['entered']),returned=deepcopy(ended),**{'finally':deepcopy(ended)},captureAlive=True,expired=None))
    def read(self,command):
        sdk=self.sdk;self.sequence+=1;before=self.stamp(sdk.tick())
        for row in self.objects+self.queues:
            if self.weak[row['id']]() is None and row['expired'] is None:
                row['expired']=self.stamp(sdk.tick());row['alive' if row in self.objects else 'captureAlive']=False
        return dict(iosWebScriptEmissionsVersion=1,commandId=command['commandId'],runId=sdk.run,fixtureUrl=sdk.fixture_url,instance=self.instance,
            sequence=self.sequence,processId=sdk.pid,clockDomain='native-process-ios-web-script-emissions',clockBefore=before,clockAfter=self.stamp(sdk.tick()),
            complete=True,callSequence=len(self.calls),queueSequence=len(self.queues),sinkSequence=len(self.sinks),objects=deepcopy(self.objects),calls=deepcopy(self.calls),
            queues=deepcopy(self.queues),sinks=[{key:deepcopy(value) for key,value in row.items() if key!='node'} for row in self.sinks])
