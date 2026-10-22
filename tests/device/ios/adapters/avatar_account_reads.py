"""Account-only native originals after ordinary logout resets the Domain.

This sampler retains the unchanged native feature DTO. It never asks an Avatar
source to supply a nonzero session UUID after NodeList::reset, and never joins
or repairs a Domain. Every passive query and returned original remains owned.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.authentication_samples import _native
from ios.adapters.avatar_input_reads import IOSAvatarInputReads

VERSION=1


class IOSAvatarAccountReads:
    # The immutable writer's ownership transitions are shared with the already
    # qualified input-read owner. Packet grammar and acquisition stay separate.
    partial_file=IOSAvatarInputReads.partial_file
    storage=IOSAvatarInputReads.storage
    finish=IOSAvatarInputReads.finish
    recover=IOSAvatarInputReads.recover

    def __init__(self,store,root,binding,run,role,subject,lock,guard,reader=None,*,historical=False,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,clock_source=None):
        from adapters.original_frame_store import OriginalFrameStore
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and role in ('primary','actor') and subject in ('primary','actor') and type(historical) is bool
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.subject,self.lock=store,root,context(binding),identifier(run),role,subject,lock
        need(store.path.name=='ios-avatar-'+role+'-'+subject+'-account-reads.json' and store.path.parent==lock.path.parent)
        lock.assert_held();need(historical and reader is None or not historical and isinstance(reader,NativeFeatureObservation)
            and reader.ios and reader.native_clock_bound and str(reader.pid)==self.binding['processIdentity'])
        need(historical and clock_source is None or not historical and isinstance(clock_source,NativeFeatureObservation)
            and clock_source.ios and clock_source.pid==reader.pid and not clock_source.native_clock_bound)
        self.guard,self.reader,self.historical,self.epoch_ms,self.monotonic=guard,reader,historical,epoch_ms,monotonic
        self.clock_source=clock_source
        namespace='avatar-'+subject+'-account-read';prefix='avatar'+subject.capitalize()+'AccountRead'
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,namespace=namespace,schema_prefix=prefix,monotonic=monotonic)
        self.previous=store.read();self.state=dict(rows=[],pending=None)
        if self.previous is not None:self.state=self.parse(self.previous)

    def envelope(self,state):
        return dict(iosAvatarAccountReadsVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,subject=self.subject,
            artifactRoot=str(self.root),payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))

    @staticmethod
    def command(value):
        exact(value,{'schemaVersion','commandId','action'})
        import re
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-native-observe'
            and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']) is not None)
        return value

    def packet(self,row,previous=None):
        need(row['original'] is not None and row['original']['phase']=='saved')
        record=self.originals.read(row['original']);exact(record,{'iosAvatarAccountReadRecordVersion','query','packet'})
        need(type(record['iosAvatarAccountReadRecordVersion']) is int and record['iosAvatarAccountReadRecordVersion']==VERSION
            and same(record['query'],row['query']))
        value=record['packet'];validate(value,row['query']['commandId'],int(self.binding['processIdentity']),value.get('capturedEpochMs'),require_account=True)
        if previous is not None:
            need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
                and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['requestId']!=previous['requestId']
                and all(value['lifecycle'][key]>=count for key,count in previous['lifecycle'].items()))
            from adapters.native_account_observation import accept
            accept(accept(None,previous['account']),value['account'])
        return value

    def pending(self,row,index):
        need(type(row['index']) is int and row['index']==index)
        need(type(row['clocks']) is list and len(row['clocks'])<=64);previous=None
        for clock in row['clocks']:
            exact(clock,{'query','packet'});self.command(clock['query'])
            if clock['packet'] is not None:
                value=clock['packet'];validate(value,clock['query']['commandId'],int(self.binding['processIdentity']),value.get('capturedEpochMs'),require_account=True)
                if previous is not None:need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
                    and value['capturedEpochMs']>=previous['capturedEpochMs'])
                previous=value
            else:need(clock is row['clocks'][-1])
        if row['query'] is not None:self.command(row['query'])
        if row['original'] is not None:self.originals.original(row['original']);need(row['original']['index']==index and row['query'] is not None)
        if row['acquisition'] is not None:
            need(len(row['clocks'])>=3 and all(clock['packet'] is not None for clock in row['clocks']))
            packet=self.packet(row);first,last=row['clocks'][0]['packet'],row['clocks'][-1]['packet']
            need(first['instance']==packet['instance']==last['instance'] and first['sequence']<packet['sequence']<last['sequence']
                and first['capturedEpochMs']<=packet['capturedEpochMs']<=last['capturedEpochMs']
                and last['capturedEpochMs']-first['capturedEpochMs']<1500)
            a=row['acquisition'];exact(a,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic','originalSha256'})
            start,end=a['hostBeforeEpochMs'],a['hostAfterEpochMs'];before,after=a['hostBeforeMonotonic'],a['hostAfterMonotonic']
            need(number(start,1,1e15) and number(end,start,start+1500) and end-start<1500
                and number(before,0,1e15) and number(after,before,before+1.5) and after-before<1.5
                and abs(end-start-(after-before)*1000)<=250 and digest(self.packet(row))==a['originalSha256'])

    def parse(self,value):
        exact(value,{'iosAvatarAccountReadsVersion','binding','runId','role','subject','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'rows','pending'});need(type(state['rows']) is list and len(state['rows'])<=128);previous=None;prefix=None;native=None
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','query','original','acquisition','status','partialFile','clocks'});self.pending(row,index)
            need(row['status'] in ('observed','abandoned'))
            if row['original'] is not None:
                need(same(row['partialFile'],self.partial_file(row['original'])))
                if row['original']['phase']=='saved':previous=self.packet(row,previous)
            else:need(row['partialFile'] is None)
            if row['status']=='observed':need(row['original'] is not None and row['original']['phase']=='saved' and row['acquisition'] is not None)
            packets=[clock['packet'] for clock in row['clocks'] if clock['packet'] is not None]
            if row['original'] is not None and row['original']['phase']=='saved':packets.append(self.packet(row))
            from adapters.native_account_observation import accept
            for packet in sorted(packets,key=lambda value:value['sequence']):
                if native is not None:need(packet['instance']==native['instance'] and packet['sequence']>native['sequence']
                    and packet['capturedEpochMs']>=native['capturedEpochMs'])
                prefix=accept(prefix,packet['account']);native=packet
        if state['pending'] is not None:
            exact(state['pending'],{'index','query','original','acquisition','clocks'});self.pending(state['pending'],len(state['rows'])+1)
        return deepcopy(state)

    def save(self):
        self.bound();value=self.envelope(self.state);self.parse(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def read(self):
        self.bound();self.recover();need(len(self.state['rows'])<128);previous=None
        for row in self.state['rows']:
            # A returned partial writer retains its exact inode and blocks a
            # later sampler from erasing an unretained native prefix.
            need(row['original'] is None or row['original']['phase']=='saved')
            if row['original'] is not None:previous=self.packet(row,previous)
        reader,clock_source=self.reader,self.clock_source
        if previous is not None and reader.sequence!=previous['sequence']:_native(reader,previous)
        previous_clock=next((clock['packet'] for row in reversed(self.state['rows']) for clock in reversed(row['clocks']) if clock['packet'] is not None),None)
        if previous_clock is not None and clock_source.sequence!=previous_clock['sequence']:_native(clock_source,previous_clock)
        p=dict(index=len(self.state['rows'])+1,query=None,original=None,acquisition=None,clocks=[])
        self.state['pending']=p;self.save();send,original=reader.send,reader.original
        clock_send,clock_original=clock_source.send,clock_source.original
        def owned_clock_send(query):
            need(len(p['clocks'])<64);p['clocks'].append(dict(query=deepcopy(self.command(query)),packet=None));self.save();return clock_send(query)
        def owned_clock_original():
            raw=clock_original()
            try:value=decode(raw) if raw else None
            except (ValueError,UnicodeError):return raw
            row=p['clocks'][-1]
            if type(value) is dict and value.get('requestId')==row['query']['commandId']:
                if row['packet'] is None:row['packet']=deepcopy(value);self.save()
                else:need(same(row['packet'],value))
            return raw
        def owned_send(query):
            need(p['query'] is None);p['query']=deepcopy(self.command(query));self.save();return send(query)
        def owned_original():
            raw=original()
            try:value=decode(raw) if raw else None
            except (ValueError,UnicodeError):return raw
            if type(value) is dict and p['query'] is not None and value.get('requestId')==p['query']['commandId']:
                need(p['original'] is None)
                self.originals.write(p['index'],dict(iosAvatarAccountReadRecordVersion=VERSION,query=deepcopy(p['query']),packet=value))
            return raw
        reader.send,reader.original=owned_send,owned_original
        clock_source.send,clock_source.original=owned_clock_send,owned_clock_original
        start,mono=self.epoch_ms(),self.monotonic()
        try:
            value=reader.read(reader.sequence,require_account=True)
            p['acquisition']=dict(hostBeforeEpochMs=start,hostAfterEpochMs=self.epoch_ms(),hostBeforeMonotonic=mono,
                hostAfterMonotonic=self.monotonic(),originalSha256=digest(value));self.save()
            row=self.finish('observed');need(same(value,self.packet(row)))
            end,last=self.epoch_ms(),self.monotonic();need(number(end,start,start+1500) and end-start<1500
                and number(last,mono,mono+1.5) and last-mono<1.5 and abs(end-start-(last-mono)*1000)<=250)
            return row
        finally:
            reader.send,reader.original=send,original
            clock_source.send,clock_source.original=clock_send,clock_original

    def reference(self,row):
        self.lock.assert_held();need(row in self.state['rows'] and row['status']=='observed')
        return dict(index=row['index'],sha256=digest(self.packet(row)))

    @classmethod
    def archive(cls,value,store,root,binding,run,role,subject,lock):
        need(same(store.read(),value));return cls(store,root,binding,run,role,subject,lock,lambda:True,historical=True)
