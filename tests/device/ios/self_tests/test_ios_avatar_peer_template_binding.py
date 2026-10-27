"""Actual peer-view construction and caller guards, without Final facts.

The boundary stops before decoding the explicitly modeled metadata. No native
observation, independent peer fact, Final proof or cleanup verdict is supplied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters import avatar_operation_clock
from ios.self_tests import test_ios_avatar_feature as fixture


class _TemplateBoundaryReached(Exception):pass


class AvatarPeerTemplateBindingTests(unittest.TestCase):
    def inspect_template(self,role,method,*,check_guard=False):
        self.f=fixture.AvatarFeatureLocksTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        caller=self.f.owner(role);other='actor' if role=='primary' else 'primary';peer=self.f.owner(other)
        bindings={subject:dict(sessionId=subject) for subject in ('primary','actor')}
        caller.state=dict(cleanup=[dict(kind='admission',operationClock=avatar_operation_clock.begin(caller.epoch_ms(),caller.monotonic()))],
            bindings=bindings)
        # This test reaches construction only. The real metadata decoder and
        # every Final proof remain outside this deliberately stopped boundary.
        raw=peer.envelope(dict(modeledMetadataBoundary=True));peer.store.write(raw,None)
        caller.load=lambda:None;visited=[]
        self.f.runtime.adapter.state_path=self.f.runtime.state_path
        def inspect(actual):
            visited.append(actual)
            self.assertIs(actual.runtime,caller.runtime);self.assertEqual(other,actual.role)
            self.assertEqual(peer.selector,actual.selector);self.assertNotEqual(caller.selector,actual.selector)
            self.assertEqual(actual.selectors[actual.role],actual.selector)
            self.assertEqual(caller.runtime.state_path(actual.selector).parent,actual.store.path.parent)
            self.assertEqual(peer.store.path,actual.store.path);self.assertIs(actual.lock,caller.locks[other])
            self.assertEqual(peer.root,actual.root);self.assertEqual(peer.policy,actual.policy)
            self.assertEqual(caller.run,actual.run);self.assertIs(actual.phase,caller.phase)
            self.assertEqual(raw,actual.store.read())
            if check_guard:
                self.assertIs(actual.client,caller.client);self.assertIs(actual.authority,caller.authority)
                self.assertIs(actual.locks,caller.locks)
                actual.state=dict(bindings=deepcopy(bindings),cleanup=[]);actual.previous=deepcopy(raw)
                owner=SimpleNamespace(VERSION=2,run=actual.run,role=other,root=actual.root,
                    bindings=deepcopy(bindings),locks=actual.locks)
                unchanged=actual.final_source_guard({},owner);self.assertTrue(unchanged())
                actual.selector=caller.selector
                with self.assertRaises(NativeUIError):unchanged()
            raise _TemplateBoundaryReached()
        with patch.object(IOSAvatarFeature,'load',inspect),self.assertRaises(_TemplateBoundaryReached):
            getattr(caller,method)()
        self.assertEqual(1,len(visited))

    def test_both_peer_views_bind_independent_selector_before_metadata_decode(self):
        for role in ('primary','actor'):
            for method in ('wait_peer_checkpoint','wait_peer_final'):
                with self.subTest(role=role,method=method):self.inspect_template(role,method)

    def test_final_peer_selector_remains_in_the_actual_caller_guard(self):
        for role in ('primary','actor'):
            with self.subTest(role=role):self.inspect_template(role,'wait_peer_final',check_guard=True)


if __name__=='__main__':unittest.main()
