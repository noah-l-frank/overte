"""Actual durable owner/readers over explicit OS, Qt, input and feet seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_background_source import NativeLifecycleBackground
from adapters.script_journey.history import unpack
from self_tests import test_pico_lifecycle_chat as chat_seams
from self_tests.test_pico_lifecycle_background_source import Native
from self_tests.test_native_feature_observation import Boundary as Feature
from self_tests.test_pico_lifecycle_source import RUN


class LifecycleBackgroundOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=chat_seams.LifecycleChatTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.chat=self.fixture.owner;self.chat.open_chat();self.chat.focus_chat();self.chat.type_chat()
        self.native,self.world,self.lock,self.root=self.fixture.native,self.fixture.joined.world,self.fixture.lock,self.fixture.root
        self.foreground=True;self.inputs=[];self.lost=None;self.ignore=None;self.backgrounds=0;self.activations=1;self.runtime_calls=[]
        self.history=Native();self.history.host=self.native.clock;self.history.epoch=self.native.epoch()
        base_frame=self.history.frame
        def original_frame(cause):
            base_frame(cause);self.native.ui.send(dict(commandId='1'*32,runId=RUN));packet=self.native.ui.value
            row=next(item for item in packet['source']['editors'] if item['id']==self.chat.state['originalId'])
            keyboard=packet['source']['keyboard'];result=self.history.frames[-1]
            result.update(uiInstance=packet['instance'],uiSequence=packet['sequence'],uiCapturedEpochMs=packet['capturedEpochMs'],
                currentId=packet['source']['current'],editor=deepcopy(row),focusedEditors=sum(item['focused'] for item in packet['source']['editors']))
            result['keyboard']={key:keyboard[key] for key in ('instance','sequence','created','enabled','visible','raised')}
            result['keyboard'].update(keyCount=len(keyboard['keys']),pressedKeys=sum(item['pressed'] for item in keyboard['keys']))
        self.history.frame=original_frame
        base_send=self.history.send
        def send(request):
            self.history.host=self.native.clock;self.history.epoch=self.native.epoch();base_send(request)
        self.send=send
        outer=self
        class Pending:
            def read(self):return dict(inputs=deepcopy(outer.owner.state['inputs']))
        self.history.pending=Pending();self.feature=Feature()
        def feature(value):
            epoch=self.native.epoch();value.update(capturedEpochMs=epoch,requestedEpochMs=epoch)
            value['animationFence']['requestedEpochMs']=epoch
            value['lifecycle'].update(backgrounds=self.backgrounds,activations=self.activations)
        self.feature.mutate=feature
        self.world.guard=lambda:self.foreground
        for reader in (self.world.source,self.world.axes,self.world.avatar):reader.guard=lambda:self.foreground
        self.owner=self.make();self.owner.prepare(self.chat)

    def sleep(self,seconds):
        self.native.sleep(seconds);self.history.host=self.native.clock;self.history.epoch=self.native.epoch()
        if self.history.active:self.history.frame('timer')

    def runtime(self,intent):
        self.assertTrue(self.foreground,'Foreground runtime acquired during actual background');self.runtime_calls.append(self.foreground)
        observer=NativeLifecycleBackground(self.send,lambda:self.history.raw,self.native.epoch,lambda:self.foreground,123,self.lock,
            intent=intent,monotonic=lambda:self.native.clock,sleep=self.sleep)
        native=self.feature.reader();native.clock_ms=self.native.epoch;native.guard=lambda:self.foreground
        native.monotonic=lambda:self.native.clock;native.sleep=self.sleep
        return self.world,observer,native

    def status(self,binding):return dict(binding=deepcopy(binding),running=True,foreground=self.foreground)
    def os_input(self,operation,binding):
        state=unpack(self.owner.store.read()['payload'])[0]
        self.assertEqual('home-issued' if operation=='lifecycle.background' else 'resume-issued',state['phase'])
        self.inputs.append(operation)
        if self.ignore!=operation:
            self.foreground=operation=='app.launch';self.backgrounds+=not self.foreground;self.activations+=self.foreground
            self.native.ui.rows[-1]['focused']=False;self.native.ui.raised=False
            self.history.host=self.native.clock;self.history.epoch=self.native.epoch()
            self.history.publish('active' if self.foreground else 'hidden');self.native.clock=self.history.host
        if self.lost==operation:raise NativeUIError('Explicit lost original normal OS response')

    def make(self):
        return PicoLifecycleBackground(self.root/'lifecycle-background-owner.json',RUN,self.chat.binding,self.lock,
            self.status,self.os_input,self.runtime,monotonic=lambda:self.native.clock,sleep=self.sleep)

    def test_actual_durable_home_return_original_history_three_second_feet_quiet_and_timer_release(self):
        result=self.owner.run_owned();self.assertFalse(result['focused']);self.assertFalse(result['keyboard'])
        self.assertNotIn('generation',result);self.assertGreaterEqual(result['quietSeconds'],3);self.assertTrue(result['processOwnedSourcesRetained'])
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
        self.assertFalse(self.history.active);self.assertEqual(['arm','release'],[row['operation'] for row in self.history.commands if row['operation']!='observe'])
        self.assertTrue(self.owner.store.path.exists());self.assertEqual('released',self.owner.state['phase'])
        self.assertGreaterEqual(self.owner.state['quiet'][-1]['hostMonotonic']-self.owner.state['quiet'][0]['hostMonotonic'],3)
        before=self.native.clock;again=self.owner.run_owned();self.assertGreaterEqual(self.native.clock-before,3)
        self.assertEqual(result['originalId'],again['originalId']);self.assertGreaterEqual(again['quietSeconds'],3);self.assertEqual(2,len(self.inputs))
    def test_lost_home_response_recovers_while_background_without_native_guard_or_repeating_home(self):
        self.lost='lifecycle.background'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertFalse(self.foreground);calls=len(self.runtime_calls);self.lost=None;self.owner=self.make()
        self.assertEqual(calls,len(self.runtime_calls));self.assertEqual('home-issued',self.owner.state['phase'])
        result=self.owner.run_owned();self.assertFalse(result['keyboard']);self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_unknown_home_without_os_effect_never_replays_input_or_treats_ack_as_background(self):
        self.ignore='lifecycle.background'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.owner=self.make()
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual(['lifecycle.background'],self.inputs);self.assertEqual('home-issued',self.owner.state['phase'])
    def test_lost_resume_response_only_reads_original_return_and_never_launches_again(self):
        self.lost='app.launch'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertTrue(self.foreground);self.lost=None;self.owner=self.make();self.owner.run_owned()
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_lost_arm_reconciles_actual_original_command_id_without_rearming(self):
        self.history.lost='arm'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.history.lost=None;self.owner=self.make();self.owner.run_owned()
        self.assertEqual(['arm','release'],[row['operation'] for row in self.history.commands if row['operation']!='observe'])
        self.assertEqual(2,len(self.inputs))
    def test_lost_release_reconciles_actual_original_command_id_without_releasing_again(self):
        self.history.lost='release'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.history.lost=None;self.owner=self.make();self.owner.run_owned()
        self.assertEqual(['arm','release'],[row['operation'] for row in self.history.commands if row['operation']!='observe'])
        self.assertEqual(2,len(self.inputs))
    def test_failed_private_intent_prevents_observer_arm_and_all_normal_os_input(self):
        with patch.object(self.owner.store,'write',side_effect=OSError('Explicit fsync failure')),self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual([],self.inputs);self.assertNotIn('arm',[row['operation'] for row in self.history.commands])
    def test_changed_original_chat_archive_blocks_recovery_and_preserves_all_journals(self):
        self.lost='lifecycle.background'
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        disk=self.chat.store.read();changed=deepcopy(disk);changed['binding']['sessionId']='foreign'
        self.chat.store.write(changed,disk)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(['lifecycle.background'],self.inputs);self.assertTrue(self.owner.store.path.exists())
    def test_final_report_copy_native_clock_jump_is_rejected_with_frozen_host_clock(self):
        report=self.owner.report
        def late():
            result=report();native=self.owner.runtime[2];clock=native.clock_ms;native.clock_ms=lambda:clock()+2000;return result
        with patch.object(self.owner,'report',side_effect=late),self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual('released',self.owner.state['phase']);self.assertFalse(self.history.active);self.assertEqual(2,len(self.inputs))
    def test_host_background_wait_without_original_native_timer_checkpoint_cannot_qualify(self):
        self.owner.sleep=self.native.sleep
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs);self.assertNotEqual('released',self.owner.state['phase'])
        self.assertTrue(self.owner.store.path.exists());self.assertNotIn('release',[row['operation'] for row in self.history.commands])
    def test_return_ack_with_actual_refocused_chat_and_visible_vr_keyboard_cannot_qualify(self):
        original=self.owner.os_input
        def refocused(operation,binding):
            result=original(operation,binding)
            if operation=='app.launch':self.native.ui.rows[-1]['focused']=True;self.native.ui.raised=True
            return result
        self.owner.os_input=refocused
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual(2,len(self.inputs));self.assertNotEqual('released',self.owner.state['phase'])
    def test_stale_final_home_intent_guard_blocks_normal_input_with_frozen_host_clock(self):
        save=self.owner.save
        def late(state):
            save(state)
            if state['phase']=='home-issued':
                native=self.owner.runtime[2];clock=native.clock_ms;native.clock_ms=lambda:clock()+2000
        with patch.object(self.owner,'save',side_effect=late),self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertEqual([],self.inputs);self.assertEqual('home-issued',self.owner.state['phase'])
    def test_unknown_owner_write_after_original_arm_chunk_cannot_adopt_or_rearm_on_recovery(self):
        write=self.owner.store.write
        def lost(value,previous):
            if len(value['originalChunks'])>len(previous['originalChunks']):raise OSError('Explicit lost owner manifest persistence')
            return write(value,previous)
        with patch.object(self.owner.store,'write',side_effect=lost),self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertTrue(self.history.active);self.assertEqual([],self.inputs)
        self.assertEqual(['arm'],[row['operation'] for row in self.history.commands if row['operation']!='observe'])
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        with self.assertRaises(NativeUIError):self.make()
        self.assertTrue(self.owner.originals.history.store(3).path.exists())
    def test_unknown_then_neutral_original_input_between_quiet_samples_requires_a_new_window(self):
        sleep=self.owner.sleep;inserted=False
        def interrupt(seconds):
            nonlocal inserted
            sleep(seconds)
            if self.owner.state['phase']=='returned' and not inserted:
                inserted=True;self.native.publish('unavailable',0,'');self.native.publish('neutral',0,'')
        self.owner.sleep=interrupt
        with self.assertRaises(NativeUIError):self.owner.run_owned()
        self.assertTrue(inserted);self.assertEqual(2,len(self.inputs));self.assertNotIn('release',[row['operation'] for row in self.history.commands])
        self.owner=self.make();result=self.owner.run_owned();self.assertGreaterEqual(result['quietSeconds'],3)
        self.assertEqual(2,len(self.inputs));self.assertFalse(self.history.active)


if __name__=='__main__':unittest.main()
