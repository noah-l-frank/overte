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
from adapters.native_script_work import NativeScriptWork,command,validate,scope
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


def activity(script_id,*,signals=0,timers=0,signal_calls=0,timer_calls=0,registrations=0):
    return dict(scriptId=script_id,signalCallbacks=signals,timerCallbacks=timers,signalInvocations=signal_calls,
        timerInvocations=timer_calls,timerRegistrations=registrations)


class ScopedWorkBoundary(WorkBoundary):
    def __init__(self):
        super().__init__();self.activity=[activity(23,signal_calls=1)];self.edit=None
        from self_tests.test_emote_source_profile import manager_pins,pins
        manager=manager_pins()[0];emote=pins()[0];self.member['url']='file:///actual/scripts/defaultScripts.js'
        self.code.update({key:manager[key] for key in ('encoding','codeUnits','sha256')})
        def compiled(identifier,path,pin,epoch):
            return dict(scriptId=identifier,resourceName=path,compiledEpochMs=epoch,**{key:pin[key] for key in ('encoding','codeUnits','sha256')})
        foreign=b'function foreignPoll() {}';foreign_units=foreign.decode().encode('utf-16-le')
        foreign_pin=dict(encoding='utf-16le-code-units',codeUnits=len(foreign_units)//2,sha256=hashlib.sha256(foreign_units).hexdigest())
        self.compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[
            compiled(11,self.member['url'],manager,15001),
            compiled(23,'file:///actual/scripts/system/+android_phoneInterface/phoneEmote.js',emote,15002),
            compiled(31,'file:///actual/scripts/foreign-poll.js',foreign_pin,15003)])
        def observed(value):
            source=value['source'];source['compiled']=deepcopy(self.compiled);work=source['work']
            work.update(scriptWorkVersion=2,activity=deepcopy(self.activity),timerEntries=len(work['timers']),activityEntries=len(self.activity))
            if self.edit:self.edit(value)
        self.mutate=observed

    def selected(self):return deepcopy(self.compiled['compilations'][1])


