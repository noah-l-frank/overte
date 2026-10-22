"""Original marker API-return/tree/weak lifetime owner, closed to two profiles.

The native CreateEntities DTO remains unchanged. A marker observed in a map is
not an API return, and removal from that map is not EntityItem weak expiry.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import create_entities as native_entities
from ios.adapters.graphics_history import restore_native
from ios.adapters.emote_native_prefix import follow as native_prefix

VERSION=1


def packet(value,*,binding,run,previous=None):
    exact(value,{'markerEntityOriginalVersion','profile','runId','role','binding','query','packet','clockJoin'})
    need(type(value['markerEntityOriginalVersion']) is int and value['markerEntityOriginalVersion']==VERSION
        and value['profile'] in ('emote','avatar') and value['runId']==run and value['role'] in ('primary','actor') and same(value['binding'],binding))
    q,p=value['query'],value['packet'];native_entities.command(q)
    native_entities.validate(p,q,int(binding['processIdentity']))
    need(q['runId']==run)
    originals=dict(entities=p,entitiesClock=dict(capturedEpochMs=p['clockAfter']['epochMs']))
    join=validate_join(value['clockJoin'],originals);native_prefix(join['nativeBefore'],join['nativeAfter'])
    need(join['nativeBefore']['processId']==p['processId'] and join['nativeBefore']['capturedEpochMs']<=p['clockBefore']['epochMs']
        <=p['clockAfter']['epochMs']<=join['nativeAfter']['capturedEpochMs'])
    if previous is not None:
        packet(previous,binding=binding,run=run)
        native_entities.validate(p,q,p['processId'],previous=previous['packet'])
        native_prefix(previous['clockJoin']['nativeAfter'],join['nativeBefore'])
        need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
    return value


def closure(before,after,scope):
    """Join actual submitted VM/code, returned UUID and actual weak death."""
    from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
    from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
    need(isinstance(scope,(IOSEmoteMarkerScope,IOSAvatarMarkerScope)) and type(scope).PROFILE in ('emote','avatar') and scope.state['phase']=='released')
    binding,run=scope.binding,scope.run;packet(before,binding=binding,run=run);packet(after,binding=binding,run=run,previous=before)
    need(before['profile']==after['profile']==type(scope).PROFILE and before['role']==after['role']==scope.role)
    a,b=before['packet'],after['packet'];need(all(p['source'][key]['complete'] for p in (a,b) for key in ('calls','tree')))
    baseline=scope.frames[scope.state['baseline']-1]
    need(before['clockJoin']['hostAfterMonotonic']<=baseline['clockJoin']['hostBeforeMonotonic']
        and before['clockJoin']['nativeAfter']['capturedEpochMs']<=baseline['clockJoin']['nativeBefore']['capturedEpochMs'])
    final=scope.frames[scope.state['quiet'][-1]-1]
    need(a['source']['tree']['treeInstance']==b['source']['tree']['treeInstance']
        ==baseline['world']['source']['tree']['treeInstance']==final['world']['source']['tree']['treeInstance'])
    need(after['clockJoin']['hostBeforeMonotonic']>=final['clockJoin']['hostAfterMonotonic'])
    native_prefix(final['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
    prior_births={row['birth'] for row in a['source']['tree']['entities']}
    no_new_births=all(row['birth'] in prior_births for row in b['source']['tree']['entities'])
    admission=scope.state['admission'];events=b['source']['calls']['events'][len(a['source']['calls']['events']):]
    if admission is None:
        need(scope.state['cleanupMode']=='unloaded' and no_new_births)
        if scope.state['directory'] is not None:
            url=scope.state['directory']+'/script-bundle/main.js'
            need(not any(event['caller']['manager']['url']==url for event in events))
        return dict(kind='unloaded',ownership=None,lifetime=None)
    need(scope.state['loadBarrier'] is not None and a['clockAfter']['epochMs']<=scope.state['loadBarrier'])
    manager,code=admission['manager'],admission['code']
    additions=[event for event in events if event['kind']=='add-returned' and same(event['caller']['manager'],manager) and same(event['caller']['code'],code)]
    if not additions:
        need(admission['marker'] is None and no_new_births and scope.state['cleanupMode'] in ('partial-execution','finished-execution'))
        return dict(kind='not-called',ownership=None,lifetime=None)
    owned=native_entities.returned(b,a,manager,code,after_epoch=scope.state['loadBarrier'])
    if admission['marker'] is not None:need(owned['returned']['entityId']==admission['marker']['id'] and owned['birth'] is not None)
    retired=native_entities.retired(b,owned,after_epoch=scope.state['stopBarrier']['epoch'])
    return dict(kind='null-return' if owned['birth'] is None else 'weak-expired',ownership=owned,lifetime=retired)


class OriginalMarkerEntities:
    PROFILE=None
    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        lock.assert_held();result.previous=store.read();result.state=result.decode(value);return result

    def __init__(self,store,root,binding,run,role,lock,guard,*,native,entities,epoch_ms,monotonic):
        need(type(self).PROFILE in ('emote','avatar') and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(entities,native_entities.IOSCreateEntities) and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        self.guard,self.native,self.entities,self.epoch_ms,self.monotonic=guard,native,entities,epoch_ms,monotonic
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.previous=store.read();self.state=dict(records=[],pending=None,abandoned=[])
        if self.previous is not None:self.state=self.decode(self.previous)
        previous=self.latest()
        if previous is not None:
            if native.sequence==0:restore_native(native,previous['clockJoin']['nativeAfter'])
            else:need(native.instance==previous['clockJoin']['nativeAfter']['instance'] and native.sequence>=previous['clockJoin']['nativeAfter']['sequence'])
            entities.last=deepcopy(previous['packet'])

    def envelope(self,state):return dict(markerEntitiesVersion=VERSION,profile=type(self).PROFILE,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),payload=pack([state]))
    def record_store(self,index):
        need(integer(index,1,256));return PrivateFeatureState(self.root/('marker-entities-'+type(self).PROFILE+'-'+self.run+'-'+self.role+'-'+str(index)+'.json'))
    def original(self,ref):
        exact(ref,{'index','sha256'});value=self.record_store(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'markerEntityRecordVersion','profile','runId','role','binding','payload'})
        need(type(value['markerEntityRecordVersion']) is int and value['markerEntityRecordVersion']==VERSION and value['profile']==type(self).PROFILE
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]
    def latest(self):
        records=self.state['records'];return None if not records else self.original(records[-1])
    def decode(self,value):
        exact(value,{'markerEntitiesVersion','profile','runId','role','binding','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','pending','abandoned'})
        need(all(type(state[k]) is list for k in ('records','abandoned')) and len(state['records'])+len(state['abandoned'])<=256)
        prior=None;indices=[]
        for ref in state['records']:
            current=self.original(ref);packet(current,binding=self.binding,run=self.run,previous=prior);prior=current;indices.append(ref['index'])
        for ref in state['abandoned']:
            abandoned=self.original(ref);self.partial(abandoned);indices.append(ref['index'])
            for later in state['records']:
                if later['index']>ref['index']:self.follow_partial(abandoned,self.original(later))
        need(sorted(indices)==list(range(1,len(indices)+1)))
        if state['pending'] is not None:self.partial(state['pending'])
        elif len(indices)<256:need(self.record_store(len(indices)+1).read() is None)
        return deepcopy(state)
    def partial(self,value):
        exact(value,{'query','nativeStart','packet','original'})
        if value['query'] is not None:native_entities.command(value['query']);need(value['query']['runId']==self.run)
        if value['nativeStart'] is not None:
            start=value['nativeStart'];exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            from adapters.native_feature_observation import validate as native_packet,number
            p=start['nativeBefore'];native_packet(p,p['requestId'],int(self.binding['processIdentity']),p['capturedEpochMs'])
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
        if value['packet'] is not None:native_entities.validate(value['packet'],value['query'],int(self.binding['processIdentity']))
        if value['original'] is not None:
            original=packet(value['original'],binding=self.binding,run=self.run)
            need(same(value['query'],original['query']) and same(value['packet'],original['packet']) and value['nativeStart'] is not None
                and all(same(original['clockJoin'][key],item) for key,item in value['nativeStart'].items()))
    def follow_partial(self,prior,current):
        if prior['nativeStart'] is not None:native_prefix(prior['nativeStart']['nativeBefore'],current['clockJoin']['nativeBefore'])
        if prior['packet'] is not None:native_entities.validate(current['packet'],current['query'],int(self.binding['processIdentity']),previous=prior['packet'])

    def bound(self):self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def retain(self,value):
        index=len(self.state['records'])+len(self.state['abandoned'])+1
        document=dict(markerEntityRecordVersion=VERSION,profile=type(self).PROFILE,runId=self.run,role=self.role,binding=self.binding,payload=pack([value]))
        store=self.record_store(index);old=store.read()
        if old is None:store.write(document,None)
        else:need(same(old,document))
        return dict(index=index,sha256=digest(document))
    def resolve(self):
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if pending['original'] is None:return False
        packet(pending['original'],binding=self.binding,run=self.run,previous=self.latest())
        ref=self.retain(pending['original']);self.state['records'].append(ref);self.state['pending']=None;self.save();return True
    def abandon(self):
        self.bound()
        if self.resolve():return False
        ref=self.retain(self.state['pending']);self.state['abandoned'].append(ref);self.state['pending']=None;self.save();return True
    def capture(self):
        self.bound();need(self.resolve() and len(self.state['records'])+len(self.state['abandoned'])<256)
        prior=self.latest();self.state['pending']=dict(query=None,nativeStart=None,packet=None,original=None);self.save();pending=self.state['pending']
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
        pending['nativeStart']=deepcopy(window.started);self.save();send=self.entities.send
        def wrapped(query):need(pending['query'] is None);pending['query']=deepcopy(query);self.save();return send(query)
        self.entities.send=wrapped
        try:actual=self.entities.read(self.run)
        finally:self.entities.send=send
        pending['packet']=deepcopy(actual);self.save()
        originals=dict(entities=actual,entitiesClock=dict(capturedEpochMs=actual['clockAfter']['epochMs']))
        join=window.finish(originals,[('entitiesClock','capturedEpochMs')]);value=dict(markerEntityOriginalVersion=VERSION,profile=type(self).PROFILE,
            runId=self.run,role=self.role,binding=self.binding,query=deepcopy(pending['query']),packet=actual,clockJoin=join)
        packet(value,binding=self.binding,run=self.run,previous=prior)
        for ref in self.state['abandoned']:
            old=self.original(ref)
            if old['nativeStart'] is not None:native_prefix(old['nativeStart']['nativeBefore'],join['nativeBefore'])
            if old['packet'] is not None:native_entities.validate(actual,pending['query'],actual['processId'],previous=old['packet'])
        pending['original']=value;self.save();self.resolve();return deepcopy(self.state['records'][-1])
    def closed(self,scope):
        self.lock.assert_held();need(self.state['pending'] is None and len(self.state['records'])>=2)
        return closure(self.original(self.state['records'][0]),self.original(self.state['records'][-1]),scope)
