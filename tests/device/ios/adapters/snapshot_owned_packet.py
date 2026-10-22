"""One native owned-file query and exact raw bytes, including late recovery.

A retained late original is historical evidence. Only the unchanged strict
native/host clock join can admit it for a subsequent live removal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
import re
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate as native_packet
from adapters.native_clock_join import digest,validate_join
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.emote_native_prefix import follow
from ios.adapters import snapshot_owned_files as source,snapshot_file_work

VERSION=1
KINDS={'owned':source,'file-work':snapshot_file_work}


def originals(packet):
    return dict(packet=packet,getterBefore=dict(capturedEpochMs=packet['clockBefore']['epochMs']),
        getterAfter=dict(capturedEpochMs=packet['clockAfter']['epochMs']))


def acquisition(value,pid):
    exact(value,{'hostBeforeEpochMs','hostBeforeMonotonic','hostAfterEpochMs','hostAfterMonotonic','nativeBefore','nativeAfter'})
    need(number(value['hostBeforeEpochMs'],1,1e15) and number(value['hostAfterEpochMs'],value['hostBeforeEpochMs'],1e15)
        and number(value['hostBeforeMonotonic'],0,1e15) and number(value['hostAfterMonotonic'],value['hostBeforeMonotonic'],1e15))
    for packet in (value['nativeBefore'],value['nativeAfter']):native_packet(packet,packet.get('requestId'),pid,packet.get('capturedEpochMs'))
    follow(value['nativeBefore'],value['nativeAfter'])
    host=value['hostAfterEpochMs']-value['hostBeforeEpochMs'];mono=(value['hostAfterMonotonic']-value['hostBeforeMonotonic'])*1000
    native=value['nativeAfter']['capturedEpochMs']-value['nativeBefore']['capturedEpochMs']
    need(abs(host-mono)<=250 and abs(native-mono)<=250);return value


def original(frame,pid,kind='owned'):
    need(kind in KINDS);module=KINDS[kind]
    exact(frame,{'query','raw','packet','acquisition'});module.command(frame['query'])
    need(type(frame['raw']) is str and len(frame['raw'].encode())<=module.LIMIT
        and same(decode(frame['raw'],limit=module.LIMIT),frame['packet']))
    module.validate(frame['packet'],frame['query'],pid);span=acquisition(frame['acquisition'],pid)
    need(span['nativeBefore']['capturedEpochMs']<=frame['packet']['clockBefore']['epochMs']
        <=frame['packet']['clockAfter']['epochMs']<=span['nativeAfter']['capturedEpochMs'])
    return frame


def qualified(frame,pid,kind='owned'):
    """Strict original acquisition; no new envelope around a late source."""
    original(frame,pid,kind);values=originals(frame['packet']);span=frame['acquisition']
    join=dict(span,clockJoinVersion=1,originalsSha256=digest(values),sourceTimes=[
        dict(source=key,field='capturedEpochMs',epochMs=values[key]['capturedEpochMs']) for key in ('getterBefore','getterAfter')])
    validate_join(join,values);return deepcopy(join)


class SnapshotOwnedPacket:
    _name='native-owned'
    _key='iosSnapshotOwnedPacketVersion'
    _namespace='snapshot-native-owned'
    _schema='snapshotNativeOwned'
    _kind='owned'
    _source=source
    @classmethod
    def history(cls,store,lock,binding,run,role,index):
        result=cls.__new__(cls);result.setup(store,lock,binding,run,role,index)
        result.feature=result.native=None
        def unavailable():need(False)
        result.guard=unavailable;result.previous=store.read();need(result.previous is not None)
        result.state=result.load(result.previous);return result

    def setup(self,store,lock,binding,run,role,index):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and integer(index,1,128))
        self.store,self.lock,self.binding,self.run,self.role,self.index=store,lock,deepcopy(context(binding)),identifier(run),role,index
        need(re.fullmatch('[1-9][0-9]*',binding['processIdentity']))
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity']
            and lock.path==store.path.with_name('script-feature-sources.lock')
            and store.path.name=='ios-snapshot-'+role+'-'+self._name+'-'+format(index,'04d')+'.json');lock.assert_held()

    def __init__(self,store,lock,binding,run,role,index,feature,native,guard,*,epoch_ms,monotonic):
        self.setup(store,lock,binding,run,role,index)
        need(isinstance(feature,FeatureObservation) and isinstance(native,NativeFeatureObservation) and native.ios
            and native.pid==self.pid and all(callable(f) for f in (guard,epoch_ms,monotonic)))
        feature.guard();need(feature.process['pid']==self.pid)
        self.feature,self.native,self.guard,self.epoch_ms,self.monotonic=feature,native,guard,epoch_ms,monotonic
        self.previous=store.read();self.state=None if self.previous is None else self.load(self.previous)

    def files(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,self.role,self.guard if live else lambda:True,
            self.storage if live else lambda *_:need(False),namespace=self._namespace,schema_prefix=self._schema)

    def load(self,value):
        exact(value,{self._key,'binding','runId','role','index','payload'})
        need(type(value[self._key]) is int and value[self._key]==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index)
        states=unpack(value['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','query','started','storage','proof'})
        self._source.command(state['query']);need(state['query']['runId']==self.run and state['phase'] in ('reserved','issued','retained'))
        if state['phase']=='reserved':need(state['started'] is state['storage'] is state['proof'] is None)
        else:
            start=state['started'];exact(start,{'hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            packet=start['nativeBefore'];native_packet(packet,packet.get('requestId'),self.pid,packet.get('capturedEpochMs'))
        if state['storage'] is not None:self.files().original(state['storage']);need(state['storage']['index']==self.index)
        if state['phase']=='retained':
            need(state['storage'] is not None and state['storage']['phase']=='saved'
                and same(self.files().expand(state['proof']),state['storage']))
            frame=self.files().read(state['storage']);original(frame,self.pid,self._kind)
            need(same(frame['query'],state['query']) and all(same(frame['acquisition'][key],v) for key,v in state['started'].items()))
        else:need(state['proof'] is None)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));self.feature.guard()
        need(self.feature.process['pid']==self.pid)

    def save(self):
        self.bound();value=dict({self._key:VERSION},binding=self.binding,runId=self.run,role=self.role,
            index=self.index,payload=pack([self.state]));self.load(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def reserve(self):
        self.bound();need(self.state is None)
        query=self._source.command(dict(schemaVersion=1,action=self._source.ACTION,commandId='ios-'+uuid.uuid4().hex,runId=self.run))
        self.state=dict(phase='reserved',query=query,started=None,storage=None,proof=None);self.save();return deepcopy(query)

    def deadline(self):
        start=self.state['started'];now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,start['hostBeforeEpochMs'],start['hostBeforeEpochMs']+1500)
            and number(mono,start['hostBeforeMonotonic'],start['hostBeforeMonotonic']+1.5)
            and now-start['hostBeforeEpochMs']<1500 and mono-start['hostBeforeMonotonic']<1.5
            and abs(now-start['hostBeforeEpochMs']-(mono-start['hostBeforeMonotonic'])*1000)<=250)

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

    def storage(self,kind,value):
        self.bound();need(kind=='original' and self.state['phase']=='issued' and value['index']==self.index)
        self.files().original(value);old=self.state['storage']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[k],old[k]) for k in old if k not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        self.state['storage']=deepcopy(value);self.save()

    def retain(self):
        """Adopt/pull only this original reply; do not resend or resample it."""
        self.bound();need(self.state is not None and self.state['phase']=='issued');files=self.files();saved=self.state['storage']
        if saved is not None:
            need(saved['phase'] in ('opened','saved'));frame=files.read(saved);original(frame,self.pid,self._kind)
            if saved['phase']=='opened':saved=dict(saved,phase='saved');self.storage('original',saved)
            proof=files.compact(saved)
        else:
            remote=self.feature.remote.rsplit('/',1)[0]+'/'+self._source.FILE
            raw=self.feature.original(remote=remote,limit=self._source.LIMIT);packet=decode(raw,limit=self._source.LIMIT)
            self._source.validate(packet,self.state['query'],self.pid);after=self.native.read(self.native.sequence)
            span=dict(self.state['started'],hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic(),nativeAfter=deepcopy(after))
            frame=dict(query=deepcopy(self.state['query']),raw=raw,packet=packet,acquisition=span);original(frame,self.pid,self._kind)
            proof=self.files(live=True).write(self.index,frame)
        need(same(frame['query'],self.state['query']) and all(same(frame['acquisition'][key],v) for key,v in self.state['started'].items()))
        self.state.update(phase='retained',proof=proof);self.save();return deepcopy(frame)

    def historical(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.state['phase']=='retained')
        self.state=self.load(self.previous);return self.files().read(self.state['storage'])

    def qualified(self):return qualified(self.historical(),self.pid,self._kind)
