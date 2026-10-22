"""Actual ordinary final Go To, loopback static bytes and durable no resend.

Qt/native/OS are physical models. Delivery never substitutes for restoration
or retained QML destruction, and no whole capability is inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_feature_transfer as transfer
from ios.self_tests.navigation_feature_next_ui_fixture import NextUI
from navigation_observation import viewpoint_urls


class NavigationFeatureReturnTests(unittest.TestCase):
    setUp=transfer.NavigationFeatureTransferTests.setUp
    action=transfer.NavigationFeatureTransferTests.action
    ready=transfer.NavigationFeatureTransferTests.ready
    restart_call=transfer.NavigationFeatureTransferTests.restart_call
    install=transfer.NavigationFeatureTransferTests.install

    def start(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call());self.ui=NextUI(self.new,self)
        return h

    def test_normal_return_fetches_actual_static_bytes_without_rewriting_admission_or_retiring_hidden_roots(self):
        h=self.start();initial=deepcopy(h.flow_fixture.f.admission.store.read())
        self.assertEqual({'performed':True},h.flow.return_to_original())
        b=self.ui.flow_fixture.b;wanted=viewpoint_urls(self.ui.base_url)['A']
        self.assertEqual(wanted,b.current);self.assertEqual(wanted,self.new.inventory.url)
        self.assertEqual(hashlib.sha256(self.new.inventory.body).hexdigest(),self.new.inventory.anchor['bodySha256'])
        self.assertFalse(self.new.sdk.navigation.source['challengeMarker']['present'])
        state=unpack(PrivateFeatureState(h.root/'ios-navigation-process-return-43.json').read()['payload'])[0]
        self.assertEqual('delivered',state['phase']);self.assertNotIn('restored',state)
        self.assertFalse(unpack(state['addressOwner']['payload'])[0]['rows'][-1]['closed']['drained'])
        calls=deepcopy(b.calls);self.assertEqual({'performed':True},h.flow_fixture.flow().return_to_original())
        self.assertEqual(calls,b.calls);self.assertEqual(initial,h.flow_fixture.f.admission.store.read())
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)

    def test_ignored_final_goto_ack_cannot_restore_the_actual_static_world_and_is_not_replayed(self):
        h=self.start();b=self.ui.flow_fixture.b;b.mutation='goto-ignored';original=self.new.inventory.anchor
        self.assertEqual({'performed':True},h.flow.return_to_original())
        self.assertNotEqual(viewpoint_urls(self.ui.base_url)['A'],b.current)
        self.assertEqual(original,self.new.inventory.anchor)
        self.assertTrue(self.new.sdk.navigation.source['challengeMarker']['present'])
        calls=deepcopy(b.calls);b.mutation=None
        self.assertEqual({'performed':True},h.flow_fixture.flow().return_to_original());self.assertEqual(calls,b.calls)
        self.assertTrue(self.new.sdk.navigation.source['challengeMarker']['present'])

    def test_lost_final_owner_write_adopts_only_complete_original_child_without_another_input(self):
        h=self.start();factory=h.runtime._navigation_process_return
        def losing(*args):
            child=factory(*args);write=child.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='delivered':raise OSError('Synthetic final return loss')
                return write(value,previous)
            child.store.write=lost;return child
        h.runtime._navigation_process_return=losing
        with self.assertRaises(OSError):h.flow.return_to_original()
        calls=deepcopy(self.ui.flow_fixture.b.calls);h.runtime._navigation_process_return=factory
        self.assertEqual({'performed':True},h.flow_fixture.flow().return_to_original())
        self.assertEqual(calls,self.ui.flow_fixture.b.calls)
        state=unpack(PrivateFeatureState(h.root/'ios-navigation-process-return-43.json').read()['payload'])[0]
        self.assertEqual('delivered',state['phase'])


if __name__=='__main__':unittest.main()
