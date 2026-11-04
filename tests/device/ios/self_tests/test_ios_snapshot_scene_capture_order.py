"""Prospective actual WAL/normal-input/independent-original order counters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters import feature_observation
from ios.adapters.snapshot_scene_capture_order import SnapshotSceneCaptureOrder
from ios.adapters.snapshot_scene_witness import SnapshotScenePending
from ios.self_tests.snapshot_scene_order_domain import OrderedSceneDomain,RUN,TICKET


class SnapshotSceneCaptureOrderTests(unittest.TestCase):
    def test_genuine_before_normal_capture_after_order_and_historical_reopen_without_transport_or_writes(self):
        d=OrderedSceneDomain(self)
        with d.owner() as owner:
            proof=owner.acquire(TICKET)
            self.assertTrue(proof['actorBeforeCaptureAfterOriginalOrderEstablished'])
            self.assertTrue(proof['actualIndependentActorSceneInputsAgree'])
            self.assertTrue(proof['canonicalActorPublicationRequired'] and proof['actorRenderedPixelsRequired'])
            self.assertFalse(proof['wholeQualified']);self.assertEqual(1,d.primary.capture.capture_count)
            self.assertEqual(2,len(d.actor.queries));self.assertEqual(1,len(d.frame_events))
            scope=(owner.store,owner.lock,owner.binding,owner.run,owner.page.fixture_url,owner.actors.root,owner.actors.lock,owner.actors.binding)
            calls=(len(d.actor.queries),len(d.primary.provenance_queries),d.actor.ctx.native.sequence,d.primary.ctx.native.sequence)
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical order proof attempted transport/write')
            with patch.object(feature_observation,'post_request',forbidden),patch.object(PrivateFeatureState,'write',side_effect=forbidden):
                archived=SnapshotSceneCaptureOrder.archive(*scope,epoch_ms=d.primary.capture.epoch,monotonic=d.primary.capture.mono)
                self.assertEqual(proof,archived.proof())
            self.assertEqual(calls,(len(d.actor.queries),len(d.primary.provenance_queries),d.actor.ctx.native.sequence,d.primary.ctx.native.sequence))

    def test_lost_normal_capture_return_recovers_original_input_without_second_capture_or_new_before(self):
        d=OrderedSceneDomain(self);d.primary.capture.lost=True
        with d.owner() as owner:
            with self.assertRaises(OSError):owner.acquire(TICKET)
            self.assertEqual('capture-issued',owner.state['phase'])
            original_before=deepcopy(owner.state['before']);started=deepcopy(owner.state['started'])
        d.primary.capture.lost=False
        with d.owner() as owner:
            # Recovery's real retained input query advances the lower input
            # clock. The already completed render event stays an old original;
            # it cannot become fresh merely because capture delivery recovered.
            with self.assertRaises(SnapshotScenePending):owner.acquire(TICKET)
            self.assertEqual('after-issued',owner.state['phase'])
            self.assertEqual(started,owner.state['started']);self.assertEqual(original_before,owner.state['before'])
            old=deepcopy(owner.state['attempts'][-1]);self.assertEqual('known-old',old['mode'])
            self.assertEqual(2,old['index']);old_actor=owner.original_actor(2,old['original'])
            frame=old_actor['nativeOriginal']['packet']['source']['frame']
            self.assertLess(frame['consumedEpochMs'],old_actor['nativeOriginal']['acquisition']['nativeBefore']['capturedEpochMs'])
            captured=deepcopy(owner.state['capture']);call_before=deepcopy(owner.state['callBefore']);call_after=deepcopy(owner.state['callAfter'])
        self.assertEqual(1,d.primary.capture.capture_count);self.assertEqual(2,len(d.actor.queries))
        self.assertEqual(1,len(d.frame_events))
        # A distinct declared lower-renderer event, between owner invocations.
        # It updates no saved packet and is not emitted by a source/query read.
        d.render_actor_frame()
        with d.owner() as owner:
            proof=owner.acquire(TICKET);self.assertTrue(proof['actorBeforeCaptureAfterOriginalOrderEstablished'])
            self.assertEqual([2,3],[row['index']for row in owner.state['attempts']])
            self.assertEqual(old,owner.state['attempts'][0]);self.assertEqual(old_actor,owner.original_actor(2,old['original']))
            self.assertEqual('accepted',owner.state['attempts'][1]['mode'])
            self.assertEqual(original_before,owner.state['before']);self.assertEqual(started,owner.state['started'])
            self.assertEqual(captured,owner.state['capture']);self.assertEqual(call_before,owner.state['callBefore']);self.assertEqual(call_after,owner.state['callAfter'])
        self.assertEqual(1,d.primary.capture.capture_count);self.assertEqual(3,len(d.actor.queries));self.assertEqual(2,len(d.frame_events))

    def test_saved_actor_before_lost_parent_cas_reconciles_same_original_without_new_before_query(self):
        d=OrderedSceneDomain(self)
        with d.owner() as owner:
            write=owner.store.write
            def lost(value,previous):
                if owner.state['phase']=='before-saved':raise OSError('Completed Actor-before saved; parent CAS lost')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=lost),self.assertRaises(OSError):owner.acquire(TICKET)
        self.assertEqual(1,len(d.actor.queries))
        with d.owner() as owner:owner.acquire(TICKET)
        self.assertEqual(2,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)

    def test_completed_normal_capture_lost_wrapper_cas_reopens_the_same_capture_without_another_input(self):
        d=OrderedSceneDomain(self)
        with d.owner() as owner:
            write=owner.store.write
            def lost(value,previous):
                if owner.state['phase']=='capture-saved':raise OSError('Completed normal capture retained; wrapper CAS lost')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=lost),self.assertRaises(OSError):owner.acquire(TICKET)
        with d.owner() as owner:owner.acquire(TICKET)
        self.assertEqual(1,d.primary.capture.capture_count);self.assertEqual(2,len(d.actor.queries))

    def test_known_complete_old_after_frame_allows_only_a_separate_new_read_after_real_model_render_event(self):
        d=OrderedSceneDomain(self);d.emit_after_capture=False
        with d.owner() as owner:
            with self.assertRaises(SnapshotScenePending):owner.acquire(TICKET)
            self.assertEqual('known-old',owner.state['attempts'][-1]['mode'])
            old=deepcopy(owner.state['attempts'][-1]);self.assertEqual(2,len(d.actor.queries))
        # Independent declared render event between invocations. It changes the
        # native model producer, never an already retained packet or its clocks.
        d.render_actor_frame()
        with d.owner() as owner:
            result=owner.acquire(TICKET);self.assertTrue(result['actorBeforeCaptureAfterOriginalOrderEstablished'])
            self.assertEqual(old,owner.state['attempts'][0]);self.assertEqual([2,3],[row['index']for row in owner.state['attempts']])
        self.assertEqual(3,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)

    def test_unknown_actor_after_without_original_cannot_allocate_another_read_or_resend(self):
        d=OrderedSceneDomain(self);d.lose_after=True
        with d.owner() as owner:
            with self.assertRaises(OSError):owner.acquire(TICKET)
            self.assertEqual('after-issued',owner.state['phase'])
        d.actor.lose=False;d.actor.raw=None
        with d.owner() as owner:
            with self.assertRaises(NativeUIError):owner.acquire(TICKET)
            self.assertEqual(1,len(owner.state['attempts']));self.assertEqual('issued',owner.state['attempts'][0]['mode'])
        self.assertEqual(2,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)

    def test_existing_completed_capture_cannot_receive_retrospective_actor_before(self):
        d=OrderedSceneDomain(self);d.primary.prepare()
        before=len(d.actor.queries);captures=d.primary.capture.capture_count
        with self.assertRaises(NativeUIError):
            with d.owner():pass
        self.assertEqual(before,len(d.actor.queries));self.assertEqual(captures,d.primary.capture.capture_count)

    def test_original_persisted_deadline_never_rebases_for_a_known_old_after_or_unknown_resume(self):
        d=OrderedSceneDomain(self);d.emit_after_capture=False
        with d.owner() as owner:
            with self.assertRaises(SnapshotScenePending):owner.acquire(TICKET)
            start=deepcopy(owner.state['started'])
        count=len(d.actor.queries);d.primary.capture.sleep(25)
        with d.owner() as owner:
            with self.assertRaises(NativeUIError):owner.acquire(TICKET)
            self.assertEqual(start,owner.state['started'])
        self.assertEqual(count,len(d.actor.queries));self.assertEqual(1,d.primary.capture.capture_count)


    def test_real_later_primary_native_original_cannot_be_reheadered_as_the_pre_capture_anchor(self):
        d=OrderedSceneDomain(self)
        with d.owner() as owner:
            owner.acquire(TICKET)
            # Produce a genuine NEW Page/native original after capture; no
            # fabricated Frame/DTO/native epoch or stored child body is used.
            late=owner.page.observe();actual=owner.page.original(late)
            saved=owner.store.read();state=unpack(saved['payload'])[0]
            state['primaryBeforeCount']=late['index']-1;state['primaryBefore']=deepcopy(late)
            changed=dict(saved,payload=pack([state]));owner.store.write(changed,saved)
            scope=(owner.store,owner.lock,owner.binding,owner.run,owner.page.fixture_url,owner.actors.root,owner.actors.lock,owner.actors.binding)
            with self.assertRaises(NativeUIError):
                archived=SnapshotSceneCaptureOrder.archive(*scope,epoch_ms=d.primary.capture.epoch,monotonic=d.primary.capture.mono)
                archived.proof()
            self.assertEqual(1,d.primary.capture.capture_count)


if __name__=='__main__':unittest.main()
