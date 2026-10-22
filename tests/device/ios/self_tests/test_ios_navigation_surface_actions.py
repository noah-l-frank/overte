"""Actual private journals and normal W3C codecs; Qt/SDK surface is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack, pack
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.adapters import places_controls as controls
from ios.self_tests import test_ios_navigation_scene_inputs as scene
from ios.self_tests.test_ios_places_controls import row as place_row
from feature_journeys.fixtures import context


class NavigationSurfaceActionsTests(unittest.TestCase):
    def setUp(self):
        self.h = scene.NavigationSceneInputsTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.b, self.admission = self.h.b, self.h.admission
        self.original = self.b.observed; self.source_sequence = 100; self.root_id = str(uuid.UUID(int=500))
        self.ignore_places = False
        def observed():
            value = self.original(); self.source_sequence += 1
            value.update(placesControlsVersion=2, placesSourceSequence=self.source_sequence,
                         elapsedMs=round(self.b.clock*1000)+100000)
            if self.b.screen == 'places' and not self.ignore_places:
                page = place_row('places.page'); page.update(profile=controls.PROFILES[2],rootId=self.root_id,
                    checked=None,rowIndex=None,popup='none',frame=dict(x=1,y=1,width=100,height=100))
                value['controls'].append(page)
            return value
        self.b.observed = observed
        self.fixture = self.admission.fixture
        with patch('feature_journeys.witness.secrets.token_hex', return_value=self.admission.run):
            self.assertEqual(self.admission.run,self.h.h.fixture.harness.open())
    def owner(self):
        return NavigationSurfaceActions(PrivateFeatureState(self.h.h.root/'ios-navigation-surface-actions.json'),
            self.admission,self.b.ui,self.h.native,monotonic=lambda:self.b.clock)
    def call(self,verb):
        ctx=context(self.admission.run)
        inputs={'name':ctx['renamed']} if verb=='bookmark-visit' else (
            {'destination':ctx['destination']} if verb=='directory-select' else {})
        ticket=uuid.uuid4().hex;self.h.h.fixture.harness.client.activate(ticket,verb,inputs)
        return dict(contractVersion=16,runId=self.admission.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=self.fixture.fixture_url)

    def test_normal_open_close_keep_independent_actual_page_and_every_mutating_intent(self):
        with self.h.h.lock.held():
            owner=self.owner();first=self.call('open');self.assertEqual({'performed':True},owner.act(first))
            self.assertEqual('places',self.b.screen);original=deepcopy(owner.store.read());inputs=list(self.b.inputs)
            self.assertEqual({'performed':True},self.owner().act(first));self.assertEqual(inputs,self.b.inputs)
            self.assertEqual(original,owner.store.read());self.assertEqual(self.root_id,owner.state['actions'][0]['page']['rootId'])
            self.assertGreaterEqual(len(owner.state['actions'][0]['intents']),3)
            owner=self.owner();owner.act(self.call('close'));self.assertIsNone(self.b.screen)
            self.assertEqual(2,len(owner.state['actions']));self.assertEqual({},owner.state['component'])
            self.assertEqual('DELETE',owner.state['actions'][-1]['intents'][-1]['method'])
            self.assertIsNotNone(owner.store.read());self.assertIsNotNone(self.admission.store.read())

    def test_a_normally_closed_page_retains_its_archive_without_blocking_a_later_owned_open(self):
        with self.h.h.lock.held():
            self.owner().act(self.call('open'));self.owner().act(self.call('close'))
            self.root_id=str(uuid.UUID(int=502));owner=self.owner();owner.act(self.call('open'))
            self.assertEqual(self.root_id,owner.state['actions'][-1]['page']['rootId'])
            owner=self.owner();owner.act(self.call('close'))
            self.assertEqual(4,len(owner.state['actions']));self.assertIsNone(self.b.screen)

    def test_foreign_preexisting_tablet_is_not_adopted_or_closed(self):
        with self.h.h.lock.held():
            self.b.screen='settings';owner=self.owner()
            with self.assertRaises(NativeUIError):owner.act(self.call('open'))
            self.assertEqual([],self.b.inputs);self.assertEqual('checking',self.owner().state['actions'][-1]['phase'])

    def test_ignored_places_input_is_not_acknowledged_or_replayed(self):
        with self.h.h.lock.held():
            self.ignore_places=True;owner=self.owner();call=self.call('open')
            with self.assertRaises(NativeUIError):owner.act(call)
            before=list(self.b.inputs);again=self.owner()
            self.assertEqual('issued',again.state['actions'][-1]['phase'])
            with self.assertRaises(NativeUIError):again.act(call)
            with self.assertRaises(NativeUIError):again.act(self.call('close'))
            self.assertEqual(before,self.b.inputs)

    def test_lost_final_write_retains_all_original_inputs_without_new_transport(self):
        with self.h.h.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['actions'][-1]['phase']=='acknowledged':raise OSError('Synthetic final write loss')
                write(value,previous)
            owner.store.write=lose;call=self.call('open')
            with self.assertRaises(OSError):owner.act(call)
            self.assertEqual('places',self.b.screen);before=list(self.b.inputs);again=self.owner()
            with self.assertRaises(NativeUIError):again.act(call)
            self.assertEqual(before,self.b.inputs);self.assertGreaterEqual(len(again.state['actions'][-1]['intents']),3)

    def test_uncertain_w3c_click_keeps_pretransport_original_and_never_resends(self):
        with self.h.h.lock.held():
            owner=self.owner();original=self.b.call
            def lost(method,path,body=None):
                result=original(method,path,body)
                if method=='POST' and path.endswith('/click'):raise OSError('Synthetic delivery return loss')
                return result
            self.b.call=lost;call=self.call('open')
            with self.assertRaises(NativeUIError):owner.act(call)
            again=self.owner();self.assertEqual(1,len(again.state['actions'][-1]['intents']));before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):again.act(call)
            self.assertEqual(before,self.b.inputs)

    def test_original_root_replacement_or_popup_prevents_closing_another_page(self):
        with self.h.h.lock.held():
            self.owner().act(self.call('open'));self.root_id=str(uuid.UUID(int=501));before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().act(self.call('close'))
            self.assertEqual(before,self.b.inputs);self.assertEqual('places',self.b.screen)

    def test_source_rollback_or_process_replacement_cannot_authorize_next_input(self):
        for fault in ('counter','process'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.h.h.lock.held():
                    self.owner().act(self.call('open'));before=list(self.b.inputs)
                    if fault=='counter':self.source_sequence=0
                    else:self.b.native_boundary.pid=43
                    with self.assertRaises(NativeUIError):self.owner().act(self.call('close'))
                    self.assertEqual(before,self.b.inputs)

    def test_actual_phase_mismatch_is_retained_before_any_normal_input(self):
        with self.h.h.lock.held():
            call=self.call('open');call['ticket']=uuid.uuid4().hex;owner=self.owner()
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual([],self.b.inputs);self.assertEqual('checking',self.owner().state['actions'][-1]['phase'])

    def test_deleted_original_intent_cannot_fabricate_acknowledged_open(self):
        with self.h.h.lock.held():
            owner=self.owner();owner.act(self.call('open'));raw=owner.store.read();state=unpack(raw['payload'])[0]
            state['actions'][0]['after']=None;changed=dict(raw,payload=pack([state]));owner.store.write(changed,raw)
            with self.assertRaises(NativeUIError):self.owner()

    def test_composite_close_retains_actual_directory_phase_without_fabricating_close_call(self):
        with self.h.h.lock.held():
            self.owner().act(self.call('open'));call=self.call('directory-select');owner=self.owner()
            owner.act(call,surface='close');row=owner.state['actions'][-1]
            self.assertEqual('directory-select',row['call']['verb']);self.assertEqual('close',row['surface'])
            self.assertEqual('directory-select',row['fixture']['verb']);self.assertIsNone(self.b.screen)
            before=list(self.b.inputs);self.owner().act(call,surface='close');self.assertEqual(before,self.b.inputs)

    def test_bookmark_visit_owns_two_surface_transitions_under_the_same_original_ticket(self):
        with self.h.h.lock.held():
            call=self.call('bookmark-visit');self.owner().act(call,surface='open')
            owner=self.owner();owner.act(call,surface='close')
            self.assertEqual(['open','close'],[row['surface'] for row in owner.state['actions']])
            self.assertEqual([call,call],[row['call'] for row in owner.state['actions']])
            self.assertEqual(call['ticket'],owner.state['actions'][1]['fixture']['ticket'])
            before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().act(call,surface='open')
            self.assertEqual(before,self.b.inputs)

    def test_composite_phase_mismatch_and_unsupported_surface_cannot_authorize_input(self):
        with self.h.h.lock.held():
            call=self.call('directory-select');owner=self.owner()
            with self.assertRaises(NativeUIError):owner.act(call,surface='open')
            self.assertIsNone(owner.store.read());self.assertEqual([],self.b.inputs)
            call=self.call('bookmark-visit');call['ticket']=uuid.uuid4().hex
            with self.assertRaises(NativeUIError):owner.act(call,surface='open')
            self.assertEqual([],self.b.inputs)

    def test_root_replacement_between_close_preflight_and_resolved_click_is_not_touched(self):
        with self.h.h.lock.held():
            self.owner().act(self.call('open'));owner=self.owner();capture=owner.capture;reads=0
            def replaced():
                nonlocal reads
                reads+=1
                if reads==2:self.root_id=str(uuid.UUID(int=501))
                return capture()
            owner.capture=replaced;before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):owner.act(self.call('close'))
            self.assertEqual(before,self.b.inputs);self.assertEqual('issued',self.owner().state['actions'][-1]['phase'])

    def test_version_one_originals_migrate_only_surface_labels_without_retiming(self):
        with self.h.h.lock.held():
            owner=self.owner();call=self.call('open');owner.act(call);current=owner.store.read()
            state=unpack(current['payload'])[0]
            for row in state['actions']:del row['surface']
            legacy=dict(current,iosNavigationSurfaceActionsVersion=1,payload=pack([state]))
            owner.store.write(legacy,current);again=self.owner();before=list(self.b.inputs)
            again.act(call);self.assertEqual(legacy,again.store.read());self.assertEqual(before,self.b.inputs)
            again.act(self.call('close'));new=again.store.read();first=unpack(new['payload'])[0]['actions'][0]
            self.assertEqual(2,new['iosNavigationSurfaceActionsVersion']);self.assertEqual('open',first.pop('surface'))
            self.assertEqual(state['actions'][0],first)

    def test_lost_composite_close_result_blocks_new_phase_and_does_not_resend(self):
        with self.h.h.lock.held():
            call=self.call('bookmark-visit');self.owner().act(call,surface='open');owner=self.owner();write=owner.store.write
            def lost(value,previous):
                rows=unpack(value['payload'])[0]['actions']
                if len(rows)==2 and rows[-1]['phase']=='acknowledged':raise OSError('Synthetic composite result loss')
                write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.act(call,surface='close')
            before=list(self.b.inputs);again=self.owner()
            with self.assertRaises(NativeUIError):again.act(call,surface='close')
            with self.assertRaises(NativeUIError):again.act(self.call('open'))
            self.assertEqual(before,self.b.inputs);self.assertEqual('issued',again.state['actions'][-1]['phase'])
