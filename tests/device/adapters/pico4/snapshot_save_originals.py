"""Complete immutable Save frames in the existing reviewed original container."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_originals import nonce

VERSION=1


class SnapshotSaveOriginals(SnapshotCancelOriginals):
    """A separate fixed scope; no adoption of Cancel or another role's chunks."""
    def __init__(self,path,run,binding):
        need(nonce(run));self.root=PrivateFeatureState(path)
        self.scope=dict(snapshotSaveOriginalsVersion=VERSION,runId=run,binding=deepcopy(context(binding)),role='snapshot-save')
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
        exact(value,{'kind','original'});need(value['kind']=='frame' and type(value['original']) is dict)

    def encode(self,state,*,host_only=False):
        self.verify();result=deepcopy(state)
        result['frames']=[self.put('frame',value,host_only=host_only) for value in state['frames']]
        self.verify();return result
    def decode(self,state):
        self.verify();result=deepcopy(state);result['frames']=[self.get('frame',value) for value in state['frames']];return result
