"""Original contact inventories at synthetic boundaries, no device input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
import unittest

from adapters.native_phone_touch_state import NativePhoneTouchState,command,released
from adapters.normal_ui import NativeUIError
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests.test_native_feature_observation import probe_source


class Boundary(AvatarBoundary):
    def __init__(self):
        super().__init__()
        self.touch=dict(phoneTouchStateVersion=1,pluginActive=True,eventPointCount=0,moveContact=False,viewContact=False,
            buttonContacts=0,unusedContacts=0,axes=[],pressedButtons=[],pendingPinchIn=0.,pendingPinchOut=0.,lastPinchScale=0.)

    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;self.epoch+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.touch))
        if self.edit:self.edit(self.sample)

    def reader(self,**options):
        return NativePhoneTouchState(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)


class PhoneTouchStateTests(unittest.TestCase):
    def test_original_inventory_is_not_a_release_receipt_or_requested_empty_state(self):
        b=Boundary();b.touch['axes']=[dict(channel=0,value=0.)];value=b.reader().read()
        self.assertEqual(b.sample,value);self.assertEqual(b.touch,released(value))
        self.assertEqual({'schemaVersion','commandId','action'},set(b.commands[0]))

    def test_every_retained_contact_axis_button_or_pinch_blocks_retirement(self):
        for edit in (dict(pluginActive=False),dict(eventPointCount=1),dict(moveContact=True),dict(viewContact=True),
                dict(buttonContacts=1),dict(unusedContacts=1),dict(axes=[dict(channel=0,value=.001)]),dict(pressedButtons=[0]),
                dict(pendingPinchIn=.01),dict(pendingPinchOut=.01),dict(lastPinchScale=1.)):
            b=Boundary();b.touch.update(edit);value=b.reader().read()
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):released(value)

    def test_closed_versioned_bounded_inventory_refuses_coercion_or_truncation(self):
        for edit in (dict(phoneTouchStateVersion=True),dict(eventPointCount=33),dict(buttonContacts=-1),dict(moveContact=0),
                dict(axes=[dict(channel=6,value=0)]),dict(axes=[dict(channel=0,value=0)]*2),
                dict(axes=[dict(channel=0,value=float('nan'))]),dict(pressedButtons=[0,0]),dict(pressedButtons=[2]),
                dict(pendingPinchIn=-1),dict(expectedReleased=True)):
            b=Boundary();b.touch.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read()

    def test_command_has_no_release_setter_expected_value_or_platform_alias(self):
        valid=dict(schemaVersion=1,commandId='a'*32,action='phone-touch-state-observe')
        self.assertEqual(valid,command(valid))
        for edit in (dict(schemaVersion=True),dict(commandId='ios-'+'a'*32),dict(released=True),dict(action='phone-touch-state-release')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(valid|edit)

    def test_missing_ignored_stale_foreign_or_nonadvancing_originals_fail(self):
        for kind in ('ignore','missing','foreign','stale','cursor','birth','pid'):
            b=Boundary();reader=b.reader();first=reader.read()
            if kind=='ignore':b.ignored=True
            elif kind=='missing':b.edit=lambda value:value.pop('source')
            elif kind=='foreign':b.edit=lambda value:value.update(requestId='a'*32)
            elif kind=='stale':b.edit=lambda value:value.update(requestedEpochMs=1,capturedEpochMs=1)
            elif kind=='cursor':b.edit=lambda value:value.update(sequence=1)
            elif kind=='birth':b.edit=lambda value:value.update(instance='a'*32)
            else:b.edit=lambda value:value.update(processId=32)
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):reader.read()
            self.assertEqual(first,reader.last)

    def test_final_guard_and_stopped_clock_cannot_hide_late_retirement(self):
        b=Boundary();reader=b.reader();count=[0]
        def guard():
            count[0]+=1
            if count[0]==4:b.clock+=1.6
            return True
        reader.guard=guard
        with self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.last)

    def test_historical_replay_does_not_query_or_retime_release_proof(self):
        b=Boundary();reader=b.reader();frames=[reader.read(),reader.read()];again=b.reader();count=len(b.commands)
        again.restore(frames);self.assertEqual(count,len(b.commands));self.assertEqual(frames[-1],again.last)
        with self.assertRaises(NativeUIError):b.reader().restore(frames[::-1])

    def test_actual_probe_forwards_once_and_missing_hooks_cannot_prove_released(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let files=[],calls=[];
const original={requestId:"a".repeat(32),capturedEpochMs:17000,source:{eventPointCount:2}};
const Test={phoneTouchObservation:c=>{calls.push(c);return original;},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"phone-touch-state-observe"};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].n!=="phone-touch-state.json")throw Error("original replaced");
applyAndroidControlCommand({...c,commandId:"b".repeat(32),released:true});
if(calls.length!==1)throw Error("expected retirement admitted");
delete Test.phoneTouchObservation;applyAndroidControlCommand({...c,commandId:"c".repeat(32)});
if(files.length!==2||files[1].v.available!==false||original.capturedEpochMs!==17000)throw Error("missing hook green/retimed");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
