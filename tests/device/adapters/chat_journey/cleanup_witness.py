"""Independent fresh cleanup-phase publication before original IPC retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.witness import ChatWitness
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import MAX_FRAMES,same,unpack
from feature_journeys.witness import Client,projection

VERSION=1


class ChatCleanupWitness:
    """Continue the original actor cursor using NEW cleanup absence sources.

    This publishes actual observations, never a native/feature cleanup verdict.
    Existing/lost publisher roots cannot be adopted or resent.
    """
    def __init__(self,original,observation,store):
        need(type(original) is ChatWitness and type(observation) is ChatObservationOwner
            and observation.stage=='cleanup' and observation.samples.role=='actor'
            and type(observation.source.client) is Client and observation.source.client is original.source.client
            and observation.source.run==original.samples.run and observation.source.fixture_url==original.source.fixture_url
            and same(observation.samples.binding,original.samples.binding)
            and same(observation.samples.peer_binding,original.samples.peer_binding)
            and all(a is b for a,b in zip(observation.samples.locks,original.samples.locks))
            and observation.samples.script_source is original.samples.script_source
            and type(store) is PrivateFeatureState and store.path.parent==observation.store.path.parent
            and store.path not in (original.store.path,observation.store.path,observation.samples.store.path)
            and store.read() is None)
        self.original,self.observation,self.store=original,observation,store
        self.previous=None;self.rows=[];self.failed=False;self._freeze_guard=None
        self.scope=dict(chatCleanupWitnessVersion=VERSION,runId=observation.source.run,fixtureUrl=observation.source.fixture_url,
            binding=deepcopy(observation.samples.binding),peerBinding=deepcopy(observation.samples.peer_binding),
            originalWitness=original.store.path.name,originalWitnessSha256=digest(original.previous),
            observation=observation.store.path.name)
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        self.base={**self.scope,'phase':'ready','delivery':'ready','revision':0,'chunks':[],'pending':None}
        with ExitStack() as held:
            for lock in sorted(observation.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            self.control()
            reference=original.rows[-1]['reference'][0];index=reference['index'];samples=original.samples
            samples.history.verify();root=samples.store.read();chunk=samples.history.store(index).read()
            need(same(root,samples.previous) and digest(chunk)==root['chunks'][index])
            frames=unpack(chunk['transcript']);need(len(frames)==1 and same(frames[0],samples.frames[index]))
            self.active_original=deepcopy(frames[0]);self.active_digest=digest(self.active_original)

    def control(self):
        self.observation.samples.locks[0].assert_held();original=self.original
        need(not self.failed and same(original.store.read(),original.previous)
            and digest(original.previous)==self.scope['originalWitnessSha256']
            and len(original.rows)==26 and all(row['phase']=='published' and row['sequence']==index+1
                for index,row in enumerate(original.rows)))
        need(same(self.store.read(),self.previous) and len(self.rows)==len(self.base['chunks']))
        self.history.verify()
        for index,row in enumerate(self.rows):
            stored=self.history.store(index).read()
            need(digest(stored)==self.base['chunks'][index] and same(unpack(stored['transcript']),[row])
                and row['sequence']==index+1 and row['payload']['actorSequence']==27+index)
        for samples in (original.initial_samples,original.samples):samples.history.verify()
        for row in original.rows:original.original(row)

    def retired(self,frame):
        """Link actual retired caches to this actor's last active originals."""
        need(digest(self.active_original)==self.active_digest)
        before=self.active_original
        for key in ('primary','peer','view','lifecycle'):
            old,new=before[key],frame[key]
            need(old['instance']==new['instance'] and old['processId']==new['processId']
                and new['sequence']>old['sequence'] and new['capturedEpochMs']>=old['capturedEpochMs'])
            if key in ('primary','peer'):
                previous,current=old['source'],new['source']
                need(previous['scopePresent'] and not previous['retired'] and not current['scopePresent'] and current['retired']
                    and current['openedCommandId']==previous['openedCommandId'] and current['retiredCommandId']
                    and current['retiredCommandId']!=current['openedCommandId']
                    and current['selfSha256']==previous['selfSha256'] and current['mixerSha256']==previous['mixerSha256']
                    and all(same(current['session'][field],previous['session'][field]) for field in
                        ('instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs')))
            elif key=='view':need(old['source']['keyboard']['instance']==new['source']['keyboard']['instance'])
            else:need(same(old['lifecycle'],new['lifecycle']))

    def write(self,value):
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=self.base=deepcopy(value)

    def bind_freeze(self,guard):
        need(callable(guard) and (self._freeze_guard is None or self._freeze_guard is guard))
        self._freeze_guard=guard

    def publish(self):
        need(not self.failed and self.base['phase']=='ready' and len(self.rows)<MAX_FRAMES-26)
        if self._freeze_guard is not None:need(self._freeze_guard() is True)
        with ExitStack() as held:
            for lock in sorted(self.observation.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            if self._freeze_guard is not None:need(self._freeze_guard() is True)
            try:
                self.control();started=self.observation.now();self.history.verify()
                self.write({**self.base,'phase':'reading','delivery':'acquiring','revision':self.base['revision']+1})
                sample=self.observation.read(len(self.observation.rows));observed=self.observation.rows[-1]
                frame=self.observation.original_source(observed['reference']['index']);self.retired(frame)
                payload=dict(ticket=observed['before']['activations'][-1]['ticket'],actor='owned-observer',
                    actorSequence=27+len(self.rows),capturedEpochMs=sample['capturedEpochMs'],facts=projection('chat',sample['state']))
                row=dict(sequence=len(self.rows)+1,observationSequence=sample['sequence'],
                    observationSha256=digest(observed),payload=deepcopy(payload))
                self.write({**self.base,'delivery':'publishing','pending':row,'revision':self.base['revision']+1})
                wire=deepcopy(payload);self.control();self.observation.final(observed,started)
                if self._freeze_guard is not None:need(self._freeze_guard() is True)
                # The common independent journal reader still has to observe
                # these original facts. A transport ACK is no cleanup proof.
                self.observation.source.client.request('/runs/'+self.scope['runId']+'/samples',wire)
                need(same(wire,payload))
                chunks=self.history.append(row,self.base['chunks'])
                self.write({**self.base,'phase':'ready','delivery':'ready','pending':None,
                    'revision':self.base['revision']+1,'chunks':chunks})
                self.rows.append(row);self.history.verify();self.control();self.observation.final(observed,started)
                return payload['actorSequence']
            except Exception:self.failed=True;raise
