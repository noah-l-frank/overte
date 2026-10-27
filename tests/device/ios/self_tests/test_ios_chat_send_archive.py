"""Bounded actual Send archive, never whole-owner cleanup authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_draft_owner import IOSChatDraftOwner,_ARCHIVE_FRONTIERS
from ios.adapters.chat_send_receive import original_sent
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.self_tests.chat_peer_send_fixture import PeerSendFixture


class IOSChatSendArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f=PeerSendFixture(self);self.f.open();self.f.type('peer');self.peer=self.f.drafts['peer']
        self.fact=IOSChatSendOperation(self.f.receive,self.peer.owner,sender_role='peer').send(self.peer.m.ticket)
    def archive(self,**changes):
        values=dict(through=self.fact['sendAfter'],ticket=self.fact['ticket'],source_bound=True,peer_actor=True)
        values.update(changes)
        return IOSChatDraftOwner.archive(self.peer.f.store,self.peer.f.root,self.peer.binding,self.peer.run,self.peer.f.lock,
            self.peer.m.owner.fixture_url,**values)
    def test_actual_send_prefix_survives_later_owned_activity_without_adopting_its_authority(self):
        self.peer.act('select-channel',dict(channel='local'));calls=self.f.pair.commands();files=self.f.pair.census()
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No prefix writes')):
            owner=self.archive();self.assertTrue(owner.subgraph_only)
            self.assertEqual(self.fact['sendAfter'],owner.state['records'][-1])
            self.assertEqual(self.fact,original_sent(owner,self.f.receive,self.fact['ticket'],self.fact['receiveBefore'],self.fact['receiveAfter'],sender_role='peer'))
            with self.assertRaises(NativeUIError):owner.restore_history('b'*32)
            with self.assertRaises(NativeUIError):owner.cleanup('b'*32)
        self.assertEqual(calls,self.f.pair.commands());self.assertEqual(files,self.f.pair.census())
    def test_wrong_ticket_or_non_send_frontier_is_not_an_original_send_archive(self):
        for changes in (dict(ticket='b'*32),dict(through=self.fact['sendBefore']),dict(through={'index':True})):
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):self.archive(**changes)
        self.assertEqual((),_ARCHIVE_FRONTIERS.get())
    def test_actual_original_corruption_and_changed_journal_head_block_the_window(self):
        owner=self.archive();reference=self.fact['sendAfter'];path=owner.frames.path(owner.frames.expand(reference));raw=path.read_bytes()
        path.write_bytes(raw[:-1]+b' ')
        with self.assertRaises((ValueError,RuntimeError)):self.archive()
        path.write_bytes(raw);owner=self.archive();previous=self.peer.f.store.read()
        self.peer.f.store.write(previous|dict(fixtureUrl=previous['fixtureUrl']+'foreign'),previous)
        with self.assertRaises(NativeUIError):owner.original(reference)
    def test_recursive_archive_frontier_is_rejected_and_scope_is_restored(self):
        owner=self.archive();key=(str(owner.store.path),owner.run,owner.frontier_ticket,owner.frontier['index'],owner.frontier['sha256'])
        token=_ARCHIVE_FRONTIERS.set((key,))
        try:
            with self.assertRaises(NativeUIError):owner.decode(owner.previous)
            self.assertEqual((key,),_ARCHIVE_FRONTIERS.get())
        finally:_ARCHIVE_FRONTIERS.reset(token)
        self.assertEqual(owner.state,owner.decode(owner.previous))


if __name__=='__main__':unittest.main()
