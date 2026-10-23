"""Preflight the SDK boundary before the separate long connected whole case."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
import uuid
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests.navigation_end_fixture import EndBoundary
from ios.self_tests import test_ios_navigation_whole_feature as fixture


class NavigationConnectedEndPreflightTests(unittest.TestCase):
    setUp=fixture.NavigationWholeFeatureTests.setUp

    def test_real_existing_whole_binding_gets_own_sdk_gate_before_first_new_bundle_response(self):
        self.whole.prepare();h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'cleanup',{})
        # No live seal is qualified by this fixture preflight. The long case
        # supplies the actual independently validated NavigationTerminal graph.
        terminal=SimpleNamespace(state=dict(description=dict(ticket=ticket)))
        with h.flow.held():
            h.flow.load();before=deepcopy(h.flow.state['binding']);previous=deepcopy(h.flow.previous)
            bridge=EndBoundary(self,connected=dict(flow=h.flow,terminal=terminal,world=h))
            source=IOSGraphicsRuntime._graphics_final_source(h.flow.runtime,h.flow.selector,before)
            client,session,sdk,_target,scope=h.flow.runtime._existing(h.flow.selector)
            self.assertEqual(before['sessionId'],session);self.assertEqual(before['processIdentity'],str(bridge.installed.process['pid']))
            self.assertEqual({key:value for key,value in before.items() if key!='processIdentity'},scope)
            self.assertEqual(sdk,bridge.sdk.read());self.assertEqual(h.flow.runtime.state_path(h.flow.selector),bridge.sdk.path)
            self.assertEqual(source,bridge.installed.source);self.assertEqual(previous,h.flow.store.read());self.assertEqual(0,bridge.stops)


if __name__=='__main__':unittest.main()
