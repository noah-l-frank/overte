"""Publisher control-flow and readonly scope seams; original decoder modeled.

Actual Final graph qualification is separate. These tests supply no Final,
product, quiet, cleanup, timing or complete Avatar result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import unpack
from ios.adapters import avatar_final
from ios.adapters.avatar_witness_publisher import AvatarWitnessPublisher
from ios.self_tests import test_ios_avatar_terminal_publisher_reuse as transfer_fixture


class AvatarPublisherReadonlySegmentTests(unittest.TestCase):
    def assert_outside(self):
        self.assertIsNone(avatar_final._ROUND.get())
        self.assertFalse(avatar_final._PREFIX_ROUND.get())

    def carrier(self):
        # Reuse the existing explicitly modeled protocol fixture, whose own
        # mkdtemp roots retain all journals and only stop its loopback server.
        case=transfer_fixture.AvatarTerminalPublisherReuseTests();self.addCleanup(case.doCleanups)
        case.setUp();return case

    def metadata_owner(self,cls):
        owner=object.__new__(cls);owner.area='avatar-people';owner.state=dict(records=[dict(ordinal=1)],pending=None)
        owner.bound=lambda:None;owner.resolve=lambda:True
        owner.original=lambda _value:({},{});return owner

    def test_nonempty_latest_branch_retains_original_failure_for_none_load_override(self):
        for cls in (PhaseWitnessPublisher,AvatarWitnessPublisher):
            with self.subTest(cls=cls.__name__):
                owner=self.metadata_owner(cls);writes=[]
                owner.load=lambda _reference:None;owner.save=lambda:writes.append(True)
                with self.assertRaises(TypeError):owner.publish(dict(metadataOnly=True))
                self.assertEqual([],writes);self.assertIsNone(owner.state['pending']);self.assert_outside()

    def test_load_callback_mutation_does_not_reevaluate_pending_or_record_branches(self):
        for cls in (PhaseWitnessPublisher,AvatarWitnessPublisher):
            with self.subTest(cls=cls.__name__):
                owner=self.metadata_owner(cls);events=[];original=dict(metadataOnly=True)
                owner.bound=lambda:events.append('bound');owner.resolve=lambda:events.append('resolve')
                def current(value):events.append('original');self.assertEqual(original,value);return {},{}
                def latest(reference):
                    events.append('load');self.assertEqual(dict(ordinal=1),reference)
                    owner.state['records'].clear();owner.state['pending']=dict(changedByLoad=True)
                    return dict(mode='published',intent=dict(original=original,body=dict(actorSequence=7)))
                owner.original=current;owner.load=latest
                owner.save=lambda:self.fail('The original duplicate branch must return before planning or writing')
                self.assertEqual(7,owner.publish(original));self.assertEqual(['bound','resolve','original','load'],events)
                self.assertEqual([],owner.state['records']);self.assertEqual(dict(changedByLoad=True),owner.state['pending'])
                self.assert_outside()

    def test_scope_closes_before_actual_cas_phase_read_and_http(self):
        case=self.carrier();f=case.f;events=[]
        with f.lock.held():
            publisher=case.publisher();original=f.original();write=PrivateFeatureState.write
            phase_read=f.phase.read;request=f.actor.request
            def writing(store,value,previous):
                self.assert_outside();events.append('CAS');return write(store,value,previous)
            def phase(*args,**kwargs):
                self.assert_outside();events.append('phase');return phase_read(*args,**kwargs)
            def http(path,*args,**kwargs):
                self.assert_outside();events.append('POST' if path.endswith('/samples') else 'HTTP')
                return request(path,*args,**kwargs)
            with (patch.object(PrivateFeatureState,'write',writing),patch.object(f.phase,'read',phase),
                  patch.object(f.actor,'request',http)):
                self.assertEqual(1,publisher.publish(original))
            self.assertGreater(events.count('CAS'),0);self.assertGreater(events.count('phase'),0)
            self.assertEqual(1,events.count('POST'));self.assert_outside()

    def test_exception_in_new_original_or_latest_read_resets_both_rounds(self):
        class OriginalReadFailure(Exception):pass
        for fault in ('new-original','latest-receipt'):
            with self.subTest(fault=fault):
                owner=self.metadata_owner(AvatarWitnessPublisher)
                def broken(_value):raise OriginalReadFailure(fault)
                owner.load=broken
                if fault=='new-original':owner.original=broken
                with self.assertRaises(OriginalReadFailure):owner.publication_original(dict(metadataOnly=True))
                self.assert_outside()
                owner.state['pending']=dict(phase='planned',original=dict(metadataOnly=True))
                owner.intent=broken
                with self.assertRaises(OriginalReadFailure):owner.publication_pending(dict(metadataOnly=True))
                self.assert_outside()

    def test_actual_lost_post_receipt_resolves_without_replaying_issued_input(self):
        case=self.carrier();f=case.f
        with f.lock.held():
            publisher=case.publisher();original=f.original();sent,request=f.posts('lost-after')
            with patch.object(f.actor,'request',side_effect=request),self.assertRaises(OSError):publisher.publish(original)
            self.assertEqual(1,len(sent));self.assertEqual('issued',publisher.state['pending']['phase'])
            pending=deepcopy(publisher.state['pending']);again,request=f.posts('normal')
            with patch.object(f.actor,'request',side_effect=request):
                recovered=case.publisher();self.assertTrue(recovered.resolve())
            self.assertEqual([],again);self.assertIsNone(recovered.state['pending'])
            record=recovered.load(recovered.state['records'][0]);self.assertEqual(pending,record['intent'])
            self.assertEqual('published',record['mode']);self.assert_outside()

    def test_both_readonly_segments_run_each_original_callback_in_independent_scopes(self):
        case=self.carrier();f=case.f;events=[]
        with f.lock.held():
            publisher=case.publisher();self.assertEqual(1,publisher.publish(f.original()))
            original=f.original(2);validate=publisher.validate_original
            def callback(value):
                events.append((avatar_final._ROUND.get(),avatar_final._PREFIX_ROUND.get(),deepcopy(value)))
                return validate(value)
            publisher.validate_original=callback
            first=publisher.publication_original(original)
            self.assertTrue(first[2]);self.assertTrue(first[3]);self.assertEqual(2,len(events))
            first_scope=events[0][0];self.assertIsNotNone(first_scope)
            self.assertTrue(all(scope is first_scope and prefix for scope,prefix,_value in events));self.assert_outside()
            # Produce an actual durable planned intent through the ordinary
            # publisher save, then stop at the first live phase read. No POST.
            with patch.object(f.phase,'read',side_effect=OSError('Declared unavailable phase before issue')):
                with self.assertRaises(OSError):publisher.publish(original)
            self.assertEqual('planned',publisher.state['pending']['phase'])
            saved=publisher.store.read();self.assertEqual('planned',unpack(saved['payload'])[0]['pending']['phase'])
            events.clear();pending,floor=publisher.publication_pending(original)
            self.assertEqual('planned',pending['phase']);self.assertIsNotNone(floor);self.assertEqual(2,len(events))
            second_scope=events[0][0];self.assertIsNotNone(second_scope);self.assertIsNot(first_scope,second_scope)
            self.assertTrue(all(scope is second_scope and prefix for scope,prefix,_value in events));self.assert_outside()
            self.assertEqual(saved,publisher.store.read())


if __name__=='__main__':unittest.main()
