"""Canonical owned prerequisites; image capture remains separately tested.

SDK/installed/candidate boundaries are explicit models. These constructor
cases never start setup, native acquisition, a service, compiler or device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.adapters.assets_image_sample import AssetsImageSample
from ios.self_tests.assets_runtime_fixture import RuntimeBoundary
from ios.self_tests.assets_usage_backend_fixture import Fixture
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL

REQUEST='ios-'+'7'*32


class AssetsImageSampleFactoryTests(unittest.TestCase):
    def setUp(self):
        self.b=RuntimeBoundary(self);temporary=tempfile.TemporaryDirectory(dir=self.b.root);self.addCleanup(temporary.cleanup)
        path=Path(temporary.name);path.chmod(0o700);self.backend=Fixture(path);self.addCleanup(self.backend.close)
        self.parts=self.b.runtime._assets_parsed_components('test-only',RUN,'primary',URL,self.b.lock,self.backend.backend.config)
        self.marker=self.b.runtime._assets_marker_components('test-only',RUN,'primary',URL,TICKET,self.b.root,self.b.lock)['marker']
    def owner(self,*,pid=None):
        b=self.b;parts=self.parts;observer,clock=parts['observer'],parts['clock_source']
        frame=VulkanWorldFrameOwner(PrivateFeatureState(b.root/('graphics-world-frame-primary-0-'+REQUEST[4:]+'.json')),
            b.root,parts['binding'],RUN,'primary',0,REQUEST,observer.vulkan_world_frame,parts['check'],source_lock=b.lock,
            monotonic=b.runtime.monotonic,sleep=observer.sleep)
        models=observer.assets_model_renderers(clock)
        if pid is not None:models.pid=pid
        return AssetsImageSample(PrivateFeatureState(b.root/('ios-assets-image-'+RUN+'-primary-'+REQUEST[4:]+'.json')),
            b.lock,parts['binding'],RUN,REQUEST,parts['check'],parsed=parts['parsed'],marker=self.marker,
            native=observer.bound_native_observer(clock),state=observer.create_state(clock),models=models,avatars=observer.avatar_renderers(clock),
            frame_owner=frame,epoch_ms=b.runtime.epoch_ms,monotonic=b.runtime.monotonic)
    def test_actual_factories_bind_existing_owners_and_source_clocks_before_any_acquisition(self):
        b=self.b;count=len(b.f.clock.commands);owner=self.owner()
        self.assertIs(self.parts['parsed'],owner.parsed);self.assertIs(self.marker,owner.marker)
        self.assertEqual('primary',owner.role);self.assertEqual(REQUEST,owner.frame_owner.request_id)
        self.assertEqual('assets-image-native',owner.raws.store.namespace);self.assertEqual('assets-image-source',owner.frames.namespace)
        self.assertIsNone(owner.state);self.assertIsNone(owner.store.read());self.assertIsNone(owner.frame_owner.store.read())
        self.assertEqual(count,len(b.f.clock.commands));self.assertEqual([],b.asset_requests)
    def test_unobserved_parser_and_marker_cannot_reserve_or_start_an_image(self):
        owner=self.owner();count=len(self.b.f.clock.commands)
        with self.assertRaises((NativeUIError,ValueError)):owner.capture(TICKET,1900000000000)
        self.assertIsNone(owner.store.read());self.assertIsNone(owner.frame_owner.store.read())
        self.assertEqual([],self.b.asset_requests);self.assertEqual(count,len(self.b.f.clock.commands))
    def test_foreign_source_pid_is_rejected_before_any_source_or_png_command(self):
        count=len(self.b.f.clock.commands)
        with self.assertRaises(NativeUIError):self.owner(pid=43)
        self.assertEqual(count,len(self.b.f.clock.commands));self.assertEqual([],self.b.asset_requests)
