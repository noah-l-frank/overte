"""Actual strict history reader/locks/storage over explicit native Qt/VR facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import lifecycle_background_source as source
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_source import editor,RUN
from feature_journeys.fixtures import context


class Native:
    def __init__(self):
        self.epoch=20000;self.host=0.;self.sequence=self.intent=self.signals=0;self.instance='b'*32
        self.owner='';self.original='';self.arm_id=self.release_id='';self.armed_epoch=0
        self.active=self.released=self.expired=False;self.available=True;self.frames=[];self.raw='';self.commands=[]
        self.pending=None;self.lost=None;self.qt='active';self.focus=True;self.text=context(RUN)['reply'];self.mutate=None
    def frame(self,cause):
        row=editor(2,'chat');row.update(text=self.text,focused=self.focus)
        index=len(self.frames)+1
        self.frames.append(dict(frameId=f'{index+1000:032x}',sequence=index,capturedEpochMs=self.epoch,elapsedMs=round(self.host*1000),
            cause=cause,applicationState=self.qt,signalSequence=self.signals,uiInstance='c'*32,uiSequence=index,
            uiCapturedEpochMs=self.epoch,tabletShown=True,onHomeScreen=False,currentId=row['id'],focusedEditors=int(self.focus),editor=row,
            keyboard=dict(instance='d'*32,sequence=index,created=True,enabled=True,visible=self.focus,raised=self.focus,keyCount=1,pressedKeys=0)))
    def publish(self,state):
        self.epoch+=250;self.host+=.25;self.qt=state;self.signals+=1;self.focus=False;self.frame('application-state')
    def send(self,request):
        source.command(request);self.commands.append(deepcopy(request));operation=request['operation'];performed=False
        if operation!='observe':
            assert self.pending.read()['inputs'][-1]==request
            assert request['ownerInstance']==self.instance and request['intentSequence']==self.intent+1
            self.intent+=1
        if operation=='arm':
            assert not self.owner;self.owner=RUN;self.original=editor(2,'chat')['id'];self.arm_id=request['commandId'];self.armed_epoch=self.epoch
            self.active=True;self.frame('arm');performed=True
        elif operation=='release':
            self.active=False;self.released=True;self.release_id=request['commandId'];performed=True
        elif self.active:self.frame('query')
        self.sequence+=1
        packet=dict(lifecycleBackgroundVersion=1,commandId=request['commandId'],runId=RUN,instance=self.instance,sequence=self.sequence,
            processId=123,capturedEpochMs=self.epoch,lastIntentSequence=self.intent,performed=performed,available=self.available,
            active=self.active,timerActive=self.active,released=self.released,expired=self.expired,ownerRunId=self.owner,originalId=self.original,
            armedEpochMs=self.armed_epoch,armCommandId=self.arm_id,releaseCommandId=self.release_id,frames=deepcopy(self.frames))
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
        if self.lost==operation:raise NativeUIError('Explicit lost original source response')


class LifecycleBackgroundSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-bg-source-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.native=Native()
        self.store=PrivateFeatureState(self.root/'intent.json');self.native.pending=self.store
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.alive=True
        self.reader=source.NativeLifecycleBackground(self.native.send,lambda:self.native.raw,lambda:self.native.epoch,lambda:self.alive,123,self.lock,
            intent=self.intent,monotonic=lambda:self.native.host,sleep=lambda dt:setattr(self.native,'host',self.native.host+dt))
    def intent(self,request):
        previous=self.store.read();self.store.write(dict(inputs=(previous or dict(inputs=[]))['inputs']+[deepcopy(request)]),previous)
    def armed(self):self.reader.read(RUN);return self.reader.arm(RUN)
    def arm_request(self):return self.store.read()['inputs'][0]
    def test_original_hidden_and_resumed_facts_are_immutable_and_release_is_actual_source_timer_only(self):
        first=self.armed();self.native.publish('hidden');self.native.publish('active');observed=self.reader.read(RUN)
        self.assertEqual(first['frames'],observed['frames'][:1]);self.assertEqual('hidden',observed['frames'][1]['applicationState'])
        self.assertFalse(observed['frames'][1]['keyboard']['visible']);self.assertFalse(observed['frames'][1]['editor']['focused'])
        self.assertEqual(context(RUN)['reply'],observed['frames'][2]['editor']['text'])
        released=self.reader.release_owned(RUN,self.arm_request())
        self.assertTrue(released['released']);self.assertFalse(released['timerActive']);self.assertFalse(released['active'])
        self.assertTrue(self.store.path.exists());self.assertEqual(2,len(self.store.read()['inputs']))
        self.assertEqual(self.reader.last_raw,self.native.raw);self.assertTrue(self.reader.last_sha256)
    def test_empty_unfocused_current_chat_is_observed_without_manufacturing_focus_or_keyboard(self):
        self.native.text='';self.native.focus=False;armed=self.armed();frame=armed['frames'][0]
        self.assertFalse(frame['editor']['focused']);self.assertFalse(frame['keyboard']['visible']);self.assertEqual('',frame['editor']['text'])
        self.assertEqual(['observe','arm'],[row['operation'] for row in self.native.commands])
    def test_cold_reader_restores_only_original_historical_bytes_then_requires_new_same_source_history(self):
        self.armed();raw=self.reader.last_raw;digest=self.reader.last_sha256
        restored=source.NativeLifecycleBackground(self.native.send,lambda:self.native.raw,lambda:self.native.epoch,lambda:self.alive,123,self.lock,
            intent=self.intent,monotonic=lambda:self.native.host,sleep=lambda _dt:None)
        self.native.publish('hidden');self.native.publish('active');before=len(self.native.commands)
        self.assertIsNone(restored.restore(raw));self.assertEqual(before,len(self.native.commands));self.assertEqual(digest,restored.last_sha256)
        self.assertEqual(raw,restored.last_raw);fresh=restored.read(RUN);self.assertGreater(fresh['sequence'],self.reader.last['sequence'])
        self.assertEqual(self.reader.last['frames'],fresh['frames'][:1])
        self.native.instance='9'*32
        with self.assertRaises(NativeUIError):restored.read(RUN)
    def test_uncertain_arm_is_read_only_reconciled_by_original_native_arm_id_without_rearm(self):
        self.reader.read(RUN);self.native.lost='arm'
        with self.assertRaises(NativeUIError):self.reader.arm(RUN)
        self.native.lost=None;current=self.reader.read(RUN);self.assertEqual(self.arm_request()['commandId'],current['armCommandId'])
        with self.assertRaises(NativeUIError):self.reader.arm(RUN)
        self.assertEqual(1,[row['operation'] for row in self.native.commands].count('arm'))
    def test_uncertain_release_never_sends_another_release(self):
        self.armed();self.native.lost='release'
        with self.assertRaises(NativeUIError):self.reader.release_owned(RUN,self.arm_request())
        self.native.lost=None;observed=self.reader.read(RUN)
        self.assertTrue(observed['released']);self.assertEqual(self.store.read()['inputs'][-1]['commandId'],observed['releaseCommandId'])
        with self.assertRaises(NativeUIError):self.reader.release_owned(RUN,self.arm_request())
        self.assertEqual(1,[row['operation'] for row in self.native.commands].count('release'))
    def test_performed_ack_with_another_original_arm_id_cannot_qualify_the_observer(self):
        self.reader.read(RUN)
        self.native.mutate=lambda packet:packet.update(armCommandId='9'*32)
        with self.assertRaises(NativeUIError):self.reader.arm(RUN)
        self.assertEqual(1,[row['operation'] for row in self.native.commands].count('arm'))
        self.native.mutate=None;observed=self.reader.read(RUN)
        self.assertEqual(self.arm_request()['commandId'],observed['armCommandId'])
    def test_foreign_source_cursor_or_original_arm_cannot_authorize_timer_release(self):
        self.armed();self.native.intent+=1
        with self.assertRaises(NativeUIError):self.reader.release_owned(RUN,self.arm_request())
        self.assertNotIn('release',[row['operation'] for row in self.native.commands]);self.assertTrue(self.native.active)
    def test_rewritten_original_frames_and_changed_context_cannot_be_adopted_as_new_history(self):
        self.armed();before=deepcopy(self.reader.last)
        self.native.frames[0]['editor']['text']=''
        with self.assertRaises(NativeUIError):self.reader.read(RUN)
        self.assertEqual(before,self.reader.last)
    def test_unavailable_native_source_never_becomes_released_keyboard_or_forged_cleanup(self):
        self.armed();self.native.available=False;self.native.active=False
        observed=self.reader.read(RUN);self.assertFalse(observed['available']);self.assertTrue(observed['frames'][0]['keyboard']['visible'])
        released=self.reader.release_owned(RUN,self.arm_request());self.assertFalse(released['available']);self.assertTrue(released['released'])
    def test_failed_intent_and_candidate_guard_prevent_first_source_mutation(self):
        self.reader.read(RUN)
        with patch.object(self.store,'write',side_effect=OSError('Explicit fsync failure')),self.assertRaises(NativeUIError):self.reader.arm(RUN)
        self.assertEqual(['observe'],[row['operation'] for row in self.native.commands]);self.alive=False
        with self.assertRaises(NativeUIError):self.reader.read(RUN)
        self.assertEqual(1,len(self.native.commands))
    def test_raw_bound_precedes_decode_and_aged_final_native_clock_is_rejected_with_frozen_host(self):
        self.reader.read(RUN);original=self.reader.original
        self.reader.original=lambda:'x'*(source.LIMIT+1)
        with patch.object(source,'decode',side_effect=AssertionError('Oversized input decoded')),self.assertRaises(NativeUIError):self.reader.read(RUN)
        self.reader.original=original;accept=source.accept;before=self.native.host
        def late(*args):accept(*args);self.native.epoch+=2000
        with patch.object(source,'accept',side_effect=late),self.assertRaises(NativeUIError):self.reader.read(RUN)
        self.assertEqual(before,self.native.host)
    def test_busy_shared_source_publisher_cannot_send_a_query(self):
        self.lock.timeout=.01
        with ScriptSourceLock(self.lock.path,timeout=.01).held(),self.assertRaises(NativeUIError):self.reader.read(RUN)
        self.assertEqual([],self.native.commands)


if __name__=='__main__':unittest.main()
