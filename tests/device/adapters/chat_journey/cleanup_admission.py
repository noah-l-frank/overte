"""Original final Chat cleanup activation after all 26 consumed input rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.chat_journey.flow_inputs import ChatFlowInputs,validate_flow
from adapters.chat_journey.source_chunks import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate

VERSION=1


class ChatCleanupAdmission:
    """Passive phase ownership only; no target facts, input or cleanup verdict.

    Construction refuses an existing journal. Admission is at most once for a
    warm parent; an uncertain phase receipt is retained, never re-admitted.
    """
    def __init__(self,flow,store):
        need(type(flow) is ChatFlowInputs and isinstance(store,PrivateFeatureState)
            and store.path.parent==flow.store.path.parent and store.path!=flow.store.path
            and store.read() is None)
        self.flow,self.store,self.previous,self.failed=flow,store,None,False
        source=flow.source
        self.source=PhaseFixtureReader(source.client,source.run,source.area,epoch_ms=source.epoch_ms,monotonic=source.monotonic)

    def completed(self):
        self.flow.roles[0].locks[0].assert_held()
        value=self.flow.store.read();need(same(value,self.flow.previous))
        rows=validate_flow(value);need(same(rows,self.flow.rows) and len(rows)==26 and all(row['phase']=='completed' for row in rows))
        need(len(rows[-1]['after']['activations'])==26)
        return value,rows[-1]['after']

    def write(self,value):
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def admit(self):
        try:
            need(not self.failed and self.previous is None)
            completed,previous=self.completed()
            started=self.source.monotonic();barrier=self.source.epoch_ms()
            need(number(started,0,1e15) and number(barrier,1,1e16))
            self.write(dict(chatCleanupAdmissionVersion=VERSION,runId=self.source.run,binding=self.flow.scope['binding'],
                peerBinding=self.flow.scope['peerBinding'],flowSha256=digest(completed),phase='reading',original=None))
            now=self.source.monotonic();epoch=self.source.epoch_ms()
            need(number(now,started,started+1.5) and number(epoch,barrier,barrier+1500))
            active=self.source.read(previous);packet=deepcopy(active['status'])
            need(active['verb']=='cleanup' and active['inputs']=={} and len(packet['activations'])==27
                and same(packet['activations'][:26],previous['activations'])
                and packet['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            self.write({**self.previous,'phase':'admitted','original':packet})
            # The CAS cannot be refreshed by issuing another phase request.
            # The final packet copy precedes both advancing original clocks.
            result=deepcopy(packet);self.original()
            measured=self.source.monotonic();final_epoch=self.source.epoch_ms();ended=self.source.monotonic()
            need(number(measured,now,started+1.5) and number(ended,measured,started+1.5)
                and number(final_epoch,epoch,barrier+1500)
                and final_epoch-barrier+math.ceil((ended-measured)*1000)<=1500)
            validate(result,run=self.source.run,area='chat',request=result['requestId'],
                epoch=final_epoch+math.ceil((ended-measured)*1000),previous=previous)
            return result
        except Exception:self.failed=True;raise

    def original(self):
        need(not self.failed and self.previous is not None and same(self.store.read(),self.previous))
        exact(self.previous,{'chatCleanupAdmissionVersion','runId','binding','peerBinding','flowSha256','phase','original'})
        completed,previous=self.completed()
        need(type(self.previous['chatCleanupAdmissionVersion']) is int and self.previous['chatCleanupAdmissionVersion']==VERSION and self.previous['phase']=='admitted'
            and self.previous['flowSha256']==digest(completed) and self.previous['runId']==self.source.run
            and same(self.previous['binding'],self.flow.scope['binding']) and same(self.previous['peerBinding'],self.flow.scope['peerBinding']))
        packet=self.previous['original']
        validate(packet,run=self.source.run,area='chat',request=packet['requestId'],epoch=packet['capturedEpochMs'],previous=previous)
        need(packet['active'] and len(packet['activations'])==27 and same(packet['activations'][:26],previous['activations'])
            and packet['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        return packet
