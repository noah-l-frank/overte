"""Actual independent production Scripts on declared native/bus/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.adapters.chat_send_receive import original_sent
from ios.self_tests.chat_peer_send_fixture import PeerSendFixture


class IOSChatPeerSendTests(unittest.TestCase):
    def setUp(self):
        self.f=PeerSendFixture(self);self.f.open();self.f.type('peer');self.draft=self.f.drafts['peer']
        self.operation=IOSChatSendOperation(self.f.receive,self.draft.owner,sender_role='peer')
    def census(self):
        return (self.f.pair.commands(),[deepcopy(model.native.commands) for model in self.f.models.values()],
            [deepcopy(model.widgets.calls) for model in self.f.models.values()],self.f.pair.census())
    def test_actual_peer_normal_send_and_primary_script_receipt_pure_repeat_and_archive(self):
        runtime=self.f.pair.runtime
        with patch.object(runtime,'draft_owner',side_effect=lambda *args,**kwargs:self.draft.owner()) as factory:
            operation=runtime._chat_send_operation('peer',self.draft.run,self.draft.f.root,object(),self.f.receive,sender_role='peer')
            fact=operation.send(self.draft.m.ticket)
            self.assertEqual(dict(source_bound=True,lock=self.f.pair.locks['peer'],peer_actor=True),factory.call_args.kwargs)
        self.assertEqual(1,fact['iosChatPeerSendReceiveDerivedVersion']);self.assertNotIn('iosChatSendReceiveDerivedVersion',fact)
        wire=self.f.models['peer'].command('read')['chatSends'][0];message=json.loads(wire['message'])
        primary=self.f.models['primary'].command('read')
        self.assertEqual([message['message']],[row['message'] for row in primary['history']])
        self.assertEqual([message['message']],primary['domain']);self.assertEqual([],primary['chatSends'])
        self.assertEqual(message['message'],fact['events']['primary']['text'])
        before=self.census()
        self.assertEqual(fact,self.operation.send(self.draft.m.ticket));self.assertEqual(before,self.census())
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No archive writes')):
            receive=IOSChatReceiveSources.archive(self.f.receive.store,self.f.receive.primary_binding,self.f.receive.binding,
                self.f.receive.run,self.f.pair.artifacts['primary'],self.f.pair.artifacts['peer'],self.f.parts['binding'],
                self.f.pair.locks['primary'],self.f.pair.locks['peer'])
            draft=IOSChatDraftOwner.archive(self.draft.f.store,self.draft.f.root,self.draft.binding,self.draft.run,
                self.draft.f.lock,self.draft.m.owner.fixture_url,source_bound=True,peer_actor=True)
            self.assertEqual(fact,original_sent(draft,receive,fact['ticket'],fact['receiveBefore'],fact['receiveAfter'],sender_role='peer'))
        self.assertEqual(before,self.census())
    def test_lost_peer_send_return_resolves_the_peer_wal_without_another_emission(self):
        self.draft.m.lose_bus_return=True
        with self.assertRaises(OSError):self.operation.send(self.draft.m.ticket)
        inputs=deepcopy(self.draft.m.widgets.calls);self.draft.m.lose_bus_return=False
        fact=self.operation.send(self.draft.m.ticket)
        self.assertEqual(1,fact['iosChatPeerSendReceiveDerivedVersion'])
        self.assertEqual(inputs,self.draft.m.widgets.calls);self.assertEqual(1,len(self.draft.m.source['chatSends']))
    def test_peer_self_echo_without_primary_receipt_cannot_satisfy_the_reverse_join(self):
        self.f.drop_primary=True
        with self.assertRaises(NativeUIError):self.operation.send(self.draft.m.ticket)
        self.assertEqual([],self.f.pair.primary.events);self.assertEqual(1,len(self.f.pair.peer.events))
        self.assertEqual(1,len(self.draft.m.source['chatSends']))
    def test_primary_role_cannot_adopt_the_independently_bound_peer_owner(self):
        before=self.census()
        with self.assertRaises(NativeUIError):IOSChatSendOperation(self.f.receive,self.draft.owner).send(self.draft.m.ticket)
        self.assertEqual(before,self.census())
    def test_literal_source_bound_four_cannot_adopt_peer_five(self):
        before=self.census()
        with self.assertRaises(NativeUIError):
            IOSChatDraftOwner.archive(self.draft.f.store,self.draft.f.root,self.draft.binding,self.draft.run,
                self.draft.f.lock,self.draft.m.owner.fixture_url,source_bound=True)
        self.assertEqual(before,self.census())
    def test_peer_local_channel_uses_actual_other_script_history_and_keeps_domain_hidden(self):
        # Change the actual already typed editor's channel through its normal
        # control, then issue the same ordinary peer Send.
        from feature_journeys.fixtures import context
        self.draft.m.add_phase('peer-send',dict(text=context(self.draft.run)['reply'],channel='local'),'a'*32)
        with self.draft.owner() as owner:owner.act(self.draft.m.ticket,'select-channel',dict(channel='local'))
        fact=self.operation.send(self.draft.m.ticket);primary=self.f.models['primary'].command('read')
        self.assertEqual('local',fact['events']['primary']['channel'])
        self.assertEqual([fact['events']['primary']['text']],primary['local']);self.assertEqual([],primary['domain'])


if __name__=='__main__':unittest.main()
