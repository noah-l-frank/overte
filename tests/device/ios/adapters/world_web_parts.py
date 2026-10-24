"""Immutable inode-bound chunks for large original native browser packets.

Only original storage changes here. Every rederivation reads and hashes the
actual retained chunks; no pack limit or native observation bound is relaxed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from adapters.original_frame_store import OriginalFrameStore
from adapters.native_feature_observation import exact,integer,need,decode
from adapters.native_clock_join import digest
from adapters.script_feature.history import canonical

CHUNK=512*1024
LIMIT=2*1024*1024
NAMES={'ledgerBefore','world','geometry','uikit','widgets','widgetReceipt','work','document','ledgerAfter','browser','keys','pointer','entities'}


class WorldWebParts:
    def __init__(self,owner):self.owner=owner;self._stores={}
    def store(self,name):
        need(name in NAMES);owner=self.owner;role='primary' if owner.role=='primary' else 'actor';code={'primary':'p','actor':'a','actor-primary':'ap'}[owner.role]
        # Reuse only the configured transport object. Every path/read/write
        # still checks the real private directory and original inode/bytes.
        # In particular this is never an OriginalFrameStore.read() cache.
        key=(name,str(owner.store.path.parent),digest(owner.binding),owner.run,owner.role,id(owner.guard),id(owner.monotonic))
        if key not in self._stores:
            need(len(self._stores)<len(NAMES)*2)
            self._stores[key]=OriginalFrameStore(owner.store.path.parent,owner.binding,owner.run,role,owner.guard,
                lambda kind,value:owner.storage_intent(name,kind,value),namespace='world-web-'+code+'-'+name.lower(),schema_prefix='worldWebSourcePart',monotonic=owner.monotonic)
        store=self._stores[key]
        need(store.root==owner.store.path.parent and store.binding==owner.binding and store.run==owner.run and store.role==role
            and store.guard is owner.guard and store.monotonic is owner.monotonic and store.namespace=='world-web-'+code+'-'+name.lower()
            and store.schema_prefix=='worldWebSourcePart' and store.kind=='sources')
        return store
    def validate(self,value):
        exact(value,{'worldWebSourcePartVersion','name','index','acquisitionId','bytes','sha256','chunks'})
        need(type(value['worldWebSourcePartVersion']) is int and value['worldWebSourcePartVersion']==1 and value['name'] in NAMES
            and integer(value['index'],1,256) and type(value['acquisitionId']) is str and value['acquisitionId'].startswith('ios-') and len(value['acquisitionId'])==36 and integer(value['bytes'],2,LIMIT) and type(value['sha256']) is str
            and len(value['sha256'])==64 and all(char in '0123456789abcdef' for char in value['sha256']) and type(value['chunks']) is list
            and len(value['chunks'])==(value['bytes']+CHUNK-1)//CHUNK)
        for offset,reference in enumerate(value['chunks']):
            self.store(value['name']).expand(reference);need(reference['index']==(value['index']-1)*4+offset+1)
        return value
    def write(self,name,index,original):
        need(name in NAMES and integer(index,1,256));acquisition=self.owner.state['pending']['start']['nativeBefore']['requestId'];raw=canonical(original);need(2<=len(raw)<=LIMIT);store=self.store(name);chunks=[]
        for offset in range(0,len(raw),CHUNK):
            frame=dict(name=name,sourceIndex=index,acquisitionId=acquisition,offset=offset,bytes=len(raw),data=base64.b64encode(raw[offset:offset+CHUNK]).decode('ascii'))
            chunks.append(store.write((index-1)*4+len(chunks)+1,frame))
        value=dict(worldWebSourcePartVersion=1,name=name,index=index,acquisitionId=acquisition,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),chunks=chunks)
        self.validate(value);need(canonical(self.read(value))==raw);return deepcopy(value)
    def read_bytes(self,value):
        self.validate(value);store=self.store(value['name']);raw=bytearray()
        for reference in value['chunks']:
            frame=store.read(store.expand(reference));exact(frame,{'name','sourceIndex','acquisitionId','offset','bytes','data'})
            need(frame['name']==value['name'] and frame['acquisitionId']==value['acquisitionId'] and type(frame['sourceIndex']) is int and frame['sourceIndex']==value['index']
                and type(frame['offset']) is int and frame['offset']==len(raw) and type(frame['bytes']) is int and frame['bytes']==value['bytes'] and type(frame['data']) is str)
            chunk=base64.b64decode(frame['data'],validate=True);need(len(chunk)==min(CHUNK,value['bytes']-len(raw)));raw.extend(chunk)
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']);return bytes(raw)
    def read(self,value):
        raw=self.read_bytes(value);decoded=decode(raw.decode('utf-8'),limit=LIMIT)
        need(canonical(decoded)==raw);return decoded
