"""Original browser graph plus actual independent observer return."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnReceiver,state,parent_node
from adapters.pico4.browser_actor_graph import PicoBrowserActorGraph,STORES
from adapters.script_journey.history import same
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_observer_process import LinuxChatObserverProcess,ObserverProcessPresent

VERSION=1


class BrowserActorReturnPending(NativeUIError):
    """The original producer has not consumed or returned; nothing is retired."""


class PicoBrowserActorReturn:
    """One originally acquired process, exact fixed graph and Parent nonce.

    This qualifies a historical source/process join only. It never grants
    browser feature success, capture retirement, archive deletion or public RPC.
    """
    def __init__(self,process,export_store,stores,lock,expected,store):
        need(type(process) is LinuxChatObserverProcess and type(lock) is ScriptSourceLock
            and type(stores) is dict and set(stores)==STORES and type(store) is PrivateFeatureState
            and all(type(value) is PrivateFeatureState and value.path.parent==store.path.parent for value in stores.values())
            and type(export_store) is PrivateFeatureState and export_store.path.parent==store.path.parent
            and expected['producerHostProcessIdentity']==process.process_identity
            and len({store.path,export_store.path,*[value.path for value in stores.values()]})==len(stores)+2
            and store.read() is None)
        for method in ('guard','source_files','original_program','require_absent','final_absence','_absent','_arguments','close'):
            need(getattr(getattr(process,method),'__func__',None) is getattr(LinuxChatObserverProcess,method))
        self.process,self.lock,self.store,self.export,self.stores=process,lock,store,export_store,dict(stores)
        self.expected=deepcopy(expected);self.graph=None;self.started=self.complete=self.failed=False
        self.previous=None;self.previous_digest=json_digest(None);self.stamp=None;self.result=None;self.result_digest=None
        self.paths=dict(receipt=str(store.path),export=str(export_store.path),sources={key:str(value.path) for key,value in stores.items()},lock=str(lock.path))
        self.paths_digest=json_digest(self.paths);self.parent=parent_node(store)
        self.scope=dict(picoBrowserActorReturnVersion=VERSION,resultJournal=store.path.name,
            sourceScope='original-independent-browser-historical-return',**deepcopy(expected))
        self.sealed=json_digest(self.scope);ChatSourceChunks(store,{}).inventory(0)
        scope={key:expected[key] for key in ('runId','producerHostProcessIdentity','originalRequestId')}|{'family':'pico-browser-actor'}
        self.receiver=ObserverReturnReceiver(process,
            PrivateFeatureState(export_store.path.with_name('pico-tablet-web-actor-return.json')),
            PrivateFeatureState(export_store.path.with_name('pico-tablet-web-actor-consumption.json')),
            scope,admit=self.admit)
        self.save('prepared')

    def admit(self,raw,physical):
        need(self.graph is None)
        with self.lock.held():self.graph=PicoBrowserActorGraph(raw,physical,self.export,self.stores,self.lock,self.expected)
        return True

    def own(self):
        paths=dict(receipt=str(self.store.path),export=str(self.export.path),sources={key:str(value.path) for key,value in self.stores.items()},lock=str(self.lock.path))
        need(json_digest(self.paths)==self.paths_digest and same(paths,self.paths) and parent_node(self.store)==self.parent
            and self.process is self.receiver.owner and self.process.process_identity==self.scope['producerHostProcessIdentity'])
        need(not self.failed and json_digest(self.scope)==self.sealed and json_digest(self.previous)==self.previous_digest and same(self.store.read(),self.previous))
        if self.stamp is not None:need(state(self.store)[2]==self.stamp)
        ChatSourceChunks(self.store,{}).inventory(0)

    def save(self,phase,**changes):
        self.own();value={**(self.previous or self.scope),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);observed,_raw,stamp=state(self.store);need(same(observed,value))
        self.previous=deepcopy(value);self.previous_digest=json_digest(value);self.stamp=stamp;self.own()

    def acknowledge(self):
        need(not self.started and not self.failed and not self.complete);self.started=True
        try:
            self.own()
            with self.lock.held():self.graph.verify()
            self.save('consumption-issued');return self.receiver.acknowledge()
        except Exception:
            if not self.receiver.issued or self.receiver.intent is None:self.failed=True
            raise

    def finish(self):
        need(self.started and not self.failed and not self.complete)
        try:
            self.own();value=self.receiver.store.read()
            if value is not None and value.get('phase')=='ready':
                self.receiver.verify_ready()
                with self.lock.held():self.graph.verify()
                raise BrowserActorReturnPending('Original browser Actor has not consumed this Parent nonce')
            try:receipt=self.receiver.receipt()
            except ObserverProcessPresent:
                raise BrowserActorReturnPending('Original browser Actor process is still present') from None
            with self.lock.held():self.graph.verify()
            result=dict(originalGraphSha256=self.graph.sealed,originalExportStamp=deepcopy(self.graph.source_stamp),processReturn=receipt)
            self.save('complete',result=result);candidate=deepcopy(self.previous);self.own()
            with self.lock.held():self.graph.verify()
            need(same(self.receiver.historical_receipt(),receipt));self.process.final_absence(receipt['processAbsence'])
            self.result,self.result_digest=candidate,json_digest(candidate);self.complete=True;return candidate
        except BrowserActorReturnPending:raise
        except Exception:
            self.failed=True;raise NativeUIError('Original browser return is unresolved; all original journals and images remain') from None

    def receipt(self):
        need(self.complete and not self.failed and json_digest(self.result)==self.result_digest)
        result=deepcopy(self.result);self.own()
        with self.lock.held():self.graph.verify()
        need(same(self.receiver.historical_receipt(),result['result']['processReturn']));return result

    def close_host(self):return self.process.close() is True
