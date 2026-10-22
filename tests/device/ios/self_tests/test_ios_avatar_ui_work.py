"""Original timer snapshots and actual callback-stack/lifetime counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_ui_work as work,avatar_scripts
from ios.self_tests.test_ios_avatar_social import SocialFixture


def component():return dict(avatarUiWorkVersion=1,instance='f'*32,complete=True,timers=[])


def timer():
    return dict(timerId='e'*32,handle=1,callerChain=['qrc:/scripts/system/avatarapp.js'],createdEpochMs=9000001150,
        singleShot=True,intervalMs=300,activeAtBirth=True,remainingAtBirthMs=300,destroyedEpochMs=9000001160,
        fired=1,entered=1,left=1,depth=0,pendingDispatch=0,lastFiredEpochMs=9000001160,
        lastCallbackEpochMs=9000001180,lastDispatchEpochMs=9000001190)


class AvatarUiWorkTests(unittest.TestCase):
    def setUp(self):
        f=SocialFixture();self.expected=f.expected;self.before=deepcopy(f.frames['primary']['originals']['scripts'])
        self.before['source']['workers'][0]['uiWork']=component();self.mid=self.before['source']['workers'][0]['membership']['instance']
        self.after=deepcopy(self.before);self.after.update(requestId='ios-'+'b'*32,sequence=self.before['sequence']+1)
        for key in ('clockBefore','clockAfter'):self.after[key]=dict(epochMs=9000001210,monotonicMs=1210)
        self.after['source']['workers'][0]['uiWork']['timers']=[timer()]
    def drained(self):return work.drained_since(self.before,self.after,{self.mid},self.expected)
    def test_optional_new_component_keeps_legacy_worker_readable_but_cannot_invent_timer_absence(self):
        legacy=deepcopy(self.before);del legacy['source']['workers'][0]['uiWork'];avatar_scripts.original(legacy)
        with self.assertRaises(NativeUIError):work.drained_since(legacy,self.after,{self.mid},self.expected)
        result=self.drained();self.assertEqual(9000001190,result['endpointEpochMs']);self.assertEqual({'e'*32},set(result['owned'][self.mid]))
        self.assertEqual(1,self.after['iosAvatarScriptsVersion'])
    def test_singleShot_weak_death_before_JS_entry_does_not_prove_original_dispatch_returned(self):
        row=self.after['source']['workers'][0]['uiWork']['timers'][0]
        row.update(entered=0,left=0,depth=0,pendingDispatch=1,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
        avatar_scripts.original(self.after)
        self.assertTrue(avatar_scripts.drained(self.after,{self.mid})) # Legacy protocol-only predicate is deliberately insufficient.
        with self.assertRaises(NativeUIError):self.drained()
    def test_retained_QTimer_or_callback_depth_or_dispatch_owner_prevents_cleanup(self):
        for fault in ('timer','callback','dispatch','missing-component','new-source','changed-module'):
            value=deepcopy(self.after);self.after=value;row=value['source']['workers'][0]['uiWork']['timers'][0]
            if fault=='timer':row['destroyedEpochMs']=None
            elif fault=='callback':row.update(left=0,depth=1,pendingDispatch=1)
            elif fault=='dispatch':row['pendingDispatch']=1
            elif fault=='missing-component':del value['source']['workers'][0]['uiWork']
            elif fault=='new-source':value['source']['workers'][0]['uiWork']['instance']='d'*32
            else:value['source']['workers'][0]['avatar']['code'][0]['sha256']='0'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.drained()
            self.setUp()
    def test_counter_and_birth_history_cannot_reset_rename_or_lose_a_once_observed_timer(self):
        base=self.after['source']['workers'][0]['uiWork']
        for fault in ('missing','counter','created','destroyed','version','prefix'):
            value=deepcopy(base)
            if fault=='missing':value['timers']=[]
            elif fault=='counter':value['timers'][0].update(entered=0,left=0,lastCallbackEpochMs=None)
            elif fault=='created':value['timers'][0]['createdEpochMs']-=1
            elif fault=='destroyed':value['timers'][0]['destroyedEpochMs']+=1
            elif fault=='version':value['avatarUiWorkVersion']=True
            else:value['timers'][0]['callerChain']=['qrc:/scripts/system/pal.js']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):work.validate(value,9000001300,base)
    def test_original_source_downgrade_and_unrelated_manager_cannot_hide_owned_UI_work(self):
        previous=deepcopy(self.before);value=deepcopy(self.after);del value['source']['workers'][0]['uiWork']
        query=dict(schemaVersion=1,commandId=value['requestId'],action=avatar_scripts.ACTION,runId=value['runId'])
        with self.assertRaises(NativeUIError):avatar_scripts.validate(value,query,value['processId'],previous=previous)
        with self.assertRaises(NativeUIError):work.drained_since(self.before,self.after,{'a'*32},self.expected)

    def test_original_unowned_periodic_timer_can_continue_without_becoming_owned_cleanup(self):
        old=timer();old.update(timerId='d'*32,handle=2,createdEpochMs=9000001000,destroyedEpochMs=None,
            lastFiredEpochMs=9000001010,lastCallbackEpochMs=9000001020,lastDispatchEpochMs=9000001030,singleShot=False,intervalMs=100)
        self.before['source']['workers'][0]['uiWork']['timers']=[old]
        current=deepcopy(old);current.update(fired=1000,entered=1000,left=1000,
            lastFiredEpochMs=9000001200,lastCallbackEpochMs=9000001201,lastDispatchEpochMs=9000001202)
        self.after['source']['workers'][0]['uiWork']['timers'].insert(0,current)
        result=self.drained();self.assertEqual({'e'*32},set(result['owned'][self.mid]));self.assertEqual(9000001190,result['endpointEpochMs'])


if __name__=='__main__':unittest.main()
