"""Two actual Scripts and one original shared phase producer from birth."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.self_tests.chat_peer_send_fixture import PeerSendFixture,HostClock,PairScriptModel


class SharedPhaseModel(PairScriptModel):
    @property
    def activations(self):return self.host.activations
    @activations.setter
    def activations(self,value):
        assert value==[]
        if not hasattr(self.host,'activations'):self.host.activations=[]
    @property
    def phase_sequence(self):return self.host.phase_sequence
    @phase_sequence.setter
    def phase_sequence(self,value):self.host.phase_sequence=value
    def add_phase(self,verb,inputs,ticket):
        if ticket=='1'*32 and self.activations:
            assert len(self.activations)==1 and self.activations[0]['ticket']==ticket
            self.verb,self.inputs,self.ticket=verb,deepcopy(inputs),ticket;return
        return super().add_phase(verb,inputs,ticket)


class PeerReceiptFixture:
    def __init__(self,case):
        clock=HostClock();clock.activations=[];clock.phase_sequence=0
        self.f=PeerSendFixture(case,model_class=SharedPhaseModel,clock=clock)
        self.primary,self.peer=self.f.drafts['primary'],self.f.drafts['peer']
        self.receipts=IOSChatPeerReceipts(self.f.receive,self.sender)
        self.primary.owner=partial(self.primary.owner,peer_receipts=self.receipts)
    @contextmanager
    def sender(self):
        peer=self.peer
        yield IOSChatDraftOwner.archive(peer.f.store,peer.f.root,peer.binding,peer.run,peer.f.lock,
            peer.m.owner.fixture_url,source_bound=True,peer_actor=True)
    def message(self):
        self.f.open();self.f.type('peer')
        fact=IOSChatSendOperation(self.f.receive,self.peer.owner,sender_role='peer').send(self.peer.m.ticket)
        return fact,self.receipts.link(fact)
    def read(self,link):
        with self.primary.owner() as owner:return owner.receive_peer(link['ticket'],link)
