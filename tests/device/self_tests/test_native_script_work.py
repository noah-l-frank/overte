"""Original worker inventory decoder against synthetic native boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_script_work import NativeScriptWork,command,validate
from adapters.normal_ui import NativeUIError

MANAGER='c'*32


class WorkBoundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.work_sequence=0;self.okay=True;self.ignored=False
        self.value=None;self.commands=[];self.mutate=None;self.extra=[];self.revision=1
        self.member=dict(instance=MANAGER,assigned=True,url='file:///actual/scripts/system/+android_phoneInterface/phoneEmote.js',
            loadGeneration=1,assignedEpochMs=14000)
        self.code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=10,sha256=hashlib.sha256(b'original').hexdigest(),submittedEpochMs=15000)
        self.timers=[];self.signal_callbacks=0;self.timer_callbacks=0;self.evaluating=False
    def sleep(self,seconds):self.clock+=seconds
    def send(self,request):
        command(request,ios=request['commandId'].startswith('ios-'));self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;self.work_sequence+=1
        worker=dict(membership=deepcopy(self.member),running=True,stopping=False,finished=False,done=False)
        self.value=dict(schemaVersion=1,requestId=request['commandId'],instance='a'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=dict(complete=True,revision=self.revision,
                manager=deepcopy(self.member),code=deepcopy(self.code),workers=[worker]+deepcopy(self.extra),
                work=dict(scriptWorkVersion=1,requestId=request['commandId'],sequence=self.work_sequence,
                    requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,signalCallbacks=self.signal_callbacks,
                    timerCallbacks=self.timer_callbacks,evaluating=self.evaluating,timers=deepcopy(self.timers))))
        if self.mutate:self.mutate(self.value)
    def original(self):return json.dumps(self.value) if self.value is not None else ''
    def reader(self,**kwargs):
        return NativeScriptWork(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)


class NativeScriptWorkTests(unittest.TestCase):
    def test_actual_original_inventory_and_callback_counts_are_not_requested_results(self):
        source=WorkBoundary();source.timers=[dict(handle=7,active=True,singleShot=True,intervalMs=2000,remainingMs=950)]
        source.signal_callbacks=2;source.timer_callbacks=1;source.evaluating=True
        reader=source.reader();value=reader.read(MANAGER)
        self.assertEqual(source.value,value);self.assertEqual(source.timers,value['source']['work']['timers'])
        self.assertEqual(2,value['source']['work']['signalCallbacks']);self.assertTrue(value['source']['work']['evaluating'])
        self.assertEqual({'schemaVersion','commandId','action','managerInstance'},set(source.commands[0]))
        self.assertNotIn('performed',value);self.assertNotIn('quiescent',value);self.assertNotIn('expected',str(source.commands))
    def test_inactive_timer_entries_still_exist_and_active_callbacks_are_not_labeled_empty(self):
        source=WorkBoundary();source.timers=[dict(handle=4,active=False,singleShot=False,intervalMs=0,remainingMs=-1)]
        source.timer_callbacks=1;value=source.reader().read(MANAGER)
        self.assertEqual(1,len(value['source']['work']['timers']));self.assertEqual(1,value['source']['work']['timerCallbacks'])
    def test_reconstruction_replays_original_membership_then_requires_new_native_work(self):
        source=WorkBoundary();first=source.reader().read(MANAGER);reader=source.reader();reader.restore([first])
        second=reader.read(MANAGER,first['sequence']);self.assertGreater(second['source']['work']['sequence'],first['source']['work']['sequence'])
        self.assertNotEqual(second['requestId'],first['requestId']);self.assertEqual(2,len(source.commands))
        with self.assertRaises(NativeUIError):reader.restore([first])
    def test_missing_stale_foreign_or_expectation_bearing_results_never_become_zero_work(self):
        for fault in ('nonce','pid','birth','subject','code','stale-work','request-order','unavailable','incomplete','expected'):
            source=WorkBoundary();reader=source.reader();first=reader.read(MANAGER)
            def changed(value):
                data=value['source'];work=data['work']
                if fault=='nonce':value['requestId']=first['requestId']
                elif fault=='pid':value['processId']=32
                elif fault=='birth':value['instance']='f'*32
                elif fault=='subject':data['manager']['instance']='f'*32
                elif fault=='code':data['code']['sha256']='f'*64
                elif fault=='stale-work':work['capturedEpochMs']=18000
                elif fault=='request-order':work['requestedEpochMs']=21000
                elif fault=='unavailable':value.clear();value.update(requestId=source.commands[-1]['commandId'],available=False)
                elif fault=='incomplete':data['complete']=False
                else:work['expectedTimers']=0
            source.mutate=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])
            self.assertEqual(first,reader.last)
    def test_unknown_subject_cannot_be_echoed_as_a_measured_worker(self):
        source=WorkBoundary()
        with self.assertRaises(NativeUIError):source.reader().read('f'*32)
        self.assertEqual('f'*32,source.commands[0]['managerInstance']);self.assertEqual(MANAGER,source.value['source']['manager']['instance'])
    def test_reused_global_or_worker_cursor_and_old_request_fence_are_rejected(self):
        for fault in ('global','worker','fence'):
            source=WorkBoundary();reader=source.reader();first=reader.read(MANAGER)
            if fault=='global':source.sequence=0
            elif fault=='worker':source.work_sequence=0
            else:source.mutate=lambda value:value.update(requestedEpochMs=19999)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])
    def test_wrong_types_duplicate_timers_inconsistent_states_and_live_scope_loss_fail(self):
        for fault in ('version','worker-version','counter','interval','remaining','duplicate','active','done','running','missing-selected'):
            source=WorkBoundary();source.timers=[dict(handle=1,active=True,singleShot=True,intervalMs=1000,remainingMs=100)]
            def changed(value):
                data=value['source'];work=data['work']
                if fault=='version':value['schemaVersion']=True
                elif fault=='worker-version':work['scriptWorkVersion']=True
                elif fault=='counter':work['signalCallbacks']=False
                elif fault=='interval':work['timers'][0]['intervalMs']=True
                elif fault=='remaining':work['timers'][0]['remainingMs']=None
                elif fault=='duplicate':work['timers'].append(deepcopy(work['timers'][0]))
                elif fault=='active':work['timers'][0]['active']=False
                elif fault=='done':data['workers'][0]['done']=True
                elif fault=='running':data['workers'][0]['running']=False
                else:data['workers']=[]
            source.mutate=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(MANAGER)
    def test_complete_related_manager_membership_is_preserved_and_retired_ids_cannot_return(self):
        source=WorkBoundary();other=dict(membership=source.member|dict(instance='d'*32),running=False,stopping=False,finished=False,done=False)
        source.extra=[other];source.revision=2;reader=source.reader();one=reader.read(MANAGER)
        self.assertEqual(2,len(one['source']['workers']));source.extra=[];source.revision=3;two=reader.read(MANAGER,one['sequence'])
        source.extra=[other];source.revision=4
        with self.assertRaises(NativeUIError):reader.read(MANAGER,two['sequence'])
        restored=source.reader();restored.restore([one,two])
        with self.assertRaises(NativeUIError):restored.read(MANAGER,two['sequence'])
    def test_frozen_external_clock_cannot_hide_slow_native_transport(self):
        source=WorkBoundary();source.mutate=lambda _value:setattr(source,'clock',2.)
        with self.assertRaises(NativeUIError):source.reader().read(MANAGER)
    def test_final_guard_latency_is_inside_the_original_sample_age_budget(self):
        source=WorkBoundary();reader=source.reader();calls=[]
        def slow():
            calls.append(True)
            if len(calls)==4:source.clock+=2
            return True
        reader.guard=slow
        with self.assertRaises(NativeUIError):reader.read(MANAGER)
        self.assertEqual(4,len(calls));self.assertIsNone(reader.last)
    def test_ignored_query_lost_guard_and_oversized_data_have_no_empty_success(self):
        source=WorkBoundary();source.ignored=True
        with self.assertRaises(NativeUIError):source.reader().read(MANAGER)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5.1)
        source=WorkBoundary();source.okay=False
        with self.assertRaises(NativeUIError):source.reader().read(MANAGER)
        self.assertEqual([],source.commands)
        source=WorkBoundary();reader=source.reader();reader.original=lambda:'x'*262145
        with self.assertRaises(NativeUIError):reader.read(MANAGER)
    def test_closed_command_refuses_expected_counts_script_code_and_other_operations(self):
        value=dict(schemaVersion=1,commandId='a'*32,action='feature-script-work-observe',managerInstance=MANAGER)
        for edit in (dict(schemaVersion=True),dict(managerInstance=MANAGER+'\n'),dict(commandId='a'*32+'\n'),
            dict(expectedTimers=0),dict(code='Script.clearTimeout(1)'),dict(action='clear-script-work')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(value|edit)
    def test_ios_nonce_grammar_keeps_original_native_clock_without_enabling_an_ios_adapter(self):
        source=WorkBoundary();value=source.reader(ios=True).read(MANAGER)
        self.assertTrue(value['requestId'].startswith('ios-'));self.assertEqual(20000,value['source']['work']['capturedEpochMs'])


if __name__=='__main__':unittest.main()
