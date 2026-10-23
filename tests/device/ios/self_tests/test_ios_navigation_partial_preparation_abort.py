"""Actual failed baseline/GPU/PNG originals joined to modeled OS/SDK end.

No source packet or retained parent is rewritten to construct a failure. Lost
returns are injected at the real operation boundary, before scene entry.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.adapters import appium_adapter as backend
from ios.adapters.navigation_partial_preparation_abort import owner as abort_owner
from ios.adapters.navigation_preparation_abort import NavigationPreparationAbort
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_failed_preparation_cleanup import verify
from ios.adapters.navigation_session_cleanup import retire_existing
from ios.adapters import feature_configuration as config
from ios.self_tests.navigation_end_fixture import EndBoundary
from ios.self_tests import test_ios_navigation_whole_preparation as fixtures


class NavigationPartialPreparationAbortTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NavigationWholePreparationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.flow=self.fixture.flow;self.h=self.fixture.h;self.whole=NavigationWholeFeature(self.flow)

    def interrupt(self,key,*,role='primary'):
        factory=self.flow.runtime._navigation_baseline_image;lost=[]
        def image(*args,**kwargs):
            child=factory(*args,**kwargs);take=child.take
            def actual(name,callback):
                value=take(name,callback)
                if name==key and child.role==role and not lost:
                    lost.append(True);raise OSError('Actual interrupted baseline return')
                return value
            child.take=actual;return child
        self.flow.runtime._navigation_baseline_image=image
        with self.assertRaises((OSError,NativeUIError)):self.whole.prepare()
        self.flow.runtime._navigation_baseline_image=factory
        self.assertTrue(lost)

    def finish_originals(self,*,public=False,generic=False,lost_stop=False):
        f=self.flow
        # The independent OS/SDK model is initialized for this actual original
        # binding before its first response. No failed source is converted.
        with f.held():bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
        call=dict(contractVersion=16,runId=f.run)
        if generic:
            constructor=f.runtime._navigation_feature
            def modeled_factory(*args,**kwargs):
                whole=constructor(*args,**kwargs);flow=whole.flow
                flow.epoch_ms=f.epoch_ms;flow.monotonic=f.monotonic;flow.sleep=f.sleep
                flow.lock=f.lock;whole.lock=f.lock
                return whole
            f.runtime._navigation_feature=modeled_factory
        with f.held():
            original={p:(p.stat().st_ino,p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
            commands=deepcopy(self.h.gpu.commands)
            with self.assertRaises(NativeUIError):NavigationPreparationAbort(f)
            if public:
                if lost_stop:
                    bridge.stop_lost=True
                    with self.assertRaises((OSError,RuntimeError,ValueError)):self.whole.cleanup(call)
                    self.assertEqual(1,bridge.stops)
                    with self.assertRaises(NativeUIError):self.whole.prepare()
                    bridge.stop_lost=False
                self.assertEqual({'performed':True},self.whole.cleanup(call));owner=abort_owner(f);result=owner.result()
                self.assertTrue(verify(self.whole,call,{'performed':True}))
            elif generic:
                # The explicit reader supplies the already authenticated real
                # loopback client; configuration validation stays production.
                value=dict(iosFeatureAdapterVersion=5,areas=['world-navigation'],fixtureConfig=str(f.root/'private-fixture.json'),
                    graphics=None,create=None,emotes=None,worldNavigation=dict(artifactRoot=str(f.root)),avatarPeople=None,worldWeb=None,tabletWeb=None)
                # This model keeps its exact source lock across the common
                # audit scope and the real nested generic cleanup entry.
                with patch.object(config,'reader',return_value=f.client):self.assertEqual({'cleaned':True},retire_existing(f.runtime,f.selector,value))
                owner=abort_owner(f);result=owner.result()
            else:owner=abort_owner(f);result=owner.finish()
            self.assertEqual(2,result['iosNavigationPreparationAbortResultVersion']);self.assertEqual('failed',result['status'])
            self.assertEqual(1,bridge.stops);self.assertEqual(1,sum(method=='DELETE' for method,_ in bridge.requests))
            self.assertIsNone(f.store.read());self.assertIsNone(bridge.sdk.read());self.assertIsNone(bridge.installed.store.read())
            # Only exact SDK/installed model metadata may retire; every failed
            # source, PNG, GPU journal and parent remains on its original inode.
            mutable={bridge.sdk.path,bridge.installed.store.path}
            for path,signature in original.items():
                if path not in mutable:self.assertEqual(signature,(path.stat().st_ino,path.read_bytes()))
            requests=deepcopy(bridge.requests)
            def forbidden(*_args,**_kwargs):self.fail('Historical failed cleanup attempted live transport')
            with patch.object(f.runtime,'_sources',side_effect=forbidden),patch.object(f.client,'request',side_effect=forbidden),patch.object(backend.WebDriver,'call',side_effect=forbidden):
                self.assertEqual(result,abort_owner(f).result())
                if public:self.assertTrue(verify(self.whole,call,{'performed':True}))
                if generic:self.assertEqual({'cleaned':True},retire_existing(f.runtime,f.selector,None))
            self.assertEqual(requests,bridge.requests);self.assertEqual(commands,self.h.gpu.commands)
            return owner,result

    def test_actual_interrupted_source_prefix_ends_once_without_reissuing_the_query(self):
        self.interrupt('base');self.finish_originals()

    def test_actual_png_and_released_storage_remain_failed_originals_after_process_end(self):
        self.interrupt('capture');self.finish_originals()

    def test_actor_failure_keeps_the_completed_primary_baseline_and_both_role_prefixes(self):
        self.interrupt('base',role='actor');self.finish_originals()

    def test_real_empty_opened_png_needs_no_capture_or_successful_pixels_to_end_process(self):
        write=VulkanWorldFrameOwner._write
        def opened(child,value=None):
            write(child,value)
            if child.state['phase']=='opened':raise OSError('Actual empty opened file return lost')
        with patch.object(VulkanWorldFrameOwner,'_write',opened),self.assertRaises((NativeUIError,OSError)):self.whole.prepare()
        self.assertEqual([],self.h.gpu.commands);self.finish_originals()

    def test_public_cleanup_bypasses_failed_capture_and_checks_original_end_without_live_sdk(self):
        self.interrupt('base');self.finish_originals(public=True)

    def test_public_unknown_stop_cannot_reenter_preparation_or_send_stop_again(self):
        self.interrupt('capture');self.finish_originals(public=True,lost_stop=True)

    def test_generic_cleanup_joins_failed_originals_then_reopens_without_configuration_or_transport(self):
        self.interrupt('base');self.finish_originals(generic=True)

    def test_replaced_partial_png_cannot_authorize_the_first_stop(self):
        self.interrupt('capture')
        with self.flow.held():
            bridge=EndBoundary(self,connected=dict(flow=self.flow,world=self.h),preparing=True)
            preparation=self.fixture.owner();preparation.load();image=preparation.baseline('primary',historical=True)
            frame=image.owner();frame._load();path=frame.root/frame.name;raw=path.read_bytes()
            path.rename(path.with_suffix('.retained-original'));path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(NativeUIError):abort_owner(self.flow)
            self.assertEqual(0,bridge.stops);self.assertIsNotNone(bridge.sdk.read())

    def test_unresolved_abort_cannot_supply_public_success_or_forget_new_input_ownership(self):
        self.interrupt('base');f=self.flow
        with f.held():
            bridge=EndBoundary(self,connected=dict(flow=f,world=self.h),preparing=True)
            owner=abort_owner(f);before=owner.previous
            with self.assertRaises(NativeUIError):verify(self.whole,dict(contractVersion=16,runId=f.run),{'performed':True})
            self.assertEqual(before,owner.store.read())
            store=PrivateFeatureState(f.store.path.with_name('ios-navigation-address-unknown-inputs.json'));store.write(dict(uncertain=True),None)
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,bridge.stops);self.assertEqual(dict(uncertain=True),store.read())


if __name__=='__main__':unittest.main()
