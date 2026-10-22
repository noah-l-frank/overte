"""Normal one-send background/activation with synthetic SDK/native lifecycle."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.scenarios import VERSION
from ios.adapters.emote_lifecycle import IOSEmoteBackground
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_animation_history import history_source


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.foreground=True;self.inputs=[];self.native_reads=0;self.clock=0.;self.fault='';self.counters=dict(backgrounds=0,activations=1,launches=1)
        self.native=Boundary();self.history=None;self.epoch=20000
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _:self.root/'session.json'
        self.runtime.existing_input_session=lambda _:nullcontext()
        self.runtime._sources=self.sources
        self.runtime.adapter=SimpleNamespace(_operation='feature.emotes.act',invoke=self.invoke)
        self.status_patch=patch.object(IOSGraphicsRuntime,'_graphics_lifecycle_status',side_effect=self.status);self.status_patch.start()
    def tearDown(self):self.status_patch.stop();self.held.__exit__(None,None,None);self.temp.cleanup()
    def sleep(self,n):self.clock+=n
    def owner(self):return IOSEmoteBackground(self.runtime,'owned',RUN,'http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/',BINDING,self.lock,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def call(self):return dict(contractVersion=VERSION,runId=RUN,ticket='2'*32,verb='background-resume',inputs={},
        fixtureUrl='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/')
    def status(self,_runtime,_selector,binding):
        self.assertEqual(BINDING,binding)
        if self.fault=='pid':raise NativeUIError('Synthetic changed OS process')
        return dict(binding=deepcopy(BINDING),foreground=self.foreground,running=True,appState=4 if self.foreground else 3)
    def invoke(self,_selector,operation,values):
        self.assertIsNone(self.runtime.adapter._operation);self.assertEqual({},values);self.inputs.append(operation)
        if operation=='lifecycle.background':
            if self.fault!='ignored-home':self.foreground=False;self.counters['backgrounds']+=1
        else:
            self.assertEqual('app.launch',operation)
            if self.fault!='ignored-activation':self.foreground=True;self.counters['activations']+=1
            if self.fault=='replacement':self.counters['launches']+=1
            if self.fault=='counterless':self.counters.update(backgrounds=0,activations=1)
        if self.fault==('lost-home' if operation=='lifecycle.background' else 'lost-activation'):
            raise OSError('Synthetic lost normal lifecycle return')
    def sources(self,_selector):
        need_foreground=self.foreground
        if not need_foreground:raise AssertionError('Foreground-only source was read in background')
        return dict(binding=deepcopy(BINDING),observer=SimpleNamespace(bound_native_observer=lambda _:SimpleNamespace(read=self.read)),clock_source=None)
    def read(self,*_args,**_kwargs):
        self.native_reads+=1;self.epoch+=1;self.native.send(dict(commandId='ios-'+format(self.native_reads,'032x')))
        value=self.native.sample;history_source(value)
        value.update(processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,lifecycle=deepcopy(self.counters))
        value['animationFence']['requestedEpochMs']=self.epoch
        animation=value['animation'];animation['capturedEpochMs']=self.epoch
        if self.history is None:self.history=deepcopy(animation['history'])
        row=dict(frameSequence=len(self.history['frames'])+1,overrideSequence=1,evaluationSequence=animation['evaluationSequence'],
            capturedEpochMs=self.epoch,overrideActive=False,joints=[dict(index=0,pose=deepcopy(animation['joints'][0]))])
        self.history['frames'].append(row);self.history['frameSequence']=row['frameSequence'];animation['history']=deepcopy(self.history)
        return deepcopy(value)

    def test_native_counter_and_original_os_transitions_are_required_and_reconstruction_does_not_resend(self):
        owner=self.owner();self.assertEqual({'performed':True},owner.act(self.call()));self.assertEqual('observed',owner.state['phase'])
        self.owner().act(self.call());self.owner().retire();self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
        self.assertEqual('feature.emotes.act',self.runtime.adapter._operation)
    def test_lost_home_recovers_without_native_reads_while_backgrounded(self):
        self.fault='lost-home'
        with self.assertRaises(OSError):self.owner().act(self.call())
        reads=self.native_reads;owner=self.owner();self.assertEqual(reads,self.native_reads);self.assertFalse(self.foreground)
        self.fault='';owner.act(self.call());self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_lost_activation_does_not_repeat_normal_activation(self):
        self.fault='lost-activation'
        with self.assertRaises(OSError):self.owner().act(self.call())
        self.fault='';self.owner().act(self.call());self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_ignored_input_missing_counters_or_replacement_cannot_be_success(self):
        for fault in ('ignored-home','ignored-activation','replacement','counterless','pid'):
            with self.subTest(fault=fault):
                self.fault=fault
                with self.assertRaises(NativeUIError):self.owner().act(self.call())
                first=deepcopy(self.inputs)
                self.assertEqual(0 if fault=='pid' else 1 if fault=='ignored-home' else 2,len(first))
                with self.assertRaises(NativeUIError):self.owner().act(self.call())
                self.assertEqual(first,self.inputs)
                path=self.root/'ios-emote-background.json'
                if path.exists():path.unlink()
                self.inputs=[];self.foreground=True;self.counters=dict(backgrounds=0,activations=1,launches=1)
    def test_failed_durable_intent_prevents_ordinary_home_input(self):
        owner=self.owner()
        with patch.object(owner.store,'write',side_effect=OSError('Synthetic durable intent failure')),self.assertRaises(OSError):owner.act(self.call())
        self.assertEqual([],self.inputs)


if __name__=='__main__':unittest.main()
