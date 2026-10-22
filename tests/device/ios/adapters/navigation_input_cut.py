"""One owned original Qt key/pointer and UIKit cut inside a native bracket.

This passive component neither releases input nor claims editor/root death.
Unknown delivery retains its original query and cannot be repeated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters import world_web_keys as keys,pointer_state as pointer
from ios.adapters.native_geometry import OriginalGeometry,validate as geometry_packet

VERSION=1
KINDS=('keys','pointer','geometry')


class NavigationInputCut:
    def __init__(self,store,root,binding,run,role,request,lock,guard,*,readers=None,historical=False,monotonic):
        need(isinstance(store,PrivateFeatureState) and role in ('primary','actor') and type(historical) is bool)
        identifier(run);need(type(request) is str and request.startswith('ios-'));identifier(request[4:]);context(binding)
        self.store,self.root,self.binding,self.run,self.role,self.request,self.lock=store,Path(root),deepcopy(binding),run,role,request,lock
        self.guard,self.readers,self.historical=guard,readers,historical;lock.assert_held()
        need(store.path==lock.path.with_name('ios-navigation-input-'+role+'-'+request[4:]+'.json'))
        if historical:need(readers is None)
        else:
            exact(readers,set(KINDS));need(isinstance(readers['keys'],keys.IOSWorldWebKeys)
                and isinstance(readers['pointer'],pointer.IOSPointerState) and isinstance(readers['geometry'],OriginalGeometry))
        self.files=OriginalFrameStore(root,binding,run,role,lambda:True if historical else guard(),self.intent,
            namespace='navigation-input-'+request[4:16],schema_prefix='navigationInput',monotonic=monotonic)
        self.previous=store.read();self.state=None if self.previous is None else self.parse(self.previous)

    def envelope(self,state):return dict(iosNavigationInputCutVersion=VERSION,runId=self.run,role=self.role,requestId=self.request,
        binding=self.binding,artifactRoot=str(self.root),payload=pack([state]))

    def parse(self,value):
        exact(value,set(self.envelope({})));rows=unpack(value['payload'])
        need(type(value['iosNavigationInputCutVersion']) is int and value['iosNavigationInputCutVersion']==1
            and len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','queries','wires','active','accepted'});need(state['phase'] in ('reading','observed'))
        for name in ('queries','wires','accepted'):need(type(state[name]) is dict and set(state[name])<=set(KINDS))
        indices=[]
        for kind,query in state['queries'].items():self.query(kind,query)
        for kind,refs in state['wires'].items():
            need(kind in state['queries'] and type(refs) is list and len(refs)<=61)
            for ref in refs:
                self.files.original(ref);need(ref['phase']=='saved');indices.append(ref['index']);self.packet(kind,state['queries'][kind],ref)
        if state['active'] is not None:
            a=state['active'];exact(a,{'kind','reference'});need(a['kind'] in state['queries']);self.files.original(a['reference'])
            indices.append(a['reference']['index'])
        need(len(indices)==len(set(indices)) and sorted(indices)==list(range(1,len(indices)+1)))
        for kind,ref in state['accepted'].items():need(ref in state['wires'].get(kind,[]))
        if state['phase']=='observed':need(set(state['accepted'])==set(KINDS) and state['active'] is None)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need((self.historical or self.guard() is not False) and same(self.store.read(),self.previous))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def query(self,kind,query):
        if kind in ('keys','pointer'):
            (keys if kind=='keys' else pointer).command(query);need(query['runId']==self.run)
        else:
            exact(query,{'schemaVersion','commandId','action'});need(type(query['schemaVersion']) is int and query['schemaVersion']==1
                and query['action']=='native-geometry-snapshot' and query['commandId'].startswith('ios-'));identifier(query['commandId'][4:])

    def validate(self,kind,query,packet):
        self.query(kind,query)
        if kind in ('keys','pointer'):
            (keys if kind=='keys' else pointer).validate(packet,query,int(self.binding['processIdentity']))
            if kind=='keys':keys.privacy_qualified(packet)
        else:geometry_packet(packet,query['commandId'],native_epoch_ms=packet['observation']['sampleEpochMs'])
        return packet

    def packet(self,kind,query,ref):
        body=self.files.read(ref);exact(body,{'iosNavigationInputOriginalVersion','requestId','kind','query','raw'})
        need(type(body['iosNavigationInputOriginalVersion']) is int and body['iosNavigationInputOriginalVersion']==1
            and body['requestId']==self.request and body['kind']==kind and same(body['query'],query) and type(body['raw']) is str)
        return self.validate(kind,query,decode(body['raw'],limit=keys.LIMIT if kind!='geometry' else 65536))

    def intent(self,event,ref):
        need(event=='original' and self.state is not None and self.state['phase']=='reading')
        self.files.original(ref);old=self.state['active']
        if ref['phase']=='planned':
            need(old is None and ref['index']==1+sum(len(rows) for rows in self.state['wires'].values()))
        else:
            need(old is not None and ref['phase']=={'planned':'opened','opened':'saved'}.get(old['reference']['phase'])
                and all(same(ref[k],old['reference'][k]) for k in ref if k not in ('phase','file'))
                and (old['reference']['phase']=='planned' or same(ref['file'],old['reference']['file'])))
        self.state['active']=dict(kind=self.active_kind,reference=deepcopy(ref));self.save()

    def acquire(self):
        need(not self.historical);self.bound();need(self.state is None)
        self.state=dict(phase='reading',queries={},wires={},active=None,accepted={});self.save()
        for kind in KINDS:
            self.active_kind=kind;reader=self.readers[kind];send,read=reader.send,reader.original
            def sending(query):
                need(kind not in self.state['queries']);self.query(kind,query)
                self.state['queries'][kind]=deepcopy(query);self.state['wires'][kind]=[];self.save();return send(query)
            def reading():
                raw=read();need(type(raw) is str and len(raw.encode())<=(65536 if kind=='geometry' else keys.LIMIT))
                try:value=decode(raw,limit=keys.LIMIT)
                except (ValueError,UnicodeError):return raw
                query=self.state['queries'][kind]
                if type(value) is not dict or value.get('commandId' if kind=='geometry' else 'requestId')!=query['commandId']:return raw
                self.validate(kind,query,value)
                rows=self.state['wires'][kind]
                if any(self.files.read(ref)['raw']==raw for ref in rows):return raw
                need(len(rows)<61);index=1+sum(len(items) for items in self.state['wires'].values())
                compact=self.files.write(index,dict(iosNavigationInputOriginalVersion=1,requestId=self.request,kind=kind,query=deepcopy(query),raw=raw))
                ref=self.files.expand(compact);need(same(self.state['active']['reference'],ref))
                rows.append(ref);self.state['active']=None;self.save();return raw
            reader.send,reader.original=sending,reading
            try:packet=reader.capture() if kind=='geometry' else reader.read(self.run)
            finally:reader.send,reader.original=send,read
            matches=[ref for ref in self.state['wires'][kind] if same(self.packet(kind,self.state['queries'][kind],ref),packet)]
            need(matches);self.state['accepted'][kind]=matches[-1];self.save()
        self.state['phase']='observed';self.save();return self.archive()

    def archive(self):
        self.bound();self.parse(self.previous);need(self.state is not None and self.state['phase']=='observed'
            and same(self.envelope(self.state),self.previous))
        return {kind:self.packet(kind,self.state['queries'][kind],self.state['accepted'][kind]) for kind in KINDS}

    def recover(self):
        need(not self.historical);self.bound();self.parse(self.previous)
        need(self.state is not None and self.state['active'] is None and set(self.state['accepted'])==set(KINDS))
        self.state['phase']='observed';self.save();return self.archive()
