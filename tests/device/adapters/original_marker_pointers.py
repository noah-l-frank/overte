"""Durable passive Qt originals and actual marker pointer retirement.

A W3C release acknowledgement never establishes contact or callback drainage.
Every passive query has a durable nonce and an interrupted query is retained,
then superseded by a different read; input is never repeated here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters import original_marker_clock_queries as clock_queries
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import pointer_state
from ios.adapters.emote_native_prefix import follow
from ios.adapters.graphics_history import restore_native

VERSION=1


def _profile(value):
    need(value in ('emote','avatar','worldweb'));return value


def _prefix(profile):return 'world-web' if _profile(profile)=='worldweb' else profile


def _key(profile,suffix):return 'ios'+('WorldWeb' if _profile(profile)=='worldweb' else profile.title())+suffix+'Version'


def receipt(value,binding,run,role,previous=None,profile=None):
    _profile(profile)
    exact(value,{_key(profile,'PointerReceipt'),'runId','role','binding','query','packet','clockJoin'}|clock_queries.fields(profile))
    need(type(value[_key(profile,'PointerReceipt')]) is int and value[_key(profile,'PointerReceipt')]==1
        and value['runId']==run and value['role']==role and same(value['binding'],binding))
    context(binding);identifier(run);need(role in ('primary','actor'));query=pointer_state.command(value['query']);p=value['packet']
    join=validate_join(value['clockJoin'],dict(pointer=p,pointerClock=dict(capturedEpochMs=p['clockAfter']['epochMs'])));pid=int(binding['processIdentity'])
    pointer_state.validate(p,query,pid,previous=None if previous is None else previous['packet'])
    need(query['runId']==run and join['nativeBefore']['processId']==pid and join['nativeBefore']['capturedEpochMs']
        <=p['clockBefore']['epochMs']<=p['clockAfter']['epochMs']<=join['nativeAfter']['capturedEpochMs'])
    clock_queries.bracket(profile,value,pid)
    follow(join['nativeBefore'],join['nativeAfter'])
    if previous is not None:
        receipt(previous,binding,run,role,profile=profile);follow(previous['clockJoin']['nativeAfter'],join['nativeBefore'])
        need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']
            and join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs'])
    return value


def zero(packet):
    pointer_state.original(packet);state=packet['source']
    need(state['complete'] and state['startup']['observed'] and state['pendingDispatches']==0 and state['contacts']==[]
        and state['qtMouseButtons']==0 and state['worldTapActive'] is False)


class OriginalMarkerPointers:
    PROFILE=None

    def receipt(self,*args,**kwargs):return receipt(*args,profile=_profile(self.PROFILE),**kwargs)

    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result.historical=True;result.previous=store.read();result.state=result.decode(value);return result

    def __init__(self,store,root,binding,run,role,lock,guard,*,native,pointer,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(pointer,pointer_state.IOSPointerState)
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        self.guard,self.native,self.pointer,self.epoch_ms,self.monotonic=guard,native,pointer,epoch_ms,monotonic
        if clock_queries.fields(self.PROFILE):
            from adapters.native_feature_observation import NativeFeatureObservation
            need(isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
                and native.pid==int(self.binding['processIdentity']))
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.historical=False;self.previous=store.read();self.state=dict(records=[],abandoned=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict({_key(self.PROFILE,'Pointers'):VERSION},runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),payload=pack([state]))

    def file(self,index,abandoned=False):
        need(integer(index,1,512));return PrivateFeatureState(self.root/(_prefix(self.PROFILE)+'-pointer-'+('abandoned-' if abandoned else '')+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def original(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{_key(self.PROFILE,'PointerOriginal'),'payload'});need(type(value[_key(self.PROFILE,'PointerOriginal')]) is int and value[_key(self.PROFILE,'PointerOriginal')]==1)
        rows=unpack(value['payload']);need(len(rows)==1);return self.receipt(rows[0],self.binding,self.run,self.role)

    def partial(self,value):
        exact(value,{'priorRecords','nativeStart','query','raw','original'}|clock_queries.fields(self.PROFILE));
        if clock_queries.fields(self.PROFILE):clock_queries.queries(value['nativeQueries'],int(self.binding['processIdentity']),strict=False)
        need(integer(value['priorRecords'],0,512))
        if value['nativeStart'] is not None:
            start=value['nativeStart'];exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            p=start['nativeBefore'];native_packet(p,p['requestId'],int(self.binding['processIdentity']),p['capturedEpochMs'])
        if value['query'] is not None:need(value['nativeStart'] is not None and pointer_state.command(value['query'])['runId']==self.run)
        if value['raw'] is not None:need(value['query'] is not None and type(value['raw']) is str and len(value['raw'].encode())<=pointer_state.LIMIT)
        if value['original'] is not None:
            item=self.receipt(value['original'],self.binding,self.run,self.role)
            need(same(value['nativeStart'],{key:item['clockJoin'][key] for key in value['nativeStart']}) and same(item['query'],value['query'])
                and same(json.loads(value['raw']),item['packet']))
        return value

    def abandoned(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index'],True).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{_key(self.PROFILE,'PointerAbandoned'),'runId','role','binding','payload'})
        need(type(value[_key(self.PROFILE,'PointerAbandoned')]) is int and value[_key(self.PROFILE,'PointerAbandoned')]==1 and value['runId']==self.run
            and value['role']==self.role and same(value['binding'],self.binding));rows=unpack(value['payload']);need(len(rows)==1)
        result=self.partial(rows[0]);need(result['original'] is None);return result

    def decode(self,value):
        exact(value,{_key(self.PROFILE,'Pointers'),'runId','role','binding','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','abandoned','pending'})
        need(all(type(state[key]) is list and len(state[key])<=512 for key in ('records','abandoned')))
        previous=None
        for index,ref in enumerate(state['records'],1):
            need(ref['index']==index);item=self.original(ref);self.receipt(item,self.binding,self.run,self.role,previous);previous=item
        for index,ref in enumerate(state['abandoned'],1):
            need(ref['index']==index);partial=self.abandoned(ref);need(partial['priorRecords']<=len(state['records']))
            if partial['priorRecords'] and partial['nativeStart'] is not None:
                prior=self.original(state['records'][partial['priorRecords']-1])['clockJoin'];start=partial['nativeStart']
                follow(prior['nativeAfter'],start['nativeBefore'])
                need(prior['hostAfterEpochMs']<=start['hostBeforeEpochMs'] and prior['hostAfterMonotonic']<=start['hostBeforeMonotonic'])
            for later in state['records'][partial['priorRecords']:]:self.floors(partial,self.original(later))
        if state['pending'] is not None:
            self.partial(state['pending']);need(state['pending']['priorRecords']==len(state['records']))
        elif not getattr(self,'historical',False):need(len(state['records'])==512 or self.file(len(state['records'])+1).read() is None)
        if not getattr(self,'historical',False):need(len(state['abandoned'])==512 or self.file(len(state['abandoned'])+1,True).read() is None)
        return deepcopy(state)

    def bound(self):self.lock.assert_held();need(not getattr(self,'historical',False) and same(self.store.read(),self.previous) and self.guard() is not False)

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def resolve(self):
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if pending['original'] is None:return False
        index=len(self.state['records'])+1;value=dict({_key(self.PROFILE,'PointerOriginal'):1},payload=pack([pending['original']]))
        store=self.file(index);existing=store.read()
        if existing is None:store.write(value,None)
        else:need(same(existing,value))
        ref=dict(index=index,sha256=digest(value));self.original(ref);self.state['records'].append(ref);self.state['pending']=None;self.save();return True

    def abandon(self):
        self.bound()
        if self.resolve():return True
        index=len(self.state['abandoned'])+1;need(index<=512);store=self.file(index,True)
        value=dict({_key(self.PROFILE,'PointerAbandoned'):1},runId=self.run,role=self.role,binding=self.binding,payload=pack([self.state['pending']]))
        existing=store.read()
        if existing is None:store.write(value,None)
        else:need(same(existing,value))
        ref=dict(index=index,sha256=digest(value));self.abandoned(ref);self.state['abandoned'].append(ref);self.state['pending']=None;self.save();return True

    def capture(self):
        with clock_queries.owned(self):return self._capture()

    def _capture(self):
        self.bound();need(self.resolve() and len(self.state['records'])<512)
        prior=None if not self.state['records'] else self.original(self.state['records'][-1])
        if prior is not None:
            last=prior['clockJoin']['nativeAfter']
            if self.native.sequence==0:restore_native(self.native,last)
            else:need(self.native.instance==last['instance'] and self.native.sequence>=last['sequence'] and self.native.captured_epoch>=last['capturedEpochMs'])
            self.pointer.last=deepcopy(prior['packet'])
        self.state['pending']=dict(priorRecords=len(self.state['records']),nativeStart=None,query=None,raw=None,original=None)
        if clock_queries.fields(self.PROFILE):self.state['pending']['nativeQueries']=[]
        self.save();pending=self.state['pending']
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
        pending['nativeStart']=deepcopy(window.started);self.save();send,read=self.pointer.send,self.pointer.original
        def sending(query):
            need(pending['query'] is None);pending['query']=deepcopy(query);self.save();return send(query)
        def reading():
            raw=read();need(type(raw) is str and len(raw.encode())<=pointer_state.LIMIT)
            pending['raw']=raw;self.save();return raw
        self.pointer.send,self.pointer.original=sending,reading
        try:packet=self.pointer.read(self.run)
        finally:self.pointer.send,self.pointer.original=send,read
        join=window.finish(dict(pointer=packet,pointerClock=dict(capturedEpochMs=packet['clockAfter']['epochMs'])),[('pointerClock','capturedEpochMs')])
        value=dict({_key(self.PROFILE,'PointerReceipt'):1},runId=self.run,role=self.role,binding=self.binding,
            query=deepcopy(pending['query']),packet=packet,clockJoin=join)
        if clock_queries.fields(self.PROFILE):value['nativeQueries']=deepcopy(pending['nativeQueries'])
        self.receipt(value,self.binding,self.run,self.role,prior)
        for ref in self.state['abandoned']:self.floors(self.abandoned(ref),value)
        pending['original']=value;self.save();need(self.resolve());return deepcopy(self.state['records'][-1])

    def floors(self,partial,current):
        """Replay every qualified abandoned source floor independently.

        priorRecords is the actual durable owner position before issuing the
        query. Earlier completed baselines are never compared to a later raw
        return. Stale files with another nonce remain bytes, not this query's
        accepted native source.
        """
        self.partial(partial);clock_queries.floor(self.PROFILE,partial,current,int(self.binding['processIdentity']));join=current['clockJoin'];start=partial['nativeStart']
        if start is not None:
            follow(start['nativeBefore'],join['nativeBefore'])
            need(join['hostBeforeEpochMs']>=start['hostBeforeEpochMs'] and join['hostBeforeMonotonic']>=start['hostBeforeMonotonic'])
        if partial['raw'] is None:return
        try:packet=json.loads(partial['raw'])
        except (ValueError,TypeError):return
        query=partial['query']
        if type(packet) is not dict or packet.get('requestId')!=query['commandId']:return
        pointer_state.validate(packet,query,int(self.binding['processIdentity']))
        need(start['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs'])
        pointer_state.validate(current['packet'],current['query'],int(self.binding['processIdentity']),previous=packet)

    def closed(self,scope):
        """Common measured quiet across Scope and unchanged Qt event originals."""
        need(scope.PROFILE==self.PROFILE)
        self.decode(self.envelope(self.state))
        need(self.state['pending'] is None and len(self.state['records'])>=4 and scope.state['phase']=='released'
            and scope.state['quiet'][-1]==len(scope.frames))
        rows=[self.original(ref) for ref in self.state['records']];baseline=rows[0];zero(baseline['packet'])
        scope_baseline=scope.frames[scope.state['baseline']-1]['clockJoin'];follow(baseline['clockJoin']['nativeAfter'],scope_baseline['nativeBefore'])
        quiet=[scope.frames[index-1] for index in scope.state['quiet']]
        return self.quiet(quiet,baseline=baseline)

    def quiet(self,quiet,*,baseline=None):
        need(len(quiet)>=3)
        rows=[self.original(ref) for ref in self.state['records']]
        baseline=rows[0] if baseline is None else baseline
        first,last=quiet[0],quiet[-1]
        # Pointer source and World use separate elapsed-clock origins. Compare
        # their original epochs and host brackets for containment; compare
        # elapsed durations only within each actual source's own clock.
        left=[row for row in rows if row['clockJoin']['hostAfterMonotonic']<=first['clockJoin']['hostBeforeMonotonic']
            and row['clockJoin']['nativeAfter']['capturedEpochMs']<=first['clockJoin']['nativeBefore']['requestedEpochMs']]
        right=[row for row in rows if row['clockJoin']['hostBeforeMonotonic']>=last['clockJoin']['hostAfterMonotonic']
            and row['clockJoin']['nativeBefore']['requestedEpochMs']>=last['clockJoin']['nativeAfter']['capturedEpochMs']]
        need(left and right);a,b=left[-1],right[-1]
        follow(a['clockJoin']['nativeAfter'],first['clockJoin']['nativeBefore'])
        follow(last['clockJoin']['nativeAfter'],b['clockJoin']['nativeBefore'])
        pointer_state.drained(baseline['packet'],b['packet'],after_epoch=baseline['packet']['clockAfter']['epochMs'])
        selected=[row for row in rows if a['packet']['sequence']<=row['packet']['sequence']<=b['packet']['sequence']]
        for row in selected:
            zero(row['packet']);need(same(row['packet']['source']['events'],a['packet']['source']['events']))
        u,v=a['packet']['clockAfter'],b['packet']['clockBefore']
        need(3000<=v['epochMs']-u['epochMs']<60000 and 3000<=v['monotonicMs']-u['monotonicMs']<60000)
        return dict(first=a,last=b,quietLast=right[0],scopeFirst=first,scopeLast=last)
