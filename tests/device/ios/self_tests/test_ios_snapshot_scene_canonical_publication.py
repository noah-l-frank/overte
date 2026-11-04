"""Prospective genuine-constructor canonical Actor-scene publication counters."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PublicationPending
from ios.adapters.snapshot_scene_canonical_runtime import SnapshotScenePublishedCaptureOrder
from ios.self_tests.snapshot_scene_canonical_domain import CanonicalSceneDomain,RUN,TICKET


class SnapshotSceneCanonicalPublicationTests(unittest.TestCase):
    def original(self,owner,index=1):
        owner.publication.prepare()
        witness=owner.actors.owner(index,historical=False)
        witness.acquire(TICKET)
        return witness,owner.publication.reference(index)

    def test_genuine_ordered_before_capture_after_publications_and_cold_original_history(self):
        d=CanonicalSceneDomain(self)
        with d.owner()as owner:
            result=owner.acquire(TICKET)
            self.assertTrue(result['canonicalActorScenePublicationEstablished'])
            self.assertTrue(result['orderedOriginal']['actorBeforeCaptureAfterOriginalOrderEstablished'])
            self.assertFalse(result['wholeQualified']);self.assertEqual(2,len(d.posts))
            self.assertEqual([1,2],[row['actorSequence']for row in d.journal.snapshot(RUN)['entries']])
            self.assertEqual(2,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)
            scope=(owner.store,owner.lock,owner.binding,owner.run,owner.page.fixture_url,owner.actors.root,owner.actors.lock,owner.actors.binding)
            calls=(len(d.actor.queries),len(d.posts),d.actor.ctx.native.sequence,d.primary.ctx.native.sequence)
            def forbidden(*_a,**_k):raise AssertionError('Historical scene publication touched live transport or storage')
            with patch.object(type(d.actor_client),'request',forbidden),patch.object(PrivateFeatureState,'write',side_effect=forbidden):
                archived=SnapshotScenePublishedCaptureOrder.archive(*scope,epoch_ms=d.primary.capture.epoch,monotonic=d.primary.capture.mono)
                self.assertEqual(result,archived.proof())
            self.assertEqual(calls,(len(d.actor.queries),len(d.posts),d.actor.ctx.native.sequence,d.primary.ctx.native.sequence))

    def test_actual_actor_only_factory_publishes_its_own_source_without_primary_input(self):
        d=CanonicalSceneDomain(self)
        with d.independent()as actor:
            result=actor.observe_original(1,TICKET)
            self.assertTrue(result['canonicalSceneOriginalPublished'])
            self.assertFalse(result['snapshotUIOutputFactsEstablished']or result['processOrSDKEndEstablished'])
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.actor.queries));self.assertEqual(0,d.primary.capture.capture_count)

    def test_wrong_actor_query_original_never_publishes_or_becomes_primary_effect(self):
        d=CanonicalSceneDomain(self);d.actor.fault=lambda packet:packet.update(requestId='ios-'+'e'*32)
        with d.owner()as owner:
            with self.assertRaises(NativeUIError):owner.acquire(TICKET)
        self.assertEqual([],d.posts);self.assertEqual(0,d.primary.capture.capture_count);self.assertEqual(1,len(d.actor.queries))

    def test_actual_saved_old_actor_original_cannot_receive_a_new_publication_clock(self):
        d=CanonicalSceneDomain(self)
        with d.owner()as owner:
            witness,reference=self.original(owner);original=deepcopy(witness.previous)
            d.primary.capture.sleep(2)
            with self.assertRaises(NativeUIError):owner.publication.publish(1)
            self.assertEqual(original,witness.store.read())
        self.assertEqual([],d.posts);self.assertEqual(1,len(d.actor.queries))

    def test_foreign_reference_and_proxy_mapping_are_rejected_by_real_historical_owner(self):
        d=CanonicalSceneDomain(self)
        with d.owner()as owner:
            witness,reference=self.original(owner)
            other=owner.actors.owner(2,historical=False);other.acquire(TICKET)
            wrong=dict(reference,ownerSha256=other.original()['ownerSha256'])
            with self.assertRaises(NativeUIError):owner.publication.validate_original(wrong)
            class Proxy(dict):pass
            with self.assertRaises(NativeUIError):owner.publication.validate_original(Proxy(reference))
        self.assertEqual([],d.posts)

    def test_same_bytes_replaced_original_frame_inode_is_not_rebound(self):
        d=CanonicalSceneDomain(self)
        with d.owner()as owner:
            witness,reference=self.original(owner);child=witness.child(historical=True);frames=child.files()
            path=frames.path(frames.expand(child.state['proof']));raw=path.read_bytes();old=path.stat()
            temporary=path.with_name(path.name+'.counter-replacement');temporary.write_bytes(raw);temporary.chmod(0o600);os.replace(temporary,path)
            self.assertNotEqual(old.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):owner.publication.validate_original(reference)
        self.assertEqual([],d.posts)

    def test_current_process_or_source_binding_mismatch_blocks_before_any_sample(self):
        d=CanonicalSceneDomain(self)
        with d.owner()as owner:
            self.original(owner);sources=owner.actors.sources
            generation=sources['binding']['generation'];sources['binding']['generation']=generation+1
            try:
                with self.assertRaises(NativeUIError):owner.publication.publish(1)
            finally:sources['binding']['generation']=generation
            process=sources['observer'].process;pid=process['pid'];process['pid']=pid+1
            try:
                with self.assertRaises(NativeUIError):owner.publication.publish(1)
            finally:process['pid']=pid
        self.assertEqual([],d.posts);self.assertEqual(1,len(d.actor.queries))

    def test_lost_real_journal_acceptance_return_recovers_receipt_without_requery_or_post_replay(self):
        d=CanonicalSceneDomain(self);d.lose_post=True
        with d.owner()as owner:
            with self.assertRaises(OSError):owner.acquire(TICKET)
            self.assertEqual('before-issued',owner.state['phase'])
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.actor.queries))
        with d.owner()as owner:self.assertTrue(owner.acquire(TICKET)['canonicalActorScenePublicationEstablished'])
        self.assertEqual(2,len(d.posts));self.assertEqual(2,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)

    def test_ignored_sample_ack_remains_issued_and_never_replays_original_post(self):
        d=CanonicalSceneDomain(self);d.drop_post=True
        with d.owner()as owner:
            with self.assertRaises(PublicationPending):owner.acquire(TICKET)
            self.assertEqual('issued',owner.publication.publisher.state['pending']['phase'])
        with d.owner()as owner:
            with self.assertRaises(PublicationPending):owner.acquire(TICKET)
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.actor.queries));self.assertEqual(0,d.primary.capture.capture_count)

    def test_default_ui_journal_refuses_scene_family_without_explicit_optin(self):
        d=CanonicalSceneDomain(self,enabled=False)
        with d.owner()as owner:
            with self.assertRaises(ValueError):owner.acquire(TICKET)
        self.assertEqual([],d.journal.snapshot(RUN)['entries']);self.assertEqual(0,d.primary.capture.capture_count)
