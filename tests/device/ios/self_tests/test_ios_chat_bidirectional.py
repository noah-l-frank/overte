"""Actual independent Chat Scripts, explicitly modeled native/UI/bus/SDK clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_draft_owner import IOSChatDraftOwner,_ARCHIVE_FRONTIERS
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.chat_peer_receipt_fixture import PeerReceiptFixture


class IOSChatBidirectionalTests(unittest.TestCase):
    def setUp(self):
        self.base=PeerReceiptFixture(self);self.f=self.base.f
        self.contexts=self.f.pair.runtime._chat_receipt_contexts('primary','peer',self.base.primary.run,
            self.base.primary.m.client(),self.f.receive)
        for role,draft in self.f.drafts.items():draft.owner=partial(draft.owner,peer_receipts=self.contexts[role])
    def send(self,role,token):
        self.f.type(role,token=token)
        return IOSChatSendOperation(self.f.receive,self.f.drafts[role].owner,sender_role=role).send(self.f.models[role].ticket)
    def read(self,role,fact):
        link=self.contexts[role].link(fact)
        with self.f.drafts[role].owner() as owner:return owner.receive_peer(fact['ticket'],link)
    def test_normal_primary_send_peer_history_reply_primary_history_and_pure_both_archives(self):
        self.f.open();outgoing=self.send('primary','unicode');peer=self.read('peer',outgoing)
        reply=self.send('peer','reply');primary=self.read('primary',reply)
        self.assertEqual(2,reply['iosChatPeerSendReceiveDerivedVersion'])
        self.assertEqual(2,self.contexts['peer'].link(outgoing)['iosChatPeerReceiptLinkVersion'])
        self.assertEqual((),_ARCHIVE_FRONTIERS.get())
        self.assertEqual(1,len(self.f.models['primary'].source['chatSends']));self.assertEqual(1,len(self.f.models['peer'].source['chatSends']))
        files=self.f.pair.census();commands=self.f.pair.commands()
        source=self.f.receive
        archived_source=IOSChatReceiveSources.archive(source.store,source.primary_binding,source.binding,source.run,
            self.f.pair.artifacts['primary'],self.f.pair.artifacts['peer'],self.f.parts['binding'],
            self.f.pair.locks['primary'],self.f.pair.locks['peer'])
        contexts=self.f.pair.runtime._chat_receipt_contexts('primary','peer',source.run,self.base.primary.m.client(),archived_source)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No archival writes')):
            for role,fact,result in (('primary',reply,primary),('peer',outgoing,peer)):
                draft=self.f.drafts[role]
                archive=IOSChatDraftOwner.archive(draft.f.store,draft.f.root,draft.binding,draft.run,draft.f.lock,
                    draft.m.owner.fixture_url,source_bound=True,peer_actor=role=='peer',peer_receipts=contexts[role])
                self.assertEqual(result,archive.receive_peer(fact['ticket'],contexts[role].link(fact)))
        self.assertEqual(files,self.f.pair.census());self.assertEqual(commands,self.f.pair.commands())
    def test_literal_actor_five_cannot_adopt_the_symmetric_seven_journal(self):
        self.f.open();draft=self.f.drafts['peer'];files=self.f.pair.census()
        with self.assertRaises(NativeUIError):
            IOSChatDraftOwner.archive(draft.f.store,draft.f.root,draft.binding,draft.run,draft.f.lock,
                draft.m.owner.fixture_url,source_bound=True,peer_actor=True)
        self.assertEqual(files,self.f.pair.census())


if __name__=='__main__':unittest.main()
