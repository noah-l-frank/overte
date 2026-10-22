"""One-shot native unlink responsibility, original ACK and passive recovery.

A positive result still requires independent fresh absence and paired quiet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.emote_native_prefix import follow
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket,qualified
from ios.adapters import snapshot_owned_files as source

VERSION=1
RECEIPT=source.REMOVE+'.json'


def receipt(raw,query):
    need(type(raw) is str and 0<len(raw.encode())<=1024)
    try:value=decode(raw,limit=1024)
    except (ValueError,UnicodeError):need(False)
    exact(value,{'iosSnapshotFileRemoveReceiptVersion','requestId','accepted'})
    need(type(value['iosSnapshotFileRemoveReceiptVersion']) is int and value['iosSnapshotFileRemoveReceiptVersion']==1
        and value['requestId']==query['commandId'] and type(value['accepted']) is bool)
    return value


class SnapshotRemoveOwner:
    def setup(self,store,lock,binding,run,role,index):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and integer(index,1,128))
        self.store,self.lock,self.binding,self.run,self.role,self.index=store,lock,deepcopy(context(binding)),identifier(run),role,index
        need(re.fullmatch('[1-9][0-9]*',binding['processIdentity']));self.pid=int(binding['processIdentity'])
        need(lock.path==store.path.with_name('script-feature-sources.lock')
            and store.path.name=='ios-snapshot-'+role+'-remove-'+format(index,'04d')+'.json');lock.assert_held()

    @classmethod
    def history(cls,store,lock,binding,run,role,index):
        result=cls.__new__(cls);result.setup(store,lock,binding,run,role,index)
        result.feature=result.native=None;result.guard=lambda:need(False)
        result.previous=store.read();need(result.previous is not None);result.state=result.load(result.previous);return result

    def __init__(self,store,lock,binding,run,role,index,feature,native,guard,*,epoch_ms,monotonic):
        self.setup(store,lock,binding,run,role,index)
        need(isinstance(feature,FeatureObservation) and isinstance(native,NativeFeatureObservation) and native.ios and native.pid==self.pid
            and all(callable(f) for f in (guard,epoch_ms,monotonic)));feature.guard();need(feature.process['pid']==self.pid)
        self.feature,self.native,self.guard,self.epoch_ms,self.monotonic=feature,native,guard,epoch_ms,monotonic
        self.previous=store.read();self.state=None if self.previous is None else self.load(self.previous)

    def owner(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,128))
        owner=SnapshotOwnedPacket.history(PrivateFeatureState(self.store.path.with_name(
            'ios-snapshot-'+self.role+'-native-owned-'+format(reference['index'],'04d')+'.json')),
            self.lock,self.binding,self.run,self.role,reference['index'])
        need(digest(owner.previous)==reference['sha256']);return owner

    def selected(self,frame,query):
        need(frame['query']['runId']==self.run and frame['packet']['source']['complete'])
        rows=[r for r in frame['packet']['source']['files'] if r['id']==query['fileId']];need(len(rows)==1)
        row=rows[0];need(row['manifestQuery']['commandId']==query['manifestCommandId']
            and row['capture']['nativeDrained'] and row['capture']['terminal']);return row

    def load(self,value):
        exact(value,{'iosSnapshotRemoveOwnerVersion','binding','runId','role','index','payload'})
        need(type(value['iosSnapshotRemoveOwnerVersion']) is int and value['iosSnapshotRemoveOwnerVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index)
        states=unpack(value['payload']);need(len(states)==1);state=states[0]
        exact(state,{'phase','query','admission','started','receiptRaw','observations'})
        source.remove_command(state['query']);need(state['query']['runId']==self.run and state['phase'] in ('reserved','issued','observed')
            and type(state['observations']) is list and len(state['observations'])<=128)
        admitted=self.owner(state['admission']).historical();qualified(admitted,self.pid)
        need(not self.selected(admitted,state['query'])['removeCommandId'])
        if state['phase']=='reserved':need(state['started'] is state['receiptRaw'] is None and not state['observations'])
        else:
            start=state['started'];exact(start,{'hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            before=start['nativeBefore'];native_packet(before,before.get('requestId'),self.pid,before.get('capturedEpochMs'))
            follow(admitted['acquisition']['nativeAfter'],before)
        if state['receiptRaw'] is not None:receipt(state['receiptRaw'],state['query'])
        if state['observations']:need(state['receiptRaw'] is not None)
        seen={state['admission']['index']}
        for ref in state['observations']:
            self.owner(ref).historical();need(ref['index'] not in seen);seen.add(ref['index'])
        if state['phase']=='observed':self.prove(state)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));self.feature.guard()
        need(self.feature.process['pid']==self.pid)

    def save(self):
        self.bound();value=dict(iosSnapshotRemoveOwnerVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,index=self.index,
            payload=pack([self.state]));self.load(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def reserve(self,owner,file_id):
        self.bound();need(self.state is None and type(owner) is SnapshotOwnedPacket and owner.binding==self.binding and owner.run==self.run
            and owner.role==self.role and owner.lock.path==self.lock.path and owner.store.path.parent==self.store.path.parent)
        frame=owner.historical();qualified(frame,self.pid);identity=source.identity(file_id)
        rows=[r for r in frame['packet']['source']['files'] if r['id']==identity];need(len(rows)==1)
        query=source.remove_command(dict(schemaVersion=1,action=source.REMOVE,commandId='ios-'+uuid.uuid4().hex,runId=self.run,
            fileId=identity,manifestCommandId=rows[0]['manifestQuery']['commandId']))
        self.state=dict(phase='reserved',query=query,admission=dict(index=owner.index,sha256=digest(owner.previous)),started=None,
            receiptRaw=None,observations=[]);self.save();return deepcopy(query)

    def deadline(self):
        start=self.state['started'];now,mono=self.epoch_ms(),self.monotonic();admitted=self.owner(self.state['admission']).historical()
        need(number(now,start['hostBeforeEpochMs'],1e15) and number(mono,start['hostBeforeMonotonic'],1e15)
            and now-start['hostBeforeEpochMs']<1500 and mono-start['hostBeforeMonotonic']<1.5
            and abs(now-start['hostBeforeEpochMs']-(mono-start['hostBeforeMonotonic'])*1000)<=250
            and 0<=now-admitted['acquisition']['hostBeforeEpochMs']<1500
            and 0<=mono-admitted['acquisition']['hostBeforeMonotonic']<1.5)

    def send(self):
        self.bound();need(self.state is not None and self.state['phase']=='reserved')
        epoch,mono=self.epoch_ms(),self.monotonic();need(number(epoch,1,1e15) and number(mono,0,1e15))
        before=self.native.read(self.native.sequence)
        self.state.update(phase='issued',started=dict(hostBeforeEpochMs=epoch,hostBeforeMonotonic=mono,nativeBefore=deepcopy(before)));self.save()
        prior=getattr(self.feature,'before_send',None)
        def guard():
            if prior is not None:need(callable(prior) and prior() is not False)
            self.bound();self.deadline();return True
        self.feature.before_send=guard
        try:self.feature.send(deepcopy(self.state['query']))
        finally:self.feature.before_send=prior

    def acknowledge(self):
        """Passive ACK read before any new probe command can replace the input."""
        self.bound();need(self.state is not None and self.state['phase']=='issued')
        if self.state['receiptRaw'] is None:
            remote=self.feature.remote.rsplit('/',1)[0]+'/'+RECEIPT
            raw=self.feature.original(remote=remote,limit=1024);receipt(raw,self.state['query'])
            self.state['receiptRaw']=raw;self.save()
        return deepcopy(receipt(self.state['receiptRaw'],self.state['query']))

    def prove(self,state):
        need(state['receiptRaw'] is not None and state['observations'])
        before=self.owner(state['admission']).historical();last=before['packet'];native=state['started']['nativeBefore']
        for ref in state['observations']:
            frame=self.owner(ref).historical();packet=frame['packet']
            source.validate(packet,frame['query'],self.pid,previous=last)
            follow(native,frame['acquisition']['nativeBefore']);native=frame['acquisition']['nativeAfter']
            need(frame['acquisition']['nativeBefore']['capturedEpochMs']>=state['started']['nativeBefore']['capturedEpochMs'])
            last=packet
        fact=source.removed(last,state['query'],self.pid)
        jobs=[r for r in last['source']['jobs'] if same(r['query'],state['query'])];need(len(jobs)==1
            and jobs[0]['queuedEpochMs']>=state['started']['nativeBefore']['capturedEpochMs'])
        return fact

    def observe(self,owner):
        self.bound();need(self.state is not None and self.state['phase']=='issued' and self.state['receiptRaw'] is not None
            and type(owner) is SnapshotOwnedPacket and owner.binding==self.binding and owner.run==self.run and owner.role==self.role
            and owner.lock.path==self.lock.path and owner.store.path.parent==self.store.path.parent)
        owner.historical();reference=dict(index=owner.index,sha256=digest(owner.previous))
        # Preserve the original before interpreting cross-source continuity or
        # outcome. A bad transition remains owned and cannot produce a result.
        self.state['observations'].append(reference);self.save();fact=self.prove(self.state)
        self.state['phase']='observed';self.save();return fact

    def proof(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.state['phase']=='observed')
        self.state=self.load(self.previous);return self.prove(self.state)
