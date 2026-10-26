"""Own passive global Qt key/IME originals without replaying a query.

Raw packets live in immutable original files. Metadata carries descriptors,
native clock brackets and interrupted-query ownership only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_file_reads import record as record_original_read
from adapters.original_key_packets import OriginalKeyPackets
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import world_web_keys
from ios.adapters.emote_native_prefix import follow
from ios.adapters.graphics_history import restore_native
from ios.adapters.native_geometry import OriginalGeometry,validate as geometry_receipt
from ios.adapters.emote_archive_round import key_original

VERSION=1


class IOSEmoteKeys:
    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result.historical=True;result.raw=result.raw_owner(lambda:True,lambda *_:need(False))
        result.previous=store.read();result.state=result.decode(value);return result

    def __init__(self,store,root,binding,run,role,lock,guard,*,native,keys,geometry,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(keys,world_web_keys.IOSWorldWebKeys)
            and isinstance(geometry,OriginalGeometry)
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        self.guard,self.native,self.keys,self.geometry,self.epoch_ms,self.monotonic=guard,native,keys,geometry,epoch_ms,monotonic
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.historical=False;self.previous=store.read();self.state=dict(records=[],abandoned=[],pending=None,serial=0)
        self.raw=self.raw_owner(guard,self.intent,monotonic=monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)

    def raw_owner(self,guard,intent,**kwargs):
        return OriginalKeyPackets(self.root,self.binding,self.run,self.role,self.role,guard,intent,profile='emote',**kwargs)

    def envelope(self,state):return dict(iosEmoteKeysVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),payload=pack([state]))

    def file(self,index,abandoned=False):
        need(integer(index,1,512));return PrivateFeatureState(self.root/('emote-keys-'+('abandoned-' if abandoned else '')+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def packet(self,value):
        # Even a warm immutable result retains the exact original carrier and
        # query grammar. No current metadata or source floor is cached here.
        self.raw.original(value['wire']);world_web_keys.command(value['query'])
        return key_original(self,'packet',dict(wire=value['wire'],query=value['query']),lambda:self._packet(value),self.parsers())

    def _packet(self,value):
        body=self.raw.read(value['wire']);need(same(body['query'],value['query']))
        packet=self.raw.packet(value['wire']);world_web_keys.privacy_qualified(packet);need(packet['runId']==self.run);return packet

    def parsers(self):
        return [self._original,self._packet,self.receipt,self.raw.read,self.raw.packet,world_web_keys.validate,
            world_web_keys.privacy_qualified,geometry_receipt,validate_join,follow,unpack,digest]

    def receipt(self,value,previous=None):
        exact(value,{'iosEmoteKeyReceiptVersion','runId','role','binding','query','wire','wires','geometry','clockJoin'})
        need(type(value['iosEmoteKeyReceiptVersion']) is int and value['iosEmoteKeyReceiptVersion']==1
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding))
        query=world_web_keys.command(value['query']);need(query['runId']==self.run);packet=self.packet(value)
        need(type(value['wires']) is list and 1<=len(value['wires'])<=64 and value['wire'] in value['wires'])
        for wire in value['wires']:need(same(self.raw.read(wire)['query'],query))
        geometry=value['geometry'];document,_rect=geometry_receipt(geometry,geometry['commandId'],native_epoch_ms=geometry['observation']['sampleEpochMs'])
        need(type(document['schemaVersion']) is int and document['schemaVersion']==1)
        join=validate_join(value['clockJoin'],dict(keys=packet,keysClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']),geometry=document))
        pid=int(self.binding['processIdentity']);world_web_keys.validate(packet,query,pid,previous=None if previous is None else self.packet(previous))
        follow(join['nativeBefore'],join['nativeAfter']);need(join['nativeBefore']['processId']==pid
            and join['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=join['nativeAfter']['capturedEpochMs'])
        need(join['nativeBefore']['capturedEpochMs']<=document['sampleEpochMs']<=join['nativeAfter']['capturedEpochMs'])
        if previous is not None:
            self.receipt(previous);follow(previous['clockJoin']['nativeAfter'],join['nativeBefore'])
            need(join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs']
                and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
            old=previous['geometry']['observation'];need(geometry['commandId']!=previous['geometry']['commandId']
                and document['sampleSequence']>=old['sampleSequence'] and document['sampleEpochMs']>=old['sampleEpochMs'])
        return value

    def original(self,ref):
        exact(ref,{'index','sha256'});need(integer(ref['index'],1,512) and type(ref['sha256']) is str
            and len(ref['sha256'])==64 and all(char in '0123456789abcdef' for char in ref['sha256']))
        return key_original(self,'receipt',ref,lambda:self._original(ref),self.parsers())

    def _original(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'iosEmoteKeyOriginalVersion','payload'});need(type(value['iosEmoteKeyOriginalVersion']) is int and value['iosEmoteKeyOriginalVersion']==1)
        rows=unpack(value['payload']);need(len(rows)==1);return self.receipt(rows[0])

    def footprint(self,original):
        self.raw.original(original)
        if original['phase']=='planned':need(not self.raw.originals.path(original).exists());return None
        actual=self.raw.inspect_partial(original)
        return {key:actual[key] for key in ('file','bytes','sha256','complete')}

    def partial(self,value):
        exact(value,{'priorRecords','nativeStart','query','wires','wire','footprint','geometryQuery','geometryRaw','original'})
        need(integer(value['priorRecords'],0,512) and type(value['wires']) is list and len(value['wires'])<=64)
        start=value['nativeStart']
        if start is not None:
            exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            packet=start['nativeBefore'];native_packet(packet,packet['requestId'],int(self.binding['processIdentity']),packet['capturedEpochMs'])
        if value['query'] is not None:need(start is not None and world_web_keys.command(value['query'])['runId']==self.run)
        for wire in value['wires']:
            need(value['query'] is not None and same(self.raw.read(wire)['query'],value['query']))
        if value['wire'] is not None:
            self.raw.original(value['wire']);need(value['query'] is not None)
            if value['wire']['phase']=='planned':need(not self.raw.originals.path(value['wire']).exists())
            if value['footprint'] is not None:
                need(same(value['footprint'],self.footprint(value['wire'])))
                if value['wire']['phase']!='planned':record_original_read(self.raw.originals.path(value['wire']))
        else:need(value['footprint'] is None)
        if value['geometryQuery'] is not None:
            q=value['geometryQuery'];exact(q,{'schemaVersion','commandId','action'})
            need(type(q['schemaVersion']) is int and q['schemaVersion']==1 and q['action']=='native-geometry-snapshot'
                and type(q['commandId']) is str and q['commandId'].startswith('ios-'));identifier(q['commandId'][4:])
        if value['geometryRaw'] is not None:need(value['geometryQuery'] is not None and type(value['geometryRaw']) is str and len(value['geometryRaw'].encode())<=65536)
        if value['original'] is not None:
            item=self.receipt(value['original']);need(same(item['query'],value['query']) and item['wire'] in value['wires']
                and same(item['wires'],value['wires'])
                and same(start,{key:item['clockJoin'][key] for key in start}))
        return value

    def abandoned(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index'],True).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'iosEmoteKeyAbandonedVersion','runId','role','binding','payload'})
        need(type(value['iosEmoteKeyAbandonedVersion']) is int and value['iosEmoteKeyAbandonedVersion']==1
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);result=self.partial(rows[0]);need(result['original'] is None)
        if result['wire'] is not None and result['wire']['phase']!='planned':need(result['footprint'] is not None)
        return result

    def decode(self,value):
        exact(value,{'iosEmoteKeysVersion','runId','role','binding','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','abandoned','pending','serial'})
        need(integer(state['serial'],0,1024) and all(type(state[key]) is list and len(state[key])<=512 for key in ('records','abandoned')))
        previous=None
        for index,ref in enumerate(state['records'],1):
            need(ref['index']==index);item=self.original(ref);self.receipt(item,previous);previous=item
            need(all(wire['index']<=state['serial'] for wire in item['wires']))
        for index,ref in enumerate(state['abandoned'],1):
            need(ref['index']==index);partial=self.abandoned(ref);need(partial['priorRecords']<=len(state['records']))
            need(all(wire['index']<=state['serial'] for wire in partial['wires']+([] if partial['wire'] is None else [partial['wire']])))
            for later in state['records'][partial['priorRecords']:]:self.floors(partial,self.original(later))
        if state['pending'] is not None:
            self.partial(state['pending']);need(state['pending']['priorRecords']==len(state['records']))
            partial=state['pending'];need(all(wire['index']<=state['serial'] for wire in partial['wires']+([] if partial['wire'] is None else [partial['wire']])))
        if not getattr(self,'historical',False):
            for abandoned in (False,True):
                count=len(state['abandoned' if abandoned else 'records']);need(count==512 or self.file(count+1,abandoned).read() is None)
        return deepcopy(state)

    def bound(self):self.lock.assert_held();need(not getattr(self,'historical',False) and same(self.store.read(),self.previous) and self.guard() is not False)
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,event,original):
        need(event=='original' and self.state['pending'] is not None);self.raw.original(original)
        self.state['pending']['wire']=deepcopy(original);self.save();return True

    def resolve(self):
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if pending['original'] is None:return False
        index=len(self.state['records'])+1;value=dict(iosEmoteKeyOriginalVersion=1,payload=pack([pending['original']]))
        store=self.file(index);existing=store.read()
        if existing is None:store.write(value,None)
        else:need(same(existing,value))
        ref=dict(index=index,sha256=digest(value));self.original(ref);self.state['records'].append(ref);self.state['pending']=None;self.save();return True

    def abandon(self):
        self.bound()
        if self.resolve():return True
        pending=self.state['pending']
        if pending['wire'] is not None:pending['footprint']=self.footprint(pending['wire']);self.save()
        index=len(self.state['abandoned'])+1;value=dict(iosEmoteKeyAbandonedVersion=1,runId=self.run,role=self.role,binding=self.binding,payload=pack([pending]))
        store=self.file(index,True);existing=store.read()
        if existing is None:store.write(value,None)
        else:need(same(existing,value))
        ref=dict(index=index,sha256=digest(value));self.abandoned(ref);self.state['abandoned'].append(ref);self.state['pending']=None;self.save();return True

    def accepted(self,partial):
        wires=list(partial['wires'])
        if partial['wire'] is not None and partial['wire']['phase']!='planned':
            actual=self.raw.inspect_partial(partial['wire'])
            if actual['complete']:wires.append(partial['wire'])
        for wire in wires:
            body=self.raw.read(wire);need(same(body['query'],partial['query']))
            try:packet=json.loads(body['raw'])
            except (ValueError,TypeError):continue
            if type(packet) is not dict or packet.get('requestId')!=partial['query']['commandId']:continue
            world_web_keys.validate(packet,partial['query'],int(self.binding['processIdentity']));world_web_keys.privacy_qualified(packet)
            need(partial['nativeStart']['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs']);yield packet

    def floors(self,partial,current):
        self.partial(partial);start=partial['nativeStart'];join=current['clockJoin']
        if start is not None:
            follow(start['nativeBefore'],join['nativeBefore'])
            need(start['hostBeforeEpochMs']<=join['hostBeforeEpochMs'] and start['hostBeforeMonotonic']<=join['hostBeforeMonotonic'])
        for packet in self.accepted(partial):world_web_keys.validate(self.packet(current),current['query'],int(self.binding['processIdentity']),previous=packet)
        if partial['geometryRaw'] is not None:
            try:original=json.loads(partial['geometryRaw'])
            except (ValueError,TypeError):return
            query=partial['geometryQuery']
            if type(original) is dict and original.get('commandId')==query['commandId']:
                prior,_rect=geometry_receipt(original,query['commandId'],native_epoch_ms=original['observation']['sampleEpochMs'])
                present=current['geometry']['observation'];need(present['sampleEpochMs']>=prior['sampleEpochMs'] and present['sampleSequence']>=prior['sampleSequence'])

    def capture(self):
        self.bound();need(self.resolve() and len(self.state['records'])<512)
        prior=None if not self.state['records'] else self.original(self.state['records'][-1])
        if prior is not None:
            last=prior['clockJoin']['nativeAfter']
            if self.native.sequence==0:restore_native(self.native,last)
            else:need(self.native.instance==last['instance'] and self.native.sequence>=last['sequence'] and self.native.captured_epoch>=last['capturedEpochMs'])
            self.keys.last=deepcopy(self.packet(prior))
        self.state['pending']=dict(priorRecords=len(self.state['records']),nativeStart=None,query=None,wires=[],wire=None,footprint=None,
            geometryQuery=None,geometryRaw=None,original=None);self.save()
        pending=self.state['pending'];window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(self.epoch_ms());pending['nativeStart']=deepcopy(window.started);self.save();send,read=self.keys.send,self.keys.original
        def sending(query):need(pending['query'] is None);pending['query']=deepcopy(query);self.save();return send(query)
        def reading():
            raw=read();need(type(raw) is str and len(raw.encode())<=world_web_keys.LIMIT)
            # Fixed native files can still contain a legacy response. Neither
            # stale transport bytes nor a matching unsafe source may become a
            # new immutable host artifact. Preserve accepted bytes unchanged.
            try:observed=json.loads(raw)
            except (ValueError,TypeError):return raw
            if type(observed) is not dict or observed.get('requestId')!=pending['query']['commandId']:return raw
            world_web_keys.validate(observed,pending['query'],int(self.binding['processIdentity']))
            world_web_keys.privacy_qualified(observed)
            for wire in pending['wires']:
                if self.raw.read(wire)['raw']==raw:return raw
            need(len(pending['wires'])<64 and self.state['serial']<1024);self.state['serial']+=1;self.save()
            wire=self.raw.write(self.state['serial'],pending['query'],raw);pending['wires'].append(wire);pending['wire']=None;self.save();return raw
        self.keys.send,self.keys.original=sending,reading
        try:packet=self.keys.read(self.run)
        finally:self.keys.send,self.keys.original=send,read
        geo_send,geo_read=self.geometry.send,self.geometry.original
        def sending_geometry(query):need(pending['geometryQuery'] is None);pending['geometryQuery']=deepcopy(query);self.save();return geo_send(query)
        def reading_geometry():
            raw=geo_read();need(type(raw) is str and len(raw.encode())<=65536);pending['geometryRaw']=raw;self.save();return raw
        self.geometry.send,self.geometry.original=sending_geometry,reading_geometry
        try:geometry=self.geometry.capture()
        finally:self.geometry.send,self.geometry.original=geo_send,geo_read
        join=window.finish(dict(keys=packet,keysClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']),geometry=geometry['observation']),
            [('keysClock','capturedEpochMs'),('geometry','sampleEpochMs')])
        matches=[]
        for wire in pending['wires']:
            try:body=json.loads(self.raw.read(wire)['raw'])
            except (ValueError,TypeError):continue
            if same(body,packet):matches.append(wire)
        need(matches)
        value=dict(iosEmoteKeyReceiptVersion=1,runId=self.run,role=self.role,binding=self.binding,query=pending['query'],wire=matches[-1],
            wires=deepcopy(pending['wires']),geometry=geometry,clockJoin=join)
        self.receipt(value,prior)
        for ref in self.state['abandoned']:self.floors(self.abandoned(ref),value)
        pending['original']=value;self.save();need(self.resolve());return deepcopy(self.state['records'][-1])

    def closed(self,scope):
        self.decode(self.envelope(self.state));need(self.state['pending'] is None and len(self.state['records'])>=4
            and scope.state['phase']=='released' and scope.state['quiet'][-1]==len(scope.frames))
        baseline=self.original(self.state['records'][0]);world_web_keys.drained(self.packet(baseline))
        self.keyboard_hidden(baseline)
        for ref in self.state['abandoned']:
            pending=self.abandoned(ref)
            if pending['nativeStart'] is not None:need(pending['priorRecords']<len(self.state['records']))
        follow(baseline['clockJoin']['nativeAfter'],scope.frames[scope.state['baseline']-1]['clockJoin']['nativeBefore'])
        quiet=[scope.frames[index-1] for index in scope.state['quiet']]
        for frame in quiet:scope.ui_absent(frame);scope.dialog_drained(frame)
        return self.quiet(quiet)

    def quiet(self,quiet):
        need(len(quiet)>=3);rows=[self.original(ref) for ref in self.state['records']];first,last=quiet[0],quiet[-1]
        left=[row for row in rows if row['clockJoin']['hostAfterMonotonic']<=first['clockJoin']['hostBeforeMonotonic']
            and row['clockJoin']['nativeAfter']['capturedEpochMs']<=first['clockJoin']['nativeBefore']['requestedEpochMs']]
        right=[row for row in rows if row['clockJoin']['hostBeforeMonotonic']>=last['clockJoin']['hostAfterMonotonic']
            and row['clockJoin']['nativeBefore']['requestedEpochMs']>=last['clockJoin']['nativeAfter']['capturedEpochMs']]
        need(left and right);a,b=left[-1],right[-1];x,y=self.packet(a),self.packet(b)
        follow(a['clockJoin']['nativeAfter'],first['clockJoin']['nativeBefore']);follow(last['clockJoin']['nativeAfter'],b['clockJoin']['nativeBefore'])
        for row in rows:
            packet=self.packet(row)
            if x['sequence']<=packet['sequence']<=y['sequence']:
                world_web_keys.drained(packet);self.keyboard_hidden(row);need(same(packet['source']['events'],x['source']['events']))
        u,v=x['clockAfter'],y['clockBefore'];need(3000<=v['epochMs']-u['epochMs']<60000 and 3000<=v['monotonicMs']-u['monotonicMs']<60000)
        return dict(first=a,last=b,quietLast=right[0])

    @staticmethod
    def keyboard_hidden(receipt):
        ui=receipt['geometry']['observation']['nativeUi']
        need(ui.get('keyboardVisible') is False and number(ui.get('imeInsetBottom'),0,0))
