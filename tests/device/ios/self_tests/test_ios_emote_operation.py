"""Whole-call work clock and final native/W3C send boundaries, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUI,NativeUIError,Locator,W3C_ELEMENT
from ios.adapters.emote_operation import operation,clock as operation_clock
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.normal_input import NativeInput
from ios.adapters.script_runtime import IOSScriptRuntime


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.clock=[0.];self.runtime=object.__new__(IOSEmoteRuntime)
        class Probe:
            def clock(self):return operation_clock(self)
        self.owner=Probe();self.owner.monotonic=lambda:self.clock[0]
        self.owner.runtime=self.runtime;self.owner.last_clock=None;self.owner.deadline=25.
        self.client=SimpleNamespace(call=lambda *_args:None)
        self.process=dict(bundleId='org.example.client',pid=31,foreground=True)
        target=dict(platform='ios',physical=True,probe=dict(kind='ios-documents'),appId=self.process['bundleId'],
            nativeUiObservation=dict(kind='uikit-documents',version=1),testBuild=dict(fixtureOrigin='http://127.0.0.1:42001',resultsDirectory='results'))
        native=NativeInput(self.client,'existing',target,lambda:deepcopy(self.process),monotonic=lambda:self.clock[0])
        observer=FeatureObservation(self.client,'existing',target,lambda:deepcopy(self.process),monotonic=lambda:self.clock[0])
        clock=FeatureObservation(self.client,'existing',target,lambda:deepcopy(self.process),monotonic=lambda:self.clock[0])
        self.source=dict(client=self.client,native=native,observer=observer,clock_source=SimpleNamespace(guard=clock.guard),
            process=lambda:deepcopy(self.process),check=lambda:True)

    def sources(self):
        with patch.object(IOSScriptRuntime,'_sources',return_value=self.source):return self.runtime._sources('existing')

    def test_slow_serialization_cannot_send_native_input_after_whole_deadline(self):
        with self.assertRaises(NativeUIError),self.runtime.operation_guard(self.owner.clock):
            source=self.sources();original=json.dumps
            def slow(value,*args,**kwargs):self.clock[0]=26.;return original(value,*args,**kwargs)
            with patch('ios.adapters.normal_input.json.dumps',side_effect=slow),patch('ios.adapters.normal_input.urlopen') as send:
                try:source['native']._request('read')
                finally:self.assertEqual(0,send.call_count)

    def test_slow_serialization_cannot_send_native_feature_command_after_whole_deadline(self):
        with self.assertRaises(NativeUIError),self.runtime.operation_guard(self.owner.clock):
            source=self.sources();original=json.dumps
            def slow(value,*args,**kwargs):self.clock[0]=26.;return original(value,*args,**kwargs)
            with patch('ios.adapters.feature_observation.json.dumps',side_effect=slow),patch('ios.adapters.feature_observation.post_request') as send:
                try:source['observer'].send(dict(schemaVersion=1,commandId='ios-'+'1'*32,action='feature-native-observe'))
                finally:self.assertEqual(0,send.call_count)

    def test_slow_w3c_lookup_never_clicks_and_clock_failure_stays_latched_inside_operation(self):
        calls=[]
        def call(method,path,body=None):
            calls.append(path)
            if path.endswith('/elements'):return [{W3C_ELEMENT:'actual-root'}]
            self.clock[0]=26.;return True
        self.client.call=call
        with self.assertRaises(NativeUIError),self.runtime.operation_guard(self.owner.clock):
            source=self.sources();normal=NativeUI(source['client'],'existing',source['check'],monotonic=lambda:self.clock[0])
            try:normal.click(Locator('accessibility id','OverteTabletOpen'))
            finally:
                self.assertFalse(any(path.endswith('/click') for path in calls))
                self.clock[0]=1.
                with self.assertRaises(NativeUIError):source['client'].call('POST','/session/existing/element/actual-root/click',{})

    def test_nested_public_call_keeps_original_deadline_and_runtime_context_releases_after_error(self):
        class Owner(type(self.owner)):
            @operation(25)
            def outer(self):
                self.monotonic.clock[0]=20.;return self.inner()
            @operation(25)
            def inner(self):
                self.monotonic.clock[0]=26.;return self.clock()
        class Clock:
            def __init__(self):self.clock=[0.]
            def __call__(self):return self.clock[0]
        owner=object.__new__(Owner);owner.monotonic=Clock();owner.runtime=self.runtime;owner.last_clock=None;owner.deadline=None
        with self.assertRaises(NativeUIError):owner.outer()
        self.assertIsNone(owner.deadline);self.assertEqual(0,owner._operation_depth)
        # No whole operation is active after failure; a later passive helper
        # retains its ordinary original continuity checks and is not poisoned.
        self.clock[0]=0.;self.assertIs(self.source,self.sources())


if __name__=='__main__':unittest.main()
