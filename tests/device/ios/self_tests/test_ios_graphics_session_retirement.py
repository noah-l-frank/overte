"""Real paired finalization and SDK-only teardown over host files/models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters.graphics_session_retirement import IOSGraphicsSessionRetirement
from ios.adapters.installed_code import VERSION as BINDING_VERSION
from ios.self_tests.test_ios_bundle_observation import Boundary as BundleBoundary
from ios.self_tests.test_ios_graphics_finalization import FinalizationHarness
from ios.self_tests.test_ios_retired_process import SOURCE
from self_tests.test_completed_frame_lease import BINDING


class GraphicsSessionHarness(FinalizationHarness):
    def setUp(self):
        super().setUp();self.sdk_deleted=False;self.sdk_calls=[];self.delete_fault='';self.actor_done=False
        self.sdk.target['serverUrl']='http://127.0.0.1:12345'
        self.session_store=PrivateFeatureState(self.adapter.state_path('owned'))
        self.session_store.write(self.base.read_session('owned'),None)
        self.base.read_session=lambda _:self.session_store.read()
        self.base._target=lambda _:self.sdk.target
        def retired_scope(_selector,scope):
            need(same(scope,{k:v for k,v in BINDING.items() if k!='processIdentity'}));return self.sdk.target
        self.base._retired_candidate_scope=retired_scope
        store=PrivateFeatureState(self.root/'installed-code-binding.json');self.base._binding_store=lambda _:store
        original_gate=self.base._binding;case=self;bundles={}
        def factory(*args):
            gate=original_gate(*args)
            class Gate:
                def __getattr__(self,name):return getattr(gate,name)
                def record(self):
                    value=gate.record();pid=value['process']['pid']
                    if pid not in bundles:
                        # A distinct model byte source produces a new original
                        # for each actual process life, never retimes PID 42.
                        import json
                        native=BundleBoundary();native.bundle['bundleId']=case.sdk.target['appId']
                        native.mutate=lambda packet:packet.update(processId=case.sdk.pid,instance=format(case.sdk.pid+9000,'032x'))
                        native.send(dict(schemaVersion=1,commandId='ios-'+format(pid+7000,'032x'),action='ios-bundle-observe'))
                        bundles[pid]=json.loads(native.original())
                    document=dict(bindingVersion=BINDING_VERSION,phase=value['phase'],scope=value['scope'],
                        source=value['source'],process=dict(bundleId=case.sdk.target['appId'],pid=value['process']['pid'],foreground=True),
                        observation=deepcopy(bundles[pid]),previousInstance=None,recovery=None)
                    previous=store.read()
                    if not same(previous,document):store.write(document,previous)
                    return document
            return Gate()
        self.base._binding=factory
        self.bridge._graphics_feature=lambda *args,**kwargs:self.feature()
        class SDKClient:
            def call(self,method,path):
                case.sdk_calls.append((method,path))
                need(path=='/session/'+BINDING['sessionId'])
                from ios.adapters.appium_adapter import WebDriverRequestError
                if case.sdk_deleted:raise WebDriverRequestError(404,'Gone')
                if method=='DELETE':
                    if case.delete_fault=='ignored':return {}
                    case.sdk_deleted=True
                    if case.delete_fault=='lost':raise RuntimeError('Unknown original DELETE return')
                else:need(method=='GET')
        boundary=patch('ios.adapters.appium_adapter.WebDriver',return_value=SDKClient());boundary.start();self.addCleanup(boundary.stop)
        self.selected=dict(artifactRoot=str(self.root/'pixels'),imagePolicy=self.feature().policy)

    def transaction(self):
        original=(PrivateFeatureState(self.root/'ios-feature-session-retirement.json').read()
                  or self.feature().store.read() or PrivateFeatureState(self.root/'ios-feature-session-retired.json').read())
        return IOSGraphicsSessionRetirement(self.bridge,'owned',self.primary_client,self.selected,original,sleep=self.sleep_actor)

    def sleep_actor(self,_seconds):
        self.sdk.clock+=1.1
        self.actor_done=self.finalizer('actor').step()

    def start(self):self.baseline();self.client.close()


class GraphicsSessionRetirementTests(GraphicsSessionHarness,unittest.TestCase):
    def test_paired_finalizer_deletes_only_original_sdk_then_repeats_from_historical_receipt(self):
        self.start();transaction=self.transaction();self.assertEqual({'cleaned':True},transaction.finalize())
        self.assertEqual(['app.stop'],self.inputs);self.assertTrue(self.sdk_deleted)
        self.assertEqual(1,sum(method=='DELETE' for method,_ in self.sdk_calls))
        self.assertIsNone(self.session_store.read());self.assertIsNone(self.base._binding_store('owned').read())
        calls=deepcopy(self.sdk_calls)
        again=IOSGraphicsSessionRetirement.from_receipt(self.bridge,'owned',transaction.receipt.read())
        self.assertEqual({'cleaned':True},again.historical(again.receipt.read()))
        self.assertEqual(calls,self.sdk_calls);self.assertEqual(['app.stop'],self.inputs)
        self.assertTrue(self.finalizer('actor').step())

    def test_lost_delete_is_resolved_by_original_sdk_404_without_second_delete_or_stop(self):
        self.start();self.delete_fault='lost';transaction=self.transaction()
        with self.assertRaises((RuntimeError,NativeUIError)):transaction.finalize()
        self.assertTrue(self.sdk_deleted);self.assertIsNotNone(transaction.store.read());self.assertIsNotNone(self.session_store.read())
        self.assertEqual('delete-issued',transaction.store.read()['phase']);self.assertEqual(['app.stop'],self.inputs)
        self.delete_fault='';self.assertEqual({'cleaned':True},self.transaction().finalize())
        self.assertEqual(1,sum(method=='DELETE' for method,_ in self.sdk_calls));self.assertEqual(['app.stop'],self.inputs)

    def test_foreign_session_after_delete_uncertainty_cannot_be_removed(self):
        self.start();self.delete_fault='lost'
        with self.assertRaises((RuntimeError,NativeUIError)):self.transaction().finalize()
        self.assertTrue(self.sdk_deleted)
        previous=self.session_store.read();self.session_store.write(previous|dict(sessionId='foreign-session'),previous)
        with self.assertRaises((RuntimeError,ValueError)):self.transaction().finalize()
        self.assertEqual('foreign-session',self.session_store.read()['sessionId']);self.assertEqual(['app.stop'],self.inputs)

    def test_ignored_sdk_delete_ack_remains_owned_and_is_never_resent(self):
        self.start();self.delete_fault='ignored'
        with self.assertRaises((RuntimeError,NativeUIError)):self.transaction().finalize()
        self.assertFalse(self.sdk_deleted);self.assertIsNotNone(self.session_store.read())
        for _ in range(2):
            with self.assertRaises((RuntimeError,NativeUIError)):self.transaction().finalize()
        self.assertEqual(1,sum(method=='DELETE' for method,_ in self.sdk_calls));self.assertEqual(['app.stop'],self.inputs)
        self.assertIsNotNone(PrivateFeatureState(self.root/'ios-feature-session-retirement.json').read())


if __name__=='__main__':unittest.main()
