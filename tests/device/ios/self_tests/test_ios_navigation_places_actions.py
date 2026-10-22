"""Durable real private journals/phase HTTP, with native Qt/SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters import normal_input
from ios.adapters.navigation_places_actions import NavigationPlacesActions
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.self_tests import test_ios_navigation_places_inputs as recipes
from ios.self_tests.test_ios_location_bookmarks import RUN
from self_tests.test_completed_frame_lease import BINDING
from self_tests import test_navigation_scene as scene_tests


class NavigationPlacesActionsTests(unittest.TestCase):
    def setUp(self):
        self.scene=scene_tests.NavigationSceneTests();self.scene.setUp();self.addCleanup(self.scene.doCleanups)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.scene.open())
        self.h=recipes.NavigationPlacesInputsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.http.stop();self.h.sdk=recipes.SDK(self.h.root/'bookmarks.json',self.scene.inputs);self.h.io=self.h.sdk.io()
        self.h.http=patch.object(normal_input,'urlopen',self.h.sdk.post);self.h.http.start();self.h.addCleanup(self.h.http.stop)
        self.fixture=NavigationFixtureReader(self.scene.client,RUN);self.fixture.attach();self.factory_calls=0
        self.okay=True
    def factory(self,intent,previous):
        self.factory_calls+=1;return self.h.flow(intent=intent,previous=previous)
    def owner(self,**changes):
        options=dict(store=PrivateFeatureState(self.h.root/'ios-navigation-places-actions.json'),binding=BINDING,run=RUN,
            lock=self.h.lock,guard=lambda:self.okay,fixture=self.fixture,factory=self.factory,
            monotonic=lambda:self.h.sdk.model.clock);options.update(changes);return NavigationPlacesActions(**options)
    def call(self,verb,**inputs):
        call=self.h.call(verb,**inputs);call['ticket']=uuid.uuid4().hex
        self.scene.client.activate(call['ticket'],verb,inputs);return call

    def test_multiple_whole_actions_retain_original_phase_input_history_and_ack_duplicate_without_new_reads_or_inputs(self):
        with self.h.lock.held():
            owner=self.owner();first=self.call('bookmark-add-cancel',name=self.h.ctx['name'])
            self.assertEqual({'performed':True},owner.act(first));original=deepcopy(owner.store.read())
            self.assertEqual('acknowledged',owner.state['actions'][-1]['phase']);self.assertGreater(len(owner.state['actions'][-1]['intents']),1)
            inputs=len(self.h.sdk.requests);factories=self.factory_calls;again=self.owner()
            self.assertEqual({'performed':True},again.act(first));self.assertEqual(inputs,len(self.h.sdk.requests))
            self.assertEqual(factories,self.factory_calls);self.assertEqual(original,again.store.read())
            second=self.call('bookmark-add',name=self.h.ctx['name']);again.act(second)
            self.assertEqual(2,len(again.state['actions']));self.assertEqual(original['payload'],self.owner().envelope(dict(
                providerInstance=self.fixture.instance,providerInputs=self.fixture.inputs,actions=[again.state['actions'][0]]))['payload'])
            self.assertEqual(self.h.sdk.urls['A'],self.h.sdk.bookmarks[self.h.ctx['name']])

    def test_uncertain_partial_input_blocks_old_and_new_tickets_after_reconstruction(self):
        with self.h.lock.held():
            owner=self.owner();call=self.call('bookmark-add',name=self.h.ctx['name']);self.h.sdk.ignore=True
            with self.assertRaises(NativeUIError):owner.act(call)
            raw=deepcopy(owner.store.read());again=self.owner();self.assertEqual('issued',again.state['actions'][-1]['phase'])
            count=len(self.h.sdk.requests);self.h.sdk.ignore=False
            with self.assertRaises(NativeUIError):again.act(call)
            different=self.call('bookmark-add-cancel',name=self.h.ctx['name'])
            with self.assertRaises(NativeUIError):again.act(different)
            self.assertEqual(count,len(self.h.sdk.requests));self.assertEqual(raw,again.store.read())

    def test_lost_ack_write_keeps_all_actual_input_intents_but_never_reexecutes_the_action(self):
        with self.h.lock.held():
            owner=self.owner();call=self.call('bookmark-add',name=self.h.ctx['name']);write=owner.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['actions'][-1]['phase']=='acknowledged':raise OSError('Synthetic lost action return')
                write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.act(call)
            self.assertIn(self.h.ctx['name'],self.h.sdk.bookmarks);again=self.owner();count=len(self.h.sdk.requests)
            self.assertEqual('issued',again.state['actions'][-1]['phase']);self.assertGreater(len(again.state['actions'][-1]['intents']),1)
            with self.assertRaises(NativeUIError):again.act(call)
            self.assertEqual(count,len(self.h.sdk.requests))

    def test_missing_phase_read_is_owned_before_any_factory_or_normal_input_and_not_retried(self):
        with self.h.lock.held():
            owner=self.owner();call=self.call('bookmark-add',name=self.h.ctx['name'])
            self.fixture.read=lambda:(_ for _ in ()).throw(OSError('Synthetic phase read loss'))
            with self.assertRaises(OSError):owner.act(call)
            again=self.owner();self.assertEqual('checking',again.state['actions'][-1]['phase'])
            with self.assertRaises(NativeUIError):again.act(call)
            self.assertEqual(0,self.factory_calls);self.assertFalse(any(row['operation']=='edit' for row in self.h.sdk.requests))

    def test_wrong_actual_phase_is_retained_and_cannot_issue_requested_input(self):
        with self.h.lock.held():
            owner=self.owner();call=self.h.call('bookmark-add',name=self.h.ctx['name']);call['ticket']=uuid.uuid4().hex
            # Actual fixture still has baseline, not this requested action.
            with self.assertRaises(NativeUIError):owner.act(call)
            again=self.owner();row=again.state['actions'][-1]
            self.assertEqual('checking',row['phase']);self.assertEqual('baseline',row['fixture']['verb'])
            self.assertEqual(0,self.factory_calls)

    def test_changed_run_or_candidate_and_provider_cannot_adopt_owned_action_history(self):
        with self.h.lock.held():
            owner=self.owner();owner.act(self.call('bookmark-add-cancel',name=self.h.ctx['name']))
            self.okay=False
            with self.assertRaises(NativeUIError):self.owner()
            self.okay=True
            with self.assertRaises(NativeUIError):self.owner(binding=dict(BINDING,generation=BINDING['generation']+1))
            self.fixture.instance='f'*32
            with self.assertRaises(NativeUIError):self.owner()

    def test_prior_observation_counter_or_same_root_source_cannot_regress_between_actions(self):
        with self.h.lock.held():
            owner=self.owner();owner.act(self.call('bookmark-add-cancel',name=self.h.ctx['name']))
            self.h.sdk.observations=0;before=len([row for row in self.h.sdk.requests if row['operation']=='edit'])
            with self.assertRaises(NativeUIError):self.owner().act(self.call('bookmark-add',name=self.h.ctx['name']))
            self.assertEqual(before,len([row for row in self.h.sdk.requests if row['operation']=='edit']))

    def test_new_call_origin_or_changed_ticket_arguments_fail_without_overwriting_original_record(self):
        with self.h.lock.held():
            owner=self.owner();call=self.call('bookmark-add-cancel',name=self.h.ctx['name']);owner.act(call)
            raw=deepcopy(owner.store.read())
            for changed in (dict(verb='bookmark-add'),dict(fixtureUrl='http://foreign.invalid/feature-fixture/v1/runs/'+RUN+'/')):
                with self.subTest(changed=changed),self.assertRaises(NativeUIError):self.owner().act(call|changed)
            self.assertEqual(raw,owner.store.read())
