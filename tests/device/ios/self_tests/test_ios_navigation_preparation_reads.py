"""Real interrupted baseline/GPU/file journals with explicit native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.adapters.navigation_preparation_reads import inspect
from ios.self_tests import test_ios_navigation_whole_preparation as fixtures


class NavigationPreparationReadsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NavigationWholePreparationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.h=self.fixture.h;self.flow=self.fixture.flow

    def interrupted(self,key):
        factory=self.flow.runtime._navigation_baseline_image;lost=[]
        def image(*args,**kwargs):
            owner=factory(*args,**kwargs);take=owner.take
            def actual(name,callback):
                result=take(name,callback)
                if name==key and not lost:lost.append(True);raise OSError('Original baseline child return lost')
                return result
            owner.take=actual;return owner
        self.flow.runtime._navigation_baseline_image=image
        with self.assertRaises((OSError,NativeUIError)):self.fixture.owner().prepare()
        self.flow.runtime._navigation_baseline_image=factory

    def test_actual_source_prefix_reopens_without_any_live_query_or_changed_parent(self):
        self.interrupted('base');commands=deepcopy(self.h.gpu.commands)
        with self.flow.held():
            parent=self.fixture.owner();parent.load();before=deepcopy(parent.previous)
            with patch.object(self.flow.runtime,'_sources',side_effect=AssertionError('Failed prefix attempted live source')):
                value=inspect(parent)
            self.assertEqual('failed-preparation-originals',value['status']);self.assertIsNone(value['baselines']['primary']['frame'])
            self.assertEqual(before,parent.store.read());self.assertIsNone(self.flow.store.read());self.assertEqual(commands,self.h.gpu.commands)

    def test_actual_captured_png_and_storage_prefix_remain_original_failed_evidence(self):
        self.interrupted('capture');commands=deepcopy(self.h.gpu.commands)
        with self.flow.held():
            parent=self.fixture.owner();value=inspect(parent);frame=value['baselines']['primary']['frame']
            self.assertIsNotNone(frame);self.assertEqual('released',frame['phase']);self.assertGreater(frame['file']['bytes'],0)
            self.assertEqual(commands,self.h.gpu.commands);self.assertIsNone(self.flow.store.read())
            parent.load();owner=parent.baseline('primary',historical=True);path=owner.root/owner.owner().name
            original=path.read_bytes();path.rename(path.with_suffix('.retained-original'));path.write_bytes(original);path.chmod(0o600)
            with self.assertRaises(NativeUIError):inspect(parent)

    def test_actual_empty_opened_file_is_retained_without_inventing_pixels_or_a_capture(self):
        write=VulkanWorldFrameOwner._write
        def opened(owner,value=None):
            write(owner,value)
            if owner.state['phase']=='opened':raise OSError('Actual opened-file return lost')
        with patch.object(VulkanWorldFrameOwner,'_write',opened),self.assertRaises((NativeUIError,OSError)):
            self.fixture.owner().prepare()
        commands=deepcopy(self.h.gpu.commands)
        with self.flow.held():
            value=inspect(self.fixture.owner());frame=value['baselines']['primary']['frame']
            self.assertEqual('opened',frame['phase']);self.assertEqual(0,frame['file']['bytes'])
            self.assertEqual(commands,self.h.gpu.commands);self.assertEqual([],commands)
            self.assertIsNone(self.flow.store.read())


if __name__=='__main__':unittest.main()
