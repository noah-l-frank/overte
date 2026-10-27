"""Actual immutable Actor originals reused only in one guarded operation.

Script/Node, private original files and ordinary input execute; native/Qt/WK/
SDK and clocks remain explicit models. No publication or terminal is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement,_ORIGINALS
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_actor_fixture import IndependentActor
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebActorFrameProofTests(unittest.TestCase):
    def setUp(self):
        self.whole=whole=ComposedWorldWeb(wall_clock=True,use_whole_snapshot=True);self.addCleanup(whole.close)
        self.actor=actor=IndependentActor(whole);self.addCleanup(actor.close);sdk=whole.sdk
        self.observer=observer=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,
            sdk.origins,lambda:True,role='actor',peer=actor.peer)
        with scope(lambda:sdk.time):observer.capture()
        before=actor.primary.state['records'][0];actions=whole.actions()
        with scope(lambda:sdk.time):actions.act(sdk.activate('open',{}))
        entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
        actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
        admission=actor.primary.capture('independent-actor-admission');observer.lease=WorldWebLease(whole.scope,actor.primary,before,admission)
        with scope(lambda:sdk.time):observer.capture()
        sdk.activate('cleanup',{});whole.scope.cleanup()
        self.owner=owner=WorldWebActorRetirement(PrivateFeatureState(actor.root/'ios-world-web-actor-retirement.json'),observer,sleep=sdk.sleep)
        with scope(lambda:sdk.time),owner.original_round():owner.cleanup(sdk.ticket)
        self.reference=deepcopy(owner.state['quiet'][-1])

    def test_same_actual_operation_reuses_predicate_copies_outward_and_next_operation_rechecks(self):
        owner=self.owner;queries=deepcopy([self.whole.sdk.counts,self.actor.sdk.counts])
        with patch.object(owner,'_measure',wraps=owner._measure) as measured:
            with owner.original_round():
                expected=owner.measure(self.reference);changed=owner.measure(self.reference)
                changed[0]['ticket']='outward-only';self.assertEqual(expected,owner.measure(self.reference))
                self.assertEqual(1,measured.call_count)
            with owner.original_round():self.assertEqual(expected,owner.measure(self.reference))
            self.assertEqual(2,measured.call_count)
        self.assertEqual(queries,[self.whole.sdk.counts,self.actor.sdk.counts])

    def test_new_actual_source_append_preserves_old_proof_but_new_original_requires_its_own_predicate(self):
        owner=self.owner
        with owner.original_round(),patch.object(owner,'_measure',wraps=owner._measure) as measured:
            expected=owner.measure(self.reference);self.assertEqual(1,measured.call_count)
            newer,_public=self.observer.capture()
            self.assertEqual(expected,owner.measure(self.reference));self.assertEqual(1,measured.call_count)
            owner.measure(newer);self.assertEqual(2,measured.call_count)

    def test_new_read_census_and_changed_parser_cannot_inherit_a_success(self):
        owner=self.owner
        with owner.original_round(),patch.object(owner,'_measure',wraps=owner._measure) as measured:
            expected=owner.measure(self.reference)
            with read_scope(fresh=True) as reads:
                self.assertEqual(expected,owner.measure(self.reference));self.assertTrue(reads)
            self.assertEqual(2,measured.call_count)
            with patch.object(owner,'native_frames',side_effect=NativeUIError('Declared changed native predicate')):
                with self.assertRaises(NativeUIError):owner.measure(self.reference)
            with patch.object(owner,'entry',side_effect=NativeUIError('Declared changed original entry parser')):
                with self.assertRaises(NativeUIError):owner.measure(self.reference)

    def test_full_private_proof_table_falls_back_to_actual_validation_without_expanding_it(self):
        owner=self.owner
        with owner.original_round(),patch.object(owner,'_measure',wraps=owner._measure) as measured:
            proofs=_ORIGINALS.get()['frames'];proofs.update({('unrelated-private-key',index):None for index in range(256)})
            expected=owner.measure(self.reference);self.assertEqual(expected,owner.measure(self.reference))
            self.assertEqual(2,measured.call_count);self.assertEqual(256,len(proofs))

    def test_changed_cleanup_ticket_cannot_reuse_the_original_native_outcome(self):
        owner=self.owner;ticket=owner.state['ticket']
        with owner.original_round():
            owner.measure(self.reference);owner.state['ticket']='f'*32
            try:
                with self.assertRaises(NativeUIError):owner.measure(self.reference)
            finally:owner.state['ticket']=ticket

    def test_same_bytes_new_original_inode_refuses_before_any_cached_success(self):
        owner=self.owner;source=self.actor.primary
        with self.assertRaises(NativeUIError),owner.original_round():
            owner.measure(self.reference)
            frame=source.frame(source.state['records'][-1]);path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0]
            replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
            owner.measure(self.reference)


if __name__=='__main__':unittest.main()
