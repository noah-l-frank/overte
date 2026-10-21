"""Graphics whole-run composition on synthetic iOS sources and real private fixtures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.scenarios import VERSION
from ios.adapters.graphics_feature import IOSGraphicsFeature
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests.test_ios_graphics_observer import ObserverHarness
from ios.self_tests.test_ios_graphics_restart import RestartHarness
from ios.self_tests.test_ios_graphics_lifetime import WebSDK
from ios.self_tests.test_ios_graphics_samples import POLICY
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from self_tests.test_completed_frame_lease import BINDING


class FeatureHarness(ObserverHarness,RestartHarness):
    def setUp(self):
        super().setUp();self.webs={};self.ticket_count=200
        self.primary_client=AdapterFixtureClient(self.client.url,self.server.adapter_token)
        def web(*_args,**_kwargs):
            pid=self.sdk.pid
            if pid not in self.webs:
                value=WebSDK(self.sdk);value.birth=format(pid+8000,'032x');self.webs[pid]=value
            return self.webs[pid].reader()
        self.adapter._web_closure_observer=web
        original=self.base.invoke
        def invoke(selector,operation,values):
            if operation=='lifecycle.background':
                self.assertIsNone(self.base._operation);self.inputs.append(operation)
                self.sdk.foreground=False;self.sdk.native_lifecycle['backgrounds']+=1;return dict(backgrounded=True)
            if operation=='app.launch' and self.sdk.running:
                self.assertIsNone(self.base._operation);self.inputs.append(operation)
                self.sdk.foreground=True;self.sdk.native_lifecycle['activations']+=1;return dict(launched=True)
            return original(selector,operation,values)
        self.base.invoke=invoke
        def status(_selector,binding):
            self.assertEqual(BINDING|dict(processIdentity=str(self.sdk.pid)),binding)
            return dict(binding=deepcopy(binding),foreground=self.sdk.foreground,running=self.sdk.running,appState=4 if self.sdk.foreground else 3)
        bridge=object.__new__(IOSGraphicsRuntime);bridge.adapter=self.base
        bridge.state_path=self.adapter.state_path;bridge._graphics_lifecycle_status=status
        self.adapter.invoke=bridge.invoke;self.adapter._graphics_lifecycle_status=status
    def feature(self,role='primary'):
        client=self.actor_client if role=='actor' else self.primary_client
        return IOSGraphicsFeature(self.adapter,'owned',GraphicsFixtureReader(client,RUN,epoch_ms=self.sdk.host_epoch),
            self.root/'pixels',POLICY,role=role,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def baseline(self):
        state=self.feature().prepare();self.assertEqual('calibrating',state['phase'])
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.assertEqual('baseline',self.feature().prepare()['phase'])
        actual=self.feature().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.feature('actor').publish();return actual
    def activate(self,verb,inputs=None):
        self.ticket_count+=1;ticket=format(self.ticket_count,'032x')
        self.client.activate(ticket,verb,inputs or {});self.gpu.marker=ticket
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.client.url+'/runs/'+RUN+'/',ticket=ticket,verb=verb,inputs=inputs or {})


class GraphicsFeatureTests(FeatureHarness,unittest.TestCase):
    def test_measured_baseline_requires_both_private_roles_and_independent_original_admission(self):
        actual=self.baseline();self.assertEqual(.6,actual['state']['resolution']);self.assertFalse(actual['state']['dialog'])
        primary=self.feature();actor=self.feature('actor')
        with primary.lock.held():
            a=primary.observer();x=primary.lifetime(0);self.assertTrue(x.state['activeProofs'])
            left=a.state['last'];first=x.load(x.state['records'][0]);self.assertEqual('active',first['mode'])
        with actor.lock.held():
            b=actor.observer();y=actor.lifetime(0);self.assertTrue(y.state['activeProofs'])
            self.assertNotEqual(left['requestId'],b.state['last']['requestId'])
            self.assertNotEqual(first['web']['commandId'],y.load(y.state['records'][0])['web']['commandId'])
        self.assertEqual(1,len(self.client.observe()['entries']));self.assertEqual([],self.primary_client.observe()['entries'])
        self.assertEqual([],self.inputs)

    def test_actor_cannot_create_owner_or_publish_before_primary_prepares(self):
        before=list(self.sdk.clicks)
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.assertIsNone(self.feature().store.read());self.assertIsNone(self.feature('actor').role_store.read())
        self.assertEqual(before,self.sdk.clicks);self.assertEqual([],self.client.observe()['entries'])

    def test_native_and_original_pixels_follow_normal_open_resolution_and_close(self):
        first=self.baseline();sequence=first['sequence']
        for verb,inputs in (('open',{}),('set-resolution',dict(value=.5)),('close',{})):
            call=self.activate(verb,inputs);self.assertEqual({'performed':True},self.feature().act(call))
            value=self.feature().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=sequence));sequence=value['sequence']
            self.feature('actor').publish();self.assertEqual(call['ticket'],self.client.observe()['entries'][-1]['ticket'])
        self.assertEqual(.5,value['state']['resolution']);self.assertEqual(.5,value['state']['renderScale']);self.assertFalse(value['state']['dialog'])
        self.assertEqual('active',self.feature().control()['phase'])

    def test_ignored_resolution_input_never_becomes_success_or_a_second_send_after_reconstruction(self):
        self.baseline();self.feature().act(self.activate('open'));call=self.activate('set-resolution',dict(value=.5));self.sdk.model.fault='resolution'
        with self.assertRaises(NativeUIError):self.feature().act(call)
        before=list(self.sdk.model.actions)
        with self.assertRaises(NativeUIError):self.feature().act(call)
        self.assertEqual(before,self.sdk.model.actions);self.assertEqual(.6,self.sdk.model.resolution)
        self.assertEqual('acting',self.feature().control()['phase'])
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()

    def test_owned_normal_background_resume_remains_a_same_pid_transition(self):
        self.baseline();call=self.activate('background-resume')
        self.feature().act(call);self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
        actual=self.feature().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0));self.feature('actor').publish()
        self.assertEqual(42,self.sdk.pid);self.assertEqual(1,actual['lifecycle']['backgrounds']);self.assertEqual(1,actual['lifecycle']['launches'])
        self.feature().act(call);self.assertEqual(['lifecycle.background','app.launch'],self.inputs)

    def test_child_preparation_time_cannot_extend_the_outer_observation_deadline(self):
        feature=self.feature();actual=feature.scene;before=[]
        def scene():
            value=actual();prepare=value.prepare
            def late():
                result=prepare();before.extend(self.sdk.model.actions);self.sdk.clock+=21;return result
            value.prepare=late;return value
        with patch.object(feature,'scene',side_effect=scene),self.assertRaises(NativeUIError):feature.observe(
            dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(before,self.sdk.model.actions)
        self.assertIsNone(PrivateFeatureState(self.root/'ios-graphics-preferences.json').read())
        self.assertEqual('preparing',feature.control()['phase']);self.assertIsNone(feature.deadline)

    def test_initially_enabled_native_settings_are_restored_before_either_public_baseline(self):
        self.sdk.model.haze=self.sdk.model.mirrors=True;actual=self.baseline()
        self.assertTrue(actual['state']['haze']);self.assertTrue(actual['state']['mirror']);self.assertFalse(actual['state']['dialog'])
        self.assertTrue(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)
        self.assertTrue(self.client.observe()['entries'][-1]['facts']['haze'])

    def test_orphaned_role_metadata_prevents_new_owner_admission_before_any_input(self):
        store=PrivateFeatureState(self.root/'ios-graphics-actor-observer.json');store.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):self.feature().prepare()
        self.assertEqual([],self.sdk.clicks);self.assertIsNone(self.feature().store.read())


if __name__=='__main__':unittest.main()
