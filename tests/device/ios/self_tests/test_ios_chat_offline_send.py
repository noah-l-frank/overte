"""Actual one-Node Script/WAL; explicitly modeled native, bus, Qt and SDK."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_offline_send_operation import IOSChatOfflineSendOperation
from ios.adapters.chat_offline_send_receive import original_local_echo
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_receive import original_sent
from ios.self_tests.chat_offline_send_fixture import OfflineSendFixture


class ChatOfflineSendTests(unittest.TestCase):
    def setUp(self):
        self.f = OfflineSendFixture(self)
        self.ticket = 'f' * 32
        self.quiet_ticket = '9' * 32
        self.operation = IOSChatOfflineSendOperation(self.f.receive, self.f.draft.owner,
                                                    sleep=self.f.model.sleep)

    def prepare(self):
        self.f.prepare(channel='domain')
        self.f.remove_mixer()
        self.f.model.add_phase('send', {}, self.ticket)

    def send(self):
        return self.operation.send(self.ticket)

    def restore(self):
        self.f.restore_mixer()
        self.f.model.add_phase('await-no-replay', {}, self.quiet_ticket)
        return self.operation.no_replay(self.quiet_ticket, self.ticket)

    def test_actual_normal_wire_local_echo_restored_mixer_quiet_and_explicit_online_resend(self):
        self.prepare()
        runtime = self.f.pair.runtime
        with patch.object(runtime, 'draft_owner', side_effect=lambda *args, **kwargs:self.f.draft.owner()) as factory:
            operation = runtime._chat_offline_send_operation('primary', self.f.draft.run,
                self.f.draft.f.root, object(), self.f.receive)
            echo = operation.send(self.ticket)
            self.assertTrue(factory.call_args_list)
            self.assertTrue(all(call.kwargs == dict(source_bound=True,
                lock=self.f.pair.locks['primary'], qml_bound=False) for call in factory.call_args_list))
        self.assertTrue(echo['localEcho']['localOnly'])
        self.assertFalse(echo['remoteDeliveryEstablished'])
        self.assertFalse(echo['domainContinuityEstablished'])
        self.assertEqual([], self.f.pair.peer.events)
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        source = self.f.model.command('read')
        self.assertEqual([echo['localEcho']['text']], [row['message'] for row in source['history']])
        quiet = self.restore()
        self.assertTrue(quiet['noRemoteReplayObserved'])
        self.assertTrue(quiet['historicalWindow'])
        self.assertFalse(quiet['wholeChatQualified'])
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual([], self.f.pair.peer.events)
        # A new ordinary type and a new Send ticket are necessary; restoring
        # the model node itself issued no product or peer input.
        self.f.draft.act('type', dict(text=echo['localEcho']['text']))
        next_ticket = '8' * 32
        self.f.model.add_phase('send', {}, next_ticket)
        online = IOSChatSendOperation(self.f.receive, self.f.draft.owner).send(next_ticket)
        self.assertEqual(echo['localEcho']['text'], online['events']['peer']['text'])
        self.assertEqual(2, len(self.f.model.source['chatSends']))
        self.assertEqual(1, len(self.f.pair.peer.events))
        self.assertEqual([echo['localEcho']['text']] * 2,
                         [row['message'] for row in self.f.model.command('read')['history']])

    def test_lost_normal_send_return_reconciles_the_same_real_wal_without_second_send(self):
        self.prepare(); self.f.model.lose_bus_return = True
        with self.assertRaises(OSError):
            self.send()
        calls = deepcopy(self.f.model.widgets.calls)
        self.f.model.lose_bus_return = False
        echo = self.send()
        self.assertEqual(self.ticket, echo['ticket'])
        self.assertEqual(calls, self.f.model.widgets.calls)
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual([], self.f.pair.peer.events)

    def test_actual_wire_without_native_callback_cannot_supply_success_or_a_second_send(self):
        self.prepare(); self.f.ignore_native_delivery = True
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual([], self.f.pair.primary.events)
        self.assertEqual([], self.f.pair.peer.events)
        self.assertEqual([], self.f.model.command('read')['history'] or [])
        self.assertIsNotNone(unpack(self.f.draft.f.store.read()['payload'])[0]['pending'])

    def test_consumed_normal_ack_without_script_wire_cannot_supply_history_or_echo(self):
        self.prepare(); self.f.model.widgets.ignore_effect = True
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual([], self.f.model.source['chatSends'])
        self.assertEqual([], self.f.lower_wires)
        self.assertEqual([], self.f.pair.primary.events)
        self.assertEqual([], self.f.pair.peer.events)

    def test_live_native_mixer_is_not_replaced_by_the_requested_offline_model_state(self):
        self.prepare()
        self.f.node_present = True
        calls = deepcopy(self.f.model.widgets.calls)
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(calls, self.f.model.widgets.calls)
        self.assertEqual([], self.f.model.source['chatSends'])

    def test_wrong_native_local_only_flag_does_not_adopt_the_actual_local_history(self):
        self.prepare(); self.f.false_local_only = True
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual(1, len(self.f.model.command('read')['history']))
        self.assertEqual([], self.f.pair.peer.events)

    def test_unexpected_foreign_peer_append_is_not_filtered_into_empty_delivery(self):
        self.prepare(); self.f.unexpected_peer_delivery = True
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(1, len(self.f.pair.peer.events))
        self.assertEqual(1, len(self.f.model.source['chatSends']))

    def test_replayed_actual_old_wire_on_restore_fails_no_replay_without_new_send(self):
        self.prepare(); self.send(); self.f.replay_on_restore = True
        with self.assertRaises(NativeUIError):
            self.restore()
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual(1, len(self.f.pair.peer.events))
        self.assertIsNotNone(self.operation.store.read())
        self.assertFalse(self.operation.store.read()['payload']['complete'])

    def test_historical_echo_and_quiet_reopen_exact_files_without_query_input_or_write(self):
        self.prepare(); echo = self.send(); quiet = self.restore()
        calls = deepcopy(self.f.model.widgets.calls)
        queries = self.f.pair.commands(); files = self.f.pair.census()
        with patch.object(PrivateFeatureState, 'write', side_effect=AssertionError('No historical write')):
            receive = self.f.archive()
            draft = IOSChatDraftOwner.archive(self.f.draft.f.store, self.f.draft.f.root,
                self.f.draft.binding, self.f.draft.run, self.f.draft.f.lock,
                self.f.model.owner.fixture_url, source_bound=True)
            self.assertEqual(echo, original_local_echo(draft, receive, self.ticket,
                             echo['receiveBefore'], echo['receiveAfter']))
            self.assertEqual(quiet, IOSChatOfflineSendOperation.archived_no_replay(draft, receive,
                             self.operation.store))
        self.assertEqual(calls, self.f.model.widgets.calls)
        self.assertEqual(queries, self.f.pair.commands()); self.assertEqual(files, self.f.pair.census())

    def test_lost_saved_no_replay_original_adopts_same_inode_without_requery_or_rebase(self):
        self.prepare(); self.send(); self.f.restore_mixer()
        self.f.model.add_phase('await-no-replay', {}, self.quiet_ticket)
        store = self.f.receive.store; write = store.write
        def lost(value, previous):
            result = write(value, previous); pending = unpack(value['payload'])[0]['pending']
            if pending is not None and pending['wire'] is not None and pending['wire']['phase'] == 'saved':
                raise OSError('Declared lost saved restored-mixer original return')
            return result
        with patch.object(store, 'write', side_effect=lost), self.assertRaises(OSError):
            self.operation.no_replay(self.quiet_ticket, self.ticket)
        pending = unpack(store.read()['payload'])[0]['pending']; wire = deepcopy(pending['wire'])
        path = self.f.receive.frames.path(wire); before = (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
        first_phase = deepcopy(self.operation.store.read()['payload']['pending']['phaseBefore'])
        query_before = self.f.pair.commands()
        self.f.attach_clocks()
        self.f.receive = IOSChatReceiveSources(self.f.parts, store, epoch_ms=self.f.model.epoch,
                                               monotonic=lambda:self.f.model.widgets.clock)
        self.operation = IOSChatOfflineSendOperation(self.f.receive, self.f.draft.owner,
                                                     sleep=self.f.model.sleep)
        selected_without_query = []
        window_write = self.operation.store.write
        def observed_selection(value, previous):
            if len(value['payload']['records']) == 1:
                self.assertEqual(query_before, self.f.pair.commands())
                selected_without_query.append(True)
            return window_write(value, previous)
        with patch.object(self.operation.store, 'write', side_effect=observed_selection):
            result = self.operation.no_replay(self.quiet_ticket, self.ticket)
        self.assertTrue(result['noRemoteReplayObserved'])
        self.assertTrue(selected_without_query)
        state = self.operation.store.read()['payload']
        self.assertEqual(wire['index'], state['records'][0]['reference']['index'])
        self.assertEqual(first_phase, state['records'][0]['phaseBefore'])
        self.assertEqual(before, (path.stat().st_dev, path.stat().st_ino, path.read_bytes()))
        self.assertEqual(1, len(self.f.model.source['chatSends']))

    def test_online_original_sent_still_refuses_the_new_offline_echo_profile(self):
        self.prepare(); echo = self.send()
        with self.f.draft.owner() as draft, self.assertRaises(NativeUIError):
            original_sent(draft, self.f.receive, self.ticket, echo['receiveBefore'], echo['receiveAfter'])

    def test_native_echo_without_actual_script_callback_history_cannot_supply_success(self):
        self.prepare(); self.f.ignore_script_callback = True
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(1, len(self.f.model.source['chatSends']))
        self.assertEqual(1, len(self.f.pair.primary.events))
        self.assertTrue(self.f.pair.primary.events[0]['localOnly'])
        self.assertEqual([], self.f.model.command('read')['history'] or [])
        self.assertEqual([], self.f.pair.peer.events)

    def test_changed_native_cache_instance_refuses_before_any_normal_send(self):
        self.prepare(); calls = deepcopy(self.f.model.widgets.calls)
        node = self.f.native_node_original
        def foreign(role, value):
            node(role, value)
            if role == 'primary':
                value['instance'] = 'f' * 32
        self.f.observation_fault = foreign
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(calls, self.f.model.widgets.calls)
        self.assertEqual([], self.f.model.source['chatSends'])

    def test_stale_native_cache_sequence_refuses_before_any_normal_send(self):
        self.prepare(); calls = deepcopy(self.f.model.widgets.calls)
        node = self.f.native_node_original
        def stale(role, value):
            node(role, value)
            if role == 'peer':
                value['sequence'] = 1
        self.f.observation_fault = stale
        with self.assertRaises(NativeUIError):
            self.send()
        self.assertEqual(calls, self.f.model.widgets.calls)
        self.assertEqual([], self.f.model.source['chatSends'])
