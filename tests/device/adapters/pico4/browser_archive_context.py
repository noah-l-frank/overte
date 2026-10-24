"""Lossless historical Browser context in existing bounded source bundles.

This stores already consumed originals only. Neither a decoded context nor a
ready-looking root supplies live source authority or permits cold resumption.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_bundles import prepare,original,logical_bytes
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state
from adapters.script_journey.history import canonical,same,unpack

VERSION=2
READS=(1,2)


def read_context(store,run):
    """Historical bytes only, with the original v1 reader kept unchanged."""
    value,raw,stamp=state(store)
    version=value.get('picoBrowserArchiveContextVersion')
    need(type(version) is int and version in READS and value['runId']==run)
    if version==1:
        exact(value,{'picoBrowserArchiveContextVersion','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1);data=rows[0]
    else:
        exact(value,{'picoBrowserArchiveContextVersion','runId','phase','bundles','logicalBytes','chunks'})
        need(value['phase']=='ready' and type(value['bundles']) is list and len(value['bundles'])==1
            and value['logicalBytes']==logical_bytes(value['bundles']))
        chunks=ChatSourceChunks(store,dict(picoBrowserArchiveContextVersion=version,runId=run))
        chunks.load(value['chunks']);data,_raw=original(chunks,value['chunks'],value['bundles'],0)
    json_digest(data);need(type(data) is dict and state(store)==(value,raw,stamp))
    return data


class BrowserArchiveContext:
    """One fresh warm writer; partial roots/children remain unresolved."""
    def __init__(self,store,run,data):
        need(type(store) is PrivateFeatureState and store.read() is None and type(data) is dict)
        self.store,self.run=store,run;self.path=store.path;self.failed=False;self.previous=None
        self.raw=self._sealed_raw=canonical(data);json_digest(data)
        self.scope=dict(picoBrowserArchiveContextVersion=VERSION,runId=run)
        self.chunks=ChatSourceChunks(store,self.scope);self.chunks.inventory(0)
        try:
            reference,parts=prepare(data,0,[])
            self.value={**self.scope,'phase':'reading','bundles':[reference],
                'logicalBytes':logical_bytes([reference]),'chunks':[]}
            self.write()
            for part in parts:
                self.value['chunks']=self.chunks.append(part,self.value['chunks']);self.write()
            decoded,raw=original(self.chunks,self.value['chunks'],[reference],0)
            need(raw==self.raw and same(decoded,data))
            self.value['phase']='ready';self.write();self.stamp=state(self.store)[2]
            self.identities=tuple(self.chunks.identities)
            need(canonical(read_context(store,run))==self.raw);self.verify()
        except BaseException:self.failed=True;raise

    def write(self):
        self.store.write(self.value,self.previous);need(same(self.store.read(),self.value))
        self.previous=deepcopy(self.value)

    def verify(self):
        try:
            need(not self.failed and self.store.path==self.path and self.raw is self._sealed_raw
                and state(self.store)==(self.previous,canonical(self.previous)+b'\n',self.stamp)
                and json_digest(self.previous)==json_digest(self.value) and self.value['phase']=='ready'
                and tuple(self.chunks.identities)==self.identities)
            self.chunks.verify()
        except BaseException:self.failed=True;raise

    def stores(self):
        self.verify()
        return [self.store,*[self.chunks.store(index) for index in range(len(self.chunks.identities))]]
