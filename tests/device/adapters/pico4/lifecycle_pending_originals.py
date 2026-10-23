"""Original Lifecycle pending-source bytes in the existing bounded container."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.original_memory import ChatOriginalMemory
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import state,parent_node
from adapters.pico4.lifecycle_background_originals import LifecycleBackgroundOriginals
from adapters.pico4.lifecycle_source import nonce

VERSION=1


class LifecyclePendingOriginals(LifecycleBackgroundOriginals):
    # Reuse the original byte-preserving encoder/decoder/container. The fixed
    # distinct scope cannot adopt the earlier background owner's children.
    def __init__(self,path,run,binding):
        need(nonce(run));self.root=PrivateFeatureState(path);self.run,self.binding=run,deepcopy(context(binding))
        need(self.root.path.name=='lifecycle-pending-originals.json')
        self.scope=dict(lifecyclePendingOriginalsVersion=VERSION,runId=run,binding=self.binding,role='lifecycle-pending')
        self.history=ChatSourceChunks(self.root,self.scope);self.parent=parent_node(self.root)
        self.disk=self.root.read();self.root_stamp=self._root_stamp=None;values=[]
        if self.disk is not None:
            observed,_raw,physical=state(self.root);need(observed==self.disk)
            self.root_stamp=self._root_stamp=tuple(physical)
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(self.disk[key]==value and type(self.disk[key]) is type(value) for key,value in self.scope.items())
                and self.disk['phase']=='reading')
            values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        self.memory=self._memory=ChatOriginalMemory(self.scope);self.hashes=self._hashes=();self.by_hash=self._by_hash={}
        for index,value in enumerate(values):
            self.original(value);need(value['sha256'] not in self.by_hash);self.by_hash[value['sha256']]=index
            self.memory.append(value,self.scope);self.hashes=self._hashes=self.hashes+(value['sha256'],)

    @property
    def frames(self):return self.memory.inspect()

    def verify(self):
        need(type(self.memory) is ChatOriginalMemory and self.memory is self._memory
            and type(self.hashes) is tuple and self.hashes is self._hashes
            and type(self.by_hash) is dict and self.by_hash is self._by_hash
            and len(self.hashes)==len(self.by_hash)==self.memory.count()==len(self.history.identities)==len(self.manifest)
            and all(self.by_hash.get(sha)==index and type(self.by_hash[sha]) is int for index,sha in enumerate(self.hashes))
            and parent_node(self.root)==self.parent and self.root.read()==self.disk)
        self.memory.control(self.scope);self.history.verify()
        if self.disk is not None:
            need(type(self.root_stamp) is tuple and self.root_stamp is self._root_stamp and len(self.root_stamp)==8
                and all(type(field) is int for field in self.root_stamp))
            observed,_raw,physical=state(self.root);need(observed==self.disk and tuple(physical)==self.root_stamp)
        else:need(self.root_stamp is None)

    def write(self,value,previous):
        self.root.write(value,previous);observed,_raw,physical=state(self.root);need(observed==value)
        self.disk=deepcopy(value);self.root_stamp=self._root_stamp=tuple(physical)

    def _put(self,value):
        self.original(value);sha=value['sha256']
        if sha not in self.by_hash:
            if self.disk is None:
                initial=dict(self.scope,phase='reading',chunks=[]);self.write(initial,None)
            manifest=self.history.append(deepcopy(value),self.disk['chunks']);updated=dict(self.disk,chunks=manifest)
            self.write(updated,self.disk)
            self.by_hash[sha]=self.memory.count();self.memory.append(value,self.scope);self.hashes=self._hashes=self.hashes+(sha,)
        index=self.by_hash[sha];need(self.memory.row(index)==value)
        return dict(lifecycleOriginal=index,sha256=sha)

    def decode(self,value):
        self.verify();result=self._decode(value);self.verify();return result

    def _decode(self,value):
        if type(value) is dict:
            if set(value)=={'lifecycleOriginal','sha256'}:
                from adapters.native_feature_observation import integer
                index=value['lifecycleOriginal'];need(integer(index,0,self.memory.count()-1))
                original=self.memory.row(index);need(value['sha256']==self.hashes[index]==original['sha256']);return original
            return {key:self._decode(item) for key,item in value.items()}
        if type(value) is list:return [self._decode(item) for item in value]
        return deepcopy(value)
