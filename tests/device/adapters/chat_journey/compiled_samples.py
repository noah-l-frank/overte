"""Closed Chat source/model joins; legacy model frames gain no source claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid

from adapters.chat_journey.samples import ChatSamples,ChatCacheAbsence
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.native_feature_observation import need
from adapters.script_journey.history import same


class _Compiled:
    compiled_model=True
    def __init__(self,*args,script_source,**kwargs):
        need(isinstance(script_source,ChatScriptSource))
        self.script_source=script_source
        super().__init__(*args,**kwargs)
        need(not self.component_only and script_source.run==self.run and script_source.role==self.role
            and script_source.binding==self.binding and script_source.lock is self.locks[0])

    def _compose(self,frame):
        need(frame.get('compiledChatSourceVersion')==1 and 'compiledChat' in frame)
        need(same(frame['compiledChat'],self.script_source.transactions.get(frame['compiledChat'].get('ticket'))))
        return super()._compose(frame)

    def _extra_frame(self,ticket,after_epoch):
        # This UUID identifies a passive source transaction, never another
        # fixture activation. The real model/phase supplies the same barrier.
        self.script_source.capture(uuid.uuid4().hex,after_epoch)
        return dict(compiledChatSourceVersion=1,compiledChat=deepcopy(self.script_source.frames[-1]))

    def _extra_clocks(self,frame):
        oldest=frame['compiledChat']['before']['requestedEpochMs']
        return ((self.script_source.roots,oldest),(self.script_source.scripts,oldest))


class CompiledChatSamples(_Compiled,ChatSamples):
    journal_field='chatCompiledSamplesVersion'
    journal_version=1


class CompiledChatCacheAbsence(_Compiled,ChatCacheAbsence):
    journal_field='chatCompiledCacheAbsenceVersion'
    journal_version=1
