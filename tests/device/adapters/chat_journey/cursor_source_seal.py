"""Seal exact warm global Chat source graphs using the existing seal machinery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.observation_cursor import ChatObservationCursor,plain
from adapters.chat_journey.observation_publisher import ChatObservationPublisher
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey.source_seal import ChatSourceSeal
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState

VERSION=1


class ChatCursorSourceSeal(ChatSourceSeal):
    """Explicit separate source extension; legacy 26-row seals stay unchanged."""
    def __init__(self,owner,store):
        need(type(owner) in (ChatObservationCursor,ChatObservationPublisher) and type(store) is PrivateFeatureState)
        self.owner=owner;self.publisher=owner if type(owner) is ChatObservationPublisher else None
        self.cursor=owner.cursor if self.publisher is not None else owner
        self.observation=self.cursor.current
        need(self.observation.stage=='cleanup' and [value.stage for value in self.cursor.owners]==['initial','active','cleanup']
            and not self.cursor.failed and (self.publisher is None or not self.publisher.failed)
            and self.cursor.scope['runId']==self.observation.source.run
            and self.cursor.scope['binding']==self.observation.samples.binding
            and self.cursor.scope['peerBinding']==self.observation.samples.peer_binding
            and store.path.parent==self.observation.store.path.parent and store.read() is None)
        graph=[value for value in (self.publisher,self.cursor) if value is not None]
        for observation in self.cursor.owners:
            graph.extend((observation,observation.samples))
            code=observation.samples.script_source
            while code is not None:graph.append(code);code=code.predecessor
        self.owners=[];paths={}
        for value in graph:
            path=value.store.path;need(path!=store.path and path.parent==store.path.parent)
            if path in paths:need(paths[path] is value)
            else:paths[path]=value;self.owners.append(value)
        self.owners=tuple(self.owners)
        self.store,self.previous,self.failed,self.completed=store,None,False,False;self.seal_stamp=None
        self.scope=dict(chatCursorSourceSealVersion=VERSION,runId=self.observation.source.run,role=self.cursor.scope['role'],
            binding=deepcopy(self.cursor.scope['binding']),peerBinding=deepcopy(self.cursor.scope['peerBinding']),
            kind='cleanup-global-publisher' if self.publisher is not None else 'cleanup-global-observation',journal=owner.store.path.name)
        self.empty_history=ChatSourceChunks(store,self.scope);self.empty_history.inventory(0);self.read_guard=self.live
        need(all(value._freeze_guard is None for value in self.cursor.owners))
        if self.publisher is None:
            need(self.cursor._freeze_guard is None);self.cursor.bind_freeze(self.read_guard)
        else:
            need(self.publisher._freeze_guard is None and self.cursor._freeze_guard is self.publisher.read_guard)
            self.publisher.bind_freeze(self.read_guard)
        for value in self.cursor.owners:value.bind_freeze(self.read_guard)

    def originals(self,*,control=True):
        if control:
            self.cursor.control()
            if self.publisher is not None:self.publisher.control()
        for owner in self.owners:plain(owner.rows if hasattr(owner,'rows') else owner.frames)
        return super().originals(control=control)
