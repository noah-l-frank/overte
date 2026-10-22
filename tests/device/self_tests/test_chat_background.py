"""Original OS route, actual strict native reader and full synthetic Chat joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.background import ChatBackground
from adapters.chat_journey.samples import ChatSamples
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.pico4.lifecycle_background_source import NativeLifecycleBackground
from adapters.script_journey.history import unpack
from self_tests import test_chat_journey_samples as chat
from self_tests.test_pico_lifecycle_background_source import Native
from self_tests.test_native_chat_observation import RUN


class OriginalOS:
    """Only device transport/installation boundaries; original OS getters run."""
    def __init__(self,case):
        self.case=case;self.pico_configuration=('explicit-layer',case.h.root);self.adb=self
        self.foreground=True;self.identity='123';self.inputs=[];self.effect=True;self.lost=None
        self.profile={'e2e_activity':'org.overte.pico/.E2eLauncherActivity'}
    def _installation(self,target):return dict(sourceRevision='1'*40,artifactSha256='2'*64)
    def process_state(self,target,package):return dict(running=True,identity=self.identity)
    def foreground_package(self,target):return 'org.overte.pico' if self.foreground else 'com.example.synthetic'
    def require_pico_session_identity(self,target):return self.identity
    def require_controlled_debug_identity(self,target):return self.identity
    def require(self,target):assert target==self.case.target
    def require_same_process(self,target,identity,operation):assert identity==self.identity
    def _pico_lifecycle_input_once(self,target,operation,binding,*,before_input):
        from adapters.pico4.lifecycle_input import issue_once
        return issue_once(self,target,operation,binding,before_input=before_input)
    def shell(self,target,*arguments):
        assert arguments in (('input','keyevent','KEYCODE_HOME'),('am','start','-W','-n',self.profile['e2e_activity']))
        return self.invoke(target,'lifecycle.background' if arguments[0]=='input' else 'app.launch',{})
    def invoke(self,target,operation,values):
        state=unpack(self.case.store.read()['payload'])[0]
        assert state['phase']==('background-issued' if operation=='lifecycle.background' else 'foreground-issued')
        self.inputs.append(operation)
        if self.effect:
            self.foreground=operation=='app.launch';self.case.native.publish('active' if self.foreground else 'hidden')
            if self.foreground:self.case.activations+=1
            else:self.case.backgrounds+=1
        if self.lost==operation:raise NativeUIError('Explicit lost original OS response')
        return dict(performed=True)


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.h=chat.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.native=Native();self.native.text='';self.native.focus=False;self.keyboard_sequence=0
        self.backgrounds=0;self.activations=1;self.next_timer=.25
        self.original=OriginalOS(self);self.os=PicoGraphicsBinding(self.original);self.target='synthetic-target'
        self.binding={key:value for key,value in self.h.samples.binding.items() if key!='scope'}|dict(sourceRevision='1'*40,artifactSha256='2'*64,
            targetFingerprint=hashlib.sha256((self.target+'\0'+str(self.original.pico_configuration)).encode()).hexdigest())
        self.peer_binding={**self.binding,'processIdentity':'456','targetFingerprint':'d'*64}
        self.h.open('domain');self.store=PrivateFeatureState(self.h.root/'background.json')
        for boundary in (self.h.primary,self.h.peer,self.h.view,self.h.native):
            previous=boundary.mutate
            def mutate(value,previous=previous):
                if previous:previous(value)
                value['capturedEpochMs']=self.native.epoch
                if 'requestedEpochMs' in value:
                    value['requestedEpochMs']=self.native.epoch;value['animationFence']['requestedEpochMs']=self.native.epoch
                    value['animation']['capturedEpochMs']=self.native.epoch;value['animation']['clip']['evaluatedEpochMs']=self.native.epoch
                if 'source' in value and 'keyboard' in value['source']:
                    self.keyboard_sequence+=1;value['source']['keyboard']['sequence']=self.keyboard_sequence
                if 'lifecycle' in value:value['lifecycle'].update(backgrounds=self.backgrounds,activations=self.activations)
            boundary.mutate=mutate
        original_frame=self.native.frame
        def frame(cause):
            original_frame(cause);self.keyboard_sequence+=1
            self.native.frames[-1]['keyboard'].update(instance='e'*32,sequence=self.keyboard_sequence,keyCount=2)
        self.native.frame=frame
        class Pending:
            def read(_self):return dict(inputs=unpack(self.store.read()['payload'])[0]['sourceInputs'])
        self.native.pending=Pending()
        self.roles=(self.samples('primary',self.h.store),self.samples('actor',PrivateFeatureState(self.h.root/'actor.json')))
        self.owner=self.create()
    def samples(self,role,store,*,kind=ChatSamples):
        peer=self.h.peer.reader();peer.pid=456
        result=kind(RUN,role,self.binding,self.peer_binding,self.h.primary.reader(),peer,self.h.view.reader(vr=True),self.h.native.reader(),store,
            self.h.primary_lock,self.h.peer_lock,vr=True,monotonic=lambda:self.native.host)
        for reader in (result.primary,result.peer,result.view,result.lifecycle):
            reader.clock_ms=lambda:self.native.epoch
            original=reader.guard
            def guard(original=original):return self.original.foreground and original()
            reader.guard=guard
        return result
    def source(self,intent):
        return NativeLifecycleBackground(self.native.send,lambda:self.native.raw,lambda:self.native.epoch,lambda:self.original.foreground,123,
            self.h.primary_lock,intent=intent,monotonic=lambda:self.native.host,sleep=self.sleep)
    def create(self):return ChatBackground(self.roles,self.source,self.os,self.target,self.store,monotonic=lambda:self.native.host,sleep=self.sleep)
    def sleep(self,seconds):
        end=self.native.host+seconds
        while self.native.active and self.next_timer<=end:
            if self.next_timer>self.native.host:
                delta=self.next_timer-self.native.host;self.native.host=self.next_timer;self.native.epoch+=round(delta*1000)
            self.next_timer+=.25;self.native.frame('timer')
        delta=end-self.native.host;self.native.host=end;self.native.epoch+=round(delta*1000)
    def test_original_home_return_hidden_keyboard_history_same_models_quiet_and_timer_release(self):
        result=self.owner.run(20000)
        self.assertTrue(all(row['state']['open'] and row['state']['channel']=='domain' and not row['state']['keyboard'] for row in result))
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)
        self.assertEqual('observed',self.owner.state['phase']);self.assertTrue(self.native.released);self.assertFalse(self.native.active)
        self.assertGreaterEqual(len(self.owner.state['quiet']),31);self.assertGreaterEqual(len(self.owner.state['releasedQuiet']),31);self.assertTrue(self.store.path.exists())
        before=len(self.native.commands);self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store));rebuilt=self.create()
        self.assertEqual(before,len(self.native.commands));self.assertEqual('observed',rebuilt.state['phase'])
        with self.assertRaises(NativeUIError):rebuilt.run(20000)
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)
    def test_lost_home_response_recovers_only_distinct_resume_and_original_timer_never_replays_home(self):
        self.original.lost='lifecycle.background'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs);self.assertTrue(self.original.foreground)
        self.assertEqual('failed',self.owner.state['phase']);self.assertTrue(self.native.released);self.assertTrue(self.store.path.exists())
    def test_cold_background_recovery_uses_only_os_sources_then_original_same_process_history(self):
        self.original.lost='lifecycle.background'
        with patch.object(ChatBackground,'recover_foreground',side_effect=NativeUIError('Explicit unavailable recovery transport')):
            with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertFalse(self.original.foreground);before=len(self.native.commands)
        self.original.lost=None;value=ChatBackground.recover_foreground(self.os,self.target,self.store,self.h.primary_lock,monotonic=lambda:self.native.host,sleep=self.sleep)
        self.assertTrue(value['foregroundRecovered']);self.assertNotIn('state',value);self.assertEqual(before,len(self.native.commands))
        self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store));self.owner=self.create()
        self.owner.run(20000);self.assertEqual('observed',self.owner.state['phase'])
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)

    def test_lost_original_release_is_reconciled_with_fresh_original_id_and_no_second_input(self):
        self.native.lost='release'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertTrue(self.native.released);self.assertFalse(self.native.active);self.native.lost=None
        original_inputs=deepcopy(self.original.inputs);before=[row['operation'] for row in self.native.commands].count('release')
        self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store));self.owner=self.create()
        self.owner.inspect_released();self.assertEqual('observed',self.owner.state['phase'])
        self.assertEqual(original_inputs,self.original.inputs);self.assertEqual(before,[row['operation'] for row in self.native.commands].count('release'))

    def test_real_os_background_cannot_borrow_missing_disabled_visible_or_focused_native_keyboard(self):
        for fault in ('missing','disabled','visible','focused','context'):
            with self.subTest(fault=fault):
                self.setUp();original=self.native.frame
                def corrupt(cause):
                    original(cause);frame=self.native.frames[-1]
                    if frame['applicationState']=='hidden':
                        if fault=='missing':frame['keyboard']['created']=False
                        elif fault=='disabled':frame['keyboard']['enabled']=False
                        elif fault=='visible':frame['keyboard']['visible']=True
                        elif fault=='focused':frame['editor']['focused']=True;frame['focusedEditors']=1
                        else:frame['editor']['contextId']='f'*32
                self.native.frame=corrupt
                with self.assertRaises(NativeUIError):self.owner.run(20000)
                self.assertNotEqual('observed',self.owner.state['phase']);self.assertTrue(self.store.path.exists())

    def test_replaced_original_chat_page_after_return_is_not_the_same_background_owner(self):
        original=self.original.invoke
        def changed(*args):
            value=original(*args)
            if args[1]=='app.launch':self.h.view.source['ui']['generation']='f'*32
            return value
        self.original.invoke=changed
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertNotEqual('observed',self.owner.state['phase'])

    def test_extra_lifecycle_activation_after_original_quiet_cannot_qualify_final_closure(self):
        original=self.owner.source.release_owned
        def changed(*args):
            value=original(*args);self.activations+=1;return value
        self.owner.source.release_owned=changed
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertTrue(self.native.released);self.assertNotEqual('observed',self.owner.state['phase'])

    def test_elapsed_without_original_native_time_and_hidden_timer_does_not_qualify(self):
        original=self.native.frame
        def changed(cause):
            original(cause)
            if self.native.frames[-1]['applicationState']=='hidden':
                hidden=[row for row in self.native.frames if row['applicationState']=='hidden']
                self.native.frames[-1]['capturedEpochMs']=hidden[0]['capturedEpochMs']
                self.native.frames[-1]['uiCapturedEpochMs']=hidden[0]['uiCapturedEpochMs']
        self.native.frame=changed
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertNotEqual('observed',self.owner.state['phase'])

    def test_delayed_keyboard_or_chat_after_actual_timer_release_cannot_escape_final_quiet(self):
        for fault in ('keyboard','chat'):
            with self.subTest(fault=fault):
                self.setUp();original=self.sleep;released_at=None;changed=False
                def sleep(seconds):
                    nonlocal released_at,changed
                    original(seconds)
                    if self.native.released:
                        if released_at is None:released_at=self.native.host
                        elif not changed and self.native.host-released_at>=2:
                            changed=True
                            if fault=='keyboard':
                                from self_tests.test_pico_chat_keyboard import keyboard
                                self.h.view.source['keyboard']=keyboard(True)
                            else:
                                from feature_journeys.fixtures import context
                                self.h.accept(context(RUN)['hidden'])
                self.owner.sleep=sleep
                with self.assertRaises(NativeUIError):self.owner.run(20000)
                self.assertTrue(changed);self.assertTrue(self.native.released);self.assertNotEqual('observed',self.owner.state['phase'])
                self.assertTrue(self.store.path.exists());self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)

    def test_error_recovery_reads_and_parent_writes_hold_both_original_locks(self):
        self.original.lost='lifecycle.background';original_guard=self.owner.source.guard;original_write=self.store.write
        def guarded():
            for lock in self.roles[0].locks:lock.assert_held()
            return original_guard()
        def write(*args):
            for lock in self.roles[0].locks:lock.assert_held()
            return original_write(*args)
        self.owner.source.guard=guarded;self.store.write=write
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs);self.assertTrue(self.native.released)
        self.assertEqual('failed',self.owner.state['phase']);self.assertFalse(self.native.active)

    def test_lost_parent_manifest_write_preserves_original_phase_and_performed_input_without_warm_overwrite(self):
        original=self.store.write;lost=False
        def write(value,previous):
            nonlocal lost
            original(value,previous)
            if not lost and unpack(value['payload'])[0]['phase']=='foreground-observed':
                lost=True;raise OSError('Explicit lost acknowledgement after actual parent manifest rename')
        self.store.write=write
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        actual=unpack(self.store.read()['payload'])[0]
        self.assertTrue(lost);self.assertEqual('foreground-observed',actual['phase']);self.assertTrue(self.native.active)
        self.assertEqual(['arm'],[row['operation'] for row in actual['sourceInputs']]);self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)
        self.store.write=original;self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store));self.owner=self.create()
        self.owner.run(20000);self.assertEqual('observed',self.owner.state['phase']);self.assertTrue(self.native.released)
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)

    def test_lost_manifest_after_actual_release_keeps_release_original_and_never_resends_it(self):
        import json
        original=self.store.write;lost=False
        def write(value,previous):
            nonlocal lost
            original(value,previous);state=unpack(value['payload'])[0]
            if not lost and state['sources'] and json.loads(state['sources'][-1]['raw'])['released']:
                lost=True;raise OSError('Explicit lost parent write response after native timer release')
        self.store.write=write
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        actual=unpack(self.store.read()['payload'])[0];self.assertTrue(lost);self.assertTrue(self.native.released)
        self.assertEqual('release-issued',actual['phase']);self.assertTrue(json.loads(actual['sources'][-1]['raw'])['released'])
        self.assertEqual(2,len(actual['sourceInputs']));self.assertEqual([],actual['releasedQuiet'])
        self.store.write=original;self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store));self.owner=self.create()
        self.owner.run(20000);self.assertEqual('observed',self.owner.state['phase'])
        self.assertEqual(1,[row['operation'] for row in self.native.commands].count('release'))
        self.assertEqual(['lifecycle.background','app.launch'],self.original.inputs)

    def test_v1_missing_post_release_originals_is_retained_without_adoption_or_new_input(self):
        self.owner.run(20000);current=self.store.read();old={**current,'chatBackgroundVersion':1};self.store.write(old,current)
        before=len(self.native.commands)
        self.roles=(self.samples('primary',self.h.store),self.samples('actor',self.roles[1].store))
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual(old,self.store.read());self.assertEqual(before,len(self.native.commands))

    def test_source_receipt_or_os_ack_cannot_replace_actual_hidden_keyboard_and_lifecycle(self):
        self.original.effect=False
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(['lifecycle.background'],self.original.inputs);self.assertNotEqual('observed',self.owner.state['phase'])
    def test_new_process_cannot_be_adopted_for_background_recovery_or_normal_activation(self):
        self.original.lost='lifecycle.background'
        invoke=self.original.invoke
        def changed(*args):
            try:return invoke(*args)
            finally:self.original.identity='999:new-start'
        self.original.invoke=changed
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(['lifecycle.background'],self.original.inputs);self.assertFalse(self.original.foreground)
        with self.assertRaises(NativeUIError):ChatBackground.recover_foreground(self.os,self.target,self.store,self.h.primary_lock,monotonic=lambda:self.native.host,sleep=self.sleep)
        self.assertEqual(['lifecycle.background'],self.original.inputs)


if __name__=='__main__':unittest.main()
