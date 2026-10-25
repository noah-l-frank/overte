"""Exact original host inventory in immutable bounded private frames.

The inventory is ownership metadata, never native/resource retirement proof.
Its parent intent precedes every real file creation. Opened complete originals
may be recovered without rewriting their bytes, inode or recorded phase.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical,same,MAX_RAW
from feature_journeys.contract import identifier
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=1
CHUNK_BYTES=524288


def inventories(value):
    need(type(value) is dict and 1<=len(value)<=2)
    for root,rows in value.items():
        path=Path(root);need(type(root) is str and path.is_absolute() and path.resolve()==path
            and type(rows) is dict and 1<=len(rows)<50000 and '.' in rows)
        for name,row in rows.items():
            name_path=Path(name);need(type(name) is str and not name_path.is_absolute() and '..' not in name_path.parts
                and type(row) is list and len(row) in (5,9) and all(type(item) is int and item>=0 for item in row))
            need(len(row)==5 and stat.S_ISDIR(row[2]) or len(row)==9 and stat.S_ISREG(row[2]))
    return value


class TabletWebProcessInventory:
    def __init__(self,root,binding,run,lock,guard,*,monotonic,historical=False):
        self.root,self.binding,self.run=Path(root),deepcopy(context(binding)),identifier(run)
        need(lock.path==self.root/'script-feature-sources.lock' and callable(guard) and type(historical) is bool)
        self.lock,self.guard,self.monotonic,self.historical=lock,guard,monotonic,historical
        self.store=PrivateFeatureState(self.root/('tabletweb-process-inventory-'+run+'.json'))
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,'primary',self.file_guard,self.intent,
            namespace='tabletweb-process-inventory',schema_prefix='tabletWebProcessInventory',monotonic=monotonic)
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def file_guard(self):self.lock.assert_held();need(self.guard() is not False);return True
    def decode(self,value):
        exact(value,{'tabletWebProcessInventoryVersion','binding','runId','bytes','sha256','chunks','complete'})
        need(type(value['tabletWebProcessInventoryVersion']) is int and value['tabletWebProcessInventoryVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and integer(value['bytes'],2,MAX_RAW)
            and type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256'])
            and type(value['chunks']) is list and len(value['chunks'])<=(value['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES
            and type(value['complete']) is bool)
        for index,ref in enumerate(value['chunks'],1):
            self.frames.original(ref);need(ref['index']==index)
            if index<len(value['chunks']):need(ref['phase']=='saved')
        if value['complete']:need(len(value['chunks'])==(value['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        return deepcopy(value)
    def save(self):
        need(not self.historical);self.file_guard();self.decode(self.state)
        self.store.write(self.state,self.previous);self.previous=deepcopy(self.state);self.file_guard()
    def intent(self,kind,reference):
        need(not self.historical and kind=='original' and self.state is not None and not self.state['complete'])
        self.frames.original(reference);index=reference['index']-1;rows=self.state['chunks']
        need(0<=index<=len(rows))
        if index==len(rows):need(reference['phase']=='planned');rows.append(deepcopy(reference))
        else:
            old=rows[index];need(all(same(old[k],reference[k]) for k in old if k not in ('phase','file'))
                and (old['phase'],reference['phase']) in (('planned','opened'),('opened','saved'))
                and (old['file'] is None or old['file']==reference['file']));rows[index]=deepcopy(reference)
        self.save()
    def paths(self):
        result=[self.store.path]
        if self.state is not None:result.extend(self.frames.path(ref) for ref in self.state['chunks'])
        return result
    def reference(self):
        need(self.state is not None and self.state['complete'])
        signatures={}
        for path in self.paths():
            PrivateFeatureState(path)._parent();value=path.lstat()
            need(stat.S_ISREG(value.st_mode) and value.st_uid==os.geteuid() and value.st_nlink==1 and stat.S_IMODE(value.st_mode)==0o600)
            signatures[str(path.relative_to(self.root))]=list(EmoteOriginalLease.signature(value))
        return dict(tabletWebProcessInventoryReferenceVersion=1,bytes=self.state['bytes'],sha256=hashlib.sha256(canonical(self.state)).hexdigest(),files=signatures)
    def retained(self):
        need(self.state is not None and len(self.state['chunks'])==(self.state['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        raw=bytearray()
        for index,ref in enumerate(self.state['chunks'],1):
            body=self.frames.read(ref)
            exact(body,{'tabletWebProcessInventoryPartVersion','ordinal','offset','bytes','sha256','data'})
            need(type(body['tabletWebProcessInventoryPartVersion']) is int and body['tabletWebProcessInventoryPartVersion']==1
                and type(body['ordinal']) is int and body['ordinal']==index and type(body['offset']) is int and body['offset']==len(raw)
                and type(body['bytes']) is int and body['bytes']==self.state['bytes'] and body['sha256']==self.state['sha256']
                and type(body['data']) is str)
            try:part=base64.b64decode(body['data'],validate=True)
            except (ValueError,TypeError):need(False)
            need(base64.b64encode(part).decode()==body['data'] and len(part)==min(CHUNK_BYTES,self.state['bytes']-len(raw)));raw.extend(part)
        need(len(raw)==self.state['bytes'] and hashlib.sha256(raw).hexdigest()==self.state['sha256'])
        try:value=json.loads(raw)
        except (ValueError,TypeError,UnicodeError):need(False)
        exact(value,{'tabletWebProcessInventoryDocumentVersion','inventories'})
        need(type(value['tabletWebProcessInventoryDocumentVersion']) is int and value['tabletWebProcessInventoryDocumentVersion']==1
            and canonical(value)==raw);return inventories(value['inventories'])
    def read(self,reference):
        exact(reference,{'tabletWebProcessInventoryReferenceVersion','bytes','sha256','files'})
        need(type(reference['tabletWebProcessInventoryReferenceVersion']) is int and reference['tabletWebProcessInventoryReferenceVersion']==1
            and same(reference,self.reference()) and same(self.store.read(),self.previous))
        value=self.retained();need(same(reference,self.reference()));return value
    def recover(self):
        need(not self.historical and self.state is not None);self.file_guard()
        self.retained()  # Partial bytes stay owned and fail here; no new file/query.
        if not self.state['complete']:self.state['complete']=True;self.save()
        return self.reference()
    def write(self,value):
        need(not self.historical);self.file_guard();inventories(value)
        raw=canonical(dict(tabletWebProcessInventoryDocumentVersion=1,inventories=value));need(2<=len(raw)<=MAX_RAW)
        if self.state is not None:
            need(self.state['bytes']==len(raw) and self.state['sha256']==hashlib.sha256(raw).hexdigest())
            reference=self.recover();need(same(self.read(reference),value));return reference
        self.state=dict(tabletWebProcessInventoryVersion=1,binding=self.binding,runId=self.run,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),chunks=[],complete=False)
        self.save()
        for index,offset in enumerate(range(0,len(raw),CHUNK_BYTES),1):
            self.frames.write(index,dict(tabletWebProcessInventoryPartVersion=1,ordinal=index,offset=offset,bytes=len(raw),
                sha256=self.state['sha256'],data=base64.b64encode(raw[offset:offset+CHUNK_BYTES]).decode()))
        self.state['complete']=True;self.save();reference=self.reference();need(same(self.read(reference),value));return reference
