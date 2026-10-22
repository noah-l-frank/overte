"""Actual run source/failure cleanup with explicit setup completion doubles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_run
from test_emote_sources import RUN
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_script_history import pack,unpack


class EarlyCleanupTests(unittest.TestCase):
    setUp=test_emote_run.EmoteRunTests.setUp
    owner=test_emote_run.EmoteRunTests.owner
    prepared=test_emote_run.EmoteRunTests.prepared
    cleanup_phase=test_emote_run.EmoteRunTests.cleanup_phase

    def call(self):return dict(contractVersion=17,runId=RUN)

    def test_failed_cache_admission_can_finish_resource_cleanup_without_creating_view_or_scene(self):
        m=self.model;m.inventory.resources[0]['model']['sha256']='f'*64;run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        self.assertEqual(dict(view='unissued',scene='unissued'),run.state['setup']);self.assertEqual([],self.setup_calls)
        self.cleanup_phase();resources=run.cleanup_resources(self.call())
        self.assertEqual(dict(scene=None,view=None),resources);self.assertEqual([],self.setup_calls)
        self.assertEqual('resources-restored',run.state['phase']);self.assertIsNone(run.state['admissionSha256'])
        with run.lock.held():
            failure=PhoneEmoteFailures(run);rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual(['admission'],[row['kind'] for row in rows]);self.assertEqual('reading',unpack(rows[0]['archive']['header']['payload'])[0]['phase'])
            self.assertIsNotNone(run.store.read());self.assertIsNotNone(failure.store.read())

    def test_failure_before_first_baseline_returns_only_no_input_ownership_proof(self):
        m=self.model;m.admission_fault='wrong-domain';run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        self.assertIsNone(run.state['baseline']);self.assertEqual([],self.setup_calls)
        self.cleanup_phase();proof=run.cleanup_inputs(self.call())
        self.assertEqual(1,proof['emoteNoInputCleanupVersion']);self.assertNotIn('state',proof);self.assertNotIn('cleaned',proof)
        self.assertIsNone(run.state['baseline']);self.assertIsNone(run.state['admissionSha256']);self.assertEqual([],m.controls.input_requests)
        self.assertEqual(dict(scene=None,view=None),run.cleanup_resources(self.call()))
        self.assertEqual('resources-restored',run.state['phase']);self.assertEqual([],self.setup_calls)
        self.assertIsNotNone(run.store.read())
        with self.assertRaises(NativeUIError):run.cleanup_quiet('primary') # Unapproved world is still unapproved.

    def test_interrupted_view_setup_restores_only_view_and_never_constructs_scene(self):
        self.setup_fault='view';run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        self.assertEqual(dict(view='issued',scene='unissued'),run.state['setup']);self.assertEqual(['view'],self.setup_calls)
        self.setup_fault=None;self.cleanup_phase();result=run.cleanup_resources(self.call())
        self.assertIsNone(result['scene']);self.assertEqual('restored',result['view']['phase'])
        self.assertEqual(['view','view-cleanup'],self.setup_calls)

    def test_parent_setup_intent_must_persist_before_view_factory_or_input(self):
        run=self.owner();save=run.save
        def ignored():
            if run.state['setup']['view']=='issued':raise NativeUIError('Synthetic lost view setup intent')
            return save()
        with patch.object(run,'save',side_effect=ignored),self.assertRaises(NativeUIError):run.prepare()
        self.assertEqual([],self.setup_calls)
        stored=unpack(run.store.read()['payload'])[0];self.assertEqual('unissued',stored['setup']['view'])
        self.cleanup_phase();run=self.owner();self.assertEqual(dict(scene=None,view=None),run.cleanup_resources(self.call()))
        self.assertEqual([],self.setup_calls)

    def test_unissued_resource_with_unaccounted_journal_cannot_be_skipped(self):
        m=self.model;m.inventory.resources[0]['model']['sha256']='f'*64;run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        unknown=PrivateFeatureState(m.root/'phone-emote-view.json');unknown.write(dict(unaccounted=True),None)
        self.cleanup_phase()
        with self.assertRaises(NativeUIError):run.cleanup_resources(self.call())
        self.assertEqual(dict(unaccounted=True),unknown.read());self.assertNotEqual('resources-restored',run.state['phase'])

    def test_legacy_run_cannot_borrow_new_unissued_resource_semantics(self):
        m=self.model;m.inventory.resources[0]['model']['sha256']='f'*64;run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        legacy=deepcopy(run.previous);legacy['emoteRunVersion']=3;state=unpack(legacy['payload'])[0];state.pop('setup');state.pop('prepared');legacy['payload']=pack([state])
        run.store.write(legacy,run.previous);run=self.owner();self.cleanup_phase()
        with patch('overte_phone_emote_run.PhoneEmoteView',side_effect=NativeUIError('No original legacy View ownership')),self.assertRaises(NativeUIError):run.cleanup_resources(self.call())
        self.assertEqual(dict(view='legacy',scene='legacy'),run.state['setup']);self.assertIsNotNone(run.store.read())

    def test_initial_open_unowned_tablet_is_preserved_and_never_reported_as_idle(self):
        m=self.model;m.widgets.tablet=True;run=self.owner()
        with self.assertRaises(NativeUIError):run.prepare()
        self.assertIsNone(run.state['baseline']);self.cleanup_phase();proof=run.cleanup_inputs(self.call())
        self.assertEqual(1,proof['emoteNoInputCleanupVersion']);self.assertTrue(m.widgets.tablet)
        self.assertEqual([],m.tablet_inputs);self.assertEqual([],m.controls.input_requests)
        self.assertNotIn('state',proof);self.assertIsNone(run.state['baseline'])

    def test_lost_scene_setup_intent_cannot_construct_or_dispatch_the_scene(self):
        run=self.owner();save=run.save
        def ignored():
            if run.state['setup']['scene']=='issued':raise NativeUIError('Synthetic lost scene setup intent')
            return save()
        with patch.object(run,'save',side_effect=ignored),self.assertRaises(NativeUIError):run.prepare()
        self.assertEqual(['view'],self.setup_calls)
        stored=unpack(run.store.read()['payload'])[0];self.assertEqual(dict(view='issued',scene='unissued'),stored['setup'])
        self.cleanup_phase();run=self.owner();result=run.cleanup_resources(self.call())
        self.assertIsNone(result['scene']);self.assertEqual(['view','view-cleanup'],self.setup_calls)

    def test_normal_ready_run_cannot_forge_unissued_or_malformed_setup_state(self):
        run=self.prepared();header=deepcopy(run.previous)
        for fault in ('unissued','scene-only','unknown','version'):
            value=deepcopy(header);state=unpack(value['payload'])[0]
            if fault=='unissued':state['setup']=dict(view='unissued',scene='unissued')
            elif fault=='scene-only':state['setup']=dict(view='unissued',scene='issued')
            elif fault=='unknown':state['setup']=dict(view='claimed',scene='issued')
            else:value['emoteRunVersion']='future'
            value['payload']=pack([state])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):run.decode(value)
        self.assertEqual(header,run.store.read())


if __name__=='__main__':unittest.main()
