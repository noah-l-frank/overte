"""Existing owned coordinator boundaries before ordinary SDK teardown."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.create_finalization import finalize_existing
from ios.self_tests import test_ios_create_runtime as fixture
from ios.self_tests.test_ios_create_files import BINDING


class CreateFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CreateRuntimeTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.runtime=self.h.runtime;self.checked=[]
        self.runtime.adapter._retired_candidate_scope=lambda selector,scope:self.checked.append((selector,deepcopy(scope)))
    def coordinator(self):
        flow=self.runtime._create_feature('actor','a'*32,role='actor',client=self.h.client,settings=self.h.settings)
        with flow.held():
            flow.load();flow.state=dict(phase='ready',binding=BINDING|dict(sessionId='peer',targetFingerprint='a'*64),primaryBinding=BINDING,
                phaseInstance='b'*32,initialTicket='c'*32,actorAdmission=None,beforeImage=None,images=[],exports=[],retirement=None);flow.save()
        return flow
    def test_absent_ownership_requires_no_candidate_or_sdk(self):
        self.assertFalse(finalize_existing(self.runtime,'actor',None,None));self.assertEqual([],self.checked)
    def test_lost_fixed_owner_does_not_hide_retained_originals_pending_carriers_or_final_archives(self):
        flow=self.coordinator();actual=flow.store.read();flow.store.path.unlink()
        for name in ('ios-create-actor-sources.json','ios-create-actor-'+('a'*32)+'-final.json',
                     'phase-publication-create-'+('a'*32)+'-actor.json',
                     'phase-retirement-create-'+('a'*32)+'-actor.json','ios-create-pending.tmp'):
            # Retain actual coordinator bytes under an unqualified carrier
            # name. No carrier payload is interpreted as a cleanup proof.
            carrier=PrivateFeatureState(flow.store.path.with_name(name));carrier.write(actual,None)
            with self.subTest(name=name),self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',None,None)
            self.assertEqual(actual,carrier.read());carrier.path.unlink()
        self.assertEqual([],self.checked);self.assertFalse(finalize_existing(self.runtime,'actor',None,None))
    def test_explicit_artifact_root_without_coordinator_cannot_hide_create_final_carriers(self):
        settings={key:value for key,value in self.h.settings.items() if key!='primaryTarget'}
        settings.update(actorTarget='actor',rezAuthority=dict(controlUrl='http://127.0.0.1:43210/v1/create-rez',token='t'*64,
            domainId='00000000-0000-4000-8000-000000000001'))
        config=dict(iosFeatureAdapterVersion=3,areas=['create'],create=settings)
        carrier=PrivateFeatureState(self.h.root/'ios-create-final-unknown.json');carrier.write(dict(unqualified=True),None)
        with self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',config,None)
        self.assertEqual([],self.checked);self.assertEqual(dict(unqualified=True),carrier.read())
        carrier.path.unlink();self.assertFalse(finalize_existing(self.runtime,'actor',config,None))
    def test_actual_unfinished_actor_remains_owned_and_cannot_fall_through_to_sdk_delete(self):
        flow=self.coordinator();actual=flow.store.read()
        with self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',None,None)
        self.assertEqual(actual,flow.store.read());self.assertEqual(1,len(self.checked))
        self.assertNotIn('processIdentity',self.checked[0][1])
    def test_malformed_mutated_header_or_dual_role_refuses_before_candidate_access(self):
        flow=self.coordinator();actual=flow.store.read()
        for field,value in (('runId','wrong'),('role','primary'),('iosCreateFeatureVersion',True)):
            changed=dict(actual,**{field:value});flow.store.write(changed,actual)
            with self.subTest(field=field),self.assertRaises((NativeUIError,ValueError)):finalize_existing(self.runtime,'actor',None,None)
            flow.store.write(actual,changed)
        twin=PrivateFeatureState(flow.store.path.with_name('ios-create-primary-feature.json'));twin.write(actual,None)
        with self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',None,None)
        self.assertEqual([],self.checked)


if __name__=='__main__':unittest.main()
