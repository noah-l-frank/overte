"""Compose existing normal Send WAL and immutable receive originals.

The draft owns input; receive sources own passive queries and original files.
Reconstruction derives the same cut selection from those durable journals.
There is no additional delivery journal, session, transport or retry service.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.chat_draft_clock import operation
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_receive import original_sent
from ios.adapters.graphics_history import follow_native


class IOSChatSendOperation:
    def __init__(self,receive,draft_owner):
        need(isinstance(receive,IOSChatReceiveSources) and not receive.historical and callable(draft_owner))
        self.receive,self.draft_owner,self.monotonic=receive,draft_owner,receive.monotonic

    @contextmanager
    def owner(self):
        self.receive.bound()
        with self.draft_owner() as draft:
            need(isinstance(draft,IOSChatDraftOwner) and not draft.historical and draft.source_bound and draft.version==4
                and draft.run==self.receive.run and same(draft.binding,self.receive.primary_binding)
                and str(draft.root)==self.receive.bound_record['primaryArtifactRoot']['path']
                and draft.lock.path==self.receive.primary_lock.path)
            draft.bound();need(draft.previous is None or same(draft.decode(draft.previous),draft.state))
            yield draft
            draft.bound();self.receive.bound()

    @staticmethod
    def retained(draft,ticket):
        need(not any(row['ticket']==ticket for row in draft.state['failures']))
        pending=draft.state['pending']
        need(pending is None or pending['ticket']==ticket and pending['verb']=='send')
        rows=[row for row in draft.state['operations'] if row['ticket']==ticket]
        if pending is not None:rows.append(pending)
        need(len(rows)<=1)
        if not rows:return None
        row=rows[0];need(row['verb']=='send' and row['inputs']=={})
        return deepcopy(row)

    def before(self,draft,send):
        first=draft.original(send['before'])['clockJoin'];eligible=[]
        for reference in self.receive.state['records']:
            frame=self.receive.original(reference);join=frame['joins']['peer']
            if (join['hostAfterEpochMs']<=first['hostBeforeEpochMs']
                    and join['hostAfterMonotonic']<=first['hostBeforeMonotonic']):eligible.append(reference)
        need(eligible);reference=eligible[-1]
        follow_native(self.receive.original(reference)['joins']['primary']['nativeAfter'],first['nativeBefore'])
        return deepcopy(reference)

    def after(self,draft,send,before):
        last=draft.original(send['after'])['clockJoin']
        baseline=self.receive.original(before)['sample']['peer']['source']['events']
        for reference in self.receive.state['records'][before['index']:]:
            frame=self.receive.original(reference);join=frame['joins']['primary']
            if (last['hostAfterEpochMs']<=join['hostBeforeEpochMs']
                    and last['hostAfterMonotonic']<=join['hostBeforeMonotonic']):
                events=frame['sample']['peer']['source']['events']
                need(same(events[:len(baseline)],baseline))
                # Empty cuts remain original evidence of no delivery. The first
                # actual append must pass the full join; it cannot be skipped
                # to hide a foreign, duplicate or otherwise invalid receipt.
                if len(events)>len(baseline):return deepcopy(reference)
        return None

    @operation
    def send(self,ticket):
        identifier(ticket);self.receive.bound();self.receive.recover()
        with self.owner() as draft:
            draft.recover_observation();send=self.retained(draft,ticket)
            before=None if send is None else self.before(draft,send)
        if before is None:before=self.receive.capture()
        with self.owner() as draft:
            send=self.retained(draft,ticket)
            if send is None or send['after'] is None:
                # Existing act resolves its durable pending input without a
                # second dispatch. A completed Send is never called again.
                draft.act(ticket,'send',{})
                send=self.retained(draft,ticket)
            need(send is not None and send['after'] is not None)
            after=self.after(draft,send,before)
        if after is None:after=self.receive.capture()
        with self.owner() as draft:return original_sent(draft,self.receive,ticket,before,after)
