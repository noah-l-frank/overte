"""An older complete native proof cannot retire later copied input owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_final_inputs import validate
from ios.self_tests import test_ios_emote_retirement as retirement_fixture


class FinalInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture=retirement_fixture.RetirementTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.owner=f.owner();self.reference=self.owner.retain(f.original)
        self.native=self.owner.original(self.reference)
        self.final=SimpleNamespace(flow=SimpleNamespace(role='primary'),path=lambda name:PrivateFeatureState(f.root/name))
        self.copies={str(self.final.path(name).path):None for name in ('ios-emote-primary-marker-files.json',
            'ios-emote-primary-marker-script.json','ios-emote-cleanup-inputs.json','ios-emote-inputs.json','ios-emote-background.json')}

    def test_matching_current_inputs_reuse_only_the_actually_proved_native_original(self):
        before=len(self.fixture.domain.history)
        self.assertTrue(validate(self.final,self.copies,self.native))
        self.assertEqual(before,len(self.fixture.domain.history))
        self.assertEqual([],self.owner.derive(self.reference)['public']['resources'])

    def test_later_pending_input_or_reappeared_child_remains_owned_despite_old_valid_native_proof(self):
        before=len(self.fixture.domain.history)
        for path in self.copies:
            changed=deepcopy(self.copies);changed[path]=dict(actual='later unresolved ownership')
            with self.subTest(path=path),self.assertRaises(NativeUIError):validate(self.final,changed,self.native)
        self.assertEqual(before,len(self.fixture.domain.history))
        self.assertEqual(self.native,self.owner.original(self.reference))
