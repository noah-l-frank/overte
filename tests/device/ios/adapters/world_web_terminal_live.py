"""Immutable restored-primary originals for the opt-in terminal live window.

Each record retains the real whole retirement original, rather than a requested
checkpoint or a copied public answer. The terminal decoder reopens it through
the original typed source/image/file/input owners before accepting a seal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import result
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
from ios.adapters.world_web_held_resources import primary,public


class WorldWebTerminalLive:
    def __init__(self,owner):
        need(type(owner) in (WorldWebRetirement,WorldWebSetupRetirement) and owner.role=='primary' and owner.source.version==5)
        self.owner,self.lock,self.binding,self.run=owner,owner.lock,deepcopy(owner.binding),owner.run
        self.store=PrivateFeatureState(owner.store.path.with_name('ios-world-web-primary-'+self.run+'-terminal-live.json'))
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        self.lock.assert_held()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:need(not any(self.store.path.parent.glob(self.store.path.stem+'-*.json')))

    def record_store(self,index):
        need(integer(index,1,96));return PrivateFeatureState(self.store.path.with_name(self.store.path.stem+'-'+str(index)+'.json'))

    def envelope(self,state):
        return dict(iosWorldWebTerminalLiveVersion=1,binding=deepcopy(self.binding),runId=self.run,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.owner.binding==self.binding
            and self.owner.run==self.run and (self.previous is None or same(unpack(self.previous['payload']),[self.state])))

    def measure(self,original):
        state,measured,_verdict=self.owner.qualified_original(original)
        last=self.owner.frame(state['quiet'][-1])
        if type(self.owner) is WorldWebSetupRetirement:owners=deepcopy(measured['held'])
        else:owners=primary(self.owner.lease,last['after'])
        value=deepcopy(measured['public'])
        value['resources']=[row['resource'] for row in public(owners)]
        result('feature.world-web.observe',value)
        return dict(public=value,held=owners,acquisition=deepcopy(measured['acquisition']),original=deepcopy(original))

    def record(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,96))
        carrier=self.record_store(reference['index']).read();need(carrier is not None and digest(carrier)==reference['sha256'])
        exact(carrier,{'iosWorldWebTerminalLiveRecordVersion','binding','runId','payload'})
        need(type(carrier['iosWorldWebTerminalLiveRecordVersion']) is int and carrier['iosWorldWebTerminalLiveRecordVersion']==1
            and carrier['binding']==self.binding and carrier['runId']==self.run)
        values=unpack(carrier['payload']);need(len(values)==1);row=values[0]
        exact(row,{'index','measurement'});need(row['index']==reference['index'] and same(row['measurement'],self.measure(row['measurement']['original'])))
        return deepcopy(row)

    def decode(self,value):
        exact(value,{'iosWorldWebTerminalLiveVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(type(value['iosWorldWebTerminalLiveVersion']) is int and value['iosWorldWebTerminalLiveVersion']==1
            and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending'});need(type(state['records']) is list and len(state['records'])<=96)
        previous=0
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);row=self.record(reference);sequence=row['measurement']['public']['sequence']
            need(sequence>previous);previous=sequence
        if state['pending'] is not None:
            row=state['pending'];exact(row,{'index','measurement'})
            need(row['index']==len(state['records'])+1 and same(row['measurement'],self.measure(row['measurement']['original']))
                and row['measurement']['public']['sequence']>previous)
        return deepcopy(state)

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def append(self,original):
        self.bound();measured=self.measure(original)
        if self.state['pending'] is not None:
            pending=self.state['pending'];index=pending['index'];carrier=self.record_store(index).read()
            if carrier is None:
                # No product action is replayed. Only this already retained,
                # fully revalidated original may complete its private carrier.
                self.write_record(pending)
            else:need(same(unpack(carrier['payload']),[pending]))
            reference=dict(index=index,sha256=digest(self.record_store(index).read()));self.record(reference)
            self.state['records'].append(reference);self.state['pending']=None;self.save()
        if self.state['records']:
            latest=self.record(self.state['records'][-1])['measurement']
            if same(latest['original'],original):need(same(latest,measured));return deepcopy(latest['public'])
            need(measured['public']['sequence']>latest['public']['sequence'])
        need(len(self.state['records'])<96);row=dict(index=len(self.state['records'])+1,measurement=measured)
        self.state['pending']=row;self.save();self.write_record(row)
        self.state['records'].append(dict(index=row['index'],sha256=digest(self.record_store(row['index']).read())))
        self.state['pending']=None;self.save();return deepcopy(measured['public'])

    def write_record(self,row):
        self.lock.assert_held();need(same(row['measurement'],self.measure(row['measurement']['original'])))
        carrier=dict(iosWorldWebTerminalLiveRecordVersion=1,binding=deepcopy(self.binding),runId=self.run,payload=pack([row]))
        store=self.record_store(row['index']);need(store.read() is None);store.write(carrier,None)
        need(same(store.read(),carrier))

    def selected(self,value):return self.selected_many([value])[0]

    def selected_many(self,values):
        """One local traversal for a requested immutable window, no cache."""
        self.bound();need(type(values) is list and 1<=len(values)<=96 and self.previous is not None)
        pins={self.store.path:WorldWebRetirement.record_signature(self.store.path)}
        try:
            for value in values:result('feature.world-web.observe',value)
            measured={}
            for reference in self.state['records']:
                path=self.record_store(reference['index']).path;signature=WorldWebRetirement.record_signature(path)
                row=self.record(reference)['measurement'];sequence=row['public']['sequence']
                need(WorldWebRetirement.record_signature(path)==signature)
                pins[path]=signature;need(sequence not in measured);measured[sequence]=row
            selected=[]
            for value in values:
                row=measured.get(value['sequence']);need(row is not None and same(row['public'],value));selected.append(row)
            self.bound();return deepcopy(selected)
        finally:
            for path,signature in pins.items():need(WorldWebRetirement.record_signature(path)==signature)
