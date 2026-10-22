"""Queued original callbacks/timers and positive weak-expiry counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import create_lifecycle as lifecycle
from ios.self_tests.test_ios_create_state import packet,version2,RUN,EPOCH,ID
from ios.self_tests.test_ios_create_work import packet as work_packet, ROOT
from self_tests.test_native_script_work import WorkBoundary


def worker(work,sequence=1,timers=None):
    seam=WorkBoundary();row=work['source']['roles'][0]
    seam.member=deepcopy(row['manager']);seam.code=deepcopy(row['code']);seam.epoch=work['clockAfter']['epochMs']+1
    seam.sequence=seam.work_sequence=sequence-1;seam.timers=[] if timers is None else deepcopy(timers)
    seam.send(dict(schemaVersion=1,commandId='ios-'+str(sequence)*32,action='feature-script-work-observe',managerInstance=row['manager']['instance']))
    result=deepcopy(seam.value);result['processId']=42;return result


def frames():
    before=version2(packet());after=deepcopy(before);after.update(sequence=2,requestId='ios-'+'f'*32)
    for key in ('epochMs','monotonicMs'):
        after['clockBefore'][key]+=100;after['clockAfter'][key]+=100
    first=work_packet();last=deepcopy(first);last.update(sequence=2,requestId='ios-'+'e'*32)
    for key in ('epochMs','monotonicMs'):
        last['clockBefore'][key]+=100;last['clockAfter'][key]+=100
    last['source']['entityLifetimes']['entities']=[dict(id=ID,bornEpochMs=EPOCH-10,destroyed=True,destructionObservedEpochMs=EPOCH+99,
        models=[dict(instance='a'*32,bornEpochMs=EPOCH-9,destroyed=True,destructionObservedEpochMs=EPOCH+99)])]
    timers=[dict(handle=7,active=True,singleShot=False,intervalMs=1000,remainingMs=999),
            dict(handle=8,active=True,singleShot=True,intervalMs=100,remainingMs=1)]
    initial=worker(first,timers=timers);current=worker(last,2,timers=timers[:1]);current['source']['work']['timers'][0]['remainingMs']=800
    return before,first,initial,after,last,current


class CreateLifecycleTests(unittest.TestCase):
    def test_original_recurring_timer_survives_and_expired_single_shot_is_not_fabricated_as_empty(self):
        args=frames();original=deepcopy(args)
        result=lifecycle.drained(*args,ROOT,[ID]);self.assertEqual([ID],result['entityIds']);self.assertEqual(args,original)
        self.assertEqual(1,len(args[-1]['source']['work']['timers']))
    def test_ack_zero_callback_or_missing_birth_cannot_replace_actual_worker_renderer_retirement(self):
        for fault in ('callback','timerCallback','evaluating','missingBirth','entityAlive','modelAlive','partial','wrongManager','wrongCode','oldWorker'):
            args=list(frames());current=args[-1];life=args[-2]['source']['entityLifetimes'];work=current['source']['work']
            if fault=='callback':work['signalCallbacks']=1
            elif fault=='timerCallback':work['timerCallbacks']=1
            elif fault=='evaluating':work['evaluating']=True
            elif fault=='missingBirth':life['entities']=[]
            elif fault=='entityAlive':life['entities'][0].update(destroyed=False,destructionObservedEpochMs=0)
            elif fault=='modelAlive':life['entities'][0]['models'][0].update(destroyed=False,destructionObservedEpochMs=0)
            elif fault=='partial':life['complete']=False
            elif fault=='wrongManager':current['source']['manager']['url']='qrc:/foreign.js'
            elif fault=='wrongCode':current['source']['code']['sha256']='f'*64
            else:current['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifecycle.drained(*args,ROOT,[ID])
    def test_new_inactive_timer_missing_recurring_timer_and_changed_configuration_are_owned_resources(self):
        for fault in ('new','removed','interval','inactive','repeat'):
            args=frames();timers=args[-1]['source']['work']['timers']
            if fault=='new':timers.append(dict(handle=9,active=False,singleShot=False,intervalMs=0,remainingMs=-1))
            elif fault=='removed':timers.clear()
            elif fault=='interval':timers[0]['intervalMs']=2000
            elif fault=='inactive':timers[0].update(active=False,remainingMs=-1)
            else:timers[0]['singleShot']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifecycle.drained(*args,ROOT,[ID])
    def test_observation_cursor_and_remaining_time_do_not_hide_real_work_activity(self):
        args=frames();first=lifecycle.drained(*args,ROOT,[ID]);current=deepcopy(args)
        current[-1]['source']['work']['timers'][0]['remainingMs']=700
        self.assertEqual(first['activitySha256'],lifecycle.drained(*current,ROOT,[ID])['activitySha256'])
        current[-2]['source']['entityLifetimes']['entities'][0]['models'][0]['destructionObservedEpochMs']+=1
        self.assertNotEqual(first['activitySha256'],lifecycle.drained(*current,ROOT,[ID])['activitySha256'])


if __name__=='__main__':unittest.main()
