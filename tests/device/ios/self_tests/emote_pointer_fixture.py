"""Actual Python dispatch/weak callbacks at a modeled Qt/native boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.self_tests import test_ios_pointer_state as qt
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class PointerDomain:
    def __init__(self,test,scope,domain):
        self.scope,self.domain=scope,domain
        self.patch=patch.object(qt,'EPOCH',20000);self.patch.start();test.addCleanup(self.patch.stop)
        self.boundary=qt.NativePointerBoundary();self.boundary.now=domain.epoch()
        def tick():
            domain.time+=.001;self.boundary.now=domain.epoch();return self.boundary.now
        self.boundary.tick=tick
        send=self.boundary.send
        def sending(query):send(query);self.boundary.packet['processId']=31
        self.boundary.send=sending
        self.store=PrivateFeatureState(scope.root/'ios-emote-primary-pointers.json')
    def owner(self):
        pointer=self.boundary.reader();pointer.pid=31;pointer.monotonic=lambda:self.domain.time
        return IOSEmotePointers(self.store,self.scope.root,BINDING,RUN,'primary',self.scope.lock,lambda:True,
            native=self.scope.native,pointer=pointer,epoch_ms=self.scope.epoch_ms,monotonic=lambda:self.domain.time)
