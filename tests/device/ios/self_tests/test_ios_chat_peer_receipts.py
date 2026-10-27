"""Primary-owned incoming reads over actual Script and original-file data.

Native, Qt/widgets, bus, SDK and clock boundaries remain declared models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.self_tests.chat_peer_receipt_fixture import PeerReceiptFixture


class IOSChatPeerReceiptTests(unittest.TestCase):
    def setUp(self):self.f=PeerReceiptFixture(self)
    def inputs(self):return [deepcopy(model.widgets.calls) for model in self.f.f.models.values()]
    def queries(self):
        return (self.f.f.pair.commands(),[(deepcopy(model.native.commands),deepcopy(model.root_queries),
            deepcopy(model.code_queries),model.view_sequence,deepcopy(model.last_receipt)) for model in self.f.f.models.values()],
            self.f.f.clock.phase_sequence)
    def test_normal_peer_send_enters_primary_original_history_without_primary_input_and_replays_purely(self):
        fact,link=self.f.message();inputs=self.inputs();result=self.f.read(link)
        self.assertEqual('peer-receive',result['verifiedDraftAction']);self.assertFalse(result['failed'])
        with self.f.primary.owner() as owner:
            self.assertEqual(6,owner.version);op=owner.state['operations'][-1]
            self.assertEqual([],op['intents']);frame=owner.original(op['after'])
            row=frame['originals']['view']['source']['storage']['events'][-1]
            self.assertEqual(fact['events']['primary']['text'],row['text']);self.assertEqual('domain',row['channel'])
            self.assertEqual([],result['local']['messages']) # Primary Local remains visible.
        self.assertEqual(inputs,self.inputs());files=self.f.f.pair.census();calls=self.queries()
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No original replay writes')):
            self.assertEqual(result,self.f.read(link))
            primary=self.f.primary
            source=self.f.f.receive
            original_source=IOSChatReceiveSources.archive(source.store,source.primary_binding,source.binding,source.run,
                self.f.f.pair.artifacts['primary'],self.f.f.pair.artifacts['peer'],self.f.f.parts['binding'],
                self.f.f.pair.locks['primary'],self.f.f.pair.locks['peer'])
            receipts=IOSChatPeerReceipts(original_source,self.f.sender)
            def forbidden():raise AssertionError('No live SDK/candidate check in pure archive')
            with patch.dict(self.f.f.parts,check=forbidden):
                archived=IOSChatDraftOwner.archive(primary.f.store,primary.f.root,primary.binding,primary.run,primary.f.lock,
                    primary.m.owner.fixture_url,source_bound=True,peer_receipts=receipts)
                self.assertEqual(result,archived.receive_peer(link['ticket'],link))
        self.assertEqual(inputs,self.inputs());self.assertEqual(files,self.f.f.pair.census());self.assertEqual(calls,self.queries())
    def test_changed_actual_dependency_or_foreign_link_refuses_before_primary_input_or_new_capture(self):
        fact,link=self.f.message();calls=self.f.f.pair.commands();inputs=self.inputs()
        changed=deepcopy(link);changed['peerBindingRecord']['runId']='b'*32
        with self.assertRaises(NativeUIError):self.f.read(changed)
        self.assertEqual(inputs,self.inputs());self.assertEqual(calls,self.f.f.pair.commands())
    def test_unexplained_actual_primary_history_append_is_not_adopted_as_the_peer_send(self):
        fact,link=self.f.message();model=self.f.primary.m
        # A different actual Script callback is real data, but it has no matching
        # controlled peer Send/original pair and must not enter this operation.
        wire=deepcopy(self.f.peer.m.source['chatSends'][0]);model.command('receive',message=wire['message'],localOnly=False)
        with self.assertRaises(NativeUIError):self.f.read(link)
        self.assertIsNotNone(model.owner.state['pending']);self.assertEqual(1,len(self.f.peer.m.source['chatSends']))
    def test_coupled_primary_can_normally_send_after_its_owned_incoming_read(self):
        fact,link=self.f.message();self.f.read(link)
        self.f.f.type('primary',token='unicode')
        result=IOSChatSendOperation(self.f.f.receive,self.f.primary.owner).send(self.f.primary.m.ticket)
        self.assertEqual(2,result['iosChatSendReceiveDerivedVersion'])
        self.assertEqual(1,len(self.f.primary.m.source['chatSends']))
        self.assertEqual(1,len(self.f.peer.m.source['chatSends']))
    def test_lost_saved_primary_original_recovers_the_actual_file_without_query_or_input(self):
        fact,link=self.f.message();store=self.f.primary.f.store;write=store.write
        def lost(value,previous):
            result=write(value,previous);observation=unpack(value['payload'])[0]['observation']
            if observation is not None and observation['wire'] is not None and observation['wire']['phase']=='saved':
                raise OSError('Declared lost saved primary incoming original return')
            return result
        with patch.object(store,'write',side_effect=lost),self.assertRaises(OSError):self.f.read(link)
        wire=unpack(store.read()['payload'])[0]['observation']['wire']
        path=self.f.primary.m.owner.frames.path(wire);info=path.stat();original=(info.st_dev,info.st_ino,path.read_bytes())
        calls=self.queries();inputs=self.inputs();result=self.f.read(link)
        self.assertEqual(wire['index'],result['original']['index']);self.assertEqual(calls,self.queries());self.assertEqual(inputs,self.inputs())
        info=path.stat();self.assertEqual(original,(info.st_dev,info.st_ino,path.read_bytes()))
    def test_delayed_actual_script_callback_retains_empty_cuts_and_never_repeats_peer_send(self):
        self.f.f.open();model=self.f.primary.m;command=model.command;pending=[]
        def delayed(action,**values):
            if action=='receive':pending.append((self.f.f.clock.value+.5,deepcopy(values)));return model.source
            if pending and self.f.f.clock.value>=pending[0][0]:
                due,wire=pending.pop(0);command('receive',**wire)
            return command(action,**values)
        with patch.object(model,'command',side_effect=delayed):
            self.f.f.type('peer');fact=IOSChatSendOperation(self.f.f.receive,self.f.peer.owner,sender_role='peer').send(self.f.peer.m.ticket)
            link=self.f.receipts.link(fact);inputs=self.inputs();result=self.f.read(link)
        with self.f.primary.owner() as owner:
            frames=[owner.original(ref) for ref in owner.state['records']]
            empty=[frame for frame in frames if frame['verb']=='peer-receive' and frame['originals']['view']['source']['storage']['count']==0]
            self.assertGreaterEqual(len(empty),2)
            self.assertEqual(1,owner.original(result['original'])['originals']['view']['source']['storage']['count'])
        self.assertEqual(inputs,self.inputs());self.assertEqual(1,len(self.f.peer.m.source['chatSends']));self.assertEqual([],pending)
    def test_primary_four_cannot_adopt_six_without_the_actual_dependency_context(self):
        fact,link=self.f.message();calls=self.queries();inputs=self.inputs()
        primary=self.f.primary
        with self.assertRaises(NativeUIError):
            IOSChatDraftOwner.archive(primary.f.store,primary.f.root,primary.binding,primary.run,primary.f.lock,
                primary.m.owner.fixture_url,source_bound=True)
        self.assertEqual(calls,self.queries());self.assertEqual(inputs,self.inputs())
    def test_live_parent_phase_cannot_rebind_the_original_sender_payload(self):
        fact,link=self.f.message();inputs=self.inputs()
        # Alter the modeled server's NEXT reply, not any retained original.
        self.f.f.clock.activations[-1]['stimulus']['inputs']['channel']='local'
        with self.assertRaises(NativeUIError):self.f.read(link)
        self.assertEqual(inputs,self.inputs());self.assertIsNotNone(self.f.primary.m.owner.state['pending'])
    def test_canonical_runtime_reopens_the_actual_actor_journal_for_the_same_link(self):
        fact,link=self.f.message();runtime=self.f.f.pair.runtime;calls=self.queries();inputs=self.inputs()
        receipts=runtime._chat_peer_receipts('peer',self.f.peer.run,self.f.peer.m.client(),self.f.f.receive)
        self.assertEqual(link,receipts.link(fact));self.assertEqual(fact,receipts.read(link)[0])
        with self.assertRaises(NativeUIError):runtime._chat_peer_receipts('primary',self.f.peer.run,self.f.peer.m.client(),self.f.f.receive)
        self.assertEqual(calls,self.queries());self.assertEqual(inputs,self.inputs())


if __name__=='__main__':unittest.main()
