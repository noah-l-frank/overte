"""Internal Chat draft transaction on one existing installed iOS candidate.

The normal tablet/Home and CHAT entry must already be available. This runtime
creates no session, configuration entry, capability or public feature dispatch.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from types import SimpleNamespace
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.chat_controls import IOSChatIO
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSChatDraftRuntime(IOSScriptRuntime):
    @contextmanager
    def draft_owner(self,selector,run,root,client):
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'));failure=None
        with lock.held():
            try:
                source=self._sources(selector);native,normal=source['clock_source'],source['native']
                from ios.adapters.chat_session_owners import register_scope
                register_scope(self.adapter,selector,source['binding'],run,root)
                view=source['observer'].chat_view()
                owner=IOSChatDraftOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-chat-draft-owner.json')),
                    root,source['binding'],run,lock,source['check'],native=native,
                    io=IOSChatIO(SimpleNamespace(capture=normal.capture,native=normal)),view=view,
                    phase=PhaseFixtureReader(client,run,'chat'),epoch_ms=lambda:time.time()*1000,
                    monotonic=time.monotonic,sleep=time.sleep)
                native_send,view_send=native.send,view.send
                observe_intent=getattr(normal,'observe_intent',None)
                def send_native(command):owner.query_intent(command);return native_send(command)
                def send_view(command):owner.query_intent(command);return view_send(command)
                native.send,view.send=send_native,send_view;normal.observe_intent=owner.query_intent
                try:
                    with self.existing_input_session(selector):
                        yield owner;need(source['check']() is not False)
                finally:
                    native.send,view.send=native_send,view_send
                    if observe_intent is None:del normal.observe_intent
                    else:normal.observe_intent=observe_intent
            except BaseException as original:failure=original
        if failure is not None:raise failure
