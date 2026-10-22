"""Compose genuine ordinary appearance inputs with new cleanup input owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_cleanup_inputs import AvatarCleanupInputOwner
from ios.adapters.avatar_cleanup_controls import IOSAvatarCleanupControls
from ios.adapters.avatar_cleanup_plan import next_step
from ios.adapters.avatar_input_reads import IOSAvatarInputReads
from ios.adapters.avatar_inputs import IOSAvatarInputs
from ios.self_tests import test_ios_avatar_observation as fixture_module
from ios.self_tests import test_ios_avatar_entities as entity_fixture


class AvatarCleanupPlanTests(unittest.TestCase):
    def setUp(self):
        self.a=fixture_module.AvatarObservationTests();self.a.setUp();self.addCleanup(self.a.doCleanups);f=self.a.fixture.fixture
        for index,(verb,inputs) in enumerate((('avatar-url',dict(resource='avatar-a.fst')),
                ('avatar-bookmark-save',dict(name='e2e-'+f.run)),('avatar-scale',dict(value=1.5)),
                ('wearable-add',dict(resource='gltf-bundle/main.gltf'))),1):self.a.act(verb,inputs,index)
        f.journal.activate(f.run,'c'*32,'cleanup');self.a.fixture.source.read()
    def plan(self):
        f=self.a.fixture
        return next_step(self.a.history(),self.a.baseline,self.a.actions.peer,
            fixture_url=f.source.phase.fixture_url,expected_code=entity_fixture.EXPECTED)
    def controls(self):
        f=self.a.fixture;s=f.source
        def unused(_):raise AssertionError('No ledger query is needed for fully returned inputs')
        reader=IOSAvatarInputs(unused,lambda:json.dumps({}),f.fixture.now,lambda:True,42,
            monotonic=lambda:f.fixture.clock,sleep=f.fixture.sleep)
        reads=IOSAvatarInputReads(PrivateFeatureState(f.path/'ios-avatar-primary-input-reads.json'),f.root,s.binding,s.run,'primary',f.lock,
            lambda:True,reader,monotonic=lambda:f.fixture.clock)
        inputs=AvatarCleanupInputOwner(PrivateFeatureState(f.path/'ios-avatar-primary-cleanup-inputs.json'),f.lock,s.binding,s.run,'primary',
            s.phase.fixture_url,lambda:True)
        return IOSAvatarCleanupControls(PrivateFeatureState(f.path/'ios-avatar-primary-cleanup-controls.json'),s,inputs,f.sdk,reads)
    def test_original_owned_wearable_model_scale_and_bookmark_drive_new_cleanup_recipes_to_actual_restoration(self):
        seen=[];f=self.a.fixture
        for index in range(1,8):
            actual=self.plan();self.assertIsNotNone(actual)
            if actual['step']=='connections':break
            seen.append(actual['step']);owner=self.controls()
            self.assertEqual({'performed':True},owner.run(dict(contractVersion=16,runId=f.fixture.run),index=index,**actual))
            f.source.read()
        self.assertEqual(['remove-wearable','restore-model','restore-scale','delete-bookmark'],seen)
        self.assertEqual(dict(avatar='original',requestedAvatar='original',modelLoaded=True,loadFailed=False,
            scale=1.,wearable=False,bookmarked=False),self.a.measure()['state'])
        self.assertEqual('connections',self.plan()['step'])
        self.assertEqual(4,len(self.controls().state['calls']))
    def test_unowned_persisted_bookmark_change_cannot_be_deleted_or_hidden_by_cleanup_plan(self):
        f=self.a.fixture;f.fixture.widget.name='private-unowned-bookmark';f.source.read()
        # Other owned resources may still need restoration first. Once those
        # operations finish, preservation must reject the foreign bookmark.
        for index in range(1,5):
            try:actual=self.plan()
            except NativeUIError:break
            self.assertNotEqual('delete-bookmark',actual.get('step'))
            self.controls().run(dict(contractVersion=16,runId=f.fixture.run),index=index,**actual);f.source.read()
        else:self.fail('Changed unowned bookmark must remain visible to the cleanup validator')
        self.assertEqual('private-unowned-bookmark',f.fixture.widget.name)


if __name__=='__main__':unittest.main()