class NativeScriptWorkTests(unittest.TestCase):
    def test_final_guard_native_clock_jump_cannot_publish_stale_work(self):
        boundary=WorkBoundary();reader=boundary.reader();count=0
        def guard():
            nonlocal count
            count+=1
            if count==4:boundary.epoch+=2000
            return True
        reader.guard=guard
        with self.assertRaises(NativeUIError):reader.read(MANAGER)
        self.assertEqual(1,len(boundary.commands));self.assertIsNone(reader.last)


    def test_v2_preserves_foreign_default_timers_and_measures_only_original_selected_function_work(self):
        source=ScopedWorkBoundary();source.timers=[dict(handle=7,active=True,singleShot=False,intervalMs=1000,remainingMs=950,functionScriptId=31)]
        source.activity.append(activity(31,registrations=1));actual=source.reader().read(MANAGER);measured=scope(actual,source.selected())
        self.assertEqual([],measured['timers']);self.assertEqual([],measured['unknownTimers'])
        self.assertEqual(1,measured['signalInvocations']);self.assertEqual(0,measured['signalCallbacks'])
        self.assertEqual(1,len(actual['source']['work']['timers']));self.assertEqual(1,len(source.timers))
        self.assertEqual({'schemaVersion','commandId','action','managerInstance'},set(source.commands[0]))

    def test_v2_inactive_owned_timer_and_running_owned_callback_remain_present(self):
        source=ScopedWorkBoundary();source.timers=[dict(handle=7,active=False,singleShot=True,intervalMs=1000,remainingMs=-1,functionScriptId=23)]
        source.activity=[activity(23,timers=1,signal_calls=1,timer_calls=1,registrations=1)];source.timer_callbacks=1
        actual=scope(source.reader().read(MANAGER),source.selected())
        self.assertEqual(1,len(actual['timers']));self.assertFalse(actual['timers'][0]['active']);self.assertEqual(1,actual['timerCallbacks'])

    def test_v2_native_or_unobserved_function_origins_are_unknown_not_foreign_empty_success(self):
        for identifier in (0,17):
            source=ScopedWorkBoundary();source.timers=[dict(handle=7,active=True,singleShot=True,intervalMs=1000,remainingMs=950,functionScriptId=identifier)]
            source.activity.insert(0,activity(identifier,signals=1,signal_calls=1,registrations=1));source.signal_callbacks=1
            with self.subTest(identifier=identifier):
                actual=scope(source.reader().read(MANAGER),source.selected())
                self.assertEqual(1,len(actual['unknownTimers']));self.assertEqual(1,actual['unknownSignalCallbacks'])
                self.assertEqual(identifier,actual['unknownActivity'][0]['scriptId'])

    def test_v2_completed_callback_and_timer_creation_activity_cannot_disappear_or_rewind(self):
        for fault in ('missing','signal','timer','registration'):
            source=ScopedWorkBoundary();source.activity=[activity(23,signal_calls=2,timer_calls=2,registrations=2)]
            reader=source.reader();first=reader.read(MANAGER)
            if fault=='missing':source.activity=[]
            else:source.activity[0][{'signal':'signalInvocations','timer':'timerInvocations','registration':'timerRegistrations'}[fault]]=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])
            self.assertEqual(first,reader.last)

    def test_v2_loss_of_timer_or_activity_rows_cannot_hide_behind_complete_flag(self):
        for fault in ('missing-timer','missing-activity','active-total','empty-activity','unknown-version','invented-field','negative-id','missing-registration','unregistered-callback'):
            source=ScopedWorkBoundary();source.timers=[dict(handle=7,active=True,singleShot=True,intervalMs=1000,remainingMs=950,functionScriptId=23)]
            source.activity[0]['timerRegistrations']=1
            def invalid(value):
                work=value['source']['work']
                if fault=='missing-timer':work['timers']=[]
                elif fault=='missing-activity':work['activity']=[]
                elif fault=='active-total':work['signalCallbacks']=1
                elif fault=='empty-activity':work['activity'][0]['signalInvocations']=0;work['activity'][0]['timerRegistrations']=0
                elif fault=='unknown-version':work['scriptWorkVersion']=3
                elif fault=='invented-field':work['expectedSelectedTimers']=0
                elif fault=='negative-id':work['timers'][0]['functionScriptId']=-1
                elif fault=='unregistered-callback':work['activity'][0].update(timerInvocations=1,timerRegistrations=0)
                else:work['activity'][0]['timerRegistrations']=0
            source.edit=invalid
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(MANAGER)

    def test_v2_actual_selected_compilation_must_match_and_cannot_be_supplied_by_legacy_work(self):
        source=ScopedWorkBoundary();value=source.reader().read(MANAGER)
        for edit in (dict(scriptId=24),dict(sha256='f'*64),dict(compiledEpochMs=15000)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):scope(value,source.selected()|edit)
        legacy=WorkBoundary().reader().read(MANAGER)
        with self.assertRaises(NativeUIError):scope(legacy,source.selected())

    def test_v2_cannot_downgrade_or_lose_compilation_after_readonly_replay(self):
        source=ScopedWorkBoundary();first=source.reader().read(MANAGER);reader=source.reader();reader.restore([first])
        source.compiled['compilations'][1]['sha256']='f'*64
        with self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])
        source=ScopedWorkBoundary();first=source.reader().read(MANAGER);reader=source.reader();reader.restore([first]);source.mutate=None
        with self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])

    def test_v2_guarded_native_hooks_read_real_function_and_bound_target_ids_without_function_stringification(self):
        root=Path(__file__).resolve().parents[3]
        engine=(root/'libraries/script-engine/src/v8/ScriptEngineV8.cpp').read_text()
        native=engine[engine.index('int ScriptEngineV8::featureFunctionScriptId('):engine.index('int ScriptEngineV8::featureCurrentScriptId()')]
        self.assertIn('function->GetBoundFunction()',native);self.assertIn('function->ScriptId()',native)
        self.assertIn('original->getV8Engine()!=this',native);self.assertNotIn('toString',native.replace('Function.toString',''))
        manager=(root/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        self.assertIn('data.featureFunctionScriptId',manager);self.assertIn('featureTimerRegistered(timerData.featureFunctionScriptId)',manager)
        self.assertIn('{"scriptWorkVersion",2}',manager);self.assertIn('{"activityEntries",_featureWorkActivity.size()}',manager)

    def test_valid_oversized_json_cannot_bypass_the_original_work_transport_bound(self):
        source=ScopedWorkBoundary();reader=source.reader()
        reader.original=lambda:json.dumps(source.value)+' '*262144
        with self.assertRaises(NativeUIError):reader.read(MANAGER)
        self.assertIsNone(reader.last)

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
