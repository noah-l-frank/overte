"""Prospective typed Scene/Actor joins through genuine original host owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters import feature_observation,snapshot_scene,snapshot_provenance
from ios.adapters.snapshot_scene_review_join import SnapshotSceneReviewJoin
from ios.adapters.snapshot_provenance_packet import SnapshotProvenancePacket
from ios.self_tests.snapshot_scene_domain import SceneCaptureDomain,SceneActorDomain,RUN,TICKET


class SnapshotSceneReviewJoinTests(unittest.TestCase):
    def domains(self,**kwargs):
        d=SceneCaptureDomain(self);actor=SceneActorDomain(self,d,**kwargs)
        # Both independent raw scene producers exist before normal input.
        return d,actor

    def prepared(self,d):
        d.prepare()
        with d.owner() as page:
            capture=d.runtime.capture_child(page);capture.provenance()
            child=capture.history('provenance',1)
            return (child.store,child.binding,child.run,child.role,child.index)

    def packet(self,scope,lock):
        store,binding,run,role,index=scope
        return SnapshotProvenancePacket.history(store,lock,binding,run,role,index)

    def test_actual_scene_camera_crop_callback_png_review_and_independent_actor_original_join_then_transport_free_reopen(self):
        d,a=self.domains();scope=self.prepared(d)
        with d.review() as review,a.held() as actor:
            packet=self.packet(scope,review.lock)
            review.acquire(TICKET);original=actor.acquire(TICKET)
            joined=SnapshotSceneReviewJoin(review,packet,actor,original).proof()
            self.assertTrue(joined['sameOrdinaryFrameCameraCropCallbackPNGEstablished'])
            self.assertTrue(joined['independentActorOriginalSceneInputsAgree'])
            self.assertTrue(joined['canonicalActorPublicationRequired'] and joined['fullSceneAppearanceFidelityRequired'])
            self.assertFalse(joined['wholeQualified'])
            queries=len(a.queries);calls=(d.capture.capture_count,d.screen_calls,len(d.provenance_queries))
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical join attempted query/write')
            with patch.object(feature_observation,'post_request',forbidden),patch.object(PrivateFeatureState,'write',side_effect=forbidden):
                historical=a.owner(historical=True)
                self.assertEqual(original,historical.original())
                self.assertEqual(joined,SnapshotSceneReviewJoin(review,packet,historical,original).proof())
            self.assertEqual(queries,len(a.queries));self.assertEqual(calls,(d.capture.capture_count,d.screen_calls,len(d.provenance_queries)))

    def test_independent_actor_changed_actual_render_transform_cannot_agree_with_captured_scene(self):
        d,a=self.domains();a.scene_inputs['entities'][0]['renderTransform'][3]=.25;scope=self.prepared(d)
        with d.review() as review,a.held() as actor:
            packet=self.packet(scope,review.lock)
            review.acquire(TICKET);original=actor.acquire(TICKET)
            with self.assertRaises(NativeUIError):SnapshotSceneReviewJoin(review,packet,actor,original).proof()
        self.assertEqual(1,len(a.queries))

    def test_same_target_is_refused_even_with_separate_directories_and_scene_owner_files(self):
        d,a=self.domains(same_target=True);scope=self.prepared(d)
        with d.review() as review,a.held() as actor:
            packet=self.packet(scope,review.lock)
            review.acquire(TICKET);original=actor.acquire(TICKET)
            with self.assertRaises(NativeUIError):SnapshotSceneReviewJoin(review,packet,actor,original)

    def test_balanced_draws_complete_scene_and_callback_original_are_mandatory_not_import_epoch_or_count(self):
        d,a=self.domains();scope=self.prepared(d)
        with d.ctx.lock.held():
            value=self.packet(scope,d.ctx.lock).historical()['packet']
        raw=deepcopy(value)
        frame=raw['source']['captures'][0]['frame'];frame['scene']['entities'][0]['returned']=0
        with self.assertRaises(NativeUIError):snapshot_provenance.original(raw)
        frame['scene']['entities'][0]['returned']=1;frame['scene']['complete']=False
        with self.assertRaises(NativeUIError):snapshot_provenance.original(raw)
        del frame['scene']
        with self.assertRaises(NativeUIError):snapshot_provenance.original(raw)

    def test_lost_actor_query_return_reopens_the_same_actual_reply_without_second_native_query(self):
        d,a=self.domains();self.prepared(d);a.lose=True
        with a.held() as actor:
            with self.assertRaises(OSError):actor.acquire(TICKET)
        a.lose=False
        with a.held() as actor:
            original=actor.acquire(TICKET);self.assertTrue(actor.validate_original(original)['localOriginalPublicationEstablished'])
        self.assertEqual(1,len(a.queries))

    def test_saved_actor_packet_lost_parent_cas_adopts_original_without_query_or_clock_reissue(self):
        d,a=self.domains();self.prepared(d)
        with a.held() as actor:
            write=actor.store.write
            def lose(value,previous):
                if actor.state['phase']=='complete':raise OSError('Actual completed child retained; parent CAS lost')
                return write(value,previous)
            with patch.object(actor.store,'write',side_effect=lose),self.assertRaises(OSError):actor.acquire(TICKET)
        count=len(a.queries);native=a.ctx.native.sequence
        with a.held() as actor:actor.acquire(TICKET)
        self.assertEqual(count,len(a.queries));self.assertEqual(native,a.ctx.native.sequence)

    def test_same_bytes_foreign_actor_frame_inode_refuses_historical_witness(self):
        d,a=self.domains();self.prepared(d)
        with a.held() as actor:
            actor.acquire(TICKET);child=actor.child(historical=True);path=child.files().path(child.state['storage'])
            raw=path.read_bytes();old=path.stat().st_ino
            path.rename(path.with_name('retained-'+path.name));path.write_bytes(raw);path.chmod(0o600)
            self.assertNotEqual(old,path.stat().st_ino)
            with self.assertRaises(NativeUIError):a.owner(historical=True)

    def test_changed_recorded_actor_camera_or_phase_binding_refuses_actual_typed_join(self):
        d,a=self.domains();a.frame['camera']['position'][0]=.5;a.frame['worldFromCamera'][3]=.5
        scope=self.prepared(d)
        with d.review() as review,a.held() as actor:
            packet=self.packet(scope,review.lock)
            review.acquire(TICKET);original=actor.acquire(TICKET)
            with self.assertRaises(NativeUIError):SnapshotSceneReviewJoin(review,packet,actor,original).proof()
            changed=deepcopy(original);changed['owner']['fixtureUrl']='https://foreign.invalid/runs/'+RUN+'/'
            with self.assertRaises(NativeUIError):actor.validate_original(changed)


if __name__=='__main__':unittest.main()
