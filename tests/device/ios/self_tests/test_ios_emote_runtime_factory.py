"""Exact private runtime construction, without session creation or native calls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.test_ios_emote_sources import RUN


class RuntimeFactoryTests(unittest.TestCase):
    def test_roles_keep_actual_target_selectors_roots_policy_and_sdk_lock_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700)
            runtime=object.__new__(IOSEmoteRuntime)
            runtime.state_path=lambda selector:root/selector/'session.json'
            policy=dict(source='world-render-target',marker=[0,0,256,64],subject=[0,64,640,400])
            client=Client('http://controlled.invalid/feature-fixture/v1','a'*64)
            primary=runtime._emote_feature('primary',RUN,role='primary',client=client,
                settings=dict(artifactRoot=str(root),imagePolicy=policy,actorTarget='actor'))
            actor=runtime._emote_feature('actor',RUN,role='actor',client=client,
                settings=dict(artifactRoot=str(root),imagePolicy=policy,primaryTarget='primary'))
            self.assertIsInstance(primary,IOSEmoteFeature);self.assertEqual('actor',primary.actor_selector)
            self.assertEqual('primary',actor.primary_selector);self.assertIs(primary.lock,primary.primary_lock)
            self.assertEqual(primary.lock.path,actor.primary_lock.path);self.assertNotEqual(actor.lock.path,actor.primary_lock.path)
            self.assertEqual(policy,actor.policy);self.assertEqual(root,actor.root)
            self.assertEqual([],list(root.iterdir()))
            with self.assertRaises(NativeUIError):runtime._emote_feature('actor',RUN,role='actor',client=client,
                settings=dict(artifactRoot=str(root),imagePolicy=policy,primaryTarget='actor'))
