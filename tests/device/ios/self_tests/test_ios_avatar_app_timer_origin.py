"""Actual original AvatarApp timers join native source2 and exact whole pins.

The Script runs in Node. Native engine identities and source snapshots remain
explicit model producers; no parser, callsite qualifier or verdict is patched.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_scripts,avatar_exact_callers
from ios.self_tests import avatar_callers2_fixture as source
from ios.self_tests.avatar_app_node import AvatarAppNode


def actual_timer(test):
    epoch=source.EPOCH+150
    node=AvatarAppNode(test,dict(self='00000000-0000-4000-8000-000000000001',joints=['Hips'],avatarUrl='https://owned.invalid/avatar.fst'),lambda:epoch)
    node.request('screen',open=True)
    actual=node.request('message',message=dict(method='addWearable',url='https://owned.invalid/wearable.gltf'))
    events=deepcopy(actual['events']);test.assertEqual(1,len(events));event=events[0];frames=event['details'].pop('callerFrames')
    test.assertEqual('created',event['kind']);test.assertTrue(frames)
    original,modules,_=source.original(tuple(row['url'].removeprefix('qrc:/scripts') for row in frames))
    for frame,observed in zip(original['frames'],frames):
        for key in ('line','column','isEval','isConstructor'):frame[key]=observed[key]
        frame['compiled']['firstObservedEpochMs']=epoch
    before=source.scripts2();after=source.scripts2(capture_offset=200,sequence=2,request='ios-'+'9'*32)
    worker=after['source']['workers'][0];caller=dict(id='a1'*16,callerStack=original,callerModules=modules)
    event['sequence']=1;event['details']['callerStackId']=caller['id']
    worker['avatar'].update(events=[event],callerStacks=[deepcopy(caller)])
    details=event['details']
    timer=dict(timerId=event['timerId'],handle=details['handle'],callerStackId=caller['id'],createdEpochMs=event['capturedEpochMs'],
        singleShot=details['singleShot'],intervalMs=details['intervalMs'],activeAtBirth=details['active'],remainingAtBirthMs=details['remainingMs'],
        destroyedEpochMs=None,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
    worker['uiWork'].update(timers=[timer],callerStacks=[deepcopy(caller)])
    return before,after


class AvatarAppTimerOriginTests(unittest.TestCase):
    def test_actual_avatar_app_timeout_is_readable_and_still_requires_exact_whole_callsite(self):
        before,after=actual_timer(self);avatar_scripts.original(after)
        manager=after['source']['workers'][0]['membership']['instance']
        self.assertEqual({'avatar-wearable-added'},set(avatar_exact_callers.owned_timers(before,after,{manager}).values()))
        changed=deepcopy(after)
        for component in ('avatar','uiWork'):changed['source']['workers'][0][component]['callerStacks'][0]['callerStack']['frames'][0]['line']+=1
        avatar_scripts.original(changed) # Module origin alone is deliberately weaker.
        with self.assertRaises(NativeUIError):avatar_exact_callers.owned_timers(before,changed,{manager})
    def test_missing_foreign_or_unsubmitted_module_never_qualifies_a_timer_origin(self):
        _before,after=actual_timer(self)
        for fault in ('missing','foreign','compiled','unsubmitted'):
            changed=deepcopy(after);worker=changed['source']['workers'][0]
            for component in ('avatar','uiWork'):
                caller=worker[component]['callerStacks'][0]
                if fault=='missing':caller['callerModules']=[]
                elif fault=='foreign':caller['callerModules'][0]['url']='https://foreign.invalid/system/avatarapp.js'
                elif fault=='compiled':caller['callerStack']['frames'][0]['compiled']['sha256']='b'*64
            if fault=='unsubmitted':worker['avatar']['code']=[row for row in worker['avatar']['code'] if not row['url'].endswith('/system/avatarapp.js')]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):avatar_scripts.original(changed)


if __name__=='__main__':unittest.main()
