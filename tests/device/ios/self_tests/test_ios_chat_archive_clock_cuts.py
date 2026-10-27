"""Actual later WAL originals remain in a bounded Send's clock scope.

The independent native/UI/bus/clock producers are explicit host models. No
future operation result, cleanup authority, device or mixer is qualified here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_send_receive import original_sent
from ios.self_tests.test_ios_chat_source_bound_owner import ChatSourceBoundOwnerTests
from ios.self_tests.chat_peer_send_fixture import PeerSendFixture


class ChatArchiveClockCutsTests(unittest.TestCase):
    def setUp(self):
        self.f=ChatSourceBoundOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.act('open');self.f.act('type',dict(text=context(self.f.run)['unicode']));self.f.act('send')
        self.ticket=self.f.m.ticket
        with self.f.owner() as owner:self.frontier=deepcopy(owner.state['operations'][-1]['after'])
        self.f.act('select-channel',dict(channel='domain'))
        self.enterContext(self.f.f.lock.held())
        self.owner=IOSChatDraftOwner.archive(self.f.f.store,self.f.f.root,self.f.binding,self.f.run,self.f.f.lock,
            self.f.m.owner.fixture_url,source_bound=True,through=self.frontier,ticket=self.ticket)

    def test_later_originals_supply_clock_context_without_entering_the_send_result(self):
        files=self.f.census();prefix=deepcopy(self.owner.state);cuts=list(self.owner._clock_cuts())
        self.assertGreater(len(cuts),len(prefix['records']));self.assertEqual('select-channel',cuts[-1]['verb'])
        self.assertNotEqual(self.ticket,cuts[-1]['ticket']);self.assertEqual(prefix,self.owner.state)
        self.assertEqual(files,self.f.census());self.assertEqual(self.frontier,self.owner.state['records'][-1])
        with self.assertRaises(NativeUIError):self.owner.restore_history('c'*32)

    def test_same_actual_original_reused_as_a_later_native_host_cut_is_refused(self):
        cuts=list(self.owner._clock_cuts());files=self.f.census()
        with self.assertRaises(NativeUIError):self.owner._frame(cuts[-1],cuts[-1],_dependencies=False)
        self.assertEqual(files,self.f.census())

    def test_changed_future_join_hash_or_phase_cannot_replace_its_original_projection(self):
        cuts=list(self.owner._clock_cuts());files=self.f.census()
        for fault in ('hash','phase','profile'):
            changed=deepcopy(cuts[-1])
            if fault=='hash':changed['clockJoin']['originalsSha256']='0'*64
            elif fault=='phase':changed['phaseAfter']['activations'][-1]['ticket']='d'*32
            else:changed['iosChatDraftObservationVersion']=True
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):
                self.owner._frame(changed,cuts[-2],_dependencies=False)
        self.assertEqual(files,self.f.census())

    def test_live_or_full_owner_has_no_dependencies_false_projection_bypass(self):
        with self.f.owner() as owner:
            with self.assertRaises(NativeUIError):list(owner._clock_cuts())
            frame=owner.original(owner.state['records'][-1])
            with self.assertRaises(NativeUIError):owner._frame(frame,_dependencies=False)


class ChatArchiveClockWindowTests(unittest.TestCase):
    def test_actual_later_other_ticket_and_control_inside_receive_window_is_not_hidden_by_prefix(self):
        f=PeerSendFixture(self);f.open();f.type('peer');peer=f.drafts['peer'];ticket=peer.m.ticket
        before=f.receive.capture()
        with peer.owner() as owner:
            owner.act(ticket,'send',{});send=deepcopy(owner.state['operations'][-1])
        # A distinct actual normal control occurs before the closing receive
        # cut. No original clock or saved file is rewritten to place it there.
        peer.act('select-channel',dict(channel='local'))
        after=f.receive.capture();files=f.pair.census();calls=f.pair.commands()
        archive=IOSChatDraftOwner.archive(peer.f.store,peer.f.root,peer.binding,peer.run,peer.f.lock,
            peer.m.owner.fixture_url,source_bound=True,peer_actor=True,through=send['after'],ticket=ticket)
        cuts=list(archive._clock_cuts());last=cuts[-1]
        self.assertEqual('select-channel',last['verb']);self.assertNotEqual(ticket,last['ticket'])
        right=f.receive.original(after)['joins']['primary']
        self.assertLessEqual(last['clockJoin']['hostBeforeEpochMs'],right['hostBeforeEpochMs'])
        with self.assertRaises(NativeUIError):original_sent(archive,f.receive,ticket,before,after,sender_role='peer')
        self.assertEqual(1,len(f.models['peer'].source['chatSends']))
        self.assertEqual(files,f.pair.census());self.assertEqual(calls,f.pair.commands())
