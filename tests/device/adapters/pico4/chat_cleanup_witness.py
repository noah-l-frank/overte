"""Warm independent Pico actor construction before process/IPC finalization."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy

from adapters.chat_journey.cleanup_witness import ChatCleanupWitness
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_composition import PicoChatWitness,record
from adapters.script_journey.history import same

VERSION=1


class PicoChatCleanupWitness:
    """No acquisition of a different actor, native reader or source lock.

    Existing publisher/client/peer/code owners remain live and independent of
    the parent. The parent's original caches-retired row authorizes only this
    stage; newly queried actor sources supply every target fact.
    """
    def __init__(self,adapter,target,original):
        need(type(original) is PicoChatWitness and original.adapter is adapter and original.target==target)
        self.adapter,self.target,self.original=adapter,target,original
        self.failed=False;self.publisher=self.observation=None
        self.parent=adapter._chat_composition_store(target);self.parent_value=deepcopy(record(self.parent.read()))
        need(self.parent_value['picoChatCompositionVersion'] in (5,6)
            and self.parent_value['phase']=='caches-retired' and self.parent_value['completedSteps']==26
            and same(self.parent_value['binding'],original.binding)
            and same(self.parent_value['peerBinding'],original.peer.binding)
            and self.parent_value['runId']==original.publisher.source.run
            and self.parent_value['fixtureUrl']==original.publisher.source.fixture_url)
        self.control()
        with ExitStack() as held:
            for lock in sorted((original.lock,original.peer.lock),key=lambda lock:str(lock.path)):held.enter_context(lock.held())
            code=original.publisher.samples.script_source
            samples=adapter._chat_cache_absence(target,original.publisher.source.run,original.peer.reader(),original.peer.binding,
                role='actor',stage='final',witness=True,source_lock=original.lock,peer_lock=original.peer.lock,script_source=code)
            # This is a NEW primary reader from the fixed factory. Its final
            # native guard also qualifies the exact parent row after every CAS
            # and immediately before publication; no callback owns an input.
            native_guard=samples.primary.guard
            def guard():self.control();return native_guard()
            samples.primary.guard=guard
            self.observation=adapter._chat_observation(target,original.publisher.source,samples,stage='cleanup',witness=True)
            need(self.observation.source is original.publisher.source and self.observation.samples is samples)
            self.publisher=ChatCleanupWitness(original.publisher,self.observation,adapter._chat_cleanup_witness_store(target))
            self.control()

    def control(self):
        original=self.original
        need(not self.failed and same(self.parent.read(),self.parent_value)
            and same(self.adapter._scripts(self.target).binding,original.binding)
            and original.native.guard() is not False and original.peer.guard() is True)

    def publish(self):
        try:
            self.control();result=self.publisher.publish();self.control();return result
        except Exception:
            self.failed=True
            raise NativeUIError('Original Pico Chat cleanup publication is unresolved; no actor or input is adopted') from None

    def detach(self):
        """The original independent witness still owns these exact host pairs."""
        return self.original.detach()
