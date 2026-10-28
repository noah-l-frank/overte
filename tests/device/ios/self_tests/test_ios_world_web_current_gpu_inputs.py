"""Real current GPU WAL/PNG reads join the unchanged paired orphan census.

This constructs actual native-frame owner/file custody over a declared GPU
model. The sample object isolates custody wiring; no Source/Scene/end verdict
or native/process/device qualification is manufactured by these cases.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as reads_scope
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory
from ios.self_tests import test_ios_world_web_rooted_inventory as census_fixture
from self_tests.test_native_vulkan_world_frame import World
from self_tests.test_completed_frame_lease import BINDING,RUN

REQUEST='ios-'+'7'*32
TICKET='8'*32


class WorldWebCurrentGPUInputsTests(unittest.TestCase):
    def setUp(self):
        self.f=census_fixture.WorldWebRootedInventoryTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.lock=self.f.owner.flow.lock;self.native=World()
        self.store=PrivateFeatureState(self.lock.path.with_name('graphics-world-frame-primary-0-'+REQUEST[4:]+'.json'))
        def factory(intent,received):
            return NativeVulkanWorldFrame(self.native.send,self.native.original,self.native.epoch,lambda:self.native.okay,42,
                intent,receipt=received,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.frame=VulkanWorldFrameOwner(self.store,self.root,BINDING,RUN,'primary',0,REQUEST,factory,lambda:self.native.okay,
            source_lock=self.lock,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.sample=object.__new__(WorldWebSample)
        self.sample.frame_owner,self.sample.lock,self.sample.binding=self.frame,self.lock,deepcopy(BINDING)
        self.sample.run,self.sample.role,self.sample.request=RUN,'primary',REQUEST
        self.sample.store=PrivateFeatureState(self.lock.path.with_name('ios-world-web-primary-'+REQUEST[4:]+'-sample.json'))
    def captured(self):
        self.frame.capture(TICKET);self.frame.release();return self.store.read()
    def test_real_owner_and_png_reads_admit_only_their_existing_custody_without_native_calls(self):
        expected=self.captured();commands=deepcopy(self.native.commands)
        self.frame.guard=self.frame.factory=lambda *_args:(_ for _ in ()).throw(AssertionError('Passive custody must not query native'))
        with reads_scope(fresh=True) as reads:
            returned=self.sample.current_owner_original(expected)
            self.assertEqual(expected,returned);returned['ticket']='changed outward copy'
            self.assertEqual(expected,self.sample.current_owner_original(expected))
            self.assertIn(self.store.path,reads);self.assertIn(self.root/self.frame.name,reads)
            WorldWebRootedInventory(self.f.owner,reads).guard()
        self.assertEqual(commands,self.native.commands);self.assertEqual(expected,self.store.read())
    def test_actual_gpu_head_must_equal_the_specific_last_retirement_original(self):
        expected=self.captured();wrong=deepcopy(expected);wrong['ticket']='9'*32
        with self.assertRaises(NativeUIError):self.sample.current_owner_original(wrong)
        self.assertEqual(expected,self.store.read())
    def test_same_inode_same_body_rewrite_during_actual_decode_cannot_refresh_the_original_pin(self):
        expected=self.captured();read=PrivateFeatureState.read;changed=[]
        def reread(store):
            value=read(store)
            if store.path==self.store.path and not changed:
                changed.append(True);before=store.path.stat();raw=store.path.read_bytes();time.sleep(.002)
                store.path.write_bytes(raw);os.utime(store.path,ns=(before.st_atime_ns,before.st_mtime_ns))
                self.assertEqual(before.st_ino,store.path.stat().st_ino);self.assertEqual(raw,store.path.read_bytes())
            return value
        with patch.object(PrivateFeatureState,'read',reread),self.assertRaises(NativeUIError):self.sample.current_owner_original(expected)
        self.assertEqual([True],changed)
    def test_same_byte_png_on_another_inode_does_not_satisfy_the_retained_gpu_file(self):
        expected=self.captured();path=self.root/self.frame.name;raw=path.read_bytes();original=self.root/'retained-original.png'
        path.rename(original);path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(original.stat().st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.sample.current_owner_original(expected)
        self.assertEqual(raw,original.read_bytes());self.assertEqual(raw,path.read_bytes())
    def test_extra_gpu_head_is_not_admitted_by_reading_the_known_owner(self):
        expected=self.captured();orphan=PrivateFeatureState(self.store.path.with_name('graphics-world-frame-primary-0-orphan.json'))
        value=dict(untrustedOrphanResponsibility=True);orphan.write(value,None)
        with reads_scope(fresh=True) as reads:
            self.sample.current_owner_original(expected);self.assertNotIn(orphan.path,reads)
            with self.assertRaises(NativeUIError):WorldWebRootedInventory(self.f.owner,reads)
        self.assertEqual(value,orphan.read())
    def test_released_partial_artifact_is_read_as_custody_without_fabricating_image_success(self):
        send=self.native.send
        def lost(query):
            send(query)
            if query['operation']=='read':raise OSError('Declared lost native capture response')
        self.native.send=lost
        with self.assertRaises(NativeUIError):self.frame.capture(TICKET)
        self.native.send=send;self.frame.release();expected=self.store.read();commands=deepcopy(self.native.commands)
        self.assertIsNone(expected['frame']);self.assertEqual(0,(self.root/self.frame.name).stat().st_size)
        with reads_scope(fresh=True) as reads:
            self.assertEqual(expected,self.sample.current_owner_original(expected))
            self.assertIn(self.root/self.frame.name,reads);WorldWebRootedInventory(self.f.owner,reads).guard()
        self.assertEqual(commands,self.native.commands)


if __name__=='__main__':unittest.main()
