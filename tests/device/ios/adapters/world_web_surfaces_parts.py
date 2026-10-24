"""Separate actual cache-original carrier; legacy Parts1 names stay closed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from ios.adapters import world_web_surfaces as surfaces,web_closures as closures

PROFILES={'surfaces':('worldWebSurfacesPartVersion','worldWebSurfacesPart'),'closures':('worldWebClosuresPartVersion','worldWebClosuresPart')}


class WorldWebSurfacesParts:
    def __init__(self,owner,*,name='surfaces'):
        need(name in PROFILES);self.owner,self.name=owner,name;self.key,self.prefix=PROFILES[name];self._store=None
    def store(self):
        owner=self.owner;role='primary' if owner.role=='primary' else 'actor';code={'primary':'p','actor':'a','actor-primary':'ap'}[owner.role]
        if self._store is None:
            self._store=OriginalFrameStore(owner.store.path.parent,owner.binding,owner.run,role,owner.guard,
                lambda kind,value:owner.storage_intent(self.name,kind,value),namespace='world-web-'+code+'-'+self.name,schema_prefix=self.prefix,monotonic=owner.monotonic)
        result=self._store
        need(result.root==owner.store.path.parent and result.binding==owner.binding and result.run==owner.run and result.role==role
            and result.guard is owner.guard and result.monotonic is owner.monotonic and result.namespace=='world-web-'+code+'-'+self.name
            and result.schema_prefix==self.prefix and result.kind=='sources')
        return result
    def validate(self,value):
        exact(value,{self.key,'name','index','acquisitionId','packet'})
        need(type(value[self.key]) is int and value[self.key]==1 and value['name']==self.name
            and integer(value['index'],1,256) and type(value['acquisitionId']) is str and value['acquisitionId'].startswith('ios-')
            and len(value['acquisitionId'])==36)
        self.store().expand(value['packet']);need(value['packet']['index']==(value['index']-1)*4+1);return value
    def write(self,index,packet):
        owner=self.owner;acquisition=owner.state['pending']['start']['nativeBefore']['requestId']
        need(integer(index,1,256))
        if self.name=='surfaces':surfaces.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=surfaces.ACTION,runId=owner.run),owner.pid)
        else:closures.validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-ios-web-closures',runId=owner.run,fixtureUrl=owner.phase.fixture_url),owner.pid,packet['capturedEpochMs'])
        reference=self.store().write((index-1)*4+1,dict(sourceIndex=index,acquisitionId=acquisition,original=packet))
        value={self.key:1,'name':self.name,'index':index,'acquisitionId':acquisition,'packet':reference}
        need(canonical(self.read(value))==canonical(packet));return deepcopy(value)
    def read(self,value):
        self.validate(value);row=self.store().read(self.store().expand(value['packet']))
        exact(row,{'sourceIndex','acquisitionId','original'});need(type(row['sourceIndex']) is int and row['sourceIndex']==value['index']
            and row['acquisitionId']==value['acquisitionId']);return row['original']
    def read_bytes(self,value):return canonical(self.read(value))
    def paths(self,value):self.validate(value);return [self.store().path(self.store().expand(value['packet']))]
