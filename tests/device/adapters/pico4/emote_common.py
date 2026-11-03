"""Proposed Parent2 delegates: once-only ordinary input, fresh later effects.

This is the original NativeCycle's optional policy/child journal, never a
second authoritative Parent or recipe. The integrated Parent bridge is not
installed yet; warm captures/public Common composition remain separate gaps.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical,same
from feature_journeys.contract import arguments
from feature_journeys.scenarios import SCENARIOS

VERSION=1
MAX_CALLS=169
OWNED=[]
UNRESOLVED=[]


def plan():
    # Only ordinary inputs enter this policy. Expected state/evidence/variant
    # goals remain in the Common runner; they are not copied into inputs.
    rows=SCENARIOS['emotes']['steps']
    return dict(picoEmoteCommonPlanVersion=VERSION,
        prefix=[dict(verb=row['verb'],inputs=deepcopy(row['inputs'])) for row in rows[:21]],
        sit=dict(minimumCalls=3,maximumCalls=72,cancelBeforeEach=True),
        tail=[dict(verb=row['verb'],inputs=deepcopy(row['inputs'])) for row in rows[24:]],
        maximumActualCalls=MAX_CALLS)


class PicoEmoteCommon:
    def __init__(self):
        self.plan=self._plan=plan();self.plan_bytes=canonical(self.plan)
        self.plan_sha=hashlib.sha256(self.plan_bytes).hexdigest()
        self.parent=self._parent=None;self.file=self._file=None;self.previous=None
        self.store=None;self.chunks=None;self.records=self._records=();self.records_sha=json_digest([])
        self.failed=False;self.host=host_identity();self._pins=None
        self.state=self._state=dict(phase='ready',chunks=[],pending=None,
            cursor=dict(stage='prefix',index=0,sitCalls=0,awaitingSit=False),played=None)
        self.state_bytes=canonical(self.state)
        OWNED.append(self)

    def attach(self,parent):
        from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
        need(type(parent) is PicoEmoteNativeCycle and getattr(parent,'common',None) is self
            and getattr(parent,'version',None)==2 and self.parent is None)
        parent.source.lock.assert_held()
        need(parent.previous is None and parent.state is None and not parent.source.frames and parent.inputs.previous is None)
        self.parent=self._parent=parent
        self.store=PrivateFeatureState(parent.store.path.with_name(parent.store.path.name+'.child-common.json'))
        need(self.store.read() is None)
        self.identity=dict(picoEmoteCommonVersion=VERSION,parentIdentity=deepcopy(parent.identity),planSha256=self.plan_sha)
        self.identity_bytes=canonical(self.identity)
        self.chunks=ChatSourceChunks(self.store,self.identity)
        self.file=self._file=object.__new__(LifecycleProcessFile)
        self._pins=(parent,parent.store,parent.source,parent.source.lock,parent.inputs,parent.effects,parent.lifetime,
            parent.source.monotonic,parent.source.clock_ms,parent.source.phase,self.store,self.store.path,self.chunks)
        try:LifecycleProcessFile.__init__(self.file,self.store);self.guard()
        except BaseException:self.fail();raise

    def fail(self):
        self.failed=True
        if self not in UNRESOLVED:UNRESOLVED.append(self)

    def guard(self):
        need(not self.failed and self.parent is self._parent and self.parent is not None
            and self.parent.common is self and self.parent.version==2 and host_identity()==self.host
            and self.plan is self._plan and canonical(self.plan)==self.plan_bytes
            and hashlib.sha256(self.plan_bytes).hexdigest()==self.plan_sha)
        p=self.parent;s=p.source;pin=self._pins
        s.lock.assert_held()
        need(p is pin[0] and p.store is pin[1] and s is pin[2] and s.lock is pin[3]
            and p.inputs is pin[4] and p.effects is pin[5] and p.lifetime is pin[6]
            and same_callable(s.monotonic,pin[7]) and same_callable(s.clock_ms,pin[8]) and s.phase is pin[9]
            and self.store is pin[10] and self.store.path==pin[11] and self.chunks is pin[12]
            and self.file is self._file and self.state is self._state and canonical(self.state)==self.state_bytes
            and self.records is self._records and json_digest(list(self.records))==self.records_sha
            and canonical(self.identity)==self.identity_bytes and same(self.identity['parentIdentity'],p.identity)
            and self.identity['planSha256']==self.plan_sha==p.identity['commonPlanSha256']
            and self.chunks.root is self.store and self.chunks.root_path==self.store.path
            and self.chunks.scope==json_digest(self.identity))
        exact(self.state,{'phase','chunks','pending','cursor','played'})
        need(self.state['phase'] in ('ready','reading') and type(self.state['chunks']) is list
            and len(self.state['chunks'])==len(self.records))
        if self.state['phase']=='ready':need(self.state['pending'] is None)
        else:
            exact(self.state['pending'],{'sha256'});need(type(self.state['pending']['sha256']) is str
                and len(self.state['pending']['sha256'])==64)
        self.file.guard();need(same(self.store.read(),self.previous));self.chunks.verify()
        if self.previous is None:
            need(same(self.state,dict(phase='ready',chunks=[],pending=None,
                cursor=dict(stage='prefix',index=0,sitCalls=0,awaitingSit=False),played=None)))
        else:
            exact(self.previous,set(self.identity)|{'phase','chunks','state'})
            need(all(same(self.previous[key],value) for key,value in self.identity.items())
                and same(self.previous['state'],self.state) and self.previous['phase']==self.state['phase']
                and same(self.previous['chunks'],self.state['chunks']))
        if p.previous is not None:
            need(p.state is not None and all(same(p.state[key],p.previous['state'][key])
                for key in ('started','epochMs','hostEpochMs')))
        return True

    def write(self,state,*,record=None):
        self.guard()
        if record is None:need(same(state['chunks'],self.state['chunks']))
        else:
            need(self.state['phase']=='reading' and self.state['pending']==dict(sha256=json_digest(record))
                and state['phase']=='ready' and state['pending'] is None
                and state['chunks'][:-1]==self.state['chunks'] and len(state['chunks'])==len(self.records)+1)
            originals=self.chunks.load(state['chunks'])
            need(same(originals,[*self.records,record]))
        value=dict(self.identity,phase=state['phase'],chunks=deepcopy(state['chunks']),state=deepcopy(state))
        try:
            self.file.write(value,self.previous);need(same(self.store.read(),value))
            self.previous=deepcopy(value);self.state=self._state=deepcopy(state);self.state_bytes=canonical(state)
            if record is not None:
                self.records=self._records=(*self._records,deepcopy(record));self.records_sha=json_digest(list(self.records))
            self.guard()
        except BaseException:self.fail();raise

    def append(self,record,**changes):
        self.guard();need(self.state['phase']=='ready')
        state=deepcopy(self.state);state.update(phase='reading',pending=dict(sha256=json_digest(record)))
        self.write(state) # Actual reading intent precedes any immutable child.
        try:
            manifest=self.chunks.append(record,self.state['chunks'])
            state=deepcopy(self.state);state.update(phase='ready',pending=None,chunks=manifest,**deepcopy(changes))
            self.write(state,record=record)
            self.guard();return dict(index=len(manifest)-1,sha256=manifest[-1])
        except BaseException:self.fail();raise

    def original(self,reference):
        self.guard();exact(reference,{'index','sha256'});index=reference['index']
        need(integer(index,0,len(self.state['chunks'])-1) and reference['sha256']==self.state['chunks'][index])
        actual=self.chunks.load(self.state['chunks']);need(same(actual,list(self.records)))
        self.guard();return deepcopy(actual[index])

    def advance(self,call,*,cursor=None):
        cursor=deepcopy(self.state['cursor'] if cursor is None else cursor);stimulus=dict(verb=call['verb'],inputs=call['inputs'])
        if cursor['stage']=='prefix':
            need(stimulus==self.plan['prefix'][cursor['index']]);cursor['index']+=1
            if cursor['index']==len(self.plan['prefix']):cursor.update(stage='sit',index=0)
        elif cursor['stage']=='sit':
            if stimulus==self.plan['tail'][0] and not cursor['awaitingSit']:
                need(cursor['sitCalls']>=self.plan['sit']['minimumCalls']);cursor.update(stage='tail',index=1)
            elif cursor['awaitingSit']:
                need(stimulus==dict(verb='sit',inputs={}) and cursor['sitCalls']<self.plan['sit']['maximumCalls'])
                cursor.update(sitCalls=cursor['sitCalls']+1,awaitingSit=False)
            else:
                need(stimulus==dict(verb='cancel',inputs={}) and cursor['sitCalls']<self.plan['sit']['maximumCalls'])
                cursor['awaitingSit']=True
        else:
            need(cursor['stage']=='tail' and cursor['index']<len(self.plan['tail'])
                and stimulus==self.plan['tail'][cursor['index']]);cursor['index']+=1
            if cursor['index']==len(self.plan['tail']):cursor['stage']='complete'
        return cursor

    def parent_save(self):
        try:self.parent.save()
        except BaseException:self.fail();raise

    def act(self,call):
        self.guard();p=self.parent;p.bound();need(p.state is not None and p.state['phase']=='ready')
        call=deepcopy(arguments('feature.emotes.act',call))
        need(call['runId']==p.source.run and call['fixtureUrl']==p.source.phase.fixture_url
            and len(p.state['steps'])<MAX_CALLS and call['verb']!='background-resume')
        # Background is an explicit still-unfulfilled existing-owner seam, not
        # a synthetic lifecycle result or an ordinary-input fallback.
        rows=p.state['steps']
        for row in rows:need(self.original(row['issued'])['call']['ticket']!=call['ticket'])
        if rows:
            need(rows[-1]['handled'] is not None and rows[-1]['latest'] is not None)
            need('picoEmotePendingRestoreVersion' not in self.original(rows[-1]['latest'])['effect'])
        cursor=self.advance(call)
        floor=p.source.frames[-1]['phaseAfter'];p.inputs.active(call,p.source.phase.status(floor));p.bound()
        issued=self.append(dict(kind='input-issued',call=call,played=deepcopy(self.state['played'])))
        rows.append(dict(issued=issued,handled=None,latest=None));p.state['phase']='input-issued';self.parent_save()
        try:
            p.inputs.act(call) # Exactly once. Its ACK is not a native effect.
            handled=self.append(dict(kind='input-handled',call=call,inputHeader=deepcopy(p.inputs.previous)),cursor=cursor)
            p.state['steps'][-1]['handled']=handled;p.state['phase']='ready';self.parent_save()
            return dict(performed=True)
        except BaseException:p.failed=True;self.fail();raise

    def observe(self):
        self.guard();p=self.parent;p.bound()
        need(p.state is not None and p.state['phase']=='ready' and p.state['steps'])
        row=p.state['steps'][-1];need(row['handled'] is not None)
        call=self.original(row['issued'])['call']
        # Existing native playback proofs require actual advancing samples.
        # Both real acquisitions are charged; neither is an input retry.
        p.source.read();p.source.read();reference=p.effects.reference()
        played=None if call['verb'] in ('play','sit','override') else deepcopy(self.state['played'])
        if p.inputs.state['current']['idleReset'] is not None:played=None
        frame=p.effects.current_original(reference)
        if call['verb'] in ('cancel','wait-complete') and frame['group']['native']['animation']['overrideActive']:
            effect=p.effects.pending_restore(reference,played)
        else:effect=p.effects.measure(reference,played=played)
        changes={}
        if effect.get('playbackReference') is not None:changes['played']=deepcopy(effect['playbackReference'])
        original=self.append(dict(kind='observation',effect=deepcopy(effect)),**changes)
        row['latest']=original;self.parent_save();p.bound();return deepcopy(effect)

    def finished(self):
        self.guard();p=self.parent
        if self.state['cursor']['stage']!='complete' or not p.state['steps']:return False
        row=p.state['steps'][-1]
        if row['latest'] is None:return False
        value=self.original(row['latest'])['effect']
        return value['call']['verb']=='close' and value['state']['panel'] is False

    def validate(self):
        """Validate Parent2 references against actual immutable child originals."""
        self.guard();p=self.parent;state=p.state
        exact(state,{'phase','started','epochMs','hostEpochMs','baseline','steps','cleanup'})
        need(state['phase'] in ('baseline-issued','ready','input-issued')
            and number(state['started'],0,1e15) and integer(state['epochMs'],1)
            and number(state['hostEpochMs'],1,1e15)
            and state['cleanup'] is None and type(state['steps']) is list and len(state['steps'])<=MAX_CALLS)
        if state['baseline'] is None:
            need(state['phase']=='baseline-issued' and not state['steps'] and state['cleanup'] is None);return
        baseline=p.effects.phase_recompute(state['baseline'])
        need(baseline['phase']=='baseline' and baseline['state']['panel'] is False)
        tickets=set();cursor=dict(stage='prefix',index=0,sitCalls=0,awaitingSit=False);played=None
        for index,row in enumerate(state['steps']):
            exact(row,{'issued','handled','latest'});issued=self.original(row['issued'])
            exact(issued,{'kind','call','played'});need(issued['kind']=='input-issued')
            call=arguments('feature.emotes.act',issued['call'])
            need(call['runId']==p.source.run and call['fixtureUrl']==p.source.phase.fixture_url
                and call['ticket'] not in tickets and same(issued['played'],played));tickets.add(call['ticket'])
            next_cursor=self.advance(call,cursor=cursor)
            if row['handled'] is None:
                need(index==len(state['steps'])-1 and state['phase']=='input-issued' and row['latest'] is None);continue
            handled=self.original(row['handled']);exact(handled,{'kind','call','inputHeader'})
            need(handled['kind']=='input-handled' and same(handled['call'],call)
                and row['handled']['index']>row['issued']['index'])
            cursor=next_cursor
            decoded,_history=p.inputs.decode(handled['inputHeader']);current=decoded['current']
            need(current is not None and current['phase']=='acknowledged' and same(current['call'],call))
            if row['latest'] is not None:
                observed=self.original(row['latest']);exact(observed,{'kind','effect'})
                need(observed['kind']=='observation' and row['latest']['index']>row['handled']['index'])
                value=observed['effect'];need(same(value['call'],call))
                if 'picoEmotePendingRestoreVersion' in value:
                    need(index==len(state['steps'])-1)
                    actual=p.effects.pending_restore(value['frame'],issued['played'])
                else:
                    actual=p.effects.recompute(value['frame'],played=None if call['verb'] in ('play','sit','override')
                        or current['idleReset'] is not None else issued['played'],call=call)
                need(same(actual,value))
                if value.get('playbackReference') is not None:played=deepcopy(value['playbackReference'])
            else:need(index==len(state['steps'])-1)
        need(same(cursor,self.state['cursor']) and same(played,self.state['played']))

    def cleanup(self,**options):
        # No placeholder quiet/OS/Actor/root-retirement proof is manufactured.
        # The normal background/warm/final retirement join is still a gap.
        self.guard();need(False)

    def close_host(self):
        """Host finalization only; actual source/Actor retirement is not implied."""
        if self.file is None:return True
        try:value=self.file.close_host()
        except BaseException:self.fail();return False
        self.failed=True
        if not value and self not in UNRESOLVED:UNRESOLVED.append(self)
        return value
