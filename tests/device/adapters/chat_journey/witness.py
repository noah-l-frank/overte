"""Separate credentialed Chat publisher using its own fresh native originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import math
import re
import time

from adapters.chat_journey.samples import ChatSamples,compose
from adapters.chat_journey.flow_inputs import validate_flow,fresh_roles
from adapters.chat_journey.erase_restore import references
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack,same,canonical
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,validate as phase
from feature_journeys.witness import projection
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1


class ChatWitness:
    """The input journal gates acquisition; it supplies no published fact.

    Run only in the separate observer process with its own publisher Client.
    Original primary/actor component transcripts are never this source store.
    """
    def __init__(self,source,samples,flow_store,store,*,monotonic=time.monotonic):
        need(isinstance(source,PhaseFixtureReader) and source.area=='chat' and isinstance(samples,ChatSamples)
            and samples.role=='actor' and samples.run==source.run and samples.vr and not samples.component_only
            and len({samples.store.path,flow_store.path,store.path})==3
            and samples.store.path.parent==flow_store.path.parent==store.path.parent and callable(monotonic))
        self.source,self.samples,self.flow_store,self.store=source,samples,flow_store,store
        self.monotonic=monotonic;self.last_clock=None;self.previous=store.read();self.rows=[]
        self.scope=dict(chatWitnessVersion=VERSION,contractVersion=CONTRACT_VERSION,runId=source.run,fixtureUrl=source.fixture_url,binding=samples.binding,
            peerBinding=samples.peer_binding,transcript=samples.store.path.name,flowJournal=flow_store.path.name)
        if self.previous is not None:
            exact(self.previous,set(self.scope)|{'payload'});need(all(same(self.previous[key],value) for key,value in self.scope.items()))
            self.rows=unpack(self.previous['payload']);need(1<=len(self.rows)<=26);tickets=set();previous=None
            for index,row in enumerate(self.rows):
                exact(row,{'ticket','sequence','phase','control','before','after','reference'})
                need(row['sequence']==index+1 and integer(row['sequence'],1) and row['ticket'] not in tickets
                    and row['phase'] in ('reading','publishing','published','retired')
                    and (index==len(self.rows)-1 or row['phase'] in ('published','retired')));tickets.add(row['ticket'])
                need(type(row['control']) is str and re.fullmatch('[0-9a-f]{64}',row['control']))
                for key in ('before','after'):
                    value=row[key]
                    if value is None:need(key=='after' and row['phase']=='reading');continue
                    phase(value,run=source.run,area='chat',request=value['requestId'],epoch=value['capturedEpochMs'],previous=previous);previous=value
                if row['phase']=='reading':need(row['reference'] is None)
                else:
                    self.original(row);need(row['before']['active'] and row['before']['activations'][-1]['ticket']==row['ticket'])
                    need(row['after']['active'] and (row['after']['activations'][-1]['ticket']!=row['ticket'])==(row['phase']=='retired'))

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock));self.last_clock=value;return value

    def original(self,row):
        refs=row['reference'];need(type(refs) is list and len(refs)==1)
        ref=refs[0];exact(ref,{'index','ticket','queries','epochs'});need(integer(ref['index'],0,len(self.samples.frames)-1))
        frame=self.samples.frames[ref['index']]
        need(ref==dict(index=ref['index'],ticket=frame['ticket'],queries=[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')],
            epochs=[frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')]) and frame['ticket']==row['ticket'])
        return compose(self.samples.run,frame,self.samples.primary.pid,self.samples.peer.pid,vr=True)

    def save(self):
        self.samples.locks[0].assert_held();need(same(self.store.read(),self.previous))
        value={**self.scope,'payload':pack(self.rows)};self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def control(self,active):
        import hashlib
        value=self.flow_store.read()
        if value is None:raise PhasePending('Original Chat input owner has not admitted this phase')
        rows=validate_flow(value)
        need(value['runId']==self.samples.run and value['fixtureUrl']==self.source.fixture_url
            and value['binding']==self.samples.binding and value['peerBinding']==self.samples.peer_binding
            and value['transcripts'][2]==self.samples.store.path.name
            and self.samples.store.path.name not in value['transcripts'][:2])
        current=rows[-1]
        if current['ticket']!=active['ticket'] or current['phase']!='completed':
            raise PhasePending('Original Chat input has not completed; no target observation was borrowed')
        need(same(dict(verb=active['verb'],inputs=active['inputs']),dict(verb=current['verb'],inputs=current['inputs'])))
        phase(active['status'],run=self.samples.run,area='chat',request=active['status']['requestId'],epoch=active['status']['capturedEpochMs'],previous=current['after'])
        return hashlib.sha256(canonical(value)).hexdigest()

    def publish(self):
        pending=None
        with ExitStack() as held:
            for lock in sorted(self.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            try:return self._publish_locked()
            except PhasePending as error:pending=error
        # The original lock intentionally normalizes exceptions. End it cleanly
        # before exposing this narrowly qualified, non-mutating pending phase.
        raise pending

    def _publish_locked(self):
        need(not self.rows or self.rows[-1]['phase'] in ('published','retired'))
        active=self.source.read();digest=self.control(active)
        if self.rows and self.rows[-1]['ticket']==active['ticket']:return None
        need(len(self.rows)<26)
        row=dict(ticket=active['ticket'],sequence=len(self.rows)+1,phase='reading',control=digest,
            before=deepcopy(active['status']),after=None,reference=None)
        self.rows.append(row);self.save();started=self.now()
        measured=self.samples.read(active['ticket'],math.ceil(active['status']['capturedEpochMs']))
        confirmed=self.source.read(active['status']);row.update(after=deepcopy(confirmed['status']),reference=references((self.samples,)))
        if confirmed['ticket']!=active['ticket']:
            row['phase']='retired';self.save();raise PhasePending('Original Chat frame retained under its retired input ticket')
        need(self.control(confirmed)==digest);row['phase']='publishing';self.save()
        # All fields come from this publisher's newly queried original
        # transcript. Parent source references and input results are unused.
        payload=dict(ticket=row['ticket'],actor='owned-observer',actorSequence=row['sequence'],
            capturedEpochMs=measured['capturedEpochMs'],facts=projection('chat',measured['state']))
        wire=deepcopy(payload);fresh_roles((self.samples,),started,self.now)
        self.source.client.request('/runs/'+self.samples.run+'/samples',wire)
        row['phase']='published';self.save();fresh_roles((self.samples,),started,self.now)
        return row['sequence']
