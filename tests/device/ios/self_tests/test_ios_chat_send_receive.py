"""Actual production Script wire, modeled native/mixer/SDK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_send_receive import original_sent
from ios.self_tests.chat_send_receive_fixture import SendReceiveFixture


class IOSChatSendReceiveTests(unittest.TestCase):
    def setUp(self):self.f=SendReceiveFixture(self)
    def joined(self,before,after,ticket,*,receive=None):
        with self.f.draft.owner() as draft:
            return original_sent(draft,receive or self.f.receive,ticket,before,after)
    def normal(self):
        before=self.f.prepare();after,ticket=self.f.send();return before,after,ticket
    def test_actual_script_output_normal_send_and_independent_originals_pure_archive(self):
        before,after,ticket=self.normal();fact=self.joined(before,after,ticket)
        self.assertEqual(1,fact['iosChatSendReceiveDerivedVersion']);self.assertEqual(1,len(self.f.model.source['chatSends']))
        wire=self.f.model.source['chatSends'][0]
        self.assertEqual(fact['events']['peer']['text'],json.loads(wire['message'])['message'])
        self.assertGreater(fact['events']['peer']['capturedEpochMs'],fact['events']['primary']['capturedEpochMs'])
        queries=self.f.pair.commands();inputs=deepcopy(self.f.model.widgets.calls);files=self.f.pair.census()
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No derived or archive writes')):
            receive=self.f.archive()
            draft=IOSChatDraftOwner.archive(self.f.draft.f.store,self.f.draft.f.root,self.f.draft.binding,
                self.f.draft.run,self.f.draft.f.lock,self.f.model.owner.fixture_url,source_bound=True)
            self.assertEqual(fact,original_sent(draft,receive,ticket,before,after))
        self.assertEqual(queries,self.f.pair.commands());self.assertEqual(inputs,self.f.model.widgets.calls)
        self.assertEqual(files,self.f.pair.census())
    def test_missing_peer_receipt_never_uses_self_echo_or_requested_text(self):
        before=self.f.prepare();self.f.drop_peer=True;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
        self.assertEqual(1,len(self.f.model.source['chatSends']));self.assertEqual([],self.f.pair.peer.events)
    def test_duplicate_peer_receipt_preserves_multiplicity_and_refuses_one_send(self):
        before=self.f.prepare();self.f.duplicate_peer=True;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
        self.assertEqual(2,len(self.f.pair.peer.events));self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_peer_local_only_refuses_without_another_send(self):
        before=self.f.prepare();self.f.local_peer=True;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
        self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_wrong_actual_sender_is_not_adopted_as_the_primary(self):
        before=self.f.prepare();self.f.wrong_sender=True;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
    def test_other_allowed_text_is_not_substituted_for_the_actual_emitted_message(self):
        before=self.f.prepare();self.f.wrong_text=True;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
    def test_normal_domain_channel_is_read_from_editor_and_actual_script_wire(self):
        before=self.f.prepare(channel='domain');after,ticket=self.f.send()
        fact=self.joined(before,after,ticket)
        self.assertEqual('domain',fact['events']['peer']['channel'])
        self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_lost_normal_send_return_resolves_actual_draft_wal_without_another_emission(self):
        before=self.f.prepare();self.f.model.lose_bus_return=True
        with self.assertRaises(OSError):self.f.draft.act('send')
        calls=deepcopy(self.f.model.widgets.calls);self.f.model.lose_bus_return=False
        self.f.draft.act('send',same=True);after=self.f.receive.capture();ticket=self.f.model.ticket
        self.joined(before,after,ticket)
        self.assertEqual(calls,self.f.model.widgets.calls);self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_foreign_original_binding_changed_private_state_and_reversed_cuts_are_rejected(self):
        before,after,ticket=self.normal()
        with self.assertRaises(NativeUIError):self.joined(after,before,ticket)
        binding=deepcopy(self.f.receive.primary_binding);self.f.receive.primary_binding['sessionId']='foreign-primary'
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
        self.f.receive.primary_binding=binding
        self.f.receive.state['interrupted'].append(dict(queries=[],partial={},wire=None))
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
    def test_absent_mixer_cannot_hide_in_the_window(self):
        before=self.f.prepare();self.f.pair.peer.mixer=False;after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)
    def test_replaced_actual_mixer_is_not_equal_to_the_original_domain(self):
        before=self.f.prepare()
        self.f.observation_fault=lambda role,value:value['source'].update(mixerSha256='a'*64)
        with self.assertRaises(NativeUIError):self.f.send()
        self.assertEqual(1,len(self.f.model.source['chatSends']))
        self.assertIsNotNone(self.f.receive.state['pending'])
        self.assertEqual([before],self.f.receive.state['records'])
    def test_outer_receive_cut_before_typing_cannot_bind_only_the_later_send(self):
        self.f.draft.act('open');before=self.f.receive.capture()
        from feature_journeys.fixtures import context
        self.f.draft.act('type',dict(text=context(self.f.draft.run)['unicode']))
        after,ticket=self.f.send()
        with self.assertRaises(NativeUIError):self.joined(before,after,ticket)


if __name__=='__main__':unittest.main()
