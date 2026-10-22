"""Connected normal Worlds inputs and real owners; lifecycle/OS are modeled.

The next-process source group is deliberately unavailable in this first seam.
An actual retained lifecycle receipt must never become a transferred stage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_before_restart import NavigationBeforeRestart
from ios.adapters.navigation_restart import NavigationRestart
from ios.self_tests.navigation_feature_observer_fixture import Whole
from ios.self_tests.test_ios_navigation_restart import LifecycleBoundary
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary


class RestartWorld(Whole):
    def __init__(self,test):
        super().__init__(test)
        f=self.flow_fixture
        self.native.native_clock_bound=True
        # Future reads use these actual live physical producers. The static
        # admission and every already retained original remain unchanged.
        self.inventory.__class__=type('SharedInventory',(type(self.inventory),),{
            'clock':property(lambda _inventory:self.sdk.gpu.clock,
                lambda _inventory,value:setattr(self.sdk.gpu,'clock',value))})
        f.f.admission.sources=dict(inventory=self.inventory.reader(),navigation=self.navigation,**self.sources)
        pointer=NativePointerBoundary()
        def tick():self.sdk.gpu.clock+=.001;pointer.now=self.sdk.gpu.epoch();return pointer.now
        pointer.now=self.sdk.gpu.epoch();pointer.tick=tick
        self.pointer=pointer.reader();self.pointer.monotonic=self.mono
        harness=SimpleNamespace(last=self.native.clock_ms(),h=f)
        world=self
        previous_sources=f.runtime._sources
        class Lifecycle(LifecycleBoundary):
            def tick(_self):return tick()
            def sources(_self,selector):
                if _self.pid==42:
                    source=previous_sources(selector)
                    observer=SimpleNamespace(**vars(source['observer']))
                    def native(clock):
                        reader=world.sdk.native();reader.native_clock_bound=True;return reader
                    observer.bound_native_observer=native
                    observer.pointer_state=lambda clock:world.pointer
                    return source|dict(binding=deepcopy(world.binding),check=lambda:world.sdk.okay,observer=observer)
                return super().sources(selector)
        self.lifecycle=Lifecycle(harness)
        # LifecycleBoundary starts only after the actual old admission exists.
        harness.initial=dict(binding=deepcopy(self.binding))
        self.lifecycle.stamp=self.sdk.gpu.epoch()
        self.runtime=f.runtime;self.runtime.adapter=self.lifecycle
        self.runtime.existing_input_session=self.lifecycle.session
        original_invoke=self.lifecycle.invoke
        def invoke(selector,operation,values):
            if selector!='owned':raise AssertionError('Foreign connected lifecycle selector')
            return original_invoke('existing',operation,values)
        self.lifecycle.invoke=invoke
        self.runtime._sources=self.lifecycle.sources
        self.runtime._navigation_before_restart=lambda selector,admission,missing=None:NavigationBeforeRestart(
            PrivateFeatureState(self.root/'ios-navigation-before-restart.json'),admission,missing=missing,
            epoch_ms=self.now,monotonic=self.mono)
        self.runtime._navigation_restart=lambda selector,initial,samples,lock,fixture:NavigationRestart(
            self.runtime,selector,initial,samples,lock,fixture,epoch_ms=self.now,monotonic=self.mono)
        def unavailable(*args):raise NativeUIError('Explicit new-process sources have not arrived')
        self.runtime._navigation_process_owner=unavailable

