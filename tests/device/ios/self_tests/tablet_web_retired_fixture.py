"""Actual loopback stopped-PID queries with explicit OS/Node-clock models.

The anchor is made by an actual live process getter before ordinary Stop.
No native/UI getter is used after process death. This is not real DVT evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.self_tests.tablet_web_lifecycle_fixture import TabletLifecycleModel


class TabletRetiredModel(TabletLifecycleModel):
    OPERATIONS=TabletLifecycleModel.OPERATIONS|{'mobile: overteRetiredProcessInfo'}
    def __init__(self,boundary):
        self.sequence=0;self.anchor=None;self.originals=[]
        super().__init__(boundary)
    def stamp(self):return dict(epochMs=self.b.host()+86400000,monotonicMs=5000+self.b.mono()*1000)
    def process(self):
        actual=super().process();self.sequence+=1
        if actual is not None:
            state=4 if actual['foreground'] else 3
            self.anchor=dict(sequence=self.sequence,pid=actual['pid'],appStates=[state,state],bundlePids=[actual['pid'],actual['pid']],
                clockBefore=self.stamp(),clockAfter=self.stamp())
        return actual
    def execute(self,operation,arguments):
        if operation!='mobile: overteRetiredProcessInfo':return super().execute(operation,arguments)
        from ios.adapters.retired_process import command
        command(arguments);need(arguments['bundleId']==self.b.target['appId'] and self.anchor is not None)
        self.calls.append((operation,deepcopy(arguments)));before=self.stamp();self.sequence+=1
        process=super().process();state=4 if process and process['foreground'] else 3 if process else 1
        self.b.sleep(.01)
        value=dict(iosRetiredProcessVersion=1,commandId=arguments['commandId'],instance=self.b.context_test.admission.fixture.source['instance'],
            sequence=self.sequence,source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',clockBefore=before,clockAfter=self.stamp(),
            anchor=deepcopy(self.anchor),appStates=[state,state],bundlePids=[42,42] if process else [0,0],
            pidChecks=[dict(pid=42,running=process is not None),dict(pid=42,running=process is not None)])
        self.originals.append(deepcopy(value));return value
