"""Private selector-free Chat samples from new original same-phase queries.

No input, cache mutation, public capability, finalization or stereo claim.
Historical rows never become fresh observations; cold ownership is refused.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import math
import time

from adapters.chat_journey.compiled_samples import CompiledChatSamples,CompiledChatCacheAbsence
from adapters.chat_journey.erase_restore import references
from adapters.chat_journey.flow_inputs import fresh_roles,validate_flow
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import MAX_FRAMES,pack,unpack,same
from feature_journeys.contract import result
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,validate as phase_packet
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1
STAGES=('initial','active','cleanup')


class ChatObservationOwner:
    """One stage/role; an uncertain reading never authorizes another query.

    The flow/admission files are input authority only. Every reported state,
    resource and lifecycle field comes from this role's newly queried sources.
    """
    def __init__(self,source,samples,flow_store,store,*,stage,cleanup_store=None,monotonic=time.monotonic):
        need(type(source) is PhaseFixtureReader and source.area=='chat' and stage in STAGES
            and type(samples) is (CompiledChatSamples if stage=='active' else CompiledChatCacheAbsence)
            and samples.run==source.run and samples.vr and not samples.component_only
            and type(flow_store) is PrivateFeatureState and type(store) is PrivateFeatureState
            and callable(monotonic) and (type(cleanup_store) is PrivateFeatureState if stage=='cleanup' else cleanup_store is None))
        paths=[flow_store.path,store.path,samples.store.path,samples.script_source.store.path]
        if cleanup_store is not None:paths.append(cleanup_store.path)
        need(len(set(paths))==len(paths) and all(path.parent==store.path.parent for path in paths))
        self.source,self.samples,self.flow_store,self.store=source,samples,flow_store,store
        self.stage,self.cleanup_store,self.monotonic=stage,cleanup_store,monotonic
        self.failed=False;self.clock=None;self.previous=store.read();self.rows=[];self._freeze_guard=None
        self.scope=dict(chatObservationOwnerVersion=VERSION,contractVersion=CONTRACT_VERSION,runId=source.run,
            fixtureUrl=source.fixture_url,role=samples.role,binding=deepcopy(samples.binding),peerBinding=deepcopy(samples.peer_binding),
            stage=stage,transcript=samples.store.path.name,flowJournal=flow_store.path.name,
            cleanupAdmission=None if cleanup_store is None else cleanup_store.path.name)
        self.history=ChatSourceChunks(store,self.scope)
        self.base={**self.scope,'phase':'ready','revision':0,'chunks':[]}
        # A ready source row is not an independently received RPC receipt.
        # Until that explicit lifetime join exists, cold ownership is refused.
        need(self.previous is None);self.history.inventory(0)

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value;return value

    def bind_freeze(self,guard):
        need(callable(guard) and (self._freeze_guard is None or self._freeze_guard is guard))
        self._freeze_guard=guard

    def flow(self):
        value=self.flow_store.read();rows=validate_flow(value)
        need(value['runId']==self.source.run and value['fixtureUrl']==self.source.fixture_url
            and same(value['binding'],self.samples.binding) and same(value['peerBinding'],self.samples.peer_binding))
        if self.stage!='cleanup':
            names=value['baselineTranscripts'] if self.stage=='initial' else value['transcripts']
            need(self.samples.store.path.name in ([names[0]] if self.samples.role=='primary' else names[1:]))
        return value,rows

    def authority(self,count,*,current=False):
        value,rows=self.flow();need(integer(count,1,27))
        if self.stage=='cleanup':
            need(count==27 and len(rows)==26 and all(row['phase']=='completed' for row in rows))
            cleanup=self.cleanup_store.read()
            exact(cleanup,{'chatCleanupAdmissionVersion','runId','binding','peerBinding','flowSha256','phase','original'})
            need(type(cleanup['chatCleanupAdmissionVersion']) is int and cleanup['chatCleanupAdmissionVersion']==1
                and cleanup['runId']==self.source.run and cleanup['phase']=='admitted'
                and same(cleanup['binding'],self.samples.binding) and same(cleanup['peerBinding'],self.samples.peer_binding)
                and cleanup['flowSha256']==digest(value))
            original=cleanup['original'];phase_packet(original,run=self.source.run,area='chat',request=original['requestId'],
                epoch=original['capturedEpochMs'],previous=rows[-1]['after'])
            need(original['active'] and len(original['activations'])==27
                and original['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            return dict(flowSha256=digest(value),cleanupSha256=digest(cleanup)),original
        need(count<=len(rows) and (count==1 if self.stage=='initial' else count>=2))
        row=rows[count-1]
        if row['phase']!='completed':raise PhasePending('Original Chat input has not completed')
        if current:need(count==len(rows))
        prefix={**value,'payload':pack(rows[:count])}
        return dict(flowSha256=digest(prefix),cleanupSha256=None),row['after']

    def current(self):
        value,rows=self.flow()
        if self.stage=='cleanup':return self.authority(27,current=True)
        return self.authority(len(rows),current=True)

    def matching(self,active,original):
        need(active['status']['active'])
        if not same(active['status']['activations'],original['activations']):
            raise PhasePending('The actual fixture phase has advanced beyond this consumed input')
        need(active['ticket']==original['activations'][-1]['ticket'])

    def sample(self,sequence,frame):
        measured=self.samples._compose(frame)
        need('state' in measured and not frame.get('settings') and not frame.get('transition'))
        value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.source.run,sequence=sequence,
            capturedEpochMs=measured['capturedEpochMs'],state=deepcopy(measured['state']),artifacts=[],
            resources=deepcopy(measured['resources']),lifecycle=deepcopy(measured['lifecycle']))
        return result('feature.chat.observe',value)

    def original_source(self,index):
        self.samples.history.verify();root=self.samples.store.read()
        need(same(root,self.samples.previous) and root['phase']=='ready')
        chunk=self.samples.history.store(index).read()
        exact(chunk,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
        need(type(chunk['chatSampleChunkVersion']) is int and chunk['chatSampleChunkVersion']==1
            and type(chunk['index']) is int and chunk['index']==index and chunk['scopeSha256']==self.samples.history.scope
            and digest(chunk)==root['chunks'][index])
        frames=unpack(chunk['transcript']);need(len(frames)==1 and same(frames[0],self.samples.frames[index]))
        return frames[0]

    def validate_row(self,row,sequence,previous=None):
        exact(row,{'sequence','before','after','authority','reference','sample'})
        need(type(row['sequence']) is int and row['sequence']==sequence)
        count=len(row['before']['activations']);authority,original=self.authority(count)
        need(same(authority,row['authority']))
        for key,prior in (('before',previous or original),('after',row['before'])):
            packet=row[key];phase_packet(packet,run=self.source.run,area='chat',request=packet['requestId'],
                epoch=packet['capturedEpochMs'],previous=prior)
            need(packet['active'] and same(packet['activations'],original['activations']))
        reference=row['reference'];exact(reference,{'index','ticket','queries','epochs','sourceSha256'})
        need(integer(reference['index'],0,len(self.samples.frames)-1))
        frame=self.original_source(reference['index'])
        expected=dict(index=reference['index'],ticket=frame['ticket'],sourceSha256=digest(frame),
            queries=[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')],
            epochs=[frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')])
        need(same(reference,expected) and frame['ticket']==row['before']['activations'][-1]['ticket']
            and frame['afterEpochMs']==math.ceil(row['before']['activations'][-1]['activatedEpochMs'])
            and same(row['sample'],self.sample(sequence,frame)))
        return frame

    def write(self,value):
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=self.base=deepcopy(value)

    def final(self,row,started):
        need(not self.failed and self.base['phase']=='ready' and same(self.store.read(),self.previous))
        self.history.verify();self.samples.history.verify();self.samples.script_source.history.verify()
        stored=self.history.store(len(self.rows)-1).read()
        need(digest(stored)==self.base['chunks'][-1] and same(unpack(stored['transcript']),[row]))
        self.validate_row(row,len(self.rows),self.rows[-2]['after'] if len(self.rows)>1 else None)
        authority,original=self.current();need(same(authority,row['authority']))
        active=self.source.read(row['after']);self.matching(active,original)
        # This additional phase query carries authority only. It never retimes
        # target epochs; all original native clocks run AFTER it and final copies.
        measured=self.now();epoch=self.source.epoch_ms();ended=self.now()
        phase_packet(active['status'],run=self.source.run,area='chat',request=active['status']['requestId'],
            epoch=epoch+math.ceil((ended-measured)*1000),previous=row['after'])
        fresh_roles((self.samples,),started,self.now)
        finished=self.now()
        need(number(finished,ended,started+1.5)
            and epoch-active['status']['capturedEpochMs']+math.ceil((finished-measured)*1000)<=1500)

    def read(self,after_sequence=0):
        need(not self.failed and integer(after_sequence,0,len(self.rows)))
        if self._freeze_guard is not None:need(self._freeze_guard() is True)
        pending=None
        with ExitStack() as held:
            for lock in sorted(self.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            if self._freeze_guard is not None:need(self._freeze_guard() is True)
            try:
                started=self.now();authority,original=self.current();active=self.source.read(original);self.matching(active,original)
            except PhasePending as error:pending=error
            except Exception:self.failed=True;raise
            if pending is None:
                try:
                    self.history.verify();need(len(self.rows)<MAX_FRAMES and self.base['phase']=='ready')
                    self.write({**self.base,'phase':'reading','revision':self.base['revision']+1})
                    self.samples.read(active['ticket'],math.ceil(active['afterEpochMs']))
                    confirmed=self.source.read(active['status']);self.matching(confirmed,original)
                    need(same(self.current()[0],authority))
                    reference={**references((self.samples,))[0],'sourceSha256':digest(self.original_source(len(self.samples.frames)-1))}
                    row=dict(sequence=len(self.rows)+1,before=deepcopy(active['status']),after=deepcopy(confirmed['status']),
                        authority=authority,reference=reference,
                        sample=self.sample(len(self.rows)+1,self.samples.frames[-1]))
                    self.validate_row(row,len(self.rows)+1,self.rows[-1]['after'] if self.rows else None)
                    self.write({**self.base,'phase':'ready','revision':self.base['revision']+1,
                        'chunks':self.history.append(row,self.base['chunks'])})
                    self.rows.append(row);value=deepcopy(row['sample']);self.final(row,started);return value
                except Exception:self.failed=True;raise
        raise pending
