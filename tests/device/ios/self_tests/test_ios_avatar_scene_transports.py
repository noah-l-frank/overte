"""Actual Avatar factory shares one original clock across passive transports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_marker_file_receipts import OriginalMarkerFileReceipts
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_scene_transports import owners
from ios.adapters.world_web_files import OwnedWorldWebFiles
from ios.self_tests import test_ios_avatar_scene_receipts as fixture
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class WorldWebFiles(OriginalMarkerFileReceipts):PROFILE='worldweb'


class AvatarSceneTransportTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarSceneReceiptTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_actual_factory_owns_inner_file_clock_queries_and_pointer_uses_same_native_original_reader(self):
        f=self.f;clock=f.clock();scope=object.__new__(IOSAvatarMarkerScope)
        scope.root,scope.binding,scope.run,scope.role,scope.lock,scope.guard=f.root,BINDING,RUN,'primary',f.lock,lambda:True
        scope.bound=lambda:f.lock.assert_held();pointer=f.qt.reader();pointer.pid=31
        def pointer_reader(given):
            self.assertIs(clock,given);pointer.clock_ms=lambda:clock.read(clock.sequence)['capturedEpochMs'];return pointer
        actual=dict(binding=BINDING,clock_source=clock,observer=SimpleNamespace(script_fixture_files=lambda:f.files,pointer_state=pointer_reader))
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,_selector):return f.root/'session.json'
            def _sources(_self,_selector):return actual
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))
        receipts=owners(runtime,'target',scope,epoch_ms=lambda:90000.,monotonic=lambda:0.)
        self.assertIsNot(receipts['files'].files,f.files);self.assertEqual(f.files.clock_ms(),20000)
        first=receipts['files'].capture('bytes',f.ownership);raw=receipts['files'].original(first)
        self.assertGreaterEqual(len(raw['nativeQueries']),4)
        count=len(f.native.commands);ref=receipts['pointers'].capture();packet=receipts['pointers'].original(ref)
        self.assertGreaterEqual(len(packet['nativeQueries']),4);self.assertEqual(len(packet['nativeQueries']),len(f.native.commands)-count)

    def test_worldweb_profile_reads_its_actual_pinned_four_files_and_original_native_absence(self):
        f=self.f;f.owned.release();owned=OwnedWorldWebFiles(f.files,PrivateFeatureState(f.root/'world-web-owned.json'),BINDING)
        ownership=owned.reserve_web(RUN,'http://fixture.invalid/feature-fixture/v1/runs/'+RUN+'/','a'*32);owned.stage_reserved()
        owner=WorldWebFiles(PrivateFeatureState(f.root/'ios-world-web-primary-file-receipts.json'),f.root,BINDING,RUN,'primary',f.lock,
            lambda:True,native=f.clock(),files=f.files,epoch_ms=lambda:90000.,monotonic=lambda:0.)
        first=owner.capture('bytes',ownership);actual=owner.original(first)
        self.assertEqual(1,actual['iosWorldWebNativeFileReceiptVersion']);self.assertTrue(owner.record_store(1).path.name.startswith('world-web-native-files-'))
        wrong=deepcopy(actual);wrong['ownership']['baseSourceSha256']='f'*64
        with self.assertRaises(NativeUIError):owner.receipt(wrong,root=f.root,binding=BINDING,run=RUN,role='primary')
        owned.release();last=owner.capture('absent',ownership)
        self.assertEqual(dict(exists=False,files=[]),owner.original(last)['packet']['source'])


if __name__=='__main__':unittest.main()
