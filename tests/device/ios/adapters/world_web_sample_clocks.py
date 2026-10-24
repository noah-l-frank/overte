"""Every real native clock query of one GPU owner, before send and as raw bytes.

This owns passive observation uncertainty only. No clock, process, callback,
renderer result, native resource absence or host-time substitute is generated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import re
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,LIMIT
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters.world_web_clock_validation import queries
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_native_prefix import follow
from ios.adapters.world_web_api_clock import check

MAX_QUERIES=1024


class WorldWebSampleClocks:
    def __init__(self,store,root,binding,run,request,lock,guard,*,native,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(native,NativeFeatureObservation)
            and native.ios and not native.native_clock_bound and callable(guard) and callable(monotonic))
        self.store,self.root,self.binding,self.run,self.request,self.lock,self.guard,self.native,self.monotonic=store,root,deepcopy(context(binding)),identifier(run),request,lock,guard,native,monotonic
        need(type(request) is str and request.startswith('ios-'));identifier(request[4:]);need(native.pid==int(binding['processIdentity']))
        self.lock.assert_held();self.frames=OriginalFrameStore(root,binding,run,'primary',guard,self.intent,namespace='wwc-'+request[4:28],schema_prefix='worldWebGPUClock',monotonic=monotonic)
        self.previous=store.read();self.state=dict(entries=[],storage={});self._raw_cache={}
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosWorldWebGPUClocksVersion=1,binding=self.binding,runId=self.run,requestId=self.request,payload=pack([state]))
    def bound(self):
        check();self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();need(type(self.state['entries']) is list and len(self.state['entries'])<=MAX_QUERIES and type(self.state['storage']) is dict and len(self.state['storage'])<=1024)
        value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def intent(self,kind,value):
        need(kind=='original');self.frames.original(value);key=str(value['index']);old=self.state['storage'].get(key)
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[field],old[field]) for field in value if field not in ('phase','file')))
        self.state['storage'][key]=deepcopy(value);self.save()
    @staticmethod
    def pin(path,pins):
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        value=EmoteOriginalLease.signature(path.lstat())
        if path in pins:need(pins[path]==value)
        else:pins[path]=value

    def context(self):
        return (deepcopy(self.binding),self.run,self.request,self.native.pid,self.native.instance,
            str(self.store.path),str(self.root),id(self.frames),str(self.frames.root),
            deepcopy(self.frames.binding),self.frames.run,self.frames.role,self.frames.namespace,self.frames.schema_prefix)

    @contextmanager
    def immutable_queries(self):
        # A local read guard, not a retained verdict cache. No query or write
        # occurs here; all actual raw carriers are still read and hashed.
        self.lock.assert_held();header=self.context();pins={};self.pin(self.store.path,pins)
        current=self.store.read();need(current is not None)
        try:yield current,pins
        finally:
            self.lock.assert_held();need(same(header,self.context()) and same(self.store.read(),current))
            for path in pins:self.pin(path,pins)
            check()

    def raw(self,reference,query_index,raw_index,query,*,pins=None):
        actual=self.frames.expand(reference);path=self.frames.path(actual)
        if pins is not None:self.pin(path,pins)
        body=self.frames.read(actual)
        if pins is not None:self.pin(path,pins)
        exact(body,{'requestId','queryIndex','rawIndex','query','raw'})
        need(body['requestId']==self.request and type(body['queryIndex']) is type(body['rawIndex']) is int and body['queryIndex']==query_index
            and body['rawIndex']==raw_index and same(body['query'],query) and type(body['raw']) is str and len(body['raw'].encode())<=LIMIT)
        return body['raw']
    @staticmethod
    def query(value):
        exact(value,{'schemaVersion','commandId','action'});need(type(value['schemaVersion']) is int and value['schemaVersion']==1
            and value['action']=='feature-native-observe' and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    def rows(self,state,*,pins=None):
        rows=[];seen=set()
        for index,entry in enumerate(state['entries'],1):
            exact(entry,{'query','raws'});self.query(entry['query']);nonce=entry['query']['commandId'];need(nonce not in seen);seen.add(nonce)
            need(type(entry['raws']) is list and len(entry['raws'])<=51)
            rows.append(dict(query=deepcopy(entry['query']),raws=[self.raw(reference,index,offset,entry['query'],pins=pins) for offset,reference in enumerate(entry['raws'],1)]))
        return rows
    def accepted(self,state=None,*,pins=None):
        return self.accepted_rows(self.rows(self.state if state is None else state,pins=pins))

    def accepted_rows(self,rows):
        # These are freshly read original rows, never a retained decoder cache.
        # Validate chunks independently and preserve the first native floor.
        first=previous=None
        for offset in range(0,len(rows),128):
            batch=rows[offset:offset+128];current=queries(batch,self.native.pid);begin=None
            for row in batch:
                begin=queries([row],self.native.pid)
                if begin is not None:break
            if begin is not None:
                if first is None:first=begin
                if previous is not None:follow(previous,begin)
            if current is not None:previous=current
        return first,previous
    def last(self,state=None):return self.accepted(state)[1]
    def snapshot(self):
        self.bound();need(self.previous is not None);self.decode(self.previous);return deepcopy(self.previous)
    @staticmethod
    def prefix(old,current):
        count=len(old['entries'])
        need(same(current['entries'][:count],old['entries'])
            and all(same(current['storage'].get(key),original) for key,original in old['storage'].items()))

    def endpoints(self,rows):
        first=last=None
        for row in rows:
            first=queries([row],self.native.pid)
            if first is not None:break
        for row in reversed(rows):
            last=queries([row],self.native.pid)
            if last is not None:break
        return first,last

    def retained(self,value):
        with self.immutable_queries() as (current_value,pins):
            current,_points,rows=self.decoded(current_value,pins=pins,with_rows=True)
            old=self.shape(value);self.prefix(old,current)
            return deepcopy(self.endpoints(rows[:len(old['entries'])]))

    def interval(self,before,after):
        """Validate current native bytes once, then exact literal prefixes.

        Old/new entries include the same query nonces AND immutable raw-file
        references/storage as the already fully checked current journal. No
        historical packet is relabeled; only its actual selected tail joins.
        """
        with self.immutable_queries() as (current_value,pins):
            current,_points,rows=self.decoded(current_value,pins=pins,with_rows=True)
            old=self.shape(before);new=self.shape(after);count=len(old['entries'])
            self.prefix(old,current);self.prefix(new,current);self.prefix(old,new)
            need(len(new['entries'])>count)
            first=last=None
            for row in rows[count:len(new['entries'])]:
                actual=queries([row],self.native.pid)
                if actual is not None:
                    if first is None:first=actual
                    if last is not None:follow(last,actual)
                    last=actual
            need(first is not None and last is not None)
            _start,floor=self.endpoints(rows[:count])
            if floor is not None:follow(floor,first)
            return deepcopy(first),deepcopy(last)

    def decode(self,value):return self.decoded(value)[0]

    def decoded(self,value,*,pins=None,with_rows=False):
        state=self.shape(value);rows=self.rows(state,pins=pins);points=self.accepted_rows(rows)
        result=(state,deepcopy(points))
        return (*result,rows) if with_rows else result

    def shape(self,value):
        exact(value,{'iosWorldWebGPUClocksVersion','binding','runId','requestId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'entries','storage'})
        need(type(state['entries']) is list and len(state['entries'])<=MAX_QUERIES and type(state['storage']) is dict and len(state['storage'])<=1024)
        references={ref['index']:ref for entry in state['entries'] for ref in entry['raws']};need(len(references)==sum(len(entry['raws']) for entry in state['entries']))
        for key,original in state['storage'].items():
            self.frames.original(original);need(key==str(original['index']))
            if original['index'] in references:need(original['phase']=='saved' and same(self.frames.compact(original),references[original['index']]))
        need(set(references)<= {int(key) for key in state['storage']});return deepcopy(state)
    @contextmanager
    def owned(self):
        self.bound();send,read=self.native.send,self.native.original
        def sending(query):
            self.query(query);need(len(self.state['entries'])<MAX_QUERIES)
            self.state['entries'].append(dict(query=deepcopy(query),raws=[]));self.save();return send(query)
        def reading():
            raw=read();need(type(raw) is str and len(raw.encode())<=LIMIT and self.state['entries']);entry=self.state['entries'][-1];rows=entry['raws'];index=len(self.state['entries'])
            if not rows or self.raw(rows[-1],index,len(rows),entry['query'])!=raw:
                need(len(rows)<51 and len(self.state['storage'])<1024);reference=self.frames.write(len(self.state['storage'])+1,
                    dict(requestId=self.request,queryIndex=index,rawIndex=len(rows)+1,query=deepcopy(entry['query']),raw=raw))
                rows.append(reference);self.save()
            return raw
        self.native.send,self.native.original=sending,reading
        try:
            last=self.last()
            if last is not None and self.native.sequence<last['sequence']:
                # Acquire a distinct actual clock query beyond the retained
                # original floor. Never relabel this already-used reader.
                self.native.read(last['sequence'])
            yield
        finally:self.native.send,self.native.original=send,read
    def validate_original(self,value):
        state=self.decode(value);return self.last(state)
