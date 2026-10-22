"""Whole actor cleanup with actual original stores and modeled native SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import pointer_state
from ios.adapters.create_retirement import CreateRetirement
from ios.self_tests import test_ios_create_actor_facts as actor_fixture
from ios.self_tests import test_ios_pointer_state as pointer_fixture
from ios.self_tests.test_ios_create_work import packet as default_work


class CreateRetirementTests(unittest.TestCase):
    def setUp(self):
        self.h=actor_fixture.CreateActorFactsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.native=pointer_fixture.NativePointerBoundary();sdk=self.h.peer_h.sdk
        domain_original=sdk.original
        def original_with_membership(name):
            value=json.loads(domain_original(name))
            if name=='domain':
                scripts=value['source']['scriptOriginal']['source']
                edit=default_work()['source']['roles'][0]
                scripts['engines']=[dict(url=edit['manager']['url'],running=True,stopping=False,finished=False,code=deepcopy(edit['code']),
                    required=dict(instance=edit['manager']['instance'],sequence=0,modules=[]))]
                scripts.update(sourceIdentityVersion=1,membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[deepcopy(edit['manager'])]))
            return json.dumps(value)
        sdk.original=original_with_membership
        def tick():self.native.now=sdk.tick();return self.native.now
        self.native.tick=tick;self.native.mono=lambda:sdk.clock
        def original():
            value=json.loads(self.native.original());value['processId']=43;return json.dumps(value)
        self.pointer=pointer_state.IOSPointerState(self.native.send,original,sdk.tick,lambda:True,43,monotonic=lambda:sdk.clock,sleep=sdk.sleep)
    def owner(self,facts):
        sdk=self.h.peer_h.sdk
        return CreateRetirement(PrivateFeatureState(self.h.peer_h.root/'ios-create-actor-retirement.json'),self.h.peer,facts,self.pointer,sleep=sdk.sleep)
    def admitted(self):
        facts=self.h.facts();facts.capture();owner=self.owner(facts);owner.admit();self.h.phase('cleanup');return facts,owner
    def test_actual_independent_actor_full_scene_worker_pointer_and_three_second_original_quiet(self):
        with self.h.held():
            facts,owner=self.admitted();original=owner.cleanup('2'*32)
            measured=owner.validate_original(original);self.assertEqual([],measured['public']['resources'])
            self.assertEqual([],measured['public']['state']['objects']);self.assertFalse(measured['public']['state']['editor'])
            self.assertGreaterEqual(measured['retirement']['quiet']['hostBeforeLastMonotonic']-measured['retirement']['quiet']['hostAfterFirstMonotonic'],3)
            requests=deepcopy(self.native.requests);fresh=self.owner(facts)
            self.assertEqual(original,fresh.original());self.assertEqual(requests,self.native.requests)
            self.assertGreater(len(owner.state['quiet']),3)
    def test_real_pending_release_cannot_retire_even_when_contact_is_already_gone(self):
        with self.h.held():
            _,owner=self.admitted();self.native.touch('touch-begin')
            def actual_pending_handler():
                self.assertEqual({},self.native.contacts);self.assertEqual(1,len(self.native.pending));self.assertFalse(self.native.world_tap)
                with self.assertRaises(NativeUIError):owner.cleanup('2'*32)
                self.assertNotEqual('retired',owner.state['phase']);self.assertTrue(owner.state['records'])
                return True
            self.native.touch('touch-end',handler=actual_pending_handler)
            original=owner.cleanup('2'*32);self.assertEqual([],owner.validate_original(original)['public']['resources'])
    def test_unknown_initial_pointer_history_and_foreign_actual_scene_stay_owned(self):
        with self.h.held():
            facts=self.h.facts();facts.capture();owner=self.owner(facts);self.native.started=False
            with self.assertRaises(NativeUIError):owner.admit()
            self.assertEqual('new',owner.state['phase'])
    def test_actual_record_replacement_is_rejected_after_warm_success_without_new_native_input(self):
        with self.h.held():
            _,owner=self.admitted();original=owner.cleanup('2'*32);owner.validate_original(original)
            requests=deepcopy(self.native.requests);ref=owner.state['records'][owner.state['quiet'][0]-1]
            carrier=owner.record_store(ref['index']);raw=carrier.read();raw['role']='primary';carrier.path.write_text(json.dumps(raw))
            with self.assertRaises(NativeUIError):owner.validate_original(original)
            self.assertEqual(requests,self.native.requests)
    def test_transient_entity_seen_only_by_actual_peer_source_still_requires_positive_weak_expiry(self):
        with self.h.held():
            _,owner=self.admitted();row=self.h.peer_product.entity('Model');row['name']='e2e-'+owner.run+'-model'
            self.h.peer_product.value['source']['entities']=[row];owner.source.capture('unpublished-resource')
            self.h.peer_product.value['source']['entities']=[]
            owner.state.update(ticket='2'*32,phase='cleaning');owner.save();frame=owner.capture('quiet')
            baseline=owner.frame(owner.state['baseline'])
            self.assertIn(row['id'],owner.responsibility_ids(frame,baseline));self.assertEqual([],owner.owned_ids(frame['components']))
            with self.assertRaises(NativeUIError):owner.drained(frame,baseline)

    def test_repeated_cleanup_reads_new_actual_originals_without_replaying_input_and_freezes_without_sdk(self):
        with self.h.held():
            facts,owner=self.admitted();first=owner.cleanup('2'*32);a=owner.validate_original(first)
            second=owner.cleanup('2'*32);b=owner.validate_original(second)
            self.assertGreater(b['public']['sequence'],a['public']['sequence'])
            self.assertGreaterEqual(b['acquisition']['hostBeforeEpochMs'],a['acquisition']['hostAfterEpochMs'])
            frozen=owner.frozen();requests=deepcopy(self.native.requests)
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical final validation touched a native SDK')
            for source in (frozen.source,frozen.history.primary):
                source.guard=forbidden
                for reader in source.readers.values():reader.read=forbidden
            self.assertEqual(b,frozen.validate_original(second));self.assertEqual(requests,self.native.requests)
            reference=frozen.state['records'][-1];component=frozen.frame(reference)['components']['history']
            carrier=PrivateFeatureState(frozen.store.path.with_name('ios-create-actor-retirement-component-'+component['sha256']+'.json'))
            packet=carrier.read();packet['role']='primary';carrier.path.write_text(json.dumps(packet))
            with self.assertRaises(NativeUIError):frozen.validate_original(second)
            self.assertEqual(requests,self.native.requests)


if __name__=='__main__':unittest.main()
