"""Lossless Snapshot owner references to the existing immutable frame container.

Complete original bundles remain unchanged in private children. A missing parent
or interrupted manifest write cannot adopt, truncate or discard those originals.
Stored history never replaces a fresh source query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_originals import nonce
from adapters.script_journey.history import canonical

VERSION=1
KINDS=('frame','reply','vm')


class SnapshotCancelOriginals:
    def __init__(self,path,run,binding):
        need(nonce(run));self.root=PrivateFeatureState(path)
        self.scope=dict(snapshotCancelOriginalsVersion=VERSION,runId=run,binding=deepcopy(context(binding)),role='snapshot-cancel-and-still')
        self.history=ChatSourceChunks(self.root,self.scope);self.disk=self.root.read();self.values=[];self.indices={}
        if self.disk is not None:
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(type(self.disk[key]) is type(value) and self.disk[key]==value for key,value in self.scope.items()) and self.disk['phase']=='reading')
            self.values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        for index,value in enumerate(self.values):
            self.original(value);digest=self.digest(value);need(digest not in self.indices);self.indices[digest]=index

    @staticmethod
    def original(value):
        exact(value,{'kind','original'});need(value['kind'] in KINDS and type(value['original']) is dict)

    @staticmethod
    def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

    def verify(self):
        need(self.root.read()==self.disk and len(self.values)==len(self.history.identities));self.history.verify()

    def put(self,kind,value,*,host_only=False):
        original=dict(kind=kind,original=deepcopy(value));self.original(original);digest=self.digest(original)
        if digest not in self.indices:
            # Locked controller publication may only reference already persisted
            # source bundles; it never appends or acquires an observation.
            need(not host_only)
            if self.disk is None:
                initial=dict(self.scope,phase='reading',chunks=[]);self.root.write(initial,None);need(self.root.read()==initial);self.disk=deepcopy(initial)
            manifest=self.history.append(original,self.disk['chunks'])
            updated=dict(self.disk,chunks=manifest);self.root.write(updated,self.disk);need(self.root.read()==updated);self.disk=deepcopy(updated)
            self.indices[digest]=len(self.values);self.values.append(original)
        index=self.indices[digest];need(self.values[index]==original)
        return dict(snapshotOriginal=index,sha256=digest,kind=kind)

    def get(self,kind,reference):
        exact(reference,{'snapshotOriginal','sha256','kind'});index=reference['snapshotOriginal']
        need(reference['kind']==kind and integer(index,0,len(self.values)-1))
        original=self.values[index];need(original['kind']==kind and self.digest(original)==reference['sha256'])
        return deepcopy(original['original'])

    def encode(self,state,*,host_only=False):
        self.verify();result=deepcopy(state)
        for key,kind in (('frames','frame'),('replies','reply')):
            result[key]=[self.put(kind,value,host_only=host_only) for value in state[key]]
        if state['vm'] is not None:result['vm']=self.put('vm',state['vm'],host_only=host_only)
        self.verify();return result

    def decode(self,state):
        self.verify();result=deepcopy(state)
        for key,kind in (('frames','frame'),('replies','reply')):
            result[key]=[self.get(kind,value) for value in state[key]]
        if state['vm'] is not None:result['vm']=self.get('vm',state['vm'])
        self.verify();return result
