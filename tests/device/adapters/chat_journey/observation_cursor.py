"""Warm source-backed global Chat query cursor, starting at original absence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import math

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.stage_join import opened
from adapters.chat_journey.evidence_archive import stamp,private
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same,unpack,MAX_FRAMES
from feature_journeys.contract import result

VERSION=1


def plain(value):
    """JSON type identity matters as well as canonical bytes."""
    if type(value) is dict:
        need(all(type(key) is str for key in value))
        for field in value.values():plain(field)
    elif type(value) is list:
        for field in value:plain(field)
    else:need(value is None or type(value) in (str,bool,int,float))


class ChatObservationCursor:
    """Actual queries across stage owners; never adopt a completed-looking root.

    Global sequences belong to this complete query history, not to fixture
    phase counts. Local source samples remain byte-for-byte original.
    """
    def __init__(self,initial,store):
        need(type(initial) is ChatObservationOwner and initial.stage=='initial' and not initial.rows and not initial.failed
            and initial.previous is None and initial._freeze_guard is None and type(store) is PrivateFeatureState
            and store.path.parent==initial.store.path.parent and store.path not in
                (initial.store.path,initial.samples.store.path,initial.samples.script_source.store.path,initial.flow_store.path)
            and store.read() is None)
        self.current=initial;self.owners=[initial];self.store=store;self.previous=None;self.rows=[];self.hashes=[]
        self.failed=False;self.root_stamp=None;self.transition_anchor=None;self.started=None;self.query_pending=False
        self._freeze_guard=None
        self.scope=dict(chatObservationCursorVersion=VERSION,runId=initial.source.run,fixtureUrl=initial.source.fixture_url,
            binding=deepcopy(initial.samples.binding),peerBinding=deepcopy(initial.samples.peer_binding),role=initial.samples.role)
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        self.base={**self.scope,'phase':'ready','chunks':[],'stages':[self.stage(initial)]}

    def stage(self,owner):
        return dict(stage=owner.stage,observation=owner.store.path.name,scopeSha256=digest(owner.scope))

    def held(self):
        held=ExitStack()
        try:
            for lock in sorted(self.current.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            return held
        except BaseException:held.close();raise

    def control(self):
        need(not self.failed and not self.current.failed and same(self.store.read(),self.previous)
            and len(self.rows)==len(self.hashes)==len(self.base['chunks'])
            and all(same(self.base[key],value) for key,value in self.scope.items())
            and self.scope['runId']==self.current.source.run and self.scope['fixtureUrl']==self.current.source.fixture_url
            and self.scope['role']==self.current.samples.role and same(self.scope['binding'],self.current.samples.binding)
            and same(self.scope['peerBinding'],self.current.samples.peer_binding))
        if self.root_stamp is not None:need(stamp(self.store.path.lstat())==self.root_stamp)
        plain(self.rows);need([digest(row) for row in self.rows]==self.hashes)
        self.history.verify()
        need(same(self.base['stages'],[self.stage(owner) for owner in self.owners]))
        for owner in self.owners:
            need(not owner.failed and same(owner.store.read(),owner.previous))
            plain(owner.rows);owner.history.verify();owner.samples.history.verify();owner.samples.script_source.history.verify()
            admitted=[row for row in self.rows if self.owners[row['stageIndex']] is owner]
            need(len(owner.rows)==len(admitted)+(1 if self.query_pending and owner is self.current else 0))
            need(all(row['sourceSequence']==index+1 and digest(owner.rows[index])==row['observationSha256']
                for index,row in enumerate(admitted)))

    def bind_freeze(self,guard):
        need(callable(guard) and (self._freeze_guard is None or self._freeze_guard is guard))
        self._freeze_guard=guard

    def query_allowed(self):
        need(not self.failed)
        if self._freeze_guard is not None:need(self._freeze_guard() is True)

    def final(self,started):
        """Read-only final authority for the current original query."""
        self.control();need(self.rows and self.base['phase']=='ready')
        self.original(self.rows[-1]);self.current.final(self.current.rows[-1],started)

    def write(self,phase,**changes):
        self.control();value={**self.base,**deepcopy(changes),'phase':phase};self.store.write(value,self.previous)
        need(same(self.store.read(),value));info=self.store.path.lstat();private(info)
        self.root_stamp=stamp(info);self.previous=self.base=deepcopy(value)

    def original(self,row):
        owner=self.owners[row['stageIndex']];index=row['sourceSequence']-1
        need(integer(index,0,len(owner.rows)-1))
        root=owner.store.read();owner.history.verify();stored=owner.history.store(index).read()
        need(same(root,owner.previous) and root['phase']=='ready' and digest(stored)==root['chunks'][index])
        local=unpack(stored['transcript']);need(len(local)==1 and same(local[0],owner.rows[index])
            and digest(local[0])==row['observationSha256'])
        frame=owner.validate_row(local[0],index+1,owner.rows[index-1]['after'] if index else None)
        need(same(row['sample'],{**local[0]['sample'],'sequence':row['sequence']}))
        return frame

    def select(self,owner):
        """Bind a new stage before querying it; no caller sequence is admitted."""
        self.query_allowed()
        need(type(owner) is ChatObservationOwner and not self.failed and self.rows and not owner.rows
            and not owner.failed and owner.previous is None and owner._freeze_guard is None
            and (self.current.stage,owner.stage) in (('initial','active'),('active','cleanup'))
            and owner.source is self.current.source and owner.flow_store.path==self.current.flow_store.path
            and owner.samples.role==self.scope['role'] and same(owner.samples.binding,self.scope['binding'])
            and same(owner.samples.peer_binding,self.scope['peerBinding'])
            and all(a is b for a,b in zip(owner.samples.locks,self.current.samples.locks))
            and owner.store.path.parent==self.store.path.parent
            and owner.store.path not in {self.store.path,*[value.store.path for value in self.owners]})
        if owner.stage=='active':need(owner.samples.script_source is self.current.samples.script_source)
        else:
            ancestor=owner.samples.script_source
            while ancestor.predecessor is not None:ancestor=ancestor.predecessor
            need(ancestor is self.owners[0].samples.script_source)
        try:
            with self.held():
                self.query_allowed()
                self.control();need(self.base['phase']=='ready')
                anchor=deepcopy(self.original(self.rows[-1]));self.write('selecting',nextStage=self.stage(owner))
                owner.current() # Original flow/admission authority only, no native query.
                stages=[*self.base['stages'],self.stage(owner)]
                self.write('ready',stages=stages,nextStage=None)
                self.current=owner;self.owners.append(owner);self.transition_anchor=anchor
        except Exception:self.failed=True;raise

    def transition(self,frame):
        if self.transition_anchor is None:return
        before=self.transition_anchor
        if self.current.stage=='active':opened(before,frame)
        else:
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

    def clocks(self):
        owner=self.current;role=owner.samples;frame=role.frames[-1]
        oldest=min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))
        oldest=min(oldest,frame['compiledChat']['before']['requestedEpochMs'])
        return [(reader.clock_ms,epoch) for reader,epoch in ((role.primary,oldest),
            (role.peer,frame['peer']['capturedEpochMs']),*role._extra_clocks(frame))]+[
                (owner.source.epoch_ms,owner.source.previous['capturedEpochMs'])]

    def released_fresh(self,clocks,started):
        measured=[]
        for clock,oldest in clocks:
            before=self.current.now();epoch=clock();fresh(oldest,epoch);measured.append((before,epoch,oldest))
        ended=self.current.now()
        need(number(ended,started,started+1.5)
            and all(epoch-oldest+math.ceil((ended-before)*1000)<=1500 for before,epoch,oldest in measured))

    def read(self,after_sequence=0):
        self.query_allowed()
        need(not self.failed and integer(after_sequence,0,len(self.rows)) and len(self.rows)<MAX_FRAMES)
        try:
            with self.held():
                self.query_allowed()
                self.control();need(self.base['phase']=='ready');started=self.current.now()
                self.write('reading');local=self.current.read(len(self.current.rows));self.query_pending=True
                source=self.current.rows[-1];frame=self.current.original_source(source['reference']['index'])
                self.transition(frame)
                row=dict(sequence=len(self.rows)+1,stageIndex=len(self.owners)-1,sourceSequence=source['sequence'],
                    observationSha256=digest(source),sample={**deepcopy(local),'sequence':len(self.rows)+1})
                chunks=self.history.append(row,self.base['chunks']);self.write('ready',chunks=chunks)
                self.rows.append(row);self.hashes.append(digest(row));self.transition_anchor=None;self.query_pending=False
                self.original(row);value=result('feature.chat.observe',deepcopy(row['sample']));self.control()
                self.current.final(source,started);clocks=self.clocks()
            self.released_fresh(clocks,started);self.started=started
            return value
        except Exception:self.failed=True;raise
