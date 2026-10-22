"""Full original static process restoration plus independently sampled inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_quiet_image import NavigationQuietImage
from ios.adapters.navigation_quiet_period import compose
from ios.self_tests import test_ios_navigation_static_comparison as static
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from ios.adapters.pointer_state import IOSPointerState


class NavigationQuietPeriodTests(unittest.TestCase):
    setUp=static.NavigationStaticComparisonTests.setUp
    acquire=static.NavigationStaticComparisonTests.acquire
    action=static.NavigationStaticComparisonTests.action
    ready=static.NavigationStaticComparisonTests.ready
    restart_call=static.NavigationStaticComparisonTests.restart_call
    install=static.NavigationStaticComparisonTests.install

    def inputs(self,call):
        h=self.h;sdk=self.new.sdk
        class Domain:
            @property
            def time(_):return sdk.gpu.clock
            @time.setter
            def time(_,value):sdk.gpu.clock=value
            def epoch(_):return sdk.gpu.epoch()
            def sleep(_,delay):sdk.gpu.sleep(delay)
        self.domain=Domain();binding=call['process_context']['restart']['input']['newBinding']
        self.keys=KeyDomain(None,self.domain,binding=binding)
        class Pointer(NativePointerBoundary):
            def send(p,query):
                super().send(query);p.packet['processId']=43
        self.pointer=Pointer()
        def tick():sdk.gpu.clock+=.001;self.pointer.now=sdk.gpu.epoch();return self.pointer.now
        self.pointer.tick=tick;self.pointer.now=sdk.gpu.epoch()
        self.pointer_reader=IOSPointerState(self.pointer.send,self.pointer.original,sdk.gpu.epoch,lambda:sdk.okay,43,
            monotonic=h.mono,sleep=sdk.gpu.sleep)

    def owner(self,call,*,historical=False,request=None):
        h=self.h;request=request or 'ios-'+uuid.uuid4().hex
        return NavigationQuietImage(PrivateFeatureState(h.root/('ios-navigation-quiet-primary-'+request[4:]+'.json')),
            h.root,call['process_context']['restart']['input']['newBinding'],h.run,'primary',request,h.flow.lock,lambda:self.new.sdk.okay,
            native=None if historical else self.new.native,sources=None if historical else self.new.sources,
            fixture=None if historical else h.fixture,frame_factory=None if historical else self.new.gpu.factory,
            historical=historical,epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep,
            process_context=call['process_context'],owner_files=call['owner_files'],directory=call['directory'],previous=self.prior_owner,
            input_readers=None if historical else dict(keys=self.keys.reader(),pointer=self.pointer_reader,geometry=self.keys.geometry()))

    def test_original_images_keys_pointer_and_uikit_require_real_quiet_without_ending_hidden_root_responsibility(self):
        call=self.acquire();self.inputs(call);h=self.h
        with h.flow.held():
            rows=[]
            for index in range(3):
                if index:self.new.sdk.gpu.sleep(1.6)
                owner=self.owner(call);owner.acquire(h.now());rows.append(owner)
            baseline=self.baseline_fixture.owner(historical=True);admission=h.flow.initial_owner();transfer=h.flow.transferred_owner()
            proof=compose(rows,baseline,admission,transfer);self.assertTrue(proof['lifetimeEndRequired'])
            self.assertEqual(3,len(proof['originals']));self.assertTrue(all(row['changedPixels']==0 for row in proof['comparisons']))
            commands=deepcopy(self.keys.commands);pointer=deepcopy(self.pointer.requests)
            frozen=[self.owner(call,historical=True,request=owner.request) for owner in rows]
            self.assertEqual(proof,compose(frozen,baseline,admission,transfer))
            self.assertEqual(commands,self.keys.commands);self.assertEqual(pointer,self.pointer.requests)
            with self.assertRaises(NativeUIError):compose(rows[:2],baseline,admission,transfer)
            with self.assertRaises(NativeUIError):compose([rows[0],rows[1],rows[1]],baseline,admission,transfer)
            # A real later completed contact is drained, yet breaks this quiet
            # interval. No archived event or receipt is altered for the test.
            self.pointer.touch('touch-begin');self.pointer.touch('touch-end')
            late=self.owner(call);late.acquire(h.now())
            with self.assertRaises(NativeUIError):compose([rows[0],rows[1],late],baseline,admission,transfer)
            fast=[]
            for _ in range(3):
                owner=self.owner(call);owner.acquire(h.now());fast.append(owner)
            with self.assertRaises(NativeUIError):compose(fast,baseline,admission,transfer)
            self.keys.qt.finish(self.keys.qt.enter('key-press'));held=self.owner(call)
            with self.assertRaises(NativeUIError):held.acquire(h.now())
            self.assertIsNotNone(held.store.read());self.assertNotIn('retired',held.state)


if __name__=='__main__':unittest.main()
