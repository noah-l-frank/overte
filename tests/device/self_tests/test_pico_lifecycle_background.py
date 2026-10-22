"""Original evidence joins over explicit Qt, OS and native lifecycle seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_background as owner
from adapters.pico4.lifecycle_back import frame
from feature_journeys.fixtures import context
from self_tests.test_pico_lifecycle_source import Boundary as Ui,editor,RUN
from self_tests.test_pico_lifecycle_background_source import Native
from self_tests.test_native_feature_observation import Boundary as Feature
from self_tests.test_pico_lifecycle_back import BINDING


def evidence():
    ui=Ui();ui.rows=[editor(2,'chat')];ui.rows[0]['text']=context(RUN)['reply']
    before=ui.source().capture(RUN);before['source']['keyboard']['instance']='d'*32
    source=Native();source.sequence=1;source.intent=1;source.owner=RUN;source.original=editor(2,'chat')['id']
    source.arm_id='8'*32;source.armed_epoch=20000;source.active=True
    source.frame('arm');source.frames[0]['uiSequence']=source.frames[0]['keyboard']['sequence']=2
    def packet():
        source.sequence+=1
        return dict(lifecycleBackgroundVersion=1,commandId=f'{source.sequence+2000:032x}',runId=RUN,instance=source.instance,sequence=source.sequence,
            processId=123,capturedEpochMs=source.epoch,lastIntentSequence=1,performed=False,available=True,active=True,timerActive=True,
            released=False,expired=False,ownerRunId=RUN,originalId=source.original,armedEpochMs=20000,armCommandId=source.arm_id,
            releaseCommandId='',frames=deepcopy(source.frames))
    home=packet();source.publish('hidden');source.publish('active')
    for index,row in enumerate(source.frames):row['uiSequence']=row['keyboard']['sequence']=index+2
    returned=packet();after=deepcopy(before);after.update(commandId='7'*32,sequence=8,capturedEpochMs=20500)
    after['source']['editors'][0]['focused']=False
    ui.raised=False;ui.send(dict(commandId='7'*32,runId=RUN));after['source']['keyboard']=ui.value['source']['keyboard']
    after['source']['keyboard'].update(instance='d'*32,sequence=8)
    native=Feature();native.send(dict(commandId='6'*32));a=deepcopy(native.sample)
    b=deepcopy(a);b.update(requestId='5'*32,sequence=2,capturedEpochMs=20500,requestedEpochMs=20500)
    b['lifecycle'].update(backgrounds=1,activations=2);b['animationFence']['requestedEpochMs']=20500
    raw=lambda value:frame(json.dumps(value))
    return dict(beforeUi=raw(before),beforeNative=raw(a),home=raw(home),background=dict(binding=deepcopy(BINDING),running=True,foreground=False),
        foreground=dict(binding=deepcopy(BINDING),running=True,foreground=True),returned=raw(returned),afterUi=raw(after),afterNative=raw(b),
        arm=dict(schemaVersion=1,commandId=source.arm_id,action='feature-lifecycle-background',operation='arm',runId=RUN,
            ownerInstance=source.instance,intentSequence=1))


class LifecycleBackgroundEvidenceTests(unittest.TestCase):
    def setUp(self):self.value=evidence()
    def check(self):return owner.validate_return(self.value,RUN,BINDING)
    def change(self,key,callback):
        packet=json.loads(self.value[key]['raw']);callback(packet);self.value[key]=frame(json.dumps(packet))
    def test_original_os_native_hidden_and_returned_sources_join_same_reply_context_without_input(self):
        result=self.check();self.assertEqual(('chat',context(RUN)['reply'],False,False),
            tuple(result[key] for key in ('editor','text','focused','keyboard')))
        self.assertNotIn('generation',result) # Earlier Create/X originals are outside this component.
        self.assertTrue(result['journalRetained']);self.assertEqual(1,result['nativeBackgroundFrames'])
        self.assertEqual(result,self.check()) # Pure archived validation has no client or clock.
    def test_resumed_only_false_focus_keyboard_and_os_ack_cannot_replace_original_background(self):
        self.change('returned',lambda packet:packet['frames'][1].update(applicationState='inactive'))
        with self.assertRaises(NativeUIError):self.check()
    def test_background_requires_original_os_process_and_foreground_boundary(self):
        for key,edit in (('background',dict(foreground=True)),('foreground',dict(foreground=False)),('background',dict(running=False))):
            with self.subTest(key=key,edit=edit):
                self.value=evidence();self.value[key].update(edit)
                with self.assertRaises(NativeUIError):self.check()
        self.value=evidence();self.value['foreground']['binding']['processIdentity']='124:500'
        with self.assertRaises(NativeUIError):self.check()
    def test_missing_disabled_or_pressed_actual_vr_keyboard_never_counts_as_quiet(self):
        for edit in (dict(created=False),dict(enabled=False),dict(pressedKeys=1),dict(visible=True),dict(raised=True),dict(keyCount=0)):
            with self.subTest(edit=edit):
                self.value=evidence();self.change('returned',lambda packet:packet['frames'][1]['keyboard'].update(edit))
                with self.assertRaises(NativeUIError):self.check()
    def test_native_counter_ack_or_another_launch_cannot_qualify_same_process_return(self):
        for edit in (dict(backgrounds=0),dict(activations=1),dict(launches=2)):
            with self.subTest(edit=edit):
                self.value=evidence();self.change('afterNative',lambda packet:packet['lifecycle'].update(edit))
                with self.assertRaises(NativeUIError):self.check()
    def test_draft_context_replacement_and_retained_partial_identity_remain_unavailable(self):
        for edit in (dict(contextId='9'*32),dict(contextAlive=False),dict(focused=True)):
            with self.subTest(edit=edit):
                self.value=evidence();self.change('returned',lambda packet:packet['frames'][1]['editor'].update(edit))
                with self.assertRaises(NativeUIError):self.check()
    def test_modified_original_prefix_and_foreign_arm_cannot_be_joined(self):
        self.change('returned',lambda packet:packet['frames'][0]['keyboard'].update(keyCount=2))
        with self.assertRaises(NativeUIError):self.check()
        self.value=evidence();self.value['arm']['commandId']='4'*32
        with self.assertRaises(NativeUIError):self.check()
    def test_hidden_frame_from_before_home_cannot_be_adopted_as_owned_background(self):
        def early(packet):
            packet['frames'][1]['capturedEpochMs']=20000;packet['frames'][1]['uiCapturedEpochMs']=20000
            packet['frames'][1]['signalSequence']=0;packet['frames'][2]['signalSequence']=1
        self.change('returned',early)
        with self.assertRaises(NativeUIError):self.check()
    def test_late_current_ui_must_follow_original_background_history_cursors(self):
        self.change('afterUi',lambda packet:packet.update(sequence=3))
        with self.assertRaises(NativeUIError):self.check()
    def test_changed_original_settings_are_not_called_restored_by_return(self):
        self.change('afterNative',lambda packet:packet['audio'].update(muted=False))
        with self.assertRaises(NativeUIError):self.check()


if __name__=='__main__':unittest.main()
