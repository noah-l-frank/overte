"""Original script-history validation at explicit native/VM observation seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from test_snapshot_source import Boundary,RUN
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_script_history import validate,continuity


def caller(sequence=1):
    return dict(callerVersion=2,method='featureCaptureEvent',sequence=sequence,invokedEpochMs=100,
        manager=dict(instance='a'*32,assigned=True,url='file:///packaged/scripts/defaultScripts.js',loadGeneration=1,assignedEpochMs=1),
        code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=20,sha256='b'*64,submittedEpochMs=2),
        compilation=dict(scriptId=2,resourceName='file:///packaged/scripts/system/snapshot.js',encoding='utf-16le-code-units',
            codeUnits=40,sha256='c'*64,compiledEpochMs=3),
        snapshotWork=dict(snapshotScriptWorkVersion=1,scriptId=2,capturedEpochMs=100,timers=[],signalCallbacks=1,timerCallbacks=0,
            signalInvocations=1,timerInvocations=0,timerRegistrations=2))


def history(phases=('pending','cancelled','pending','complete')):
    events=[]
    for index,phase in enumerate(phases,1):
        events.append(dict(sequence=index,kind=phase,id='snap_100_'+str(1 if index<=2 else 2),mode='animated',revision=1 if index<=2 else 2,
            capturedEpochMs=100,elapsedMs=0,caller=caller(index)))
    return dict(snapshotScriptHistoryVersion=1,instance='f'*32,complete=True,sequence=len(events),events=events)


class SnapshotScriptHistoryTests(unittest.TestCase):
    def test_real_pending_contexts_are_distinct_from_idle_cancel_or_native_allocation(self):
        value=history();validate(value,100)
        self.assertEqual(['pending','cancelled','pending','complete'],[row['kind'] for row in value['events']])
        b=Boundary();b.fault=lambda v:v['source'].update(scriptHistory=value)
        source=b.reader().read(RUN)['source'];self.assertEqual([],source['captures']);self.assertEqual([],source['history']['events'])
        self.assertEqual(value,source['scriptHistory'])

    def test_missing_original_context_late_callback_or_duplicate_completion_is_rejected(self):
        for phases in (('cancelled',),('complete',),('pending','cancelled','complete'),('pending','complete','complete'),('pending','pending')):
            with self.subTest(phases=phases),self.assertRaises(RuntimeError):validate(history(phases),100)

    def test_original_caller_code_compilation_or_manager_cannot_be_substituted(self):
        for fault in ('missing','method','version','code','compilation','manager','clock','counter','foreign-id','mode'):
            with self.subTest(fault=fault):
                value=history();row=value['events'][1];origin=row['caller']
                if fault=='missing':origin.clear()
                elif fault=='method':origin['method']='overrideAnimation'
                elif fault=='version':origin['callerVersion']=1
                elif fault=='code':origin['code']['sha256']='d'*64
                elif fault=='compilation':origin['compilation']['scriptId']=3
                elif fault=='manager':origin['manager']['instance']='d'*32
                elif fault=='clock':origin['invokedEpochMs']=101
                elif fault=='counter':origin['sequence']=1
                elif fault=='foreign-id':row['id']='snap_100_999'
                else:row['mode']='still'
                with self.assertRaises(RuntimeError):validate(value,100)

    def test_old_or_incomplete_native_history_cannot_become_empty_success(self):
        for fault in ('missing','version','incomplete','future'):
            with self.subTest(fault=fault):
                b=Boundary();value=history()
                def mutate(v):
                    v['source']['scriptHistory']=deepcopy(value)
                    if fault=='missing':v['source'].pop('scriptHistory')
                    elif fault=='version':v['source']['phoneSnapshotObservationVersion']=4
                    elif fault=='incomplete':v['source']['scriptHistory']['complete']=False
                    else:v['source']['scriptHistory']['events'][-1]['capturedEpochMs']=v['capturedEpochMs']+1
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_original_prefix_rewrite_or_recorder_replacement_is_rejected(self):
        before=history();after=deepcopy(before);continuity(before,after)
        after['events'][0]['caller']['compilation']['sha256']='d'*64
        with self.assertRaises(RuntimeError):continuity(before,after)
        after=deepcopy(before);after['instance']='0'*32
        with self.assertRaises(RuntimeError):continuity(before,after)

    def test_processing_is_an_original_animated_intermediate_and_not_an_extra_pending(self):
        value=history(('pending','processing'));value['events'].append(dict(deepcopy(value['events'][1]),sequence=3,kind='complete',caller=caller(3)))
        value['sequence']=3;validate(value,100)
        value['events'][1]['mode']='still'
        with self.assertRaises(RuntimeError):validate(value,100)

    def test_foreign_or_missing_work_and_impossible_timer_facts_are_rejected(self):
        for fault in ('missing','source','future','count','timer','duplicate','unknown'):
            with self.subTest(fault=fault):
                value=history();origin=value['events'][0]['caller'];work=origin['snapshotWork']
                if fault=='missing':origin.pop('snapshotWork')
                elif fault=='source':work['scriptId']=3
                elif fault=='future':work['capturedEpochMs']=101
                elif fault=='count':work['signalCallbacks']=2
                elif fault=='unknown':work['expectedPending']=True
                else:
                    timer=dict(handle=1,active=True,singleShot=True,intervalMs=350,remainingMs=349)
                    work['timers']=[timer]
                    if fault=='timer':timer['remainingMs']=-1
                    else:work['timers'].append(deepcopy(timer))
                with self.assertRaises(RuntimeError):validate(value,100)


if __name__=='__main__':unittest.main()
