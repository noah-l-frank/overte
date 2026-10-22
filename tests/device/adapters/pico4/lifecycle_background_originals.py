"""Lossless Lifecycle references to the reviewed immutable source container.

Original raw bytes stay in complete immutable private children. The bounded
owner journal contains references, never truncated or projected observations.
Unknown child/root writes remain unresolved; no file is adopted or removed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import LIMIT,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_source import nonce

VERSION=1


class LifecycleBackgroundOriginals:
    def __init__(self,path,run,binding):
        need(nonce(run));self.root=PrivateFeatureState(path);self.run,self.binding=run,deepcopy(context(binding))
        self.scope=dict(lifecycleBackgroundOriginalsVersion=VERSION,runId=run,binding=self.binding,role='lifecycle-background')
        self.history=ChatSourceChunks(self.root,self.scope);self.disk=self.root.read();self.frames=[];self.by_hash={}
        if self.disk is not None:
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(self.disk[key]==value and type(self.disk[key]) is type(value) for key,value in self.scope.items()) and self.disk['phase']=='reading')
            self.frames=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        for index,value in enumerate(self.frames):
            self.original(value);need(value['sha256'] not in self.by_hash);self.by_hash[value['sha256']]=index

    @staticmethod
    def original(value):
        exact(value,{'raw','sha256'});need(type(value['raw']) is str and len(value['raw'].encode())<=LIMIT and frame(value['raw'])==value)

    @property
    def manifest(self):return [] if self.disk is None else deepcopy(self.disk['chunks'])

    def verify(self):
        need(self.root.read()==self.disk and len(self.frames)==len(self.history.identities)==len(self.manifest));self.history.verify()

    def _put(self,value):
        self.original(value)
        digest=value['sha256']
        if digest not in self.by_hash:
            if self.disk is None:
                initial=dict(self.scope,phase='reading',chunks=[]);self.root.write(initial,None);need(self.root.read()==initial);self.disk=deepcopy(initial)
            manifest=self.history.append(deepcopy(value),self.disk['chunks'])
            updated=dict(self.disk,chunks=manifest);self.root.write(updated,self.disk);need(self.root.read()==updated);self.disk=deepcopy(updated)
            self.by_hash[digest]=len(self.frames);self.frames.append(deepcopy(value))
        index=self.by_hash[digest];need(self.frames[index]==value)
        return dict(lifecycleOriginal=index,sha256=digest)

    def encode(self,value):
        self.verify();result=self._encode(value);self.verify();return result

    def _encode(self,value):
        if type(value) is dict:
            if set(value)=={'raw','sha256'}:return self._put(value)
            return {key:self._encode(item) for key,item in value.items()}
        if type(value) is list:return [self._encode(item) for item in value]
        return deepcopy(value)

    def decode(self,value):
        if type(value) is dict:
            if set(value)=={'lifecycleOriginal','sha256'}:
                index=value['lifecycleOriginal'];need(integer(index,0,len(self.frames)-1))
                original=self.frames[index];need(value['sha256']==original['sha256']);return deepcopy(original)
            return {key:self.decode(item) for key,item in value.items()}
        if type(value) is list:return [self.decode(item) for item in value]
        return deepcopy(value)
