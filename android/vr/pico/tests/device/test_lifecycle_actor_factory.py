"""Original canonical source factory in an actual independent host process."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_actor_originals import ActorOriginals
from self_tests import test_lifecycle_independent_actor as actor_fixture
from self_tests.test_vr_graphics_subject import framework_source
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey import source_bundles
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from feature_journeys.fixtures import context
from adapters.normal_ui import NativeUIError
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

    def create(self,stage):
        stage.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
        stage.editor.focused()

    def typing(self,stage):
        stage.client.activate(uuid.uuid4().hex,'type',dict(text=context(stage.run)['unicode']))

    def originals(self,stage):
        return PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json').read()

    def rejected_phase(self,stage):
        store=PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json')
        return ActorOriginals(store).last('phase-before')

    def test_canonical_actor_measures_normal_create_and_actual_ime_text_from_same_original_field(self):
        stage=self.stage()
        for _ in range(2):
            self.assertEqual('none',stage.sample()['facts']['editor']);stage.native.sleep(.25)
        self.create(stage)
        for _ in range(2):
            opened=stage.sample()['facts'];self.assertEqual(('create','',1,True,True),
                tuple(opened[key] for key in ('editor','text','generation','focused','keyboard')))
            stage.native.sleep(.25)
        before=deepcopy(stage.editor.owner.state)
        self.typing(stage);stage.editor.owner.type_create()
        for _ in range(2):
            typed=stage.sample()['facts'];self.assertEqual(context(stage.run)['unicode'],typed['text'])
            self.assertEqual(('create',1,True,True),tuple(typed[key] for key in ('editor','generation','focused','keyboard')))
            stage.native.sleep(.25)
        owner=stage.editor.owner.state
        self.assertEqual('typed',owner['phase']);self.assertEqual(before['originalId'],owner['originalId'])
        self.assertEqual(before['fieldObjects'],owner['fieldObjects'])
        self.assertEqual(len(before['inputs'])+1,len(owner['inputs']))
        self.assertTrue(all(row['consumed'] is not None for row in owner['inputs']))
        original=self.originals(stage);self.assertEqual(6,len(original['records']))
        self.assertEqual('delivered',original['publication']['phase'])
        self.assertEqual(['gesture','drive','ui','pending','feature','subject']*6,stage.native_calls())
        self.assertFalse((Path(stage.waiting['root'])/'lifecycle-world-owner.json').exists())
        self.assertEqual(1,len(stage.editor.transport.envelopes));self.assertEqual(2,len(stage.editor.field.calls))
        stage.command('exit');stage.worker.wait(timeout=10);self.assertEqual(0,stage.worker.returncode)
        absence=stage.process.require_absent();stage.process.final_absence(absence)
        print('Canonical Actor normal Create/Qt-IME originals: '+str(Path(stage.waiting['root'])),flush=True)

    def test_type_without_original_create_activation_refuses_before_any_new_source_query(self):
        stage=self.stage();stage.sample();before=deepcopy(stage.native_calls())
        self.typing(stage);stage.failed_worker()
        self.assertEqual(before,stage.native_calls());self.assertEqual(1,len(self.originals(stage)['records']))
        self.assertEqual([],stage.editor.transport.envelopes);self.assertEqual([],stage.editor.field.calls)
        self.assertEqual(['baseline','type'],[row['stimulus']['verb'] for row in self.rejected_phase(stage)['activations']])

    def test_repeated_create_activation_is_not_another_owned_stage_or_source_query(self):
        stage=self.stage();stage.sample();self.create(stage);stage.sample();before=deepcopy(stage.native_calls())
        stage.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'));stage.failed_worker()
        self.assertEqual(before,stage.native_calls());self.assertEqual(2,len(self.originals(stage)['records']))
        self.assertEqual(1,len(stage.editor.transport.envelopes));self.assertEqual(1,len(stage.editor.field.calls))
        self.assertEqual(['baseline','open-editor','open-editor'],
            [row['stimulus']['verb'] for row in self.rejected_phase(stage)['activations']])

    def test_ignored_normal_ime_stays_empty_in_actor_facts_despite_owned_type_phase(self):
        stage=self.stage();stage.sample();self.create(stage);stage.sample();self.typing(stage)
        stage.editor.field.ignore={'replace'}
        with self.assertRaises(NativeUIError):stage.editor.owner.type_create()
        observed=stage.sample()['facts'];self.assertEqual('',observed['text'])
        self.assertNotEqual(context(stage.run)['unicode'],observed['text'])
        self.assertEqual('typing',stage.editor.owner.state['phase']);self.assertEqual(2,len(stage.editor.field.calls))
        with self.assertRaises(NativeUIError):stage.editor.owner.type_create()
        self.assertEqual(2,len(stage.editor.field.calls));self.assertEqual(3,len(self.originals(stage)['records']))

    def test_changed_original_context_after_actual_type_is_retained_and_never_published(self):
        stage=self.stage();stage.sample();self.create(stage);stage.sample();self.typing(stage)
        stage.editor.owner.type_create();stage.native.ui.rows[0]['contextId']='f'*32
        before=len(stage.native_calls());stage.failed_worker()
        self.assertEqual(['gesture','drive','ui'],stage.native_calls()[before:])
        original=self.originals(stage);self.assertEqual(2,len(original['records']))
        self.assertIn('ui',[row['key'] for row in ActorOriginals(PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json')).pending()]);self.assertEqual(2,len(stage.client.observe()['entries']))
        self.assertEqual(2,len(stage.editor.field.calls));self.assertEqual('typed',stage.editor.owner.state['phase'])

    def test_foreign_factory_fingerprint_refuses_before_any_target_source_query(self):
        stage=self.stage();stage.failed_worker('sample-foreign-factory-fingerprint')
        self.assertEqual([],stage.native_calls());self.assertEqual([],stage.editor.transport.envelopes)
        self.assertIsNone(PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json').read())

    def test_original_subject2_is_retained_and_refused_by_unchanged_framework_requirement(self):
        stage=self.stage(framework=False);stage.failed_worker()
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],stage.native_calls())
        self.assertEqual([],stage.client.observe()['entries']);self.assertEqual([],stage.editor.transport.envelopes)
        store=PrivateFeatureState(Path(stage.waiting['root'])/'lifecycle-actor-originals.json');original=store.read()
        self.assertEqual([],original['records'])
        bundle=ActorOriginals(store).last('subject')
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
