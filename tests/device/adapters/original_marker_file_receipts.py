"""Closed-profile immutable original native marker-file bytes and observed absence receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.native_script_files import NativeScriptFiles,command as file_command
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters import original_marker_clock_queries as clock_queries
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters.graphics_history import restore_native
from adapters.native_clock_source_history import restore as restore_clock_source

VERSION=1


def _profile(value):
    need(value in ('emote','avatar','worldweb'));return value


def _prefix(profile):return 'world-web' if _profile(profile)=='worldweb' else profile


def _key(profile,suffix):return 'ios'+('WorldWeb' if _profile(profile)=='worldweb' else profile.title())+suffix+'Version'


def _ownership_key(profile):return {'emote':'markerFilesVersion','avatar':'avatarMarkerFilesVersion','worldweb':'worldWebFilesVersion'}[_profile(profile)]


def _originals(profile,*args):
    _profile(profile)
    if profile=='emote':
        from ios.adapters.emote_marker_files import originals
    elif profile=='avatar':
        from ios.adapters.avatar_marker_files import originals
    else:
        from ios.adapters.world_web_files import originals
    return originals(*args)


def receipt(value,*,root,binding,run,role,previous=None,profile=None):
    _profile(profile)
    exact(value,{_key(profile,'NativeFileReceipt'),'runId','role','binding','kind','ownership','query','packet','clockJoin'}|clock_queries.fields(profile))
    need(type(value[_key(profile,'NativeFileReceipt')]) is int and value[_key(profile,'NativeFileReceipt')]==VERSION
        and value['runId']==run and value['role']==role and same(value['binding'],binding) and value['kind'] in ('bytes','absent'))
    context(binding);identifier(run);need(role in ('primary','actor'))
    owner=value['ownership'];exact(owner,{'contractVersion',_ownership_key(profile),'runId','ownerToken','binding','hashes','fixtureUrl','ticket','nonce'}|({'baseSourceSha256'} if profile=='worldweb' else set()))
    need(type(owner['contractVersion']) is type(owner[_ownership_key(profile)]) is int and owner['contractVersion']==owner[_ownership_key(profile)]==1
        and same(owner['binding'],binding) and owner['runId']==run)
    if profile=='worldweb':
        import hashlib
        from feature_journeys.fixtures import pinned_resource
        need(owner['baseSourceSha256']==hashlib.sha256(pinned_resource('web-source/client.js')).hexdigest())
    raw=_originals(profile,run,owner['fixtureUrl'],owner['ticket'],owner['nonce'])
    import hashlib
    need(owner['hashes']=={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()})
    query=value['query'];file_command(query,ios=True);need(query['operation']=='observe' and query['runId']==run and query['ownerToken']==owner['ownerToken'])
    p=value['packet'];exact(p,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
    need(type(p['schemaVersion']) is int and p['schemaVersion']==1 and p['requestId']==query['commandId'] and p['operation']=='observe'
        and p['runId']==run and type(p['processId']) is int and p['processId']==int(binding['processIdentity'])
        and integer(p['sequence'],1) and integer(p['requestedEpochMs'],1) and integer(p['capturedEpochMs'],p['requestedEpochMs']))
    identifier(p['instance']);NativeScriptFiles.validate_source(p['source'],'observe',run)
    join=validate_join(value['clockJoin'],dict(files=p));native_prefix(join['nativeBefore'],join['nativeAfter'])
    need(join['nativeBefore']['processId']==p['processId'] and join['nativeBefore']['capturedEpochMs']<=p['requestedEpochMs']
        <=p['capturedEpochMs']<=join['nativeAfter']['capturedEpochMs'])
    clock_queries.bracket(profile,value,int(binding['processIdentity']))
    source=p['source']
    if value['kind']=='bytes':
        need(source['exists'] and all(row['exists'] for row in source['files'])
            and {row['name']:base64.b64decode(row['base64'],validate=True) for row in source['files']}==raw)
    else:need(source==dict(exists=False,files=[]))
    if previous is not None:
        receipt(previous,root=root,binding=binding,run=run,role=role,profile=profile)
        old=previous['packet'];need(old['instance']==p['instance'] and p['sequence']>old['sequence']
            and p['requestId']!=old['requestId'] and p['requestedEpochMs']>=old['capturedEpochMs']
            and same(owner,previous['ownership']))
        native_prefix(previous['clockJoin']['nativeAfter'],join['nativeBefore'])
        need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
    return value


class OriginalMarkerFileReceipts:
    PROFILE=None

    def receipt(self,*args,**kwargs):return receipt(*args,profile=_profile(self.PROFILE),**kwargs)

    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        result.historical=True;result.previous=store.read();result.state=result.decode(value);return result

    def __init__(self,store,root,binding,run,role,lock,guard,*,native,files,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(files,NativeScriptFiles) and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        self.guard,self.native,self.files,self.epoch_ms,self.monotonic=guard,native,files,epoch_ms,monotonic
        if clock_queries.fields(self.PROFILE):
            from adapters.native_feature_observation import NativeFeatureObservation
            need(isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
                and native.pid==int(self.binding['processIdentity']))
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.historical=False;self.previous=store.read();self.state=dict(records=[],pending=None,abandoned=[])
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict({_key(self.PROFILE,'FileReceipts'):VERSION},runId=self.run,role=self.role,binding=self.binding,
        artifactRoot=str(self.root),payload=pack([state]))

    def record_store(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/(_prefix(self.PROFILE)+'-native-files-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def original(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'])
        return self.receipt(value,root=self.root,binding=self.binding,run=self.run,role=self.role)

    def abandoned_store(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/(_prefix(self.PROFILE)+'-native-files-abandoned-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def abandoned(self,reference):
        exact(reference,{'index','sha256'});value=self.abandoned_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'])
        exact(value,{_key(self.PROFILE,'AbandonedFileRead'),'runId','role','binding','payload'})
        need(type(value[_key(self.PROFILE,'AbandonedFileRead')]) is int and value[_key(self.PROFILE,'AbandonedFileRead')]==VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1)
        pending=rows[0];self.partial(pending);need(pending['original'] is None);return pending

    def partial(self,pending):
        exact(pending,{'kind','ownership','query','nativeStart','packet','original'}|(clock_queries.fields(self.PROFILE)|{'priorRecords'} if clock_queries.fields(self.PROFILE) else set()));
        if clock_queries.fields(self.PROFILE):
            need(integer(pending['priorRecords'],0,128));clock_queries.queries(pending['nativeQueries'],int(self.binding['processIdentity']),strict=False)
        need(pending['kind'] in ('bytes','absent'))
        owner=pending['ownership'];need(type(owner) is dict)
        if pending['query'] is not None:
            q=pending['query'];file_command(q,ios=True);need(q['operation']=='observe' and q['runId']==owner['runId'] and q['ownerToken']==owner['ownerToken'])
        if pending['nativeStart'] is not None:
            start=pending['nativeStart'];exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15)
                and number(start['hostBeforeMonotonic'],0,1e15))
            p=start['nativeBefore'];native_packet(p,p['requestId'],int(owner['binding']['processIdentity']),p['capturedEpochMs'])
        if pending['packet'] is not None:
            p=pending['packet'];q=pending['query'];need(q is not None)
            exact(p,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
            need(type(p['schemaVersion']) is int and p['schemaVersion']==1 and p['requestId']==q['commandId'] and p['operation']=='observe'
                and p['runId']==owner['runId'] and type(p['processId']) is int and p['processId']==int(owner['binding']['processIdentity'])
                and integer(p['sequence'],1) and integer(p['requestedEpochMs'],1) and integer(p['capturedEpochMs'],p['requestedEpochMs']))
            identifier(p['instance']);NativeScriptFiles.validate_source(p['source'],'observe',owner['runId'])

    def decode(self,value):
        exact(value,{_key(self.PROFILE,'FileReceipts'),'runId','role','binding','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','pending','abandoned'})
        need(type(state['records']) is list and len(state['records'])<=128 and type(state['abandoned']) is list and len(state['abandoned'])<=128)
        old=None
        for index,ref in enumerate(state['records'],1):
            need(ref['index']==index);current=self.original(ref)
            if old is not None:self.receipt(current,root=self.root,binding=self.binding,run=self.run,role=self.role,previous=old)
            old=current
        pending=state['pending']
        if pending is not None:
            self.partial(pending)
            if pending['original'] is not None:self.receipt(pending['original'],root=self.root,binding=self.binding,run=self.run,role=self.role,previous=old)
        elif not getattr(self,'historical',False):need(len(state['records'])==128 or self.record_store(len(state['records'])+1).read() is None)
        for index,ref in enumerate(state['abandoned'],1):
            need(ref['index']==index);partial=self.abandoned(ref)
            if clock_queries.fields(self.PROFILE):
                need(partial['priorRecords']<=len(state['records']))
                for original in state['records'][partial['priorRecords']:]:
                    clock_queries.floor(self.PROFILE,partial,self.original(original),int(self.binding['processIdentity']))
        if pending is None and not getattr(self,'historical',False):need(len(state['abandoned'])==128 or self.abandoned_store(len(state['abandoned'])+1).read() is None)
        return deepcopy(state)

    def bound(self):self.lock.assert_held();need(not getattr(self,'historical',False) and same(self.store.read(),self.previous) and self.guard() is not False)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def resolve(self):
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if pending['original'] is None:return False
        value=pending['original'];index=len(self.state['records'])+1;store=self.record_store(index);old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        ref=dict(index=index,sha256=digest(value));self.original(ref);self.state['records'].append(ref);self.state['pending']=None;self.save();return True

    def capture(self,kind,ownership):
        with clock_queries.owned(self):return self._capture(kind,ownership)

    def _capture(self,kind,ownership):
        self.bound();need(kind in ('bytes','absent') and self.resolve() and len(self.state['records'])<128)
        if self.state['records']:
            prior=self.original(self.state['records'][-1]);last=prior['clockJoin']['nativeAfter']
            if self.native.sequence==0:
                (restore_native if self.PROFILE=='emote' else restore_clock_source)(self.native,last)
            else:need(self.native.instance==last['instance'] and self.native.sequence>=last['sequence'] and self.native.captured_epoch>=last['capturedEpochMs'])
        else:prior=None
        self.state['pending']=dict(kind=kind,ownership=deepcopy(ownership),query=None,nativeStart=None,packet=None,original=None)
        if clock_queries.fields(self.PROFILE):self.state['pending'].update(nativeQueries=[],priorRecords=len(self.state['records']))
        self.save()
        pending=self.state['pending'];window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(self.epoch_ms());pending['nativeStart']=deepcopy(window.started);self.save()
        old_send=self.files.send
        def send(query):
            need(pending['query'] is None);pending['query']=deepcopy(query);self.save();return old_send(query)
        self.files.send=send
        try:self.files.request('observe',self.run,ownership['ownerToken'])
        finally:self.files.send=old_send
        pending['packet']=deepcopy(self.files.last_packet);self.save();need(pending['packet'] is not None)
        join=window.finish(dict(files=pending['packet']),[('files','capturedEpochMs')])
        value=dict({_key(self.PROFILE,'NativeFileReceipt'):VERSION},runId=self.run,role=self.role,binding=self.binding,kind=kind,
            ownership=deepcopy(ownership),query=deepcopy(pending['query']),packet=deepcopy(pending['packet']),clockJoin=join)
        if clock_queries.fields(self.PROFILE):value['nativeQueries']=deepcopy(pending['nativeQueries'])
        self.receipt(value,root=self.root,binding=self.binding,run=self.run,role=self.role,previous=prior)
        for ref in self.state['abandoned']:
            abandoned=self.abandoned(ref)
            clock_queries.floor(self.PROFILE,abandoned,value,int(self.binding['processIdentity']))
            if abandoned['nativeStart'] is not None:native_prefix(abandoned['nativeStart']['nativeBefore'],join['nativeBefore'])
            if abandoned['packet'] is not None:
                old=abandoned['packet'];need(old['instance']==value['packet']['instance'] and value['packet']['sequence']>old['sequence']
                    and value['packet']['requestedEpochMs']>=old['capturedEpochMs'])
        pending['original']=value;self.save();self.resolve();return deepcopy(self.state['records'][-1])

    def abandon(self):
        self.bound()
        if self.resolve():return True
        need(len(self.state['abandoned'])<128);index=len(self.state['abandoned'])+1;store=self.abandoned_store(index)
        value=dict({_key(self.PROFILE,'AbandonedFileRead'):VERSION},runId=self.run,role=self.role,binding=self.binding,payload=pack([self.state['pending']]))
        old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        ref=dict(index=index,sha256=digest(value));self.abandoned(ref)
        self.state['abandoned'].append(ref);self.state['pending']=None;self.save();return True
