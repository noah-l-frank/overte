"""Original typed Chat graph plus independent host return, never whole cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid

from adapters.chat_journey.remote_actor_graph import ChatRemoteActorGraph,STORES
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.observation_cursor import plain
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnReceiver,state
from adapters.script_journey.history import same
from fixture.chat_observer_process import LinuxChatObserverProcess,ObserverProcessPresent

VERSION=1


class ChatRemoteActorPending(NativeUIError):
    """No source/nonce/absence claim; the original warm transaction may wait."""


class ChatRemoteActorReturn:
    """One fixed historical return, private durable intent and original nonce.

    The reviewed process owner and all paths come from the original typed
    Parent, never discovery or a completed-looking private result. Neither
    successful common execution nor native Actor build provenance is inferred.
    """
    def __init__(self,process,stores,expected,store):
        need(type(process) is LinuxChatObserverProcess and type(stores) is dict and set(stores)==STORES|{'return','consumption'}
            and type(store) is PrivateFeatureState and store.read() is None
            and all(type(value) is PrivateFeatureState and value.path.parent==store.path.parent for value in stores.values())
            and len({store.path,*[value.path for value in stores.values()]})==len(stores)+1)
        for method in ('guard','source_files','original_program','require_absent','final_absence','_absent','_arguments','close'):
            need(getattr(getattr(process,method),'__func__',None) is getattr(LinuxChatObserverProcess,method))
        self.process,self.stores,self.store=process,dict(stores),store
        self.previous=None;self.previous_sha=digest(None);self.root_stamp=None;self.graph=None
        self.started=self.complete=self.failed=False;self.result=None;self.result_sha=None
        ChatSourceChunks(store,{}).inventory(0)
        scope=dict(runId=expected['runId'],family='pico-chat-cursor-actor',producerHostProcessIdentity=expected['hostProcessIdentity'],
            originalRequestId=expected['stopCommand']['commandId'])
        self.receiver=ObserverReturnReceiver(process,stores['return'],stores['consumption'],scope,
            admit=lambda raw,physical:self.admit(raw,physical,expected))
        self.scope=dict(chatRemoteActorReturnVersion=VERSION,instance=uuid.uuid4().hex,runId=expected['runId'],
            binding=deepcopy(expected['binding']),peerBinding=deepcopy(expected['peerBinding']),
            actorInstance=expected['instance'],hostProcessIdentity=expected['hostProcessIdentity'],
            originalRequestId=scope['originalRequestId'],resultJournal=store.path.name,sourceScope='original-independent-chat-historical-return')
        self.scope_sha=digest(self.scope);self.save('prepared')

    def admit(self,raw,physical,expected):
        need(self.graph is None);self.graph=ChatRemoteActorGraph(raw,physical,{key:self.stores[key] for key in STORES},expected)
        return True

    def own(self):
        plain(self.scope);plain(self.previous)
        need(self.store.path.name==self.scope['resultJournal'] and self.store.path.parent==self.stores['actor'].path.parent)
        need(not self.failed and digest(self.scope)==self.scope_sha and digest(self.previous)==self.previous_sha
            and same(self.store.read(),self.previous))
        if self.root_stamp is not None:need(state(self.store)[2]==self.root_stamp)
        ChatSourceChunks(self.store,{}).inventory(0)

    def save(self,phase,**changes):
        self.own();value={**(self.previous or self.scope),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);actual,_raw,physical=state(self.store)
        need(same(value,actual));self.previous=deepcopy(value);self.previous_sha=digest(value);self.root_stamp=physical;self.own()

    def quarantine(self):
        self.failed=True
        if self.graph is not None:self.graph.failed=True

    def acknowledge(self):
        need(not self.started and not self.complete and not self.failed);self.started=True
        try:
            self.own();self.graph.verify();self.save('consumption-issued')
            return self.receiver.acknowledge()
        except Exception:
            # A known original issued nonce may have reached the Actor even
            # when its write response was lost. Only passive finish is allowed.
            if not self.receiver.issued or self.receiver.intent is None:self.quarantine()
            raise

    def finish(self):
        need(self.started and not self.complete and not self.failed)
        try:
            self.own();value=self.stores['return'].read()
            if value is not None and value.get('phase')=='ready':
                self.receiver.verify_ready();self.graph.verify()
                raise ChatRemoteActorPending('Original Actor has not independently consumed this Parent nonce')
            self.receiver.consumed()
            if self.graph.successor is None:
                actor=self.stores['actor'].read()
                if actor is not None and actor.get('phase')=='host-closed':
                    self.graph.verify();raise ChatRemoteActorPending('Original Actor has not published its controlled successor')
                self.graph.admit_successor(self.receiver)
            else:self.graph.verify()
            try:returned=self.receiver.receipt()
            except ObserverProcessPresent:
                raise ChatRemoteActorPending('Original Actor PID is still present; no kernel absence exists') from None
            self.graph.verify()
            result=dict(sourceGraphVersion=1,sourceGraphSha256=self.graph.cache_sha,
                originalActorSha256=hashlib.sha256(self.graph.raw).hexdigest(),originalActorStamp=deepcopy(self.graph.source_stamp),
                finalActorSha256=hashlib.sha256(self.graph.successor[0]).hexdigest(),finalActorStamp=deepcopy(self.graph.successor[1]),
                sourceSealSha256=self.graph.root['sealSha256'],processReturn=deepcopy(returned))
            self.save('complete',result=result);result=deepcopy(self.previous)
            self.result_sha=digest(result);self.result=result;self.own();self.graph.verify()
            need(same(self.receiver.historical_receipt(),returned))
            self.process.final_absence(returned['processAbsence']);self.complete=True;self.graph.pending=False
            return result
        except ChatRemoteActorPending:raise
        except Exception:
            self.quarantine();raise NativeUIError('Original typed Chat return is unresolved; all originals remain') from None

    def receipt(self):
        plain(self.result);need(self.complete and not self.failed and digest(self.result)==self.result_sha)
        result=deepcopy(self.result);self.own();self.graph.verify()
        need(same(self.receiver.historical_receipt(),result['result']['processReturn']))
        return result

    def close_host(self):
        """Original Parent-side program OFDs only; no journal retirement."""
        return self.process.close() is True
