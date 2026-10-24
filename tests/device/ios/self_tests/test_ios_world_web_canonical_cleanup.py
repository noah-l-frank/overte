"""Canonical cleanup refuses incomplete original World Web end ownership.

These are SDK/Node-free real private-file and role-lock cases. The separate
normal Whole test qualifies the actual composed original end decoder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_finalization import retire_existing
from ios.self_tests import test_ios_world_web_runtime as fixture


class WorldWebCanonicalCleanupTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_absence_returns_none_without_candidate_sdk_or_fixture_calls(self):
        self.assertIsNone(retire_existing(self.f.runtime,'actor',None,None))
        self.assertEqual([],self.f.checked)

    def test_lost_owner_with_actual_retained_carrier_blocks_fallback_cleanup(self):
        path=self.f.root/'actor'/'ios-world-web-actor-sources.json'
        value=dict(explicitInterruptedOriginal='owned')
        PrivateFeatureState(path).write(value,None)
        with self.assertRaises(NativeUIError):retire_existing(self.f.runtime,'actor',None,None)
        self.assertEqual(value,PrivateFeatureState(path).read());self.assertEqual([],self.f.checked)

    def test_unfinished_actual_coordinator_cannot_start_a_live_finalizer(self):
        flow=self.f.coordinator();original=flow.store.read()
        with self.assertRaises(NativeUIError):retire_existing(self.f.runtime,'actor',None,None)
        self.assertEqual(original,flow.store.read());self.assertEqual([],self.f.checked)
        self.assertIsNone(flow.lock._owner);self.assertIsNone(flow.primary_lock._owner)

    def test_retired_phase_label_without_full_terminal_originals_remains_owned(self):
        flow=self.f.coordinator()
        with flow.held():flow.state['phase']='retired';flow.save()
        original=flow.store.read()
        with self.assertRaises(NativeUIError):retire_existing(self.f.runtime,'actor',None,None)
        self.assertEqual(original,flow.store.read());self.assertEqual(1,len(self.f.checked))
        self.assertIsNone(flow.lock._owner);self.assertIsNone(flow.primary_lock._owner)

    def retired(self):
        flow=self.f.coordinator()
        with flow.held():flow.state['phase']='retired';flow.save()
        return flow

    def test_complete_label_with_pending_recovery_never_enters_decoder_or_writes(self):
        # Explicit terminal-constructor boundary model: no native/end verdict
        # is supplied by this test. The guard must precede even finish/recover.
        flow=self.retired();original=flow.store.read()
        terminal=SimpleNamespace(state=dict(phase='complete',seal={},end={},records=[{},{}],pending=dict(phase='saved')),
            finish=Mock(side_effect=AssertionError('Canonical cleanup entered metadata recovery')))
        with patch('ios.adapters.world_web_terminal.WorldWebTerminal',return_value=terminal):
            with self.assertRaises(NativeUIError):retire_existing(self.f.runtime,'actor',None,None)
        terminal.finish.assert_not_called();self.assertEqual(original,flow.store.read())

    def test_candidate_change_only_after_decoder_is_refused_without_outward_success(self):
        # Only the terminal decoder is a sentinel here. Actual candidate scope
        # reads surround it; the separate retained-end test checks real graphs.
        flow=self.retired();original=flow.store.read();calls=[];changed=[False]
        def candidate(target,scope):
            calls.append((target,deepcopy(scope)))
            if changed[0]:raise NativeUIError('Actual candidate changed during historical validation')
            return dict(explicitCandidateBoundary=True)
        terminal=SimpleNamespace(state=dict(phase='complete',seal={},end={},records=[{},{},{}],pending=None))
        def decoded(_seal):changed[0]=True;return dict(stage='finish',end={})
        terminal.finish=Mock(side_effect=decoded)
        with patch.object(self.f.runtime.adapter,'_retired_candidate_scope',side_effect=candidate),patch(
                'ios.adapters.world_web_terminal.WorldWebTerminal',return_value=terminal):
            with self.assertRaises(NativeUIError):retire_existing(self.f.runtime,'actor',None,None)
        self.assertEqual(2,len(calls));self.assertEqual(calls[0],calls[1]);self.assertEqual('actor',calls[0][0])
        self.assertNotIn('processIdentity',calls[0][1]);terminal.finish.assert_called_once()
        self.assertEqual(original,flow.store.read())


if __name__=='__main__':unittest.main()
