"""Durable read-only Snapshot manifest with independent native clock originals.

This is evidence transport, not installed-code admission or a whole feature.
The caller's candidate guard and source lock must already be held.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.feature_observation import FeatureObservation
from snapshot_file_contract import MAX_FILES,MAX_FILE_BYTES,read_request

VERSION=1
FILE='ios-snapshot-file-result.json'
LIMIT=8192


def manifest(value,query,pid):
    read_request(query);need(query['operation']=='list')
    exact(value,{'schemaVersion','commandId','operation','prefix','processId','sampleEpochMs','ok','files'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==query['commandId']
        and value['operation']=='list' and value['prefix']==query['prefix'] and type(value['processId']) is int
        and value['processId']==pid and integer(pid,1) and integer(value['sampleEpochMs'],1) and value['ok'] is True
        and type(value['files']) is list and len(value['files'])<=MAX_FILES)
    names=[];total=0
    for row in value['files']:
        exact(row,{'name','size','revision','sha256'})
        need(integer(row['size'],0,MAX_FILE_BYTES) and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
        read_request(dict(query,operation='read',name=row['name'],revision=row['revision'],offset=0))
        names.append(row['name']);total+=row['size']
    need(names==sorted(set(names)) and total<=MAX_FILE_BYTES)
    return value


def original(frame,pid):
    exact(frame,{'query','packet','clockJoin'})
    manifest(frame['packet'],frame['query'],pid)
    validate_join(frame['clockJoin'],dict(manifest=frame['packet']))
    need(frame['clockJoin']['nativeBefore']['processId']==pid)
    return frame


def absent(frame,pid,run,mode):
    """A bounded historical original, never permission to skip later quiet reads."""
    identifier(run);need(mode in ('still-png','still-jpg','animated','panorama','cubemap'))
    original(frame,pid);need(frame['query']['prefix']=='parity-'+run[:16]+'-'+mode and frame['packet']['files']==[])
    return dict(iosSnapshotManifestAbsenceVersion=1,processId=pid,runId=run,prefix=frame['query']['prefix'],
        sampleEpochMs=frame['packet']['sampleEpochMs'],quietWindowRequired=True)


class SnapshotManifest:
    _store_prefix='ios-snapshot'
    _name='manifest'
    _owner_key='iosSnapshotManifestOwnerVersion'
    _namespace='snapshot-manifest'
    _schema_prefix='snapshotManifest'
    _max_index=128
    _file=FILE
    _limit=LIMIT
    _source_name='manifest'
    _packet=staticmethod(manifest)
    _frame=staticmethod(original)

    @staticmethod
    def _query(query):read_request(query);need(query['operation']=='list')

    @classmethod
    def history(cls,store,lock,binding,run,role,index):
        """Construct only a local original reader after SDK retirement."""
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));context(binding);identifier(run)
        need(role in ('primary','actor') and integer(index,1,cls._max_index) and re.fullmatch('[1-9][0-9]*',binding['processIdentity'])
            and store.path.parent==lock.path.parent and store.path.name==cls._store_prefix+'-'+role+'-'+cls._name+'-'+format(index,'04d')+'.json')
        reader=cls.__new__(cls);reader.store,reader.lock,reader.binding=store,lock,deepcopy(binding)
        reader.run,reader.role,reader.index,reader.pid=run,role,index,int(binding['processIdentity'])
        reader.feature=reader.clock=None
        def unavailable():raise NativeUIError('Historical Snapshot manifest cannot issue live operations')
        reader.guard=unavailable;lock.assert_held();reader.previous=store.read();need(reader.previous is not None)
        reader.state=reader.load(reader.previous);return reader

    def __init__(self,store,lock,binding,run,role,index,feature,clock,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(feature,FeatureObservation) and isinstance(clock,NativeClockAcquisition) and callable(guard))
        context(binding);identifier(run);need(role in ('primary','actor') and integer(index,1,self._max_index)
            and re.fullmatch('[1-9][0-9]*',binding['processIdentity'])
            and store.path.parent==lock.path.parent and store.path.name==self._store_prefix+'-'+role+'-'+self._name+'-'+format(index,'04d')+'.json')
        self.store,self.lock,self.binding,self.run,self.role,self.index=store,lock,deepcopy(binding),run,role,index
        self.feature,self.clock,self.guard=feature,clock,guard;self.pid=int(binding['processIdentity'])
        need(clock.native.pid==self.pid and clock.native.ios)
        self.previous=store.read();self.state=None if self.previous is None else self.load(self.previous)

    def files(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,self.role,self.guard if live else lambda:True,
            self.storage if live else lambda *_:need(False),namespace=self._namespace,schema_prefix=self._schema_prefix)

    def load(self,value):
        exact(value,{self._owner_key,'binding','runId','role','index','payload'})
        need(type(value[self._owner_key]) is int and value[self._owner_key]==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index)
        records=unpack(value['payload']);need(len(records)==1);state=records[0]
        exact(state,{'phase','query','started','storage','proof'})
        need(state['phase'] in ('reserved','issued','saved'));self._query(state['query'])
        need(state['query']['prefix'].startswith('parity-'+self.run[:16]+'-'))
        if state['phase']=='reserved':need(state['started'] is None and state['storage'] is None and state['proof'] is None)
        else:
            started=state['started'];exact(started,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(started['clockJoinVersion']) is int and started['clockJoinVersion']==1
                and number(started['hostBeforeEpochMs'],1,1e15) and number(started['hostBeforeMonotonic'],0,1e15))
            from adapters.native_feature_observation import validate
            packet=started['nativeBefore'];validate(packet,packet.get('requestId'),self.pid,packet.get('capturedEpochMs'))
        if state['storage'] is not None:self.files().original(state['storage']);need(state['storage']['index']==self.index)
        if state['phase']=='saved':
            need(state['storage'] is not None and state['storage']['phase']=='saved'
                and same(self.files().expand(state['proof']),state['storage']))
            frame=self.files().read(self.files().expand(state['proof']));self._frame(frame,self.pid)
            need(same(frame['query'],state['query']) and all(same(frame['clockJoin'][key],val) for key,val in state['started'].items()))
        else:need(state['proof'] is None)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        self.feature.guard();need(self.feature.process['pid']==self.pid)

    def deadline(self):
        before=self.state['started']['hostBeforeMonotonic'];now=self.clock.monotonic()
        need(number(now,before,before+1.5) and now-before<1.5)

    def save(self):
        self.bound();value=dict({self._owner_key:VERSION},binding=self.binding,runId=self.run,role=self.role,
            index=self.index,payload=pack([self.state]));self.load(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def reserve(self,mode):
        self.bound();need(self.state is None and mode in ('still-png','still-jpg','animated','panorama','cubemap'))
        query=read_request(dict(schemaVersion=1,action='snapshot-files',commandId='ios-'+uuid.uuid4().hex,
            operation='list',prefix='parity-'+self.run[:16]+'-'+mode))
        return self._reserve(query)

    def _reserve(self,query):
        self.bound();need(self.state is None);self._query(query)
        self.state=dict(phase='reserved',query=deepcopy(query),started=None,storage=None,proof=None);self.save();return deepcopy(query)

    def send(self,host_barrier):
        self.bound();need(self.state is not None and self.state['phase']=='reserved')
        self.clock.begin(host_barrier);self.state.update(phase='issued',started=deepcopy(self.clock.started));self.save()
        # Include process verification and the actual HTTP boundary in the
        # original acquisition budget. Never reissue an uncertain command.
        previous=getattr(self.feature,'before_send',None)
        def before_send():
            if previous is not None:need(callable(previous) and previous() is not False)
            self.bound();self.deadline();return True
        self.feature.before_send=before_send
        try:self.feature.send(deepcopy(self.state['query']))
        finally:self.feature.before_send=previous

    def storage(self,kind,value):
        self.bound();need(self.state['phase']=='issued' and kind=='original' and value['index']==self.index)
        self.files().original(value);old=self.state['storage']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(old[k],value[k]) for k in old if k not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        self.state['storage']=deepcopy(value);self.save()

    def recover(self):
        """Read this original only; saved storage is adopted without SDK access."""
        self.bound();need(self.state is not None and self.state['phase']=='issued');store=self.files();saved=self.state['storage']
        if saved is not None:
            need(saved['phase'] in ('opened','saved'));frame=store.read(saved);self._frame(frame,self.pid)
            if saved['phase']=='opened':saved=dict(saved,phase='saved');self.storage('original',saved)
            proof=store.compact(saved)
        else:
            started=self.state['started'];self.deadline()
            remote=self.feature.remote.rsplit('/',1)[0]+'/'+self._file
            raw=self.feature.original(remote=remote,limit=self._limit);packet=decode(raw,limit=self._limit)
            self._packet(packet,self.state['query'],self.pid);self.bound()
            need(self.clock.started is None or same(self.clock.started,started));self.clock.started=deepcopy(started)
            join=self.clock.finish({self._source_name:packet},((self._source_name,'sampleEpochMs'),))
            frame=dict(query=deepcopy(self.state['query']),packet=packet,clockJoin=join);self._frame(frame,self.pid)
            proof=self.files(live=True).write(self.index,frame)
        need(same(frame['query'],self.state['query']) and all(same(frame['clockJoin'][key],val) for key,val in self.state['started'].items()))
        self.state.update(phase='saved',proof=proof);self.save();return deepcopy(frame)

    def historical(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.state['phase']=='saved')
        self.state=self.load(self.previous);return self.files().read(self.files().expand(self.state['proof']))
