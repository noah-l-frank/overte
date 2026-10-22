"""Canonical teardown cannot bypass an independent unfinished Emote owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.emote_session_cleanup import ensure_finalized,session_entry
from ios.self_tests import test_ios_sdk_operation_guard as sdk_boundary
from ios.self_tests.test_ios_emote_sources import RUN


class SessionCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.calls=[]
        def forbidden(*_args,**_kwargs):self.calls.append('unexpected SDK/candidate input');raise AssertionError('Cleanup created an input before retirement')
        from ios.self_tests.test_ios_emote_sources import BINDING
        self.binding=BINDING
        self.adapter=SimpleNamespace(state_path=lambda _:self.root/'session.json',_candidate_guard=forbidden,_binding=forbidden,
            _retired_candidate_scope=lambda *_:None,_binding_store=lambda _:PrivateFeatureState(self.root/'binding.json'))
    def put(self,name,value):
        store=PrivateFeatureState(self.root/name);store.write(value,None);return store
    def test_default_without_owned_metadata_adds_no_source_session_or_file(self):
        self.assertTrue(ensure_finalized(self.adapter,'owned'))
        self.assertEqual([],self.calls);self.assertEqual([],list(self.root.iterdir()))
    def test_owned_actor_feature_remains_owned_and_no_foreign_selector_is_invented(self):
        store=self.put('ios-emote-actor-feature.json',dict(runId=RUN,role='actor',actual='owned input responsibility'))
        original=store.path.read_bytes()
        for _ in range(2):
            with self.assertRaises(NativeUIError):ensure_finalized(self.adapter,'owned')
            self.assertEqual(original,store.path.read_bytes());self.assertEqual([],self.calls)
    def test_lost_actor_feature_metadata_does_not_skip_pending_actual_archive(self):
        value=dict(runId=RUN,role='actor',payload=pack([dict(phase='retiring')]))
        store=self.put('ios-emote-actor-'+RUN+'-finalization.json',value);before=store.path.read_bytes()
        with self.assertRaises(NativeUIError):ensure_finalized(self.adapter,'owned')
        self.assertEqual(before,store.path.read_bytes());self.assertEqual([],self.calls)
    def test_owned_primary_without_explicit_current_configuration_never_stops_or_guesses_target(self):
        store=self.put('ios-emote-primary-feature.json',dict(runId=RUN,role='primary'))
        before=store.path.read_bytes()
        with patch('ios.adapters.feature_configuration.configuration',return_value=None):
            with self.assertRaises(NativeUIError):ensure_finalized(self.adapter,'owned')
        self.assertEqual(before,store.path.read_bytes());self.assertEqual([],self.calls)

    def test_missing_parent_metadata_cannot_hide_a_retained_actual_component_owner(self):
        store=self.put('ios-emote-primary-pointers.json',dict(actual='retained pointer responsibility'))
        original=store.path.read_bytes()
        with self.assertRaises(NativeUIError):ensure_finalized(self.adapter,'owned')
        self.assertEqual(original,store.path.read_bytes());self.assertEqual([],self.calls)

    def test_missing_sdk_directory_leaves_default_unchanged(self):
        self.adapter.state_path=lambda _:self.root/'missing'/'session.json'
        self.assertTrue(ensure_finalized(self.adapter,'owned'))
        self.assertFalse((self.root/'missing').exists())

    def plan(self):
        return self.put('ios-emote-primary-'+RUN+'-finalization.json',dict(runId=RUN,role='primary',artifactRoot=str(self.root),payload=pack([dict(phase='complete')])))

    def verified(self,_directory,path,_value,**kwargs):
        # Ordering/deadline spy only. Full typed replay has its actual whole-role suite.
        kwargs['membership'].add(path);return self.binding

    def test_foreign_source_wait_only_observes_actual_owners_removal(self):
        self.plan();foreign=self.put('ios-emote-actor-sources.json',dict(actual='independent Actor original'))
        original=foreign.path.read_bytes();clock=[0.];waits=[]
        def wait(seconds):
            waits.append(seconds);self.assertEqual(original,foreign.path.read_bytes())
            clock[0]+=seconds
            # This callback represents the independent owner, never the helper.
            foreign.discard(dict(actual='independent Actor original'))
        with patch('ios.adapters.emote_completed_archive.verify',side_effect=self.verified):
            self.assertTrue(ensure_finalized(self.adapter,'owned',monotonic=lambda:clock[0],sleep=wait))
        self.assertEqual([.15],waits);self.assertEqual([],self.calls)

    def test_foreign_source_timeout_retains_original_without_native_poll(self):
        self.plan();foreign=self.put('ios-emote-actor-sources.json',dict(actual='independent Actor original'))
        original=foreign.path.read_bytes();clock=[0.]
        def wait(_seconds):clock[0]+=10.
        with patch('ios.adapters.emote_completed_archive.verify',side_effect=self.verified),self.assertRaises(NativeUIError):ensure_finalized(self.adapter,'owned',monotonic=lambda:clock[0],sleep=wait)
        self.assertEqual(original,foreign.path.read_bytes());self.assertEqual([],self.calls)

    def test_outer_budget_remains_active_after_helper_through_actual_sdk_stop(self):
        self.plan();sdk=sdk_boundary.SDKOperationGuardTests();sdk.setUp();self.addCleanup(sdk.doCleanups);clock=[0.]
        def cleanup(adapter,selector):
            self.assertTrue(ensure_finalized(adapter,selector,monotonic=lambda:clock[0]))
            clock[0]=60.;return sdk.send()
        with patch('ios.adapters.emote_completed_archive.verify',side_effect=self.verified),self.assertRaises(NativeUIError):
            session_entry(cleanup,monotonic=lambda:clock[0])(self.adapter,'owned')
        self.assertEqual([],sdk.requests)
        sdk.send();self.assertEqual(1,len(sdk.requests))

    def test_slow_ownership_scan_counts_before_any_actual_sdk_send(self):
        self.plan();sdk=sdk_boundary.SDKOperationGuardTests();sdk.setUp();self.addCleanup(sdk.doCleanups);clock=[0.]
        def scan(_adapter,_selector):clock[0]=61.;return True
        with patch('ios.adapters.emote_session_cleanup.owned',side_effect=scan):
            with self.assertRaises(NativeUIError):session_entry(lambda *_:sdk.send(),monotonic=lambda:clock[0])(self.adapter,'owned')
        self.assertEqual([],sdk.requests)

    def test_non_emote_default_does_not_limit_ordinary_sdk_cleanup(self):
        sdk=sdk_boundary.SDKOperationGuardTests();sdk.setUp();self.addCleanup(sdk.doCleanups);clock=[0.]
        def cleanup(*_):clock[0]=1000.;return sdk.send()
        self.assertEqual(dict(received=True),session_entry(cleanup,monotonic=lambda:clock[0])(self.adapter,'owned'))
        self.assertEqual(1,len(sdk.requests))

    def test_complete_flag_without_validated_originals_cannot_authorize_sdk_stop(self):
        plan=self.plan();before=plan.path.read_bytes()
        with self.assertRaises((NativeUIError,ValueError,KeyError)):ensure_finalized(self.adapter,'owned')
        self.assertEqual(before,plan.path.read_bytes());self.assertEqual([],self.calls)

    def test_lost_all_fixed_metadata_cannot_hide_a_generic_gpu_owner(self):
        store=self.put('graphics-world-frame-primary-0-'+'7'*32+'.json',dict(actual='unknown GPU ownership'))
        before=store.path.read_bytes()
        config=dict(areas=['emotes'],emotes=dict(artifactRoot=str(self.root),actorTarget='independent'))
        with patch('ios.adapters.feature_configuration.configuration',return_value=config),self.assertRaises(NativeUIError):
            ensure_finalized(self.adapter,'owned')
        self.assertEqual(before,store.path.read_bytes());self.assertEqual([],self.calls)

    def test_without_emote_configuration_generic_foreign_owner_is_not_adopted(self):
        store=self.put('graphics-world-frame-primary-0-'+'7'*32+'.json',dict(actual='other feature owns this'))
        before=store.path.read_bytes()
        with patch('ios.adapters.feature_configuration.configuration',return_value=None):
            self.assertTrue(ensure_finalized(self.adapter,'owned'))
        self.assertEqual(before,store.path.read_bytes());self.assertEqual([],self.calls)
