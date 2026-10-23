"""Upload components in the existing immutable original-frame container."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_originals import nonce

VERSION=1
KINDS=('base','upload','provider','account')
ALL_KINDS=KINDS+('received',)


class SnapshotUploadOriginals(SnapshotCancelOriginals):
    VERSION_KEY='snapshotUploadOriginalsVersion'
    VERBS=('upload-fail','upload')
    def __init__(self,path,run,binding,verb):
        need(nonce(run) and verb in self.VERBS);self.root=PrivateFeatureState(path)
        self.scope={self.VERSION_KEY:VERSION,'runId':run,'binding':deepcopy(context(binding)),'role':'snapshot-'+verb}
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
        exact(value,{'kind','original'});need(value['kind'] in ALL_KINDS and type(value['original']) is dict)

    def encode(self,state,*,host_only=False):
        self.verify();result=deepcopy(state)
        result['frames']=[dict({kind:self.put(kind,row[kind],host_only=host_only) for kind in KINDS},hostMonotonic=row['hostMonotonic']) for row in state['frames']]
        if state['received'] is not None:result['received']=self.put('received',state['received'],host_only=host_only)
        self.verify();return result

    def decode(self,state):
        self.verify();result=deepcopy(state)
        result['frames']=[dict({kind:self.get(kind,row[kind]) for kind in KINDS},hostMonotonic=row['hostMonotonic']) for row in state['frames']]
        if state['received'] is not None:result['received']=self.get('received',state['received'])
        self.verify();return result


class SnapshotBackgroundOriginals(SnapshotUploadOriginals):
    VERSION_KEY='snapshotBackgroundOriginalsVersion'
    VERBS=('background',)
