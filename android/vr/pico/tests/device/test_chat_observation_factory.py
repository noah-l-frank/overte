"""Original Pico factories, actual owned stdin peer; SDK/native producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
import test_chat_composition as seams


class PicoChatObservationFactoryTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.PicoChatCompositionTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adapter,self.target=self.h.instance,self.h.native.target
        self.parent=self.h.compose();self.h.prepare_sources(self.parent);self.parent.prepare()
        source=PhaseFixtureReader(Client('http://127.0.0.1:48300/feature-fixture/v1','b'*48),seams.RUN,'chat')
        self.original=self.adapter._chat_witness_composition(self.target,source,self.h.peer.config)
        self.h.owners.append(self.original)

    def samples(self):
        original=self.original
        return self.adapter._chat_cache_absence(self.target,seams.RUN,original.peer.reader(),original.peer.binding,
            role='actor',stage='final',witness=True,source_lock=original.lock,peer_lock=original.peer.lock,
            script_source=original.publisher.samples.script_source)

    def test_original_final_actor_factory_preserves_independent_live_code_readers_and_lock_objects(self):
        samples=self.samples();original=self.original
        owner=self.adapter._chat_observation(self.target,original.publisher.source,samples,stage='cleanup',witness=True)
        self.assertIs(original.publisher.source,owner.source);self.assertIsNot(self.parent.source.client,owner.source.client)
        self.assertIs(samples.script_source,original.publisher.samples.script_source)
        self.assertIs(samples.locks[0],original.lock);self.assertIs(samples.locks[1],original.peer.lock)
        self.assertIsNot(samples.primary,original.publisher.samples.primary);self.assertIsNot(samples.peer,original.publisher.samples.peer)
        self.assertIsNot(samples.view,original.publisher.samples.view);self.assertIsNot(samples.lifecycle,original.publisher.samples.lifecycle)
        self.assertIsNot(samples.script_source,self.parent.code_sources[1])
        self.assertEqual(self.adapter._chat_cleanup_admission_store(self.target).path,owner.cleanup_store.path)
        self.assertIsNone(owner.store.read());self.assertEqual([],samples.frames);self.assertEqual([],self.h.native.inputs)

    def test_adapter_credentials_and_premature_parent_cannot_construct_independent_cleanup_publisher(self):
        samples=self.samples()
        with self.assertRaises((ValueError,NativeUIError)):
            self.adapter._chat_observation(self.target,self.parent.source,samples,stage='cleanup',witness=True)
        with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_cleanup_witness(self.target,self.original)
        self.assertIsNone(self.adapter._chat_cleanup_witness_store(self.target).read())
        self.assertIsNone(self.adapter._chat_observation_store(self.target,'actor',stage='cleanup',witness=True).read())
        self.assertEqual([],self.h.native.inputs)

    def test_actual_primary_seal_factory_binds_only_fixed_cleanup_owner_without_native_queries(self):
        parent=self.parent
        samples=self.adapter._chat_cache_absence(self.target,seams.RUN,parent.peer.reader(),parent.peer.binding,
            role='primary',stage='final',source_lock=parent.lock,peer_lock=parent.peer.lock,script_source=parent.code_sources[0])
        owner=self.adapter._chat_observation(self.target,parent.source,samples,stage='cleanup')
        before=len(self.h.prepare_chat.commands)
        seal=self.adapter._chat_source_seal(self.target,owner,witness=False)
        self.assertIs(owner,seal.owner);self.assertEqual(self.adapter._chat_cleanup_source_seal_store(self.target,witness=False).path,seal.store.path)
        self.assertIsNone(seal.store.read());self.assertTrue(seal.live())
        with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_source_seal(self.target,owner,witness=True)
        self.assertEqual(before,len(self.h.prepare_chat.commands));self.assertEqual([],self.h.native.inputs)

    def test_initial_cursor_factory_keeps_exact_source_owner_and_rejects_independent_credential_alias(self):
        parent=self.parent
        initial=self.adapter._chat_observation(self.target,parent.source,parent.initial[0],stage='initial')
        cursor=self.adapter._chat_observation_cursor(self.target,initial)
        self.assertIs(initial,cursor.current);self.assertEqual([],cursor.rows);self.assertIsNone(cursor.store.read())
        self.assertEqual(self.adapter._chat_observation_cursor_store(self.target,'primary').path,cursor.store.path)
        with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_observation_cursor(self.target,initial,witness=True)
        with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_cursor_source_seal(self.target,cursor,witness=False)
        self.assertIsNone(self.adapter._chat_cursor_source_seal_store(self.target,witness=False).read())
        with self.assertRaises((ValueError,NativeUIError)):
            self.adapter._chat_cursor_cleanup_consumption(self.target,parent,cursor,object())
        self.assertIsNone(self.adapter._chat_cursor_cleanup_consumption_store(self.target).read())
        self.assertEqual([],self.h.native.inputs)

    def test_original_actor_publisher_factory_requires_fixed_independent_cursor_and_keeps_exact_guard_owner(self):
        original=self.original
        initial=self.adapter._chat_observation(self.target,original.publisher.source,original.publisher.initial_samples,stage='initial',witness=True)
        cursor=self.adapter._chat_observation_cursor(self.target,initial,witness=True)
        publisher=self.adapter._chat_observation_publisher(self.target,cursor)
        self.assertIs(cursor,publisher.cursor);self.assertIs(publisher.read_guard,cursor._freeze_guard)
        self.assertIs(original.publisher.source.client,publisher.client);self.assertEqual([],publisher.rows)
        self.assertEqual(self.adapter._chat_observation_publisher_store(self.target).path,publisher.store.path)
        self.assertIsNone(publisher.store.read());self.assertEqual([],self.h.native.inputs)

    def test_actual_global_actor_constructor_owns_original_peer_pairs_and_retains_intent_on_host_only_detach(self):
        actor=self.adapter._chat_cursor_actor(self.target,self.original.publisher.source,self.h.peer.config)
        self.addCleanup(actor.detach);self.assertEqual('publishing',actor.store.read()['phase'])
        self.assertEqual(2,len(actor.pairs));self.assertFalse(actor.closed);self.assertFalse(actor.failed)
        self.assertIs(actor.source,actor.publisher.observation.source)
        self.assertIsNot(self.original.peer,actor.original.peer)
        self.assertIs(actor.original.lock,actor.publisher.observation.samples.locks[0])
        self.assertIs(actor.original.peer.lock,actor.publisher.observation.samples.locks[1])
        before=actor.store.path.read_bytes()
        with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_cursor_actor(self.target,actor.source,self.h.peer.config)
        self.assertEqual(before,actor.store.path.read_bytes());self.assertTrue(self.adapter._chat_application_retained(self.target))
        self.assertTrue(actor.detach());self.assertTrue(all(owner.closed and not owner.lost for owner,_row in actor.pairs))
        self.assertFalse(actor.closed);self.assertEqual(before,actor.store.path.read_bytes());self.assertEqual([],self.h.native.inputs)

    def test_remote_actor_return_cannot_write_result_before_original_cache_retirement(self):
        store=self.adapter._chat_remote_actor_return_store(self.target)
        with self.assertRaises((ValueError,NativeUIError)):
            self.adapter._chat_remote_actor_return(self.target,self.parent,object(),{})
        self.assertIsNone(store.read());self.assertEqual([],self.h.native.inputs)

    def test_rootless_original_observation_and_cleanup_publisher_chunks_keep_generic_cleanup_closed(self):
        self.assertFalse(self.adapter._chat_application_retained(self.target))
        stores=(self.adapter._chat_observation_store(self.target,'actor',stage='cleanup',witness=True),
            self.adapter._chat_cleanup_witness_store(self.target),
            self.adapter._chat_cleanup_baseline_store(self.target),
            self.adapter._chat_cleanup_source_seal_store(self.target,witness=False),
            self.adapter._chat_cleanup_source_seal_store(self.target,witness=True),
            self.adapter._chat_observation_cursor_store(self.target,'primary'),
            self.adapter._chat_observation_cursor_store(self.target,'actor',witness=True),
            self.adapter._chat_observation_publisher_store(self.target),
            self.adapter._chat_cursor_source_seal_store(self.target,witness=False),
            self.adapter._chat_cursor_source_seal_store(self.target,witness=True),
            self.adapter._chat_cursor_cleanup_consumption_store(self.target),
            self.adapter._chat_cursor_actor_store(self.target),self.adapter._chat_cursor_actor_stop_store(self.target),
            self.adapter._chat_cursor_actor_return_store(self.target),self.adapter._chat_cursor_actor_consumption_store(self.target),
            self.adapter._chat_remote_actor_return_store(self.target))
        for store in stores:
            child=PrivateFeatureState(store.path.with_name(store.path.name+'.frame-000.json'))
            child.write(dict(explicitOriginalOrphan=True),None)
            self.assertTrue(self.adapter._chat_application_retained(self.target));self.assertTrue(child.path.exists())
        self.assertTrue(all(store.read() is None for store in stores));self.assertEqual([],self.h.native.inputs)

    def test_optional_archive_baseline_metadata_never_invents_legacy_or_partial_seal_fields(self):
        state,_ui=self.adapter._script_paths(self.target);key=state.stem.removeprefix('normal-script-state-')
        directory=state.parent/('chat-evidence-'+key+'-'+seams.RUN);directory.mkdir(mode=0o700)
        metadata=dict(picoChatArchivePlanVersion=4,runId=seams.RUN,
            oldBinding=deepcopy(self.parent.binding),newBinding=deepcopy(self.parent.binding))
        evidence=dict(metadata=metadata,chatEvidenceArchiveVersion=4,fileOwnership='closed-immutable-originals',
            unlinkPolicy='original-source-16-unlinks-250ms',copyVerification='full-current-copy-and-original-physical-inventory')
        # Archive-byte verification is an explicit seam here, not a claim
        # this empty fixture directory is a sealed completed archive.
        with patch('adapters.chat_journey.evidence_archive.completed_archive',return_value=evidence):
            self.assertFalse(self.adapter._chat_application_retained(self.target));self.assertNotIn('chatCleanupSourceSeals',metadata)
            metadata.update(chatCleanupBaselineSha256='a'*64,chatCleanupSourceSeals=['b'*64,'c'*64])
            self.assertFalse(self.adapter._chat_application_retained(self.target))
            for replacement in ({'chatCleanupBaselineSha256':True},{'chatCleanupSourceSeals':['b'*64,'b'*64]},
                {'chatCleanupSourceSeals':'b'*64},{'chatCleanupSourceSeals':None}):
                original=deepcopy(metadata);metadata.update(replacement)
                with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_application_retained(self.target)
                metadata.clear();metadata.update(original)

    def test_global_archive_metadata_requires_complete_true_extension_without_legacy_proof_aliases(self):
        state,_ui=self.adapter._script_paths(self.target);key=state.stem.removeprefix('normal-script-state-')
        directory=state.parent/('chat-evidence-'+key+'-'+seams.RUN);directory.mkdir(mode=0o700)
        metadata=dict(picoChatArchivePlanVersion=4,runId=seams.RUN,
            oldBinding=deepcopy(self.parent.binding),newBinding=deepcopy(self.parent.binding))
        evidence=dict(metadata=metadata,chatEvidenceArchiveVersion=4,fileOwnership='closed-immutable-originals',
            unlinkPolicy='original-source-16-unlinks-250ms',copyVerification='full-current-copy-and-original-physical-inventory')
        extension=dict(chatCursorCleanupConsumptionVersion=1,chatCursorCleanupConsumptionSha256='a'*64,
            chatCursorSourceSeals=['b'*64,'c'*64],chatCursorSequenceSucceeded=True)
        # The original completed_archive byte/hash verifier is explicitly a
        # seam in this parser test; an empty directory is not a real archive.
        with patch('adapters.chat_journey.evidence_archive.completed_archive',return_value=evidence):
            for key,value in extension.items():
                metadata[key]=value
                with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_application_retained(self.target)
                del metadata[key]
            metadata.update(extension);self.assertFalse(self.adapter._chat_application_retained(self.target))
            for changes in (dict(chatCursorCleanupConsumptionVersion=True),dict(chatCursorSequenceSucceeded=False),
                dict(chatCursorSequenceSucceeded=1),dict(chatCursorCleanupConsumptionSha256='unknown'),
                dict(chatCursorSourceSeals=['b'*64,'b'*64]),dict(chatCursorSourceSeals=('b'*64,'c'*64)),
                dict(chatCleanupBaselineSha256='d'*64,chatCleanupSourceSeals=['e'*64,'f'*64])):
                original=deepcopy(metadata);metadata.update(changes)
                with self.assertRaises((ValueError,NativeUIError)):self.adapter._chat_application_retained(self.target)
                metadata.clear();metadata.update(original)


if __name__=='__main__':unittest.main()
