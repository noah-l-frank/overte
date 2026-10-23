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

    def test_rootless_original_observation_and_cleanup_publisher_chunks_keep_generic_cleanup_closed(self):
        self.assertFalse(self.adapter._chat_application_retained(self.target))
        stores=(self.adapter._chat_observation_store(self.target,'actor',stage='cleanup',witness=True),
            self.adapter._chat_cleanup_witness_store(self.target),
            self.adapter._chat_cleanup_baseline_store(self.target),
            self.adapter._chat_cleanup_source_seal_store(self.target,witness=False),
            self.adapter._chat_cleanup_source_seal_store(self.target,witness=True))
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


if __name__=='__main__':unittest.main()
