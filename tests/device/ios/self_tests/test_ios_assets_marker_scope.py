"""Actual staged marker JS and normal Script input on separate child WALs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.create_marker_recovery import IOSCreateMarkerRecovery
from ios.self_tests.test_ios_assets_marker_namespace import AssetsMarkerNamespaceTests
from ios.self_tests.assets_marker_scope_fixture import AssetsMarkerDomain


class AssetsMarkerScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AssetsMarkerNamespaceTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.old=self.fixture.owner('create');self.old.once('retained-checkpoint-only',lambda:None)
        self.legacy=(self.old.store.path.stat().st_ino,self.old.store.path.read_bytes())
        self.scope=self.fixture.owner('assets');self.domain=AssetsMarkerDomain(self.scope)

    def test_original_marker_child_prepares_and_retires_without_touching_retained_create_metadata(self):
        admission=self.scope.prepare();self.assertEqual(self.domain.vm['added'][0]['id'],admission['marker']['id'])
        self.assertIn('script-file.confirm',self.domain.io.actions);self.assertTrue(self.domain.running)
        self.assertEqual('assetsMarker',self.scope.originals.schema_prefix);self.assertEqual(3,self.scope.store.read()['iosCreateMarkerScopeVersion'])
        self.domain.paint();self.scope.admit_rendered()
        archived=CreateMarkerScope.archive(self.scope.snapshot(),root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock,namespace='assets',require_ready=True)
        self.assertEqual(admission,archived.state['admission']);self.assertEqual(self.scope.frames,archived.frames)
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual('released',self.scope.state['phase'])
        self.assertFalse(self.domain.running);self.assertFalse(self.domain.files.root.exists())
        inputs=deepcopy(self.domain.io.actions);restored=self.fixture.owner('assets');self.domain.attach(restored)
        self.assertEqual({'performed':True},restored.cleanup());self.assertEqual(inputs,self.domain.io.actions)
        self.assertEqual(self.legacy,(self.old.store.path.stat().st_ino,self.old.store.path.read_bytes()))

    def test_lost_actual_stop_keeps_original_child_and_recovers_without_second_stop(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();activate=self.domain.io.activate;failure=NativeUIError('lost original Assets marker stop return')
        def lost(identifier,**kwargs):
            result=activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise failure
            return result
        with patch.object(self.domain.io,'activate',side_effect=lost),self.assertRaises(NativeUIError) as caught:self.scope.cleanup()
        self.assertIs(failure,caught.exception);self.assertEqual('stopping-marker',self.scope.state['phase']);self.assertFalse(self.domain.running)
        restored=self.fixture.owner('assets');self.domain.attach(restored)
        self.assertEqual({'performed':True},restored.cleanup());self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
        self.assertEqual('released',restored.state['phase']);self.assertEqual(self.legacy,(self.old.store.path.stat().st_ino,self.old.store.path.read_bytes()))

    def test_lost_passive_original_is_retained_in_profile_two_recovery_without_a_second_load(self):
        activate=self.domain.io.activate
        def loaded(identifier,**kwargs):
            result=activate(identifier,**kwargs)
            if identifier=='script-file.confirm':self.domain.web_failure=True
            return result
        with patch.object(self.domain.io,'activate',side_effect=loaded),self.assertRaises(OSError):self.scope.prepare()
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'));self.assertIsNotNone(self.scope.state['pending'])
        self.domain.web_failure=False;restored=self.fixture.owner('assets');self.domain.attach(restored)
        admission=restored.prepare();recovery=IOSCreateMarkerRecovery(restored)
        self.assertTrue(recovery.state['records']);self.assertEqual(2,recovery.store.read()['iosCreateMarkerRecoveryVersion'])
        retained=recovery.record(recovery.state['records'][0]);self.assertEqual(2,retained['iosCreateMarkerAbandonedReadVersion'])
        self.assertEqual(3,retained['priorOwner']['iosCreateMarkerScopeVersion']);self.assertTrue(retained['priorOwner']['scopeNamespace']=='assets')
        self.assertEqual(self.domain.vm['added'][0]['id'],admission['marker']['id']);self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'))
        self.domain.paint();restored.admit_rendered();self.assertEqual({'performed':True},restored.cleanup())
        self.assertEqual(self.legacy,(self.old.store.path.stat().st_ino,self.old.store.path.read_bytes()))
