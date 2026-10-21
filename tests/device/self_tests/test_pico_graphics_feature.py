"""Pico whole-run coordination at synthetic original SDK/native boundaries.

These cases exercise normal input/phase/recovery ownership; they do not replace
the separately required full shared-engine/stereo/independent-actor test.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid

from adapters.graphics_journey.feature import GraphicsFeature
from adapters.graphics_journey.fixture import GraphicsFixtureReader,GraphicsPhasePending
from adapters.graphics_journey.lifetime import GraphicsLifetime
from adapters.normal_ui import NativeUIError
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE
from feature_journeys.witness import Journal
from self_tests.test_pico_graphics_lifetime import Model as Base,WebBoundary,HttpBoundary,RUN,TICKET


class Model(Base):
    def __init__(self):
        super().__init__();self.lifecycle_fault=None;self.web_pid=self.pid;self.flow._script_file_io=self.script_io
        self.journal=Journal(clock=lambda:self.native.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('graphics')
        self.journal.activate(RUN,TICKET);self.client.closed=False
        self.client.observe=lambda:self.journal.snapshot(RUN);self.client.request=self.request
        self.original_adapter.adb.process_state=lambda target,package:dict(running=self.running,identity=self.identity if self.running else None)
    def request(self,path,value=None):
        if path=='/runs/'+RUN+'/active':return self.journal.active(RUN)
        if path=='/runs/'+RUN+'/samples':self.journal.publish(RUN,value);return dict(accepted=True)
        raise AssertionError('Unexpected synthetic fixture request')
    def activate(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;inputs={} if inputs is None else inputs
        self.provider.activate(RUN,ticket);self.journal.activate(RUN,ticket,verb,inputs)
        return dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=self.source.fixture_url,verb=verb,inputs=inputs)
    def feature(self,role='primary'):
        source=GraphicsFixtureReader(self.client,RUN,epoch_ms=lambda:self.native.epoch)
        owner=GraphicsFeature(self.flow,'owned',source,self.root/'artifacts',SURFACE_PROFILE,role=role,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        if role=='primary':self.lock=owner.lock
        return owner
    def invoke(self,target,operation,values):
        if operation=='lifecycle.background' or operation=='app.launch' and self.running:
            self.events.append(operation);assert values=={}
            if operation=='lifecycle.background':
                if self.lifecycle_fault=='ignored-home':return dict(performed=True)
                self.foreground=False;self.backgrounds+=1
                if self.lifecycle_fault=='lost-home':raise OSError('Synthetic lost applied Home reply')
            else:
                if self.lifecycle_fault=='ignored-activation':return dict(performed=True)
                self.foreground=True;self.activations+=1
                if self.lifecycle_fault=='lost-activation':raise OSError('Synthetic lost applied activation reply')
            return dict(performed=True)
        try:return super().invoke(target,operation,values)
        finally:
            if self.pid!=self.web_pid:
                self.web_pid=self.pid;self.web=WebBoundary(self);self.http=HttpBoundary()


class PicoGraphicsFeatureTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_normal_controls_and_recreated_feature_keep_actual_native_originals(self):
        m=self.model;owner=m.feature();state=owner.prepare();self.assertEqual('baseline',state['phase'])
        for verb,inputs in [('open',{}),('set-resolution',dict(value=.5)),('close',{}),('open',{}),
                ('set-resolution',dict(value=.6)),('set-haze',dict(enabled=False)),('set-haze',dict(enabled=True)),
                ('set-mirrors',dict(enabled=False)),('set-mirrors',dict(enabled=True)),('close',{})]:
            call=m.activate(verb,inputs);owner=m.feature();self.assertEqual(dict(performed=True),owner.act(call))
        before=list(m.native.inputs);owner=m.feature();owner.act(call);self.assertEqual(before,m.native.inputs)
        self.assertEqual(.6,m.native.graph.resolution);self.assertTrue(m.native.graph.haze);self.assertTrue(m.native.graph.mirrors)
    def test_foreign_ticket_is_rejected_before_normal_input(self):
        m=self.model;owner=m.feature();owner.prepare();call=m.activate('open');call['ticket']=uuid.uuid4().hex
        before=list(m.native.inputs)
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(before,m.native.inputs)
    def test_ignored_setting_keeps_parent_and_child_intent_and_cannot_be_replayed(self):
        m=self.model;owner=m.feature();owner.prepare();owner.act(m.activate('open'));m.native.graph.fault='resolution'
        call=m.activate('set-resolution',dict(value=.5))
        with self.assertRaises(NativeUIError):owner.act(call)
        before=list(m.native.graph.actions)
        with self.assertRaises(NativeUIError):m.feature().act(call)
        self.assertEqual(before,m.native.graph.actions)
        with owner.lock.held():self.assertEqual('acting',owner.control()['phase'])
    def test_lost_background_reply_recovers_before_foreground_only_scene_construction(self):
        m=self.model;owner=m.feature();owner.prepare();m.lifecycle_fault='lost-home';call=m.activate('background-resume')
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertFalse(m.foreground);self.assertEqual(['lifecycle.background'],m.events)
        m.lifecycle_fault=None;m.feature().act(call)
        self.assertTrue(m.foreground);self.assertEqual(['lifecycle.background','app.launch'],m.events)
        self.assertEqual(1,m.launches)
    def test_normal_restart_keeps_coordinator_stage_and_recovers_lost_launch_without_replay(self):
        m=self.model;owner=m.feature();owner.prepare();m.fault='lost-launch';call=m.activate('restart-app')
        with patch('adapters.android_process_query.subprocess.run',side_effect=m.query):
            with self.assertRaises(NativeUIError):owner.act(call)
            m.fault=None;owner=m.feature();owner.act(call)
        with owner.lock.held():self.assertEqual(1,owner.control()['stage'])
        self.assertEqual(['app.stop','app.launch'],m.events);self.assertEqual(32,m.pid)
    def test_actor_cannot_prepare_or_deliver_normal_input(self):
        m=self.model;owner=m.feature('actor');call=m.activate('open');before=list(m.native.inputs)
        with self.assertRaises(NativeUIError):owner.prepare()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(before,m.native.inputs)
    def test_completed_input_ack_cannot_be_reused_after_an_unrelated_process_replacement(self):
        m=self.model;owner=m.feature();owner.prepare();call=m.activate('open');owner.act(call)
        m.pid=32;m.native.pid=32;m.identity=m.bound='32:replacement'
        m.native.bridge='33333333-3333-4333-8333-333333333333';before=list(m.native.inputs)
        with self.assertRaises(NativeUIError):m.feature().act(call)
        self.assertEqual(before,m.native.inputs)


if __name__=='__main__':unittest.main()
