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
from adapters.native_script_roots import NativeScriptRoots,FILE as ROOTS_FILE,LIMIT as ROOTS_LIMIT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.chat_controls import IOSChatIO
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSChatDraftRuntime(IOSScriptRuntime):
    def _chat_peer_receipts(self,peer_selector,run,client,receive):
        from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
        from ios.adapters.chat_receive_sources import IOSChatReceiveSources
        need(isinstance(receive,IOSChatReceiveSources) and run==receive.run
            and receive.lock.path==self.state_path(peer_selector).with_name('script-feature-sources.lock'))
        receive.bound();fixture_url=PhaseFixtureReader(client,run,'chat').fixture_url
        @contextmanager
        def sender():
            receive.lock.assert_held()
            yield IOSChatDraftOwner.archive(PrivateFeatureState(self.state_path(peer_selector).with_name('ios-chat-draft-owner.json')),
                receive.bound_record['peerArtifactRoot']['path'],receive.binding,run,receive.lock,fixture_url,
                source_bound=True,peer_actor=True)
        return IOSChatPeerReceipts(receive,sender)

    def _chat_send_operation(self,selector,run,root,client,receive,*,sender_role='primary',peer_receipts=None):
        from pathlib import Path
        from ios.adapters.chat_receive_sources import IOSChatReceiveSources
        from ios.adapters.chat_send_operation import IOSChatSendOperation
        from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
        need(type(sender_role) is str and sender_role in ('primary','peer'))
        need(peer_receipts is None or sender_role=='primary' and isinstance(peer_receipts,IOSChatPeerReceipts)
            and peer_receipts.receive is receive)
        need(isinstance(receive,IOSChatReceiveSources) and run==receive.run
            and str(Path(root))==receive.bound_record[sender_role+'ArtifactRoot']['path'])
        lock=receive.primary_lock if sender_role=='primary' else receive.lock
        need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        options=dict(source_bound=True,lock=lock)
        if sender_role=='peer':options['peer_actor']=True
        if peer_receipts is not None:options['peer_receipts']=peer_receipts
        return IOSChatSendOperation(receive,lambda:self.draft_owner(selector,run,root,client,
            **options),sender_role=sender_role)

    def _chat_receive_components(self,primary_selector,peer_selector,run,primary_root,peer_root,primary_lock,peer_lock):
        from ios.adapters.chat_receive_runtime import receive_components
        return receive_components(self,primary_selector,peer_selector,run,primary_root,peer_root,primary_lock,peer_lock)

    @contextmanager
    def draft_owner(self,selector,run,root,client,*,source_bound=False,lock=None,peer_actor=False,peer_receipts=None):
        from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
        need(type(source_bound) is bool and type(peer_actor) is bool and (not peer_actor or source_bound)
            and (peer_receipts is None or isinstance(peer_receipts,IOSChatPeerReceipts) and source_bound and not peer_actor))
        path=self.state_path(selector).with_name('script-feature-sources.lock')
        if lock is None:lock=ScriptSourceLock(path)
        else:need(isinstance(lock,ScriptSourceLock) and lock.path==path);lock.assert_held()
        failure=None
        with lock.held():
            try:
                source=self._sources(selector);native,normal=source['clock_source'],source['native']
                from ios.adapters.chat_session_owners import register_scope
                register_scope(self.adapter,selector,source['binding'],run,root)
                view=source['observer'].chat_view()
                code_sources=code_roots=None
                if source_bound:
                    observer=source['observer'];code_sources=observer.chat_script_sources(clock_source=native)
                    code_roots=NativeScriptRoots(observer.send,lambda:observer.original(remote=observer.remote.rsplit('/',1)[0]+'/'+ROOTS_FILE,limit=ROOTS_LIMIT),
                        source['native_clock'],source['check'],native.pid,ios=True,monotonic=time.monotonic,sleep=time.sleep)
                owner=IOSChatDraftOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-chat-draft-owner.json')),
                    root,source['binding'],run,lock,source['check'],native=native,
                    io=IOSChatIO(SimpleNamespace(capture=normal.capture,native=normal)),view=view,
                    phase=PhaseFixtureReader(client,run,'chat'),epoch_ms=lambda:time.time()*1000,
                    monotonic=time.monotonic,sleep=time.sleep,source_bound=source_bound,code_sources=code_sources,code_roots=code_roots,
                    peer_actor=peer_actor,peer_receipts=peer_receipts)
                native_send,view_send=native.send,view.send
                observe_intent=getattr(normal,'observe_intent',None)
                def send_native(command):owner.query_intent(command);return native_send(command)
                def send_view(command):owner.query_intent(command);return view_send(command)
                native.send,view.send=send_native,send_view;normal.observe_intent=owner.query_intent
                original_sends=[]
                for reader in (() if not source_bound else (code_roots,code_sources)):
                    original_send=reader.send;original_sends.append((reader,original_send))
                    def sending(command,original_send=original_send):owner.query_intent(command);return original_send(command)
                    reader.send=sending
                try:
                    with self.existing_input_session(selector):
                        yield owner;need(source['check']() is not False)
                finally:
                    native.send,view.send=native_send,view_send
                    for reader,original_send in original_sends:reader.send=original_send
                    if observe_intent is None:del normal.observe_intent
                    else:normal.observe_intent=observe_intent
            except BaseException as original:failure=original
        if failure is not None:raise failure
