"""Synchronous proof guards on real private Chat stores and original locks.

Empty decoder fixtures isolate memo safety; they establish no sent message or
native/user outcome. The unchanged connected bidirectional journey is separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from feature_journeys.witness import Client
from ios.adapters import chat_archive_round as rounds
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.test_ios_chat_receive_runtime import IOSChatReceiveRuntimeTests
from self_tests.test_native_chat_observation import RUN


class IOSChatArchiveRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=IOSChatReceiveRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        parts=self.f.parts();self.binding=parts['binding'];self.calls=0;self.good=True
        root=self.f.artifacts['peer'];store=PrivateFeatureState(self.f.paths['peer'].with_name('ios-chat-receive-sources.json'))
        envelope=dict(iosChatReceiveSourcesVersion=1,binding=parts['peer']['binding'],primaryBinding=parts['primary']['binding'],
            runId=RUN,artifactRoot=str(root),peerBindingRecord=self.binding,payload=pack([IOSChatReceiveSources.empty()]))
        store.write(envelope,None)
        self.source=IOSChatReceiveSources.archive(store,parts['primary']['binding'],parts['peer']['binding'],RUN,
            self.f.artifacts['primary'],root,self.binding,self.f.locks['primary'],self.f.locks['peer'])
        client=object.__new__(Client);client.url='http://fixture.invalid'
        self.contexts=self.f.runtime._chat_receipt_contexts('primary','peer',RUN,client,self.source)
        self.fixture=client.url+'/runs/'+RUN+'/'
        for role in ('primary','peer'):
            value=dict(iosChatDraftOwnerVersion=6 if role=='primary' else 7,runId=RUN,binding=parts[role]['binding'],
                artifactRoot=str(self.f.artifacts[role]),fixtureUrl=self.fixture,payload=pack([IOSChatDraftOwner.empty()]))
            PrivateFeatureState(self.f.paths[role].with_name('ios-chat-draft-owner.json')).write(value,None)
        self.owner=self.archive();self.owner.historical=False
        def guard():self.calls+=1;return self.good
        self.owner.guard=guard

    def archive(self,role='primary'):
        return IOSChatDraftOwner.archive(PrivateFeatureState(self.f.paths[role].with_name('ios-chat-draft-owner.json')),
            self.f.artifacts[role],self.binding[role+'Binding'],RUN,self.f.locks[role],self.fixture,
            source_bound=True,peer_actor=role=='peer',peer_receipts=self.contexts[role])

    def outer(self,callback):
        return rounds.decode(self.owner,self.owner.previous,callback)

    def test_completed_nodes_are_reused_with_actual_callbacks_and_detached_results(self):
        def body():
            first=self.archive();count=self.calls;second=self.archive()
            self.assertGreater(self.calls,count);self.assertGreaterEqual(rounds._ACTIVE.get().hits,1)
            first.state['records'].append('external scratch')
            self.assertEqual([],second.state['records'])
            return self.owner.decode_body(self.owner.previous)
        self.assertEqual(self.owner.state,self.outer(body));self.assertIsNone(rounds._ACTIVE.get())

    def test_memory_header_file_inode_mode_and_inventory_changes_refuse_reuse(self):
        for fault in ('memory','header','file','inode','mode','inventory'):
            with self.subTest(fault=fault):
                def body():
                    self.archive();path=self.owner.store.path
                    if fault=='memory':self.owner.binding['generation']+=1
                    elif fault=='header':
                        value=self.owner.store.read();self.owner.store.write(value|dict(fixtureUrl=self.fixture+'foreign'),value)
                    elif fault=='file':path.write_bytes(path.read_bytes()+b' ')
                    elif fault=='inode':
                        temporary=path.with_name('replacement');temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);temporary.replace(path)
                    elif fault=='mode':path.chmod(0o640)
                    else:(self.owner.root/'unexpected').write_bytes(b'foreign')
                    self.archive()
                original=deepcopy(self.owner.binding);raw=self.owner.store.path.read_bytes()
                with self.assertRaises((ValueError,RuntimeError)):self.outer(body)
                self.owner.binding=original;self.owner.store.path.write_bytes(raw);self.owner.store.path.chmod(0o600)
                (self.owner.root/'unexpected').unlink(missing_ok=True)
                self.assertIsNone(rounds._ACTIVE.get())

    def test_write_query_input_and_live_capture_cannot_cross_a_round(self):
        actions=(self.owner.save,lambda:self.owner.query_intent({}),lambda:self.owner.input_intent({}),
            lambda:self.owner.storage_intent('original',{}),lambda:self.owner.capture('a'*32,'open',{}),
            self.source.save,lambda:self.source.query_intent('primary',{}),self.source.capture)
        for action in actions:
            with self.subTest(action=action):
                def body():
                    self.archive()
                    with self.assertRaises(NativeUIError):action()
                    return self.owner.decode_body(self.owner.previous)
                files=self.f.census();self.outer(body);self.assertEqual(files,self.f.census())

    def test_changed_decoder_uses_literal_path_instead_of_a_completed_proof(self):
        def body():
            self.archive()
            with patch.object(IOSChatDraftOwner,'decode_body',side_effect=NativeUIError('Actual substituted parser')) as parser:
                with self.assertRaisesRegex(NativeUIError,'substituted parser'):self.archive()
                self.assertEqual(1,parser.call_count)
            return self.owner.decode_body(self.owner.previous)
        self.outer(body)

    def test_pending_cycle_is_never_a_completed_node_and_the_context_is_restored(self):
        owner=self.archive()
        with self.assertRaises(NativeUIError):rounds.decode(owner,owner.previous,lambda:self.archive())
        self.assertIsNone(rounds._ACTIVE.get())
        self.assertEqual(owner.state,owner.decode(owner.previous))

    def test_separate_outer_decoders_cannot_retain_a_finished_proof(self):
        for _ in range(2):
            def body():
                self.assertEqual(0,rounds._ACTIVE.get().hits);self.archive();self.assertEqual(0,rounds._ACTIVE.get().hits)
                self.archive();self.assertGreaterEqual(rounds._ACTIVE.get().hits,1)
                return self.owner.decode_body(self.owner.previous)
            self.outer(body);self.assertIsNone(rounds._ACTIVE.get())

    def test_original_receive_decoder_has_its_distinct_completed_key(self):
        def body():
            self.assertEqual(self.source.state,self.source.decode(self.source.previous))
            self.assertEqual(self.source.state,self.source.decode(self.source.previous))
            self.assertGreaterEqual(rounds._ACTIVE.get().hits,1)
            return self.owner.decode_body(self.owner.previous)
        self.outer(body)

    def test_peer_outer_round_pins_the_primary_wal_parent_as_well(self):
        self.owner=self.archive('peer');self.owner.historical=False;self.owner.guard=lambda:True
        def body():
            first=self.archive();second=self.archive();self.assertEqual(first.state,second.state)
            self.assertGreaterEqual(rounds._ACTIVE.get().hits,1)
            return self.owner.decode_body(self.owner.previous)
        self.outer(body)

    def test_instance_parser_override_and_changed_candidate_cannot_use_a_completed_node(self):
        def body():
            self.archive()
            with patch.object(self.owner.frames,'read',side_effect=AssertionError('Foreign instance parser')):
                with self.assertRaises(NativeUIError):self.archive()
            self.good=False
            with self.assertRaises(NativeUIError):self.archive()
            self.good=True
            return self.owner.decode_body(self.owner.previous)
        self.outer(body)

    def test_transitive_native_validator_substitution_keeps_the_literal_path(self):
        from adapters import native_chat_view
        def body():
            self.archive();hits=rounds._ACTIVE.get().hits
            with patch.object(native_chat_view,'validate',side_effect=AssertionError('Substituted native validator')):
                self.assertFalse(rounds.original_methods())
                self.archive();self.assertEqual(hits,rounds._ACTIVE.get().hits)
            return self.owner.decode_body(self.owner.previous)
        self.outer(body)

    def test_external_candidate_metadata_read_disables_reuse_without_adopting_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);store=PrivateFeatureState(root/'actual-candidate.json')
            store.write(dict(candidate='actual-installed-snapshot'),None)
            def body():
                self.archive();self.assertTrue(rounds._ACTIVE.get().memo)
                rounds.decode(self.source,self.source.previous,lambda:(store.read(),self.source.decode_body(self.source.previous))[1])
                current=rounds._ACTIVE.get();self.assertTrue(current.disabled);self.assertFalse(current.memo)
                self.assertNotIn(root,current.roots)
                self.archive();self.assertFalse(current.memo)
                return self.owner.decode_body(self.owner.previous)
            self.outer(body)

    def test_memo_entry_aggregate_and_single_payload_limits_keep_literal_results(self):
        for field,limit in (('_MAX_ENTRIES',1),('_MAX_BYTES',1),('_MAX_ENTRY_BYTES',1)):
            with self.subTest(field=field):
                def body():
                    with patch.object(rounds,field,limit):
                        first=self.archive()
                        actual=self.source.decode(self.source.previous)
                        self.assertEqual(self.source.state,actual)
                        current=rounds._ACTIVE.get();self.assertTrue(current.disabled)
                        self.assertFalse(current.memo);self.assertEqual(0,current.memo_bytes)
                        self.assertEqual(first.state,self.archive().state)
                    return self.owner.decode_body(self.owner.previous)
                self.outer(body)
