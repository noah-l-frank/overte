"""Existing normal-input WAL, actual Script output and immutable peer cuts.

Native/SDK/mixer/QML/clock producers remain explicitly modeled; files, codecs,
locks and production JavaScript execute. No real device or network is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.self_tests.chat_send_receive_fixture import SendReceiveFixture


class IOSChatSendOperationTests(unittest.TestCase):
    def setUp(self):
        self.f=SendReceiveFixture(self);self.f.prepare();self.ticket='f'*32
        self.f.model.add_phase('send',{},self.ticket)
        self.operation=IOSChatSendOperation(self.f.receive,self.f.draft.owner)
    def test_canonical_runtime_normal_send_and_repeated_original_result_have_one_emission(self):
        runtime=self.f.pair.runtime;client=object()
        with patch.object(runtime,'draft_owner',side_effect=lambda *args,**kwargs:self.f.draft.owner()) as factory:
            operation=runtime._chat_send_operation('primary',self.f.draft.run,self.f.draft.f.root,client,self.f.receive)
            fact=operation.send(self.ticket)
            calls=self.f.pair.commands();files=self.f.pair.census();inputs=deepcopy(self.f.model.widgets.calls)
            self.assertEqual(fact,operation.send(self.ticket))
            self.assertTrue(all(call.kwargs==dict(source_bound=True,lock=self.f.pair.locks['primary']) for call in factory.call_args_list))
        self.assertEqual(1,len(self.f.model.source['chatSends']));self.assertEqual(calls,self.f.pair.commands())
        self.assertEqual(files,self.f.pair.census());self.assertEqual(inputs,self.f.model.widgets.calls)
    def test_lost_normal_send_return_resolves_existing_input_wal_without_another_emission(self):
        self.f.model.lose_bus_return=True
        with self.assertRaises(OSError):self.operation.send(self.ticket)
        inputs=deepcopy(self.f.model.widgets.calls);self.f.model.lose_bus_return=False
        fact=self.operation.send(self.ticket)
        self.assertEqual(self.ticket,fact['ticket']);self.assertEqual(inputs,self.f.model.widgets.calls)
        self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_delayed_peer_callback_keeps_empty_original_and_retries_only_passive_observation(self):
        self.f.drop_peer=True
        with self.assertRaises(NativeUIError):self.operation.send(self.ticket)
        empty=self.f.receive.state['records'][-1];self.assertEqual([],self.f.receive.original(empty)['sample']['peerMessages'])
        inputs=deepcopy(self.f.model.widgets.calls);self.f.drop_peer=False
        self.f.deliver(self.f.model.source['chatSends'][0],roles=('peer',))
        fact=self.operation.send(self.ticket)
        self.assertIn(empty,self.f.receive.state['records']);self.assertGreater(fact['receiveAfter']['index'],empty['index'])
        self.assertEqual(inputs,self.f.model.widgets.calls);self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_saved_after_original_return_loss_adopts_same_file_without_queries_or_input(self):
        store=self.f.receive.store;write=store.write
        def lost(value,previous):
            result=write(value,previous);pending=unpack(value['payload'])[0]['pending']
            if pending is not None and pending['wire'] is not None and pending['wire']['index']==3 and pending['wire']['phase']=='saved':
                raise OSError('Declared lost saved after-Send original return')
            return result
        with patch.object(store,'write',side_effect=lost),self.assertRaises(OSError):self.operation.send(self.ticket)
        pending=unpack(store.read()['payload'])[0]['pending'];wire=deepcopy(pending['wire'])
        path=self.f.receive.frames.path(wire);info=path.stat();original=(info.st_dev,info.st_ino,path.read_bytes())
        calls=self.f.pair.commands();inputs=deepcopy(self.f.model.widgets.calls)
        self.f.attach_clocks()
        self.f.receive=IOSChatReceiveSources(self.f.parts,store,epoch_ms=self.f.model.epoch,
            monotonic=lambda:self.f.model.widgets.clock)
        fact=IOSChatSendOperation(self.f.receive,self.f.draft.owner).send(self.ticket)
        self.assertEqual(3,fact['receiveAfter']['index']);self.assertEqual(calls,self.f.pair.commands())
        self.assertEqual(inputs,self.f.model.widgets.calls)
        info=path.stat();self.assertEqual(original,(info.st_dev,info.st_ino,path.read_bytes()))
        self.assertEqual(1,len(self.f.model.source['chatSends']))
    def test_foreign_runtime_context_refuses_before_factory_input_or_query(self):
        calls=self.f.pair.commands();inputs=deepcopy(self.f.model.widgets.calls);files=self.f.pair.census()
        with patch.object(self.f.pair.runtime,'draft_owner',side_effect=AssertionError('No foreign factory')):
            for values in (dict(selector='peer'),dict(run='b'*32),dict(root=self.f.pair.artifacts['peer'])):
                arguments=dict(selector='primary',run=self.f.draft.run,root=self.f.draft.f.root,client=object(),receive=self.f.receive)
                arguments.update(values)
                with self.subTest(values=values),self.assertRaises(NativeUIError):self.f.pair.runtime._chat_send_operation(**arguments)
        self.assertEqual(calls,self.f.pair.commands());self.assertEqual(inputs,self.f.model.widgets.calls)
        self.assertEqual(files,self.f.pair.census())
    def test_first_foreign_append_cannot_be_skipped_in_favor_of_a_later_valid_receipt(self):
        self.f.wrong_sender=True
        with self.assertRaises(NativeUIError):self.operation.send(self.ticket)
        rejected=self.f.receive.state['records'][-1];calls=self.f.pair.commands()
        inputs=deepcopy(self.f.model.widgets.calls);self.f.wrong_sender=False
        self.f.deliver(self.f.model.source['chatSends'][0],roles=('peer',))
        with self.assertRaises(NativeUIError):self.operation.send(self.ticket)
        self.assertEqual(rejected,self.f.receive.state['records'][-1]);self.assertEqual(calls,self.f.pair.commands())
        self.assertEqual(inputs,self.f.model.widgets.calls);self.assertEqual(1,len(self.f.model.source['chatSends']))


if __name__=='__main__':unittest.main()
