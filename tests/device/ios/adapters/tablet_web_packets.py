"""Durable ownership of actual Tablet source queries and immutable raw replies.

Each existing reader still owns its native grammar and freshness checks. This
owner retains actual matching replies, including accepted pending originals,
before interpretation. An unknown query return is never resent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.script_feature.history import same,canonical
from adapters.operation_transport_guard import scope as transport_scope
from adapters.original_file_reads import record as original_read
from ios.adapters import tablet_web_source,tablet_web_sources,tablet_web_dom,tablet_web_buttons,tablet_web_state,tablet_web_closures,uikit_input,web_script_emissions,tablet_web_deferred
from ios.adapters.tablet_web_segments import TabletWebSourceSegments,CHUNK_BYTES,sha
from ios.adapters.tablet_web_native_semantics import checked as checked_native

VERSION=2
READS=(1,2)
COMPONENTS={'trace':tablet_web_source,'sources':tablet_web_sources,'dom':tablet_web_dom,
    'buttons':tablet_web_buttons,'state':tablet_web_state,'closures':tablet_web_closures,'uikit':uikit_input,'emissions':web_script_emissions,'deferred':tablet_web_deferred}
CAPTURES=128


class TabletWebPackets:
    def __init__(self,root,binding,run,role,fixture_url,pid,component,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000),historical=False,storage_guard=None):
        need(type(component) is str and component in COMPONENTS and integer(pid,1)
            and type(historical) is bool and all(callable(value) for value in (guard,monotonic,epoch_ms)))
        self.root=Path(root);self.binding=deepcopy(context(binding));self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        need(self.binding['processIdentity']==str(pid))
        self.component,self.module,self.guard,self.monotonic,self.epoch_ms=component,COMPONENTS[component],guard,monotonic,epoch_ms
        self.historical=historical
        need(storage_guard is None or callable(storage_guard));self.storage_guard=guard if storage_guard is None else storage_guard
        if not historical:need(guard() is not False)
        self.module.command(dict(schemaVersion=1,action=self.module.ACTION,commandId='ios-'+'0'*32,runId=run,fixtureUrl=fixture_url))
        need(role in ('primary','actor'));self.clock=None
        self.store=PrivateFeatureState(self.root/('tabletweb-'+component+'-queries-'+run+'-'+role+'.json'))
        self.state=self.store.read()
        if self.state is not None and self.state.get('tabletWebPacketsVersion')==3:
            if 'tabletWebNativeChildContinuationVersion' in self.state:
                from ios.adapters.tablet_web_native_child_continuation import read_barrier
            elif component=='uikit':
                from ios.adapters.tablet_web_uikit_continuation import read_barrier
            else:
                from ios.adapters.tablet_web_dom_continuation import read_barrier
            read_barrier(self.state,binding,run,role,fixture_url,pid,component)
        self._original_storage()
        if self.state is None:
            need(not self.historical)
            self.state=dict(tabletWebPacketsVersion=VERSION,binding=self.binding,runId=run,role=role,fixtureUrl=fixture_url,
                processId=pid,component=component,nextRaw=1,records=[],pending=None,recordIntent=None,recordInspection=None)
            self.store.write(self.state,None)
        self.saved=deepcopy(self.state);self.history()

    def _original_storage(self):
        root,binding,run,role,component,monotonic=self.root,self.binding,self.run,self.role,self.component,self.monotonic
        self.segments=TabletWebSourceSegments(root,binding,run,role,component,self.original_guard,self.segment_intent,monotonic=monotonic)
        self.originals=OriginalFrameStore(root,binding,run,role,self.original_guard,self.record_intent,
            namespace='tabletweb-'+component+'-packets',schema_prefix='tabletWebSourcePacket',monotonic=monotonic)

    @classmethod
    def _closed_dom(cls,root,binding,run,role,fixture_url,pid,state,*,monotonic=time.monotonic):
        """Literal, read-only DOM replay after its canonical head is fenced."""
        owner=object.__new__(cls);owner.root=Path(root);owner.binding=deepcopy(context(binding))
        owner.run,owner.role,owner.fixture,owner.pid=run,role,fixture_url,pid
        need(role in ('primary','actor') and owner.binding['processIdentity']==str(pid))
        owner.component,owner.module='dom',tablet_web_dom
        def forbidden(*_args,**_kwargs):need(False)
        owner.guard=owner.storage_guard=owner.epoch_ms=forbidden;owner.monotonic=monotonic
        owner.historical=True;owner.clock=None
        owner.store=PrivateFeatureState(owner.root/('tabletweb-dom-queries-'+run+'-'+role+'.json'))
        owner.state=deepcopy(state);owner.saved=deepcopy(state);owner._original_storage();owner.history();return owner

    def original_guard(self):
        # Historical file reconstruction is deliberately SDK/query-free. All
        # live mutations retain their explicit not-historical gate and intent
        # callbacks; a forbidden live guard must never be called just to read
        # an already owned original.
        if not self.historical:need(self.storage_guard() is not False)
        return True

    def save(self):
        need(not self.historical and self.guard() is not False)
        self.state['tabletWebPacketsVersion']=VERSION
        self.store.write(self.state,self.saved);self.saved=deepcopy(self.state)

    def stamp(self):
        epoch,mono=self.epoch_ms(),self.monotonic();need(integer(epoch,1) and number(mono,0,1e15))
        if self.clock is not None:need(epoch>=self.clock['epochMs'] and mono>=self.clock['monotonic'])
        self.clock=dict(epochMs=epoch,monotonic=mono);return deepcopy(self.clock)

    def segment_intent(self,value):
        need(not self.historical)
        pending=self.state['pending'];need(pending is not None and pending['raws'])
        pending['raws'][-1]['segments']=deepcopy(value);self.save()

    def record_intent(self,kind,value):
        need(not self.historical)
        need(kind=='original' and self.state['pending'] is not None)
        self.state['recordIntent']=deepcopy(value);self.state['recordInspection']=None;self.save()

    def inspect_record(self):
        ref=self.originals.original(self.state['recordIntent']);path=self.originals.path(ref)
        if ref['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),ref);raw=stream.read(ref['bytes']+1);self.originals.file(path,stream.fileno(),ref)
        need(len(raw)<=ref['bytes']);original_read(path)
        result=dict(bytes=len(raw),sha256=sha(raw),complete=len(raw)==ref['bytes'] and sha(raw)==ref['sha256'])
        if ref['phase']=='saved':need(result['complete'])
        return result

    def check_value(self,value,query,previous):
        checked_native(self.module,'validate',value,query,self.pid)
        if self.component=='uikit':need(value['iosUIKitInputVersion']==uikit_input.VERSION)
        if previous is not None:
            if value['commandId']==previous['commandId']:
                if self.component=='dom':self.module.continuity(previous,value)
                else:need(same(previous,value))
            else:checked_native(self.module,'validate',value,query,self.pid,previous)
        return value

    def record(self,value,index,previous):
        from ios.adapters.tablet_web_record_cache import returned_record
        return returned_record(self,value,index,previous,lambda:self._record(value,index,previous))

    def _record(self,value,index,previous):
        version=value.get('tabletWebSourcePacketVersion');need(type(version) is int and version in READS)
        exact(value,({'readbacks'} if version>=2 else set())|{'tabletWebSourcePacketVersion','index','before','after','query','sendReturned','status','raws','unsafe','resultSha256'})
        need(type(value['tabletWebSourcePacketVersion']) is int and value['tabletWebSourcePacketVersion'] in READS
            and type(value['index']) is int and value['index']==index and type(value['sendReturned']) is bool
            and value['status'] in ('preparing','issued','returned','failed','abandoned')
            and type(value['raws']) is list and len(value['raws'])<=16 and type(value['unsafe']) is list and len(value['unsafe'])<=16)
        for rejected in value['unsafe']:
            exact(rejected,{'bytes','sha256'});need(integer(rejected['bytes'],1,self.module.LIMIT if version==1 else 2147483647)
                and type(rejected['sha256']) is str and len(rejected['sha256'])==64
                and all(char in '0123456789abcdef' for char in rejected['sha256']))
        if value['unsafe']:self.blocked=True
        def clock(row):
            exact(row,{'epochMs','monotonic'});need(integer(row['epochMs'],1) and number(row['monotonic'],0,1e15))
        clock(value['before'])
        if value['after'] is not None:
            clock(value['after']);need(value['after']['epochMs']>=value['before']['epochMs'] and value['after']['monotonic']>=value['before']['monotonic'])
        if value['query'] is None:need(value['status'] in ('preparing','failed','abandoned') and not value['sendReturned'] and not value['raws'] and not value['unsafe'])
        else:
            query=self.module.command(value['query']);need(query['runId']==self.run and query['fixtureUrl']==self.fixture)
        readbacks=value.get('readbacks',[]);need(type(readbacks) is list and len(readbacks)<=16)
        capture_count=readbacks[0]['startRaw'] if readbacks else len(value['raws']);need(integer(capture_count,0,len(value['raws'])))
        raw_spans={};issued_raws=set();last_recovery=value['after']
        for at,recovery in enumerate(readbacks):
            exact(recovery,{'before','after','startRaw','endRaw','status'})
            need(value['status'] in ('failed','abandoned') and value['after'] is not None
                and recovery['status'] in ('issued','returned','failed') and integer(recovery['startRaw'],capture_count,len(value['raws']))
                and integer(recovery['endRaw'],recovery['startRaw'],len(value['raws']))
                and (at==0 or recovery['startRaw']==readbacks[at-1]['endRaw']))
            clock(recovery['before']);need(recovery['before']['epochMs']>=last_recovery['epochMs']
                and recovery['before']['monotonic']>=last_recovery['monotonic'])
            if recovery['after'] is None:need(at==len(readbacks)-1 and recovery['status']=='issued');end=None
            else:
                end=recovery['after'];clock(end);need(end['epochMs']>=recovery['before']['epochMs'] and end['monotonic']>=recovery['before']['monotonic']
                    and recovery['status']!='issued');last_recovery=end
            if recovery['status']=='returned':need(recovery['endRaw']>recovery['startRaw'])
            for ordinal in range(recovery['startRaw'],recovery['endRaw']):
                need(ordinal not in raw_spans);raw_spans[ordinal]=(recovery['before'],end)
                if recovery['status']=='issued':issued_raws.add(ordinal)
        if readbacks:need(readbacks[-1]['endRaw']==len(value['raws']))
        values=[]
        last_clock=value['before']
        for ordinal,row in enumerate(value['raws']):
            exact(row,{'before','after','segments','inspection','outcome'});clock(row['before']);clock(row['after'])
            need(row['outcome'] in ('unchecked','accepted','rejected'))
            need(last_clock['epochMs']<=row['before']['epochMs']<=row['after']['epochMs']
                and last_clock['monotonic']<=row['before']['monotonic']<=row['after']['monotonic'])
            if ordinal in raw_spans:
                start,end=raw_spans[ordinal];need(row['before']['epochMs']>=start['epochMs'] and row['before']['monotonic']>=start['monotonic'])
                if end is not None:need(row['after']['epochMs']<=end['epochMs'] and row['after']['monotonic']<=end['monotonic'])
            elif value['after'] is not None:need(ordinal<capture_count and row['after']['epochMs']<=value['after']['epochMs'] and row['after']['monotonic']<=value['after']['monotonic'])
            last_clock=row['after']
            self.segments.parent(row['segments']);need(row['segments']['label']==self.component
                and row['segments']['tag']==sha(canonical(value['query'])))
            inspection=self.segments.inspect(row['segments'])
            if row['inspection'] is not None:need(same(self.segments.retained(row['segments'],row['inspection']),inspection))
            if value['status'] in ('returned','failed','abandoned'):need(row['inspection'] is not None or ordinal in issued_raws)
            if len(inspection)!=max(1,(row['segments']['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) or not all(part is not None and part['complete'] for part in inspection):
                need(value['status']!='returned' and row['outcome']=='unchecked');continue
            raw=self.segments.read(row['segments']);need(len(raw)<=self.module.LIMIT)
            packet=decode(raw.decode('utf-8'),limit=self.module.LIMIT);checked_native(self.module,'original',packet)
            if self.component=='uikit':need(packet['iosUIKitInputVersion']==uikit_input.VERSION)
            try:self.check_value(packet,value['query'],previous)
            except NativeUIError:
                need(row['outcome']!='accepted');self.blocked=True
            else:
                need(row['outcome']!='rejected');previous=packet;values.append(packet)
        if value['status']=='returned':
            need(value['after'] is not None and value['sendReturned'] and values
                and not value['unsafe'] and all(row['outcome']=='accepted' for row in value['raws'])
                and value['resultSha256']==sha(canonical(values[-1])))
        else:need(value['resultSha256'] is None)
        return previous,values

    def _record_start(self):return 1

    def _next_index(self):return self._record_start()+len(self.state['records'])

    def reference(self,index):
        need(integer(index,1,len(self.state['records'])))
        reference=self.state['records'][index-1];need(reference['index']==index);return deepcopy(reference)

    def _history_prefix(self):return None,[],1,set(),None

    def _header(self):
        value=self.state
        exact(value,{'tabletWebPacketsVersion','binding','runId','role','fixtureUrl','processId','component','nextRaw','records','pending','recordIntent','recordInspection'})
        need(type(value['tabletWebPacketsVersion']) is int and value['tabletWebPacketsVersion'] in READS and same(value['binding'],self.binding)
            and value['runId']==self.run and value['role']==self.role and value['fixtureUrl']==self.fixture and type(value['processId']) is int
            and value['processId']==self.pid and value['component']==self.component and integer(value['nextRaw'],1,MAX_FRAMES+1)
            and type(value['records']) is list and len(value['records'])<=CAPTURES)
    def history(self):
        if not self.historical:need(self.guard() is not False)
        self._header();value=self.state;self.blocked=False
        previous,result,raw_floor,queries,capture_clock=self._history_prefix()
        def floor(row):
            nonlocal raw_floor,capture_clock
            if capture_clock is not None:need(row['before']['epochMs']>=capture_clock['epochMs'] and row['before']['monotonic']>=capture_clock['monotonic'])
            capture_clock=row.get('readbacks',[])[-1]['after'] if row.get('readbacks') and row['readbacks'][-1]['after'] is not None else row['after'] or (row['raws'][-1]['after'] if row['raws'] else row['before'])
            if row['query'] is not None:
                query=row['query']['commandId'];need(query not in queries);queries.add(query)
            for part in row['raws']:
                parent=part['segments'];need(parent['first']==raw_floor)
                raw_floor+=max(1,(parent['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        for index,ref in enumerate(value['records'],self._record_start()):
            original=self.originals.expand(ref);need(original['index']==index)
            row=self.originals.read(original);need(row['status'] in ('returned','failed','abandoned'))
            previous,packets=self.record(row,index,previous);result.extend(packets);floor(row)
        if value['pending'] is not None:
            need(len(value['records'])<CAPTURES)
            previous,packets=self.record(value['pending'],self._next_index(),previous);result.extend(packets);floor(value['pending'])
        need(value['nextRaw']==raw_floor)
        if value['recordIntent'] is not None:
            ref=self.originals.original(value['recordIntent']);need(value['pending'] is not None and ref['index']==self._next_index())
            inspection=self.inspect_record()
            if value['recordInspection'] is not None:need(same(inspection,value['recordInspection']))
        else:need(value['recordInspection'] is None)
        if capture_clock is not None:
            self.clock={key:max(capture_clock[key],self.clock[key] if self.clock is not None else capture_clock[key]) for key in capture_clock}
        if not self.historical:need(self.guard() is not False)
        return deepcopy(result)

    def archive_pending(self,*,abandon=False):
        need(not self.historical)
        self.history();pending=self.state['pending'];need(pending is not None and self.state['recordIntent'] is None)
        if abandon:
            need(pending['status']!='returned')
            for row in pending['raws']:
                if row['inspection'] is None:row['inspection']=self.segments.inspect(row['segments'])
            pending.update(status='abandoned',resultSha256=None);self.save()
        else:need(pending['status'] in ('returned','failed'))
        ref=self.originals.write(pending['index'],deepcopy(pending))
        self.state['records'].append(ref);self.state['pending']=self.state['recordIntent']=self.state['recordInspection']=None;self.save();return deepcopy(ref)

    def recover_record(self):
        need(not self.historical)
        self.history();ref=self.state['recordIntent'];need(ref is not None and ref['phase'] in ('opened','saved'))
        row=self.originals.read(ref);need(same(row,self.state['pending']) and row['status'] in ('returned','failed','abandoned'))
        # Actual complete opened bytes are retained without repeating a write.
        committed=dict(ref,phase='saved');self.state['records'].append(self.originals.compact(committed))
        self.state['pending']=self.state['recordIntent']=self.state['recordInspection']=None;self.save();return deepcopy(self.state['records'][-1])

    def reconcile(self,reader):
        """Read only the exact issued nonce, with separately retained clocks.

        The original failure endpoint and status never move. A readback may
        establish an actual raw source floor, including pending DOM, but is
        never a fresh acquisition or a successful feature observation.
        """
        need(not self.historical);previous=self.history();pending=self.state['pending']
        need(not self.blocked and pending is not None and pending['status']=='failed' and pending['query'] is not None
            and pending['after'] is not None and self.state['recordIntent'] is None and not pending['unsafe']
            and reader.pid==self.pid and reader._action==self.module.ACTION and self.guard() is not False)
        if pending['tabletWebSourcePacketVersion']==1:
            need(not pending['raws']);pending['tabletWebSourcePacketVersion']=VERSION;pending['readbacks']=[]
        need(not pending['raws'] or pending['readbacks'] and pending['readbacks'][0]['startRaw']==0
            and all(row['outcome'] in ('accepted','unchecked') for row in pending['raws']))
        if pending['raws']:
            # A complete original survived a lost host flush/interpretation
            # return. Revalidate exactly those bytes; retain the failed span
            # and its original clocks, without any new SDK/native request.
            for row in pending['raws']:
                raw=self.segments.read(row['segments']);packet=decode(raw.decode('utf-8'),limit=self.module.LIMIT)
                self.module.original(packet);self.check_value(packet,pending['query'],previous[-1] if previous else None)
                row['outcome']='accepted'
                if row['inspection'] is None:row['inspection']=self.segments.inspect(row['segments'])
            if pending['readbacks'][-1]['status']=='issued':pending['readbacks'][-1].update(status='failed',after=self.stamp())
            self.save();self.history();return deepcopy(packet)
        need(len(pending['readbacks'])<16 and all(row['status']!='issued' for row in pending['readbacks']))
        span=dict(before=self.stamp(),after=None,startRaw=len(pending['raws']),endRaw=len(pending['raws']),status='issued')
        pending['readbacks'].append(span);self.save()
        try:
            need(reader.guard() is not False);raw=reader.original();received=self.stamp();need(reader.guard() is not False and type(raw) is str)
            encoded=raw.encode('utf-8')
            if not 0<len(encoded)<=self.module.LIMIT:
                if encoded:pending['unsafe'].append(dict(bytes=len(encoded),sha256=sha(encoded)));self.save()
                need(False)
            packet=decode(raw,limit=self.module.LIMIT);need(type(packet) is dict and packet.get('commandId')==pending['query']['commandId'])
            try:
                self.module.original(packet)
                if self.component=='uikit':need(packet['iosUIKitInputVersion']==uikit_input.VERSION)
            except Exception:
                pending['unsafe'].append(dict(bytes=len(encoded),sha256=sha(encoded)));self.save();raise
            first=self.state['nextRaw'];count=max(1,(len(encoded)+CHUNK_BYTES-1)//CHUNK_BYTES)
            need(first+count-1<=MAX_FRAMES and len(pending['raws'])<16);self.state['nextRaw']+=count
            pending['raws'].append(dict(before=deepcopy(span['before']),after=received,segments=None,inspection=None,outcome='unchecked'))
            span['endRaw']=len(pending['raws'])
            self.segments.write(self.component,sha(canonical(pending['query'])),encoded,first)
            pending['raws'][-1]['inspection']=self.segments.inspect(pending['raws'][-1]['segments']);self.save()
            try:self.check_value(packet,pending['query'],previous[-1] if previous else None)
            except NativeUIError:pending['raws'][-1]['outcome']='rejected';self.save();raise
            pending['raws'][-1]['outcome']='accepted';span.update(status='returned',after=self.stamp());self.save();self.history()
            return deepcopy(packet)
        except Exception:
            if pending['raws'] and pending['raws'][-1]['inspection'] is None:
                pending['raws'][-1]['inspection']=self.segments.inspect(pending['raws'][-1]['segments'])
            span.update(status='failed',after=self.stamp());self.save();raise

    def capture(self,reader):
        need(not self.historical)
        previous=self.history();need(not self.blocked and self.state['pending'] is self.state['recordIntent'] is None and len(self.state['records'])<CAPTURES
            and reader.pid==self.pid and reader._action==self.module.ACTION and self.guard() is not False)
        # A fresh reader cannot discard earlier accepted pending/source floors.
        if previous:
            need(reader.last is None or same(reader.last,previous[-1]))
            reader.last=deepcopy(previous[-1])
            if self.component=='dom':
                need(reader.accepted is None or same(reader.accepted,previous[-1]));reader.accepted=deepcopy(previous[-1])
        else:need(reader.last is None and getattr(reader,'accepted',None) is None)
        pending=dict(tabletWebSourcePacketVersion=VERSION,index=self._next_index(),before=self.stamp(),after=None,
            query=None,sendReturned=False,status='preparing',raws=[],unsafe=[],resultSha256=None,readbacks=[])
        self.state['pending']=pending;self.save();send,original=reader.send,reader.original
        last=deepcopy(previous[-1]) if previous else None
        def issued(query):
            self.module.command(query);need(pending['query'] is None and query['runId']==self.run and query['fixtureUrl']==self.fixture)
            pending.update(query=deepcopy(query),status='issued');self.save();result=send(query)
            pending['sendReturned']=True;self.save();return result
        def received():
            nonlocal last
            before=self.stamp();raw=original();after=self.stamp()
            if not raw:return raw
            need(type(raw) is str and len(raw.encode())<=self.module.LIMIT)
            packet=decode(raw,limit=self.module.LIMIT)
            if type(packet) is not dict or packet.get('commandId')!=pending['query']['commandId']:return raw
            # Unknown/private grammar must not become a new host artifact.
            # Standalone typed originals are safe to retain before semantic
            # process/query/prefix interpretation, including actual rejection.
            try:
                self.module.original(packet)
                if self.component=='uikit':need(packet['iosUIKitInputVersion']==uikit_input.VERSION)
            except Exception:
                pending['unsafe'].append(dict(bytes=len(raw.encode()),sha256=sha(raw.encode())));self.save();raise
            if pending['raws'] and sha(raw.encode())==pending['raws'][-1]['segments']['sha256']:return raw
            first=self.state['nextRaw'];count=max(1,(len(raw.encode())+CHUNK_BYTES-1)//CHUNK_BYTES)
            need(first+count-1<=MAX_FRAMES and len(pending['raws'])<16);self.state['nextRaw']+=count
            pending['raws'].append(dict(before=before,after=after,segments=None,inspection=None,outcome='unchecked'))
            # segments.write durably reports its planned parent before opening.
            self.segments.write(self.component,sha(canonical(pending['query'])),raw.encode(),first)
            pending['raws'][-1]['inspection']=self.segments.inspect(pending['raws'][-1]['segments']);self.save()
            try:self.check_value(packet,pending['query'],last)
            except NativeUIError:
                pending['raws'][-1]['outcome']='rejected';self.save();raise
            pending['raws'][-1]['outcome']='accepted';self.save()
            last=deepcopy(packet);return raw
        reader.send,reader.original=issued,received
        started=self.monotonic();last_transport=started
        def transport_guard():
            nonlocal last_transport
            now=self.monotonic();need(number(now,last_transport,1e15) and now-started<1.5)
            last_transport=now;return True
        try:
            with transport_scope(transport_guard):value=reader.read(self.run,self.fixture)
            need(last is not None and same(value,last))
            pending.update(after=self.stamp(),status='returned',resultSha256=sha(canonical(value)));self.save()
            self.archive_pending();need(self.guard() is not False);return deepcopy(value)
        except Exception:
            # Do not overwrite an interrupted immutable record-write intent.
            if self.state['recordIntent'] is None:
                for row in pending['raws']:
                    if row['inspection'] is None:row['inspection']=self.segments.inspect(row['segments'])
                pending.update(after=self.stamp(),status='failed',resultSha256=None);self.save()
            else:
                self.state['recordInspection']=self.inspect_record();self.save()
            raise
        finally:reader.send,reader.original=send,original
