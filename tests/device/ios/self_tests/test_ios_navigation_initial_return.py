"""Actual initial-process return input; restored-source admission stays closed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_whole_feature as fixture
from navigation_observation import viewpoint_urls


class NavigationInitialReturnTests(unittest.TestCase):
    setUp=fixture.NavigationWholeFeatureTests.setUp

    def test_original_process_return_uses_its_existing_one_send_child_and_keeps_historical_roots(self):
        h=self.h;self.whole.prepare();binding=deepcopy(h.binding)
        self.assertEqual({'performed':True},h.flow.return_to_original())
        store=PrivateFeatureState(h.flow.store.path.with_name('ios-navigation-scene-inputs.json'))
        original=store.read();state=unpack(original['payload'])[0]
        self.assertEqual('return-delivered',state['phase']);self.assertEqual(binding,original['binding'])
        with h.flow.held():wanted=viewpoint_urls(h.flow.initial_owner().archive()['base']['url'])['A']
        self.assertEqual(wanted,h.flow_fixture.b.current)
        self.assertFalse(state['returnedUi']['navigationInventory']['roots'][0]['visible'])
        calls=deepcopy(h.flow_fixture.b.calls)
        self.assertEqual({'performed':True},h.flow.return_to_original());self.assertEqual(calls,h.flow_fixture.b.calls)
        self.assertEqual(original,store.read());self.assertEqual(0,h.flow.state['stage'])

    def test_lost_complete_original_process_return_adopts_real_child_without_resending_go(self):
        h=self.h;self.whole.prepare();factory=h.flow.runtime._navigation_scene_inputs
        def losing(*args):
            child=factory(*args);write=child.store.write
            def save(value,previous):
                if unpack(value['payload'])[0]['phase']=='return-delivered':raise OSError('Modeled lost parent return')
                return write(value,previous)
            child.store.write=save;return child
        with patch.object(h.flow.runtime,'_navigation_scene_inputs',side_effect=losing),self.assertRaises(OSError):h.flow.return_to_original()
        calls=deepcopy(h.flow_fixture.b.calls)
        self.assertEqual({'performed':True},h.flow.return_to_original());self.assertEqual(calls,h.flow_fixture.b.calls)
        state=unpack(PrivateFeatureState(h.flow.store.path.with_name('ios-navigation-scene-inputs.json')).read()['payload'])[0]
        self.assertEqual('return-delivered',state['phase'])


if __name__=='__main__':unittest.main()
