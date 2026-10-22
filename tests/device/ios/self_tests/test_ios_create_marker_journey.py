"""Whole marker setup/retirement recipes; Qt/native/rendering remain synthetic.

Actual staged JS/companion bytes run in a host Node sandbox; real normal Script
manager/picker owners drive token UI models. No device acceptance is asserted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_create_marker_scope as marker_fixture
from ios.self_tests.create_marker_domain_fixture import RunningDomain
from ios.adapters.create_marker_scope import CreateMarkerScope


class MarkerJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=marker_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=RunningDomain(self.scope)
    def test_normal_bundle_source_actual_js_UUID_render_lifetime_and_repeated_original_cleanup(self):
        owned=self.scope.prepare();self.assertTrue(self.domain.running)
        self.assertEqual(self.domain.vm['added'][0]['id'],owned['marker']['id'])
        self.assertEqual(self.domain.vm['deleted'],[owned['marker']['id']])
        self.assertIn('script-file.confirm',self.domain.io.actions)
        self.assertEqual('first person look at',self.domain.world_template['source']['view']['mode'])
        self.domain.paint();self.scope.admit_rendered();self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertFalse(self.domain.running);self.assertFalse(self.domain.files.root.exists())
        self.assertEqual('first person look at',self.domain.world_template['source']['view']['mode'])
        self.assertEqual(['thread-bound','shutdown-drained','thread-finished'],[r['kind'] for r in self.domain.terminal_events])
        before=list(self.domain.io.actions);self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual(before,self.domain.io.actions)
        rebuilt=self.fixture.owner();self.assertEqual('released',rebuilt.state['phase']);self.assertEqual(self.scope.frames,rebuilt.frames)
    def test_lost_actual_stop_return_uses_terminal_originals_and_never_clicks_stop_again(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();activate=self.domain.io.activate
        def lost(identifier,**kwargs):
            activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise NativeUIError('Synthetic lost actual stop return')
        with patch.object(self.domain.io,'activate',side_effect=lost),self.assertRaises(NativeUIError):self.scope.cleanup()
        self.assertEqual('stopping-marker',self.scope.state['phase']);self.assertFalse(self.domain.running)
        rebuilt=self.fixture.owner();self.domain.attach(rebuilt)
        self.assertEqual({'performed':True},rebuilt.cleanup());self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
        self.assertEqual('released',rebuilt.state['phase']);self.assertFalse(self.domain.files.root.exists())
    def test_accepted_load_lost_before_render_admission_still_stops_owned_code_and_drains_zero_created_resources(self):
        self.scope.prepare();self.assertIsNone(self.scope.state['webAdmission'])
        # Setup reached the actual running source but no image/resource was
        # admitted; cleanup must retain that distinction.
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual('partial-execution',self.scope.state['cleanupMode'])
        self.assertFalse(self.domain.running);self.assertFalse(self.domain.files.root.exists())
        self.assertTrue(all(not row['web']['contexts'] for row in self.scope.frames))
    def test_ignored_confirm_is_cancelled_once_and_actual_returned_empty_callback_precedes_retirement(self):
        activate=self.domain.io.activate
        def ignored(identifier,**kwargs):
            if identifier=='script-file.confirm':self.domain.io.actions.append(identifier);return
            return activate(identifier,**kwargs)
        with patch.object(self.domain.io,'activate',side_effect=ignored),self.assertRaises(NativeUIError):self.scope.prepare()
        self.assertFalse(self.domain.running);self.assertEqual('preparing',self.scope.state['phase'])
        self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual('unloaded',self.scope.state['cleanupMode']);self.assertFalse(self.domain.files.root.exists())
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'));self.assertEqual(1,self.domain.io.actions.count('script-file.review-cancel'))
        self.assertEqual('',self.domain.dialog_events[1]['response']['text']);self.assertEqual('response-returned',self.domain.dialog_events[2]['kind'])
        self.assertFalse(self.domain.terminal_events);self.assertFalse(any(r['label']=='stop-marker-script' for r in self.scope.state['operations']))
    def test_destroyed_picker_with_unreturned_callback_retains_files_and_pending_selection(self):
        activate=self.domain.io.activate
        def ignored(identifier,**kwargs):
            if identifier=='script-file.confirm':self.domain.io.actions.append(identifier);raise NativeUIError('Synthetic ignored confirmation')
            return activate(identifier,**kwargs)
        with patch.object(self.domain.io,'activate',side_effect=ignored),self.assertRaises(NativeUIError):self.scope.prepare()
        # Native listener disappearance can precede queued Application response.
        self.domain.dialog_return=lambda *_args:None
        with self.assertRaises(NativeUIError):self.scope.cleanup()
        self.assertTrue(self.domain.files.root.exists());self.assertNotEqual('released',self.scope.state['phase'])
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'))
    def test_setup_that_already_ended_uses_original_preload_worker_and_terminal_receipts_without_a_stop(self):
        self.scope.prepare();self.domain.stop()
        self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual('finished-execution',self.scope.state['cleanupMode']);self.assertFalse(self.domain.files.root.exists())
        self.assertEqual('first person look at',self.domain.world_template['source']['view']['mode'])
        self.assertNotIn('scripts.stop.0',self.domain.io.actions)
        rebuilt=self.fixture.owner();self.assertEqual(self.scope.frames,rebuilt.frames);self.assertEqual('released',rebuilt.state['phase'])
    def test_started_worker_without_original_actual_thread_finished_receipt_cannot_retire(self):
        self.scope.prepare();self.domain.stop();self.domain.terminal_events.pop()
        with self.assertRaises(NativeUIError):self.scope.cleanup()
        self.assertTrue(self.domain.files.root.exists());self.assertNotEqual('released',self.scope.state['phase'])
    def test_lost_home_return_after_actual_root_destruction_never_replays_home(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();activate=self.domain.io.activate;lost=[False]
        def delivered(identifier,**kwargs):
            activate(identifier,**kwargs)
            if identifier=='tablet.home' and not self.domain.running and not lost[0]:
                lost[0]=True;raise NativeUIError('Synthetic lost actual Home return')
        with patch.object(self.domain.io,'activate',side_effect=delivered),self.assertRaises(NativeUIError):self.scope.cleanup()
        before=self.domain.io.actions.count('tablet.home');rebuilt=self.fixture.owner();self.domain.attach(rebuilt)
        self.assertEqual({'performed':True},rebuilt.cleanup())
        self.assertEqual(before,self.domain.io.actions.count('tablet.home'));self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
    def test_historical_image_admission_keeps_actual_files_code_UUID_without_live_guard_or_SDK(self):
        self.scope.prepare();self.domain.paint();frame=self.scope.admit_rendered();original=self.scope.snapshot()
        self.scope.guard=lambda:(_ for _ in ()).throw(AssertionError('historical live guard'))
        retained=CreateMarkerScope.archive(original,root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock,require_ready=True)
        expected=retained.bind_image_world(frame['create'],frame['world']);self.assertEqual(self.scope.state['fileOwnership']['nonce'],expected['nonce'])
        altered=__import__('copy').deepcopy(frame['create']);altered['source']['entities'][0]['position'][0]+=.01
        with self.assertRaises(NativeUIError):retained.bind_image_world(altered,frame['world'])
        self.scope.guard=lambda:True;self.scope.cleanup()
        # Retired native fixture files are no reason to rewrite or reacquire
        # their immutable original admission records.
        again=CreateMarkerScope.archive(original,root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock,require_ready=True)
        self.assertEqual(expected,again.bind_image_world(frame['create'],frame['world']))
    def test_historical_version1_scope_remains_readable_without_returned_entity_qualification(self):
        self.scope._version=1;self.assertEqual({'performed':True},self.scope.cleanup())
        original=self.scope.snapshot();self.assertEqual(1,original['iosCreateMarkerScopeVersion'])
        self.assertTrue(self.scope.frames);self.assertNotIn('entities',self.scope.frames[0])
        retained=CreateMarkerScope.archive(original,root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock)
        self.assertEqual('released',retained.state['phase'])
        with self.assertRaises(NativeUIError):retained.returned_entity()

    def test_pending_actual_native_api_return_is_observed_with_new_reads_and_never_another_load(self):
        # SDK boundary models an in-flight native API after real map insertion;
        # no Native C++/installed VM execution is claimed by this host model.
        self.domain.entity_return_delay=5;owned=self.scope.prepare()
        loaded=[row for row in self.scope.frames if row['label']=='marker-loaded']
        self.assertGreaterEqual(len(loaded),2);self.assertFalse(loaded[0]['entities']['source']['calls']['events'])
        self.assertEqual(owned['marker']['id'],loaded[-1]['entities']['source']['calls']['events'][0]['entityId'])
        self.assertLess(loaded[0]['entities']['clockAfter']['epochMs'],loaded[-1]['entities']['clockBefore']['epochMs'])
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'));self.assertEqual(1,self.domain.io.actions.count('scripts.from-file'))
        self.domain.paint();self.scope.admit_rendered();self.scope.cleanup()

    def test_reconstructed_prepare_after_lost_passive_read_uses_original_load_and_no_input_replay(self):
        activate=self.domain.io.activate
        def loaded(identifier,**kwargs):
            result=activate(identifier,**kwargs)
            if identifier=='script-file.confirm':self.domain.web_failure=True
            return result
        with patch.object(self.domain.io,'activate',side_effect=loaded),self.assertRaises(OSError):self.scope.prepare()
        self.assertEqual('preparing',self.scope.state['phase']);self.assertTrue(self.domain.running)
        self.domain.web_failure=False;rebuilt=self.fixture.owner();self.domain.attach(rebuilt)
        owned=rebuilt.prepare();self.assertEqual(self.domain.vm['added'][0]['id'],owned['marker']['id'])
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'));self.assertEqual(1,self.domain.io.actions.count('scripts.from-file'))
        self.domain.paint();rebuilt.admit_rendered();self.assertEqual({'performed':True},rebuilt.cleanup())

    def test_actual_weak_owner_keeps_marker_and_native_files_owned_after_scene_and_api_return_are_gone(self):
        owned=self.scope.prepare();self.domain.paint();self.scope.admit_rendered()
        held=self.domain.entity_items[owned['marker']['id']]
        with self.assertRaises(NativeUIError):self.scope.cleanup()
        self.assertFalse(self.domain.running);self.assertTrue(self.domain.files.root.exists())
        self.assertEqual('stopping-marker',self.scope.state['phase'])
        actual=self.scope.frames[-1]['entities']['source'];self.assertEqual('delete-returned',actual['calls']['events'][-1]['kind'])
        self.assertGreater(actual['tree']['entities'][0]['removedSequence'],0);self.assertFalse(actual['tree']['entities'][0]['destroyed'])
        del held
        rebuilt=self.fixture.owner();self.domain.attach(rebuilt);self.assertEqual({'performed':True},rebuilt.cleanup())
        self.assertFalse(self.domain.files.root.exists());self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
        self.assertTrue(rebuilt.frames[-1]['entities']['source']['tree']['entities'][0]['destroyed'])
    def test_actual_scene_and_script_ack_cannot_supply_a_missing_native_return(self):
        start=self.domain.start
        def lost_return():start();self.domain.entity_calls.clear()
        with patch.object(self.domain,'start',side_effect=lost_return),self.assertRaises(NativeUIError):self.scope.prepare()
        self.assertTrue(self.domain.running);self.assertTrue(self.domain.files.root.exists())
        rebuilt=self.fixture.owner();self.domain.attach(rebuilt)
        with self.assertRaises(NativeUIError):rebuilt.cleanup()
        self.assertTrue(self.domain.files.root.exists());self.assertNotEqual('released',rebuilt.state['phase'])
    def test_unrendered_transient_raw_uuid_has_retained_original_tree_birth_and_positive_weak_death(self):
        self.scope.prepare();self.domain.stop();self.assertEqual({'performed':True},self.scope.cleanup())
        owned=self.scope.returned_entity();self.assertIsNone(self.scope.state['admission']['marker'])
        self.assertEqual(self.domain.vm['added'][0]['id'],owned['returned']['entityId']);self.assertIsNotNone(owned['birth'])
        from ios.adapters.create_entities import retired
        row=retired(self.scope.frames[-1]['entities'],owned,after_epoch=self.scope.state['stopBarrier']['epoch'])
        self.assertTrue(row['destroyed']);self.assertFalse(self.domain.files.root.exists())
    def test_original_tree_and_self_identity_must_join_native_scene_and_domain_sources(self):
        self.scope.prepare();frame=__import__('copy').deepcopy(self.scope.frames[-1])
        for fault in ('tree','self'):
            value=__import__('copy').deepcopy(frame)
            if fault=='tree':value['entities']['source']['tree']['treeInstance']='0'*32
            else:value['world']['source']['domain']['selfSha256']='0'*64
            originals={k:v for k,v in value.items() if k not in ('clockJoin','label')}
            from adapters.native_clock_join import digest
            value['clockJoin']['originalsSha256']=digest(originals)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.scope.validate_frame(value)

    def test_returned_callback_without_actual_listener_destruction_cannot_retire(self):
        returned=self.domain.dialog_return
        def alive(*args):returned(*args);self.domain.dialog_events.pop()
        self.domain.dialog_return=alive
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered()
        with self.assertRaises(NativeUIError):self.scope.cleanup()
        self.assertTrue(self.domain.files.root.exists());self.assertEqual('quiet',self.scope.state['phase'])
        self.assertTrue(any(row['kind']=='response-returned' for row in self.domain.dialog_events))
        self.assertFalse(any(row['kind']=='listener-destroyed' for row in self.domain.dialog_events))


if __name__=='__main__':unittest.main()
