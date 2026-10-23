"""Issued-once original native bootstrap for an admitted existing Tablet SDK.

The bootstrap establishes a current original native birth against genuine
prepared setup metadata. It creates no SDK and performs no installed-code
verification write. Unknown query/write returns retain their responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import time
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,validate as native_original,LIMIT
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import record as original_read
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.graphics_history import follow_native
from ios.adapters.tablet_web_admission import validate as admission_original
from feature_journeys.contract import identifier

VERSION=1


class TabletWebContext:
    def __init__(self,root,binding,run,role,lock,admission,setup_native,guard,*,monotonic=time.monotonic,historical=False):
        self.root=Path(root);self.binding=deepcopy(context(binding));self.run=identifier(run);self.role=role
        need(role in ('primary','actor') and isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock'
            and callable(guard) and callable(monotonic) and type(historical) is bool)
        self.lock,self.guard,self.monotonic,self.historical=lock,guard,monotonic,historical
        self.admission,self.setup=deepcopy(admission),deepcopy(setup_native)
        admission_original(self.admission,self.binding)
        native_original(self.setup,self.setup['requestId'],int(self.binding['processIdentity']),self.setup['capturedEpochMs'])
        self.store=PrivateFeatureState(self.root/('tabletweb-context-'+run+'-'+role+'.json'))
        self.state=self.store.read()
        if self.state is None:
            self.live();self.state=dict(tabletWebContextVersion=VERSION,binding=self.binding,runId=self.run,role=role,admission=self.admission,setupNative=self.setup,
                status='prepared',query=None,pending=None,original=None,inspection=None,unsafe=[])
            self.store.write(self.state,None)
        self.saved=deepcopy(self.state)
        self.originals=OriginalFrameStore(root,binding,run,role,self.file_guard,self.intent,namespace='tabletweb-bootstrap',schema_prefix='tabletWebBootstrap',monotonic=monotonic)
        self.validate()

    def live(self):
        need(not self.historical);self.lock.assert_held();need(self.guard() is not False)

    def file_guard(self):
        # Pure local ownership only. The original native reader separately
        # performs its actual process/SDK guard at native transport boundaries.
        if not self.historical:self.lock.assert_held()
        return True

    def save(self):
        need(not self.historical);self.lock.assert_held();self.store.write(self.state,self.saved);self.saved=deepcopy(self.state)

    def intent(self,kind,value):
        need(kind=='original' and self.state['query'] is not None);self.state['pending']=deepcopy(value);self.state['inspection']=None;self.save()

    def inspect(self):
        value=self.originals.original(self.state['pending']);path=self.originals.path(value)
        if value['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),value);raw=stream.read(value['bytes']+1);self.originals.file(path,stream.fileno(),value)
        need(len(raw)<=value['bytes']);original_read(path)
        result=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        if value['phase']=='saved':need(result['complete'])
        return result

    def packet(self,reference):
        record=self.originals.read(reference);exact(record,{'tabletWebBootstrapPacketVersion','admission','setupNative','query','rawJSON'})
        need(type(record['tabletWebBootstrapPacketVersion']) is int and record['tabletWebBootstrapPacketVersion']==VERSION
            and same(record['admission'],self.admission) and same(record['setupNative'],self.setup) and same(record['query'],self.state['query'])
            and type(record['rawJSON']) is str and len(record['rawJSON'].encode())<=LIMIT)
        value=decode(record['rawJSON']);native_original(value,value['requestId'],value['processId'],value['capturedEpochMs'])
        need(value['requestId']==record['query']['commandId'] and value['processId']==int(self.binding['processIdentity']))
        need(value['requestedEpochMs']>=self.admission['installedBefore']['observation']['capturedEpochMs'])
        follow_native(self.setup,value);return value

    def validate(self):
        value=self.state;exact(value,{'tabletWebContextVersion','binding','runId','role','admission','setupNative','status','query','pending','original','inspection','unsafe'})
        need(type(value['tabletWebContextVersion']) is int and value['tabletWebContextVersion']==VERSION and same(value['binding'],self.binding)
            and value['runId']==self.run and value['role']==self.role and same(value['admission'],self.admission) and same(value['setupNative'],self.setup)
            and value['status'] in ('prepared','issued','returned','failed') and type(value['unsafe']) is list and len(value['unsafe'])<=16)
        for row in value['unsafe']:
            exact(row,{'bytes','sha256'});need(integer(row['bytes'],1,LIMIT) and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
        query=value['query']
        if query is None:need(value['status']=='prepared' and value['pending'] is value['original'] is value['inspection'] is None and not value['unsafe']);return
        exact(query,{'schemaVersion','commandId','action'});need(type(query['schemaVersion']) is int and query['schemaVersion']==1
            and query['action']=='feature-native-observe' and type(query['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',query['commandId']))
        if value['pending'] is not None:
            need(value['original'] is None);actual=self.inspect()
            if value['inspection'] is not None:need(same(actual,value['inspection']))
        else:need(value['inspection'] is None)
        if value['original'] is not None:
            need(value['status']=='returned' and not value['unsafe']);self.packet(self.originals.expand(value['original']))
        else:need(value['status']!='returned')

    def bootstrap(self,reader):
        self.live();self.validate();need(self.state['status']=='prepared' and isinstance(reader,NativeFeatureObservation) and reader.ios and reader.pid==int(self.binding['processIdentity']))
        send,original=reader.send,reader.original;stored=[None]
        def issued(query):
            need(self.state['query'] is None);self.state.update(status='issued',query=deepcopy(query));self.save();self.validate();return send(query)
        def received():
            raw=original()
            if not raw:return raw
            need(type(raw) is str and len(raw.encode())<=LIMIT);packet=decode(raw)
            if type(packet) is not dict or packet.get('requestId')!=self.state['query']['commandId']:return raw
            try:native_original(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
            except Exception:
                self.state['unsafe'].append(dict(bytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest()));self.save();raise
            need(stored[0] is None)
            value=dict(tabletWebBootstrapPacketVersion=VERSION,admission=self.admission,setupNative=self.setup,query=self.state['query'],rawJSON=raw)
            stored[0]=self.originals.write(1,value);return raw
        reader.send,reader.original=issued,received
        try:
            value=reader.read(reader.sequence);need(stored[0] is not None and same(value,self.packet(self.originals.expand(stored[0]))))
            self.state.update(status='returned',original=deepcopy(stored[0]),pending=None,inspection=None);self.save();self.validate();return deepcopy(value)
        except Exception:
            self.state['status']='failed'
            if self.state['pending'] is not None:self.state['inspection']=self.inspect()
            self.save();raise
        finally:reader.send,reader.original=send,original

    def recover(self):
        self.live();self.validate();ref=self.state['pending'];need(ref is not None and ref['phase'] in ('opened','saved') and not self.state['unsafe'])
        value=self.packet(ref);self.state.update(status='returned',original=self.originals.compact(dict(ref,phase='saved')),pending=None,inspection=None);self.save();self.validate();return deepcopy(value)

    def original(self):
        self.validate();need(self.state['status']=='returned');return self.packet(self.originals.expand(self.state['original']))
