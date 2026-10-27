"""Original canonical source factory in an actual independent host process."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from self_tests import test_lifecycle_independent_actor as actor_fixture
from self_tests.test_vr_graphics_subject import framework_source
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey import source_bundles
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
import test_normal_scripts as canonical_fixture


class LifecycleActorFactoryTests(unittest.TestCase):
    def stage(self,*,framework=True):
        stage=actor_fixture.LifecycleIndependentActorTests();stage.setUp();self.addCleanup(stage.doCleanups)
        config=stage.configuration.read();stage.configuration.write(dict(config,canonicalFactory=True),config)
        framework_source(stage.products.subject)
        pose=stage.products.subject.source['avatarPose']
        stage.native.drive.source.update(feetPosition=deepcopy(pose['feetPosition']),
            bodyPosition=deepcopy(pose['feetPosition']),orientation=deepcopy(pose['orientation']),modelScale=pose['modelScale'])
        if not framework:
            stage.products.subject.source.update(subjectVersion=2)
            stage.products.subject.source.pop('framework');stage.products.subject.source.pop('hmd')
        stage.start()
        # Exact current candidate/process metadata from the child adapter's
        # original native/OS fixture, before its first target-source query.
        # No measurement or Parent live owner crosses this boundary.
        stage.editor.binding=deepcopy(stage.waiting['binding'])
        self.assertEqual([],stage.native_calls())
        return stage

    def test_actual_independent_canonical_factory_reads_six_original_target_sources(self):
        stage=self.stage()
        result=stage.sample();self.assertEqual('none',result['facts']['editor'])
        self.assertEqual(0,result['facts']['generation']);self.assertEqual([],stage.editor.transport.envelopes)
        root=Path(stage.waiting['root']);original=PrivateFeatureState(root/'lifecycle-actor-originals.json').read()
        self.assertEqual(stage.waiting['binding'],original['binding']);self.assertEqual(1,len(original['records']))
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],stage.native_calls())
        self.assertFalse((root/'lifecycle-world-owner.json').exists())
        self.assertFalse((root/'state.json').exists()) # No Default Script manager sample.
        stage.command('exit');stage.worker.wait(timeout=10);self.assertEqual(0,stage.worker.returncode)
        absence=stage.process.require_absent();stage.process.final_absence(absence)
        print('Actual canonical Actor factory originals: '+str(root),flush=True)

    def test_foreign_factory_fingerprint_refuses_before_any_target_source_query(self):
        stage=self.stage();stage.failed_worker('sample-foreign-factory-fingerprint')
        self.assertEqual([],stage.native_calls());self.assertEqual([],stage.editor.transport.envelopes)
        self.assertIsNone(PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json').read())

    def test_original_subject2_is_retained_and_refused_by_unchanged_framework_requirement(self):
        stage=self.stage(framework=False);stage.failed_worker()
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],stage.native_calls())
        self.assertEqual([],stage.client.observe()['entries']);self.assertEqual([],stage.editor.transport.envelopes)
        store=PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json');original=store.read()
        self.assertEqual([],original['records']);self.assertIsNotNone(original['pending']['subject'])
        keys=('picoLifecycleActorSourceVersion','runId','binding','role','stage','producerHostProcessIdentity',
            'parentHostProcessIdentity','fixtureUrl')
        history=ChatSourceChunks(store,{key:original[key] for key in keys});history.load(original['chunks'])
        bundle,_=source_bundles.original(history,original['chunks'],original['bundles'],original['pending']['subject'])
        self.assertEqual(2,decode(bundle['subject']['raw'])['source']['subjectVersion'])

    def test_same_host_factory_caller_refuses_before_candidate_or_native_access(self):
        fixture=canonical_fixture.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,target=fixture.instance,fixture.native.target;calls=[]
        from self_tests.test_pico_lifecycle_world import BINDING,RUN
        phases=PhaseFixtureReader(Client('http://controlled.invalid/feature-fixture/v1','r'*64),RUN,'lifecycle-input')
        def unexpected(*_args,**_kwargs):calls.append(True);raise AssertionError('Unexpected caller reached candidate/native')
        with patch.object(adapter,'_installation',unexpected),patch.object(adapter,'_native_feature_observer',unexpected):
            with self.assertRaises(ValueError):adapter._lifecycle_actor_source(target,RUN,binding=BINDING|dict(generation=0),
                phases=phases,parent_host=host_identity())
        self.assertEqual([],calls);self.assertEqual([],fixture.native.inputs);self.assertEqual([],fixture.native.controllers)


if __name__=='__main__':unittest.main()
