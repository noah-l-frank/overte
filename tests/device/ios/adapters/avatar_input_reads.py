"""Durable passive input-ledger reads and no-resend interrupted-read recovery.

This owner retains original native DTOs in private immutable files. It never
dispatches a pointer/IME action or supplies a feature verdict. An incomplete
read is kept before a distinct later source query may be attempted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import avatar_inputs as ledger

VERSION=1


class IOSAvatarInputReads:
    def __init__(self,store,root,binding,run,role,lock,guard,reader=None,*,historical=False,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
            and type(historical) is bool and role in ('primary','actor'))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),context(binding),identifier(run),role,lock
        need(store.path.name=='ios-avatar-'+role+'-input-reads.json' and store.path.parent==lock.path.parent)
        self.guard,self.reader,self.historical=guard,reader,historical;lock.assert_held()
        need(historical and reader is None or not historical and isinstance(reader,ledger.IOSAvatarInputs))
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,
            namespace='avatar-input-read',schema_prefix='avatarInputRead',monotonic=monotonic)
        self.previous=store.read();self.state=dict(rows=[],pending=None)
        if self.previous is not None:self.state=self.parse(self.previous)

    def envelope(self,state):
        return dict(iosAvatarInputReadsVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            artifactRoot=str(self.root),payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))

    def partial_file(self,original):
        self.originals.original(original);path=self.originals.path(original)
        if original['phase']=='planned':need(not path.exists());return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes'])
        if original['phase']=='saved':need(len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256'])
        return dict(identity=deepcopy(original['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def packet(self,row,previous=None):
        need(row['original'] is not None and row['original']['phase']=='saved')
        frame=self.originals.read(row['original']);exact(frame,{'iosAvatarInputReadRecordVersion','query','nativeRequestedEpochMs','packet'})
        need(type(frame['iosAvatarInputReadRecordVersion']) is int and frame['iosAvatarInputReadRecordVersion']==VERSION
            and same(frame['query'],row['query']) and frame['nativeRequestedEpochMs']==row['epochs'][0])
        value=ledger.validate(frame['packet'],row['query'],int(self.binding['processIdentity']),previous=previous)
        need(value['clockBefore']['epochMs']>=row['epochs'][0]);return value

    def parse(self,value):
        exact(value,{'iosAvatarInputReadsVersion','binding','runId','role','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'rows','pending'});need(type(state['rows']) is list and len(state['rows'])<=128);previous=None
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','status','query','epochs','original','acquisition','partialFile'})
            need(row['index']==index and row['status'] in ('observed','abandoned'));self.pending(row,index)
            if row['original'] is not None:
                need(same(row['partialFile'],self.partial_file(row['original'])))
                if row['original']['phase']=='saved':previous=self.packet(row,previous)
            else:need(row['partialFile'] is None)
            if row['status']=='observed':
                need(row['original'] is not None and row['original']['phase']=='saved' and row['acquisition'] is not None)
        if state['pending'] is not None:
            exact(state['pending'],{'index','query','epochs','original','acquisition'})
            self.pending(state['pending'],len(state['rows'])+1)
        return deepcopy(state)

    def pending(self,value,index):
        need(type(value['index']) is int and value['index']==index and type(value['epochs']) is list and len(value['epochs'])<=2)
        for item in value['epochs']:need(integer(item,1))
        if len(value['epochs'])==2:need(value['epochs'][1]>=value['epochs'][0])
        if value['query'] is not None:ledger.command(value['query']);need(value['query']['runId']==self.run and value['epochs'])
        if value['original'] is not None:self.originals.original(value['original']);need(value['original']['index']==index and value['query'] is not None)
        if value['acquisition'] is not None:
            a=value['acquisition'];exact(a,{'hostBeforeMonotonic','hostAfterMonotonic','nativeRequestedEpochMs','nativeAfterEpochMs','originalSha256','iosAvatarInputsAcquisitionVersion'})
            need(type(a['iosAvatarInputsAcquisitionVersion']) is int and a['iosAvatarInputsAcquisitionVersion']==1 and len(value['epochs'])==2
                and a['nativeRequestedEpochMs']==value['epochs'][0] and a['nativeAfterEpochMs']==value['epochs'][1]
                and number(a['hostBeforeMonotonic'],0,1e15) and number(a['hostAfterMonotonic'],a['hostBeforeMonotonic'],a['hostBeforeMonotonic']+1.5)
                and a['hostAfterMonotonic']-a['hostBeforeMonotonic']<1.5)
            packet=self.packet(value);ledger.validate(packet,value['query'],int(self.binding['processIdentity']),value['epochs'][1])
            need(a['originalSha256']==digest(packet))

    def save(self):
        self.bound();value=self.envelope(self.state);self.parse(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def storage(self,kind,value):
        self.bound();pending=self.state['pending'];need(kind=='original' and pending is not None)
        self.originals.original(value);old=pending['original']
        need(value['index']==pending['index'] and (value['phase']=='planned' if old is None else
            value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file']))))
        pending['original']=deepcopy(value);self.save()

    def finish(self,status):
        self.bound();pending=self.state['pending'];need(pending is not None and status in ('observed','abandoned'))
        row=dict(deepcopy(pending),status=status,partialFile=None)
        if row['original'] is not None:row['partialFile']=self.partial_file(row['original'])
        self.state['rows'].append(row);self.state['pending']=None;self.save();return deepcopy(row)

    def recover(self):
        self.bound();pending=self.state['pending']
        if pending is None:return
        # A complete returned read is adopted from its original file. A lost
        # source return without its final acquisition stays an abandoned read.
        return self.finish('observed' if pending['acquisition'] is not None else 'abandoned')

    def read(self):
        self.bound();self.recover();need(len(self.state['rows'])<128)
        previous=None
        for row in self.state['rows']:
            # The native DTO returned before this writer began. If its actual
            # file did not reach a completed saved original, a fresh query must
            # not erase the unretained native prefix. Keep that responsibility
            # blocked rather than invent a new source birth or empty history.
            need(row['original'] is None or row['original']['phase']=='saved')
            if row['original'] is not None and row['original']['phase']=='saved':previous=self.packet(row,previous)
        reader=self.reader;reader.last=deepcopy(previous)
        pending=dict(index=len(self.state['rows'])+1,query=None,epochs=[],original=None,acquisition=None)
        self.state['pending']=pending;self.save();send,read,clock=reader.send,reader.original,reader.clock_ms
        def native_clock():
            value=clock();pending['epochs'].append(value);self.save();return value
        def owned_send(query):
            need(pending['query'] is None);pending['query']=deepcopy(ledger.command(query));self.save();return send(query)
        def original():
            raw=read()
            try:value=decode(raw,limit=ledger.LIMIT) if raw else None
            except (ValueError,UnicodeError):return raw
            if type(value) is dict and pending['query'] is not None and value.get('requestId')==pending['query']['commandId']:
                need(pending['original'] is None)
                self.originals.write(pending['index'],dict(iosAvatarInputReadRecordVersion=VERSION,
                    query=deepcopy(pending['query']),nativeRequestedEpochMs=pending['epochs'][0],packet=value))
            return raw
        reader.send,reader.original,reader.clock_ms=owned_send,original,native_clock
        try:
            value=reader.read(self.run);pending['acquisition']=deepcopy(reader.acquisition);self.save()
            row=self.finish('observed');need(same(value,self.packet(row)))
            ended=reader.monotonic();acquisition=row['acquisition']
            need(number(ended,acquisition['hostAfterMonotonic'],acquisition['hostBeforeMonotonic']+1.5)
                and ended-acquisition['hostBeforeMonotonic']<1.5)
            return row
        finally:reader.send,reader.original,reader.clock_ms=send,read,clock

    def delivered(self,row,original_intent):
        self.lock.assert_held();need(row in self.state['rows'] and row['status']=='observed')
        return ledger.delivered(self.packet(row),original_intent)
