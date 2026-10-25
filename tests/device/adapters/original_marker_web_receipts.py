"""Passive worldless Web originals with durable query and raw-file ownership.

Closed Avatar/Emote profiles preserve WebClosure5 and NativeFeature1 unchanged.
No input, World/Avatar-session getter, Script execution or publication occurs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
import time
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,LIMIT as NATIVE_LIMIT,decode,exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.original_file_reads import record as original_read
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.native_clock_source_history import restore as restore_clock_source
from feature_journeys.contract import identifier
from ios.adapters import web_closures as web
from ios.adapters.emote_native_prefix import follow

VERSION=1
PROFILES={'avatar':'Avatar','emote':'Emote'}


class OriginalMarkerWebReceipts:
    PROFILE=None
    def key(self,name):
        need(self.PROFILE in PROFILES and name in ('Receipts','Raw','Receipt','ClockStart','ClockReference'))
        return 'ios'+PROFILES[self.PROFILE]+'MarkerWeb'+name+'Version'
    def __init__(self,store,root,binding,run,role,lock,guard,*,native,reader,fixture_url,epoch_ms,monotonic):
        need(self.PROFILE in PROFILES and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(reader,web.IOSWebClosures) and isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),context(binding),identifier(run),role,lock
        need(role in ('primary','actor') and native.pid==reader.pid==int(self.binding['processIdentity'])
            and store.path==lock.path.with_name('ios-'+self.PROFILE+'-'+role+'-marker-web.json'))
        self.guard,self.native,self.reader,self.fixture_url=guard,native,reader,fixture_url
        web.command(dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-ios-web-closures',runId=run,fixtureUrl=fixture_url))
        self.epoch_ms,self.monotonic,self.historical=epoch_ms,monotonic,False
        self._storage_init();self.previous=store.read();self.state=dict(rows=[],pending=None,nextOriginal=1)
        if self.previous is not None:self.state=self.parse(self.previous)
    def _storage_init(self):
        self.slot=None;self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,lambda:True,self.storage,
            namespace=self.PROFILE+'-marker-web',schema_prefix=self.PROFILE+'MarkerWeb',monotonic=getattr(self,'monotonic',time.monotonic))
    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock,fixture_url):
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),context(binding),identifier(run),role,lock
        lock.assert_held();need(role in ('primary','actor') and store.path==lock.path.with_name('ios-'+result.PROFILE+'-'+role+'-marker-web.json'))
        result.fixture_url,result.historical,result.previous=fixture_url,True,deepcopy(value)
        result._storage_init();result.state=result.parse(value);return result
    def envelope(self,state):
        return dict({self.key('Receipts'):VERSION},binding=self.binding,runId=self.run,role=self.role,artifactRoot=str(self.root),fixtureUrl=self.fixture_url,payload=pack([state]))
    def bound(self):self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.parse(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def raw(self,ref):
        value=self.originals.read(ref);exact(value,{self.key('Raw'),'query','hex'})
        need(type(value[self.key('Raw')]) is int and value[self.key('Raw')]==1 and type(value['hex']) is str)
        try:raw=bytes.fromhex(value['hex']).decode('utf-8')
        except (ValueError,UnicodeError):need(False)
        need(raw.encode().hex()==value['hex']);return value['query'],raw
    def completed(self,ref):
        state=self.partial_file(ref)
        if state is not None and state['bytes']==ref['bytes']:need(state['sha256']==ref['sha256']);return True
        return False
    def native_original(self,ref):
        query,raw=self.raw(ref);value=decode(raw)
        native_packet(value,query['commandId'],int(self.binding['processIdentity']),value.get('capturedEpochMs'))
        return value
    def native_reference(self,packet):
        p=self.state['pending'];need(p is not None)
        for row in p['nativeQueries']:
            if row['query']['commandId']!=packet['requestId']:continue
            for ref in row['raws']:
                if not self.completed(ref):continue
                query,raw=self.raw(ref)
                try:value=decode(raw)
                except ValueError:continue
                if type(value) is dict and value.get('requestId')==query['commandId']:
                    native_packet(value,query['commandId'],int(self.binding['processIdentity']),value.get('capturedEpochMs'))
                    if same(value,packet):return deepcopy(ref)
        need(False)
    def web_reference(self,p,packet):
        for ref in p['raws']:
            if not self.completed(ref):continue
            query,raw=self.raw(ref)
            try:value=decode(raw)
            except ValueError:continue
            if type(value) is dict and value.get('commandId')==query['commandId'] and same(value,packet):return deepcopy(ref)
        need(False)
    def clock_start(self,value):
        result={key:deepcopy(item) for key,item in value.items() if key!='nativeBefore'}
        result[self.key('ClockStart')]=1;result['nativeBeforeOriginal']=self.native_reference(value['nativeBefore']);return result
    def start_original(self,value):
        exact(value,{self.key('ClockStart'),'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBeforeOriginal'})
        need(type(value[self.key('ClockStart')]) is int and value[self.key('ClockStart')]==1)
        return dict(clockJoinVersion=value['clockJoinVersion'],hostBeforeEpochMs=value['hostBeforeEpochMs'],
            hostBeforeMonotonic=value['hostBeforeMonotonic'],nativeBefore=self.native_original(value['nativeBeforeOriginal']))
    def clock_reference(self,value):
        result={key:deepcopy(item) for key,item in value.items() if key not in ('nativeBefore','nativeAfter')}
        result[self.key('ClockReference')]=1
        for key in ('nativeBefore','nativeAfter'):result[key+'Original']=self.native_reference(value[key])
        return result
    def join_original(self,value):
        exact(value,{self.key('ClockReference'),'clockJoinVersion','hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic',
            'hostAfterMonotonic','sourceTimes','originalsSha256','nativeBeforeOriginal','nativeAfterOriginal'})
        need(type(value[self.key('ClockReference')]) is int and value[self.key('ClockReference')]==1)
        result={key:deepcopy(item) for key,item in value.items() if key not in (self.key('ClockReference'),'nativeBeforeOriginal','nativeAfterOriginal')}
        for key in ('nativeBefore','nativeAfter'):result[key]=self.native_original(value[key+'Original'])
        return result
    def partial_file(self,ref):
        self.originals.original(ref);path=self.originals.path(ref)
        if ref['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),ref);raw=stream.read(ref['bytes']+1);self.originals.file(path,stream.fileno(),ref)
        need(len(raw)<=ref['bytes'])
        if ref['phase']=='saved':need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'])
        original_read(path)
        return dict(file=deepcopy(ref['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    def descriptors(self,p):
        rows=[ref for row in p['nativeQueries'] for ref in row['raws']]+p['raws']
        if p['receipt'] is not None:rows.append(p['receipt'])
        return rows
    def partial(self,p):
        exact(p,{'index','nativeQueries','query','raws','nativeStart','receipt'})
        need(integer(p['index'],1,64) and type(p['nativeQueries']) is list and len(p['nativeQueries'])<=128 and type(p['raws']) is list and len(p['raws'])<=16)
        nonces=set()
        for row in p['nativeQueries']:
            exact(row,{'query','raws'});query=row['query'];exact(query,{'schemaVersion','commandId','action'})
            need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']=='feature-native-observe'
                and type(query['commandId']) is str and query['commandId'].startswith('ios-'))
            identifier(query['commandId'][4:]);need(query['commandId'] not in nonces);nonces.add(query['commandId'])
            need(type(row['raws']) is list and len(row['raws'])<=51)
        if p['query'] is not None:need(web.command(p['query'])['runId']==self.run and p['query']['fixtureUrl']==self.fixture_url)
        else:need(not p['raws'])
        if p['nativeStart'] is not None:
            start=self.start_original(p['nativeStart'])
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            native_packet(start['nativeBefore'],start['nativeBefore']['requestId'],int(self.binding['processIdentity']),start['nativeBefore']['capturedEpochMs'])
            need(any(same(ref,p['nativeStart']['nativeBeforeOriginal']) for row in p['nativeQueries'] for ref in row['raws']))
        for ref in self.descriptors(p):
            self.originals.original(ref);self.partial_file(ref)
        for row in p['nativeQueries']:
            for ref in row['raws']:
                if self.completed(ref):query,raw=self.raw(ref);need(same(query,row['query']))
        for ref in p['raws']:
            if self.completed(ref):query,raw=self.raw(ref);need(same(query,p['query']))
        return p
    def native_floor(self,p):
        result=None
        for row in p['nativeQueries']:
            accepted=None
            for ref in row['raws']:
                if not self.completed(ref):continue
                query,raw=self.raw(ref)
                try:value=decode(raw)
                except ValueError:continue
                if type(value) is not dict or value.get('requestId')!=query['commandId']:continue
                native_packet(value,query['commandId'],int(self.binding['processIdentity']),value.get('capturedEpochMs'))
                if accepted is not None:need(same(accepted,value))
                else:
                    if result is not None:follow(result,value)
                    accepted=result=value
        return result
    def web_floor(self,p):
        result=None
        for ref in p['raws']:
            if not self.completed(ref):continue
            query,raw=self.raw(ref)
            try:value=decode(raw)
            except ValueError:continue
            if type(value) is not dict or value.get('commandId')!=query['commandId']:continue
            web.validate(value,query,int(self.binding['processIdentity']),value.get('capturedEpochMs'))
            if result is not None:need(same(result,value))
            result=value
        return result
    def packet(self,row,previous=None):
        p=row['partial'];need(p['receipt'] is not None and p['receipt']['phase']=='saved');value=self.originals.read(p['receipt'])
        exact(value,{self.key('Receipt'),'binding','runId','role','query','webOriginal','clockReference'})
        need(type(value[self.key('Receipt')]) is int and value[self.key('Receipt')]==1 and same(value['binding'],self.binding)
            and value['runId']==self.run and value['role']==self.role and same(value['query'],p['query']))
        need(value['webOriginal'] in p['raws']);query,raw=self.raw(value['webOriginal']);need(same(query,p['query']))
        packet=decode(raw);join=validate_join(self.join_original(value['clockReference']),dict(web=packet));pid=int(self.binding['processIdentity'])
        for key in ('nativeBeforeOriginal','nativeAfterOriginal'):
            need(any(same(ref,value['clockReference'][key]) for row in p['nativeQueries'] for ref in row['raws']))
        web.validate(packet,p['query'],pid,join['nativeAfter']['capturedEpochMs']);need(packet['iosWebClosureVersion']==5)
        need(join['nativeBefore']['processId']==pid and same(self.native_floor(p),join['nativeAfter'])
            and same(self.web_floor(p),packet) and same(self.start_original(p['nativeStart']),{key:join[key] for key in ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')}))
        if previous is not None:follow(previous['clockJoin']['nativeAfter'],join['nativeBefore']);web.continuity(previous['packet'],packet,pid)
        return dict(**{self.key('Receipt'):1},binding=deepcopy(self.binding),runId=self.run,role=self.role,query=deepcopy(p['query']),packet=packet,clockJoin=join)
    def floors(self,p,current):
        self.partial(p);last=self.native_floor(p)
        if last is not None:follow(last,current['clockJoin']['nativeBefore'])
        if p['nativeStart'] is not None:follow(self.start_original(p['nativeStart'])['nativeBefore'],current['clockJoin']['nativeBefore'])
        previous=self.web_floor(p)
        if previous is not None:web.continuity(previous,current['packet'],int(self.binding['processIdentity']))
    def parse(self,value):
        exact(value,{self.key('Receipts'),'binding','runId','role','artifactRoot','fixtureUrl','payload'})
        states=unpack(value['payload']);need(len(states)==1 and same(value,self.envelope(states[0])));state=states[0];exact(state,{'rows','pending','nextOriginal'})
        need(type(state['rows']) is list and len(state['rows'])<=64 and integer(state['nextOriginal'],1,MAX_FRAMES+1));indices=[];last=None;abandoned=[]
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','status','partial','files'});need(type(row['index']) is int and row['index']==index and row['status'] in ('observed','abandoned'))
            p=self.partial(row['partial']);need(p['index']==index and same(row['files'],[self.partial_file(ref) for ref in self.descriptors(p)]))
            indices.extend(ref['index'] for ref in self.descriptors(p))
            if row['status']=='observed':
                current=self.packet(row,last)
                for old in abandoned:self.floors(old,current)
                last=current
            else:abandoned.append(p)
        if state['pending'] is not None:
            p=self.partial(state['pending']);need(p['index']==len(state['rows'])+1);indices.extend(ref['index'] for ref in self.descriptors(p))
        need(sorted(indices)==list(range(1,state['nextOriginal'])) and len(set(indices))==len(indices))
        return deepcopy(state)
    def storage(self,kind,value):
        self.bound();p=self.state['pending'];need(kind=='original' and p is not None and self.slot is not None)
        self.originals.original(value);slot,name=self.slot
        rows=p['nativeQueries'][-1]['raws'] if slot=='native' else p['raws'] if slot=='web' else None
        old=p['receipt'] if rows is None else rows[-1] if rows and rows[-1]['phase']!='saved' else None
        if old is None:need(value['phase']=='planned' and value['index']==self.state['nextOriginal']);self.state['nextOriginal']+=1
        else:need(value['phase']=={'planned':'opened','opened':'saved'}[old['phase']] and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        if rows is None:p['receipt']=deepcopy(value)
        elif old is None:rows.append(deepcopy(value))
        else:rows[-1]=deepcopy(value)
        self.save()
    def write(self,slot,frame):
        need(self.slot is None);self.slot=(slot,None)
        try:return self.originals.write(self.state['nextOriginal'],frame)
        finally:self.slot=None
    def raw_return(self,slot,query,raw):
        need(type(raw) is str and len(raw.encode())<=(NATIVE_LIMIT if slot=='native' else web.LIMIT))
        self.write(slot,{self.key('Raw'):1,'query':deepcopy(query),'hex':raw.encode().hex()});return raw
    @contextmanager
    def transports(self):
        send,read=self.native.send,self.native.original;wsend,wread=self.reader.send,self.reader.original
        def native_send(q):self.state['pending']['nativeQueries'].append(dict(query=deepcopy(q),raws=[]));self.save();return send(q)
        def native_read():return self.raw_return('native',self.state['pending']['nativeQueries'][-1]['query'],read())
        def web_send(q):need(self.state['pending']['query'] is None);self.state['pending']['query']=deepcopy(q);self.save();return wsend(q)
        def web_read():return self.raw_return('web',self.state['pending']['query'],wread())
        self.native.send,self.native.original,self.reader.send,self.reader.original=native_send,native_read,web_send,web_read
        try:yield
        finally:self.native.send,self.native.original,self.reader.send,self.reader.original=send,read,wsend,wread
    def finish(self,status):
        self.bound();p=self.state['pending'];need(p is not None);row=dict(index=p['index'],status=status,partial=deepcopy(p),files=[self.partial_file(ref) for ref in self.descriptors(p)])
        self.state['rows'].append(row);self.state['pending']=None;self.save();return deepcopy(row)
    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return
        self.partial(p)
        # Only already-complete bytes can be adopted. A missing/lost source
        # query gets no resend; its exact raw and partial inodes stay retained.
        if p['receipt'] is not None and p['receipt']['phase'] in ('opened','saved'):
            try:self.originals.read(p['receipt'])
            except Exception:self.finish('abandoned');return
            p['receipt']['phase']='saved';self.save();self.finish('observed');return
        self.finish('abandoned')
    def capture(self):
        self.bound();self.recover();need(len(self.state['rows'])<64);last_native=last_web=None
        for row in self.state['rows']:
            a,b=self.native_floor(row['partial']),self.web_floor(row['partial'])
            if a is not None:last_native=a
            if b is not None:last_web=b
        if last_native is not None:
            if self.native.sequence==0:restore_clock_source(self.native,last_native)
            else:need(self.native.instance==last_native['instance'] and self.native.sequence>=last_native['sequence'])
        self.reader.last=deepcopy(last_web)
        self.state['pending']=dict(index=len(self.state['rows'])+1,nativeQueries=[],query=None,raws=[],nativeStart=None,receipt=None);self.save()
        with self.transports():
            window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
            p=self.state['pending'];p['nativeStart']=self.clock_start(window.started);self.save();packet=self.reader.read(self.run,self.fixture_url)
            join=window.finish(dict(web=packet),[('web','capturedEpochMs')])
        web_original=self.web_reference(p,packet)
        body=dict({self.key('Receipt'):1},binding=self.binding,runId=self.run,role=self.role,query=deepcopy(p['query']),
            webOriginal=deepcopy(web_original),clockReference=self.clock_reference(join))
        self.write('receipt',body);row=self.finish('observed');self.bound();a=join;now,mono=self.epoch_ms(),self.monotonic()
        need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500 and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250)
        return row
