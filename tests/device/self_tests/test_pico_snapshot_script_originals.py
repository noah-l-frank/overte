"""Original script-history validation at explicit native/VM observation seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from pathlib import Path
import json,tempfile,sys
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import snapshot_script_originals as source
from adapters.script_journey.lock import ScriptSourceLock
RUN="e"*32
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_script_history import validate,continuity,join_compilation


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
    def test_reviewed_pin_tracks_the_exact_selected_production_source_not_a_url_or_requested_value(self):
        import hashlib
        root=Path(__file__).resolve().parents[3]
        raw=(root/'scripts/system/snapshot.js').read_text().encode('utf-16le')
        pin=json.loads((root/'tests/device/adapters/pico4/snapshot-script-pin.v1.json').read_text())
        self.assertEqual(dict(encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()),pin)
    def test_real_pending_contexts_are_distinct_from_idle_cancel_or_native_allocation(self):
        value=history();validate(value,100)
        self.assertEqual(['pending','cancelled','pending','complete'],[row['kind'] for row in value['events']])

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


class Boundary:
    def __init__(self):
        self.time=0.;self.epoch=20000;self.sequence=0;self.commands=[];self.value=None;self.edit=None
        self.history=history();self.okay=True
    def clock(self):return self.epoch+round(self.time*1000)
    def send(self,command):
        self.commands.append(deepcopy(command));self.sequence+=1
        self.value=dict(snapshotScriptOriginalsVersion=source.VERSION,activeUploads=0,commandId=command['commandId'],runId=command['runId'],pid=31,
            sequence=self.sequence,capturedEpochMs=self.clock(),history=deepcopy(self.history))
        if self.edit:self.edit(self.value)
    def read(self):return json.dumps(self.value)
    def sleep(self,amount):self.time+=amount
    def reader(self,lock):return source.PicoSnapshotScriptOriginals(self.send,self.read,self.clock,lambda:self.okay,31,lock,
        monotonic=lambda:self.time,sleep=self.sleep)


class SnapshotScriptSourceTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.lock=ScriptSourceLock(Path(directory.name)/'script-sources.lock')
    def test_immutable_raw_history_and_cold_prefix_rewrite_are_distinct_from_query_ack(self):
        native=Boundary();reader=native.reader(self.lock);first=reader.capture(RUN)
        self.assertEqual(set(native.commands[0]),{'schemaVersion','action','commandId','runId'})
        self.assertEqual(reader.original()['raw'],native.read())
        reader=native.reader(self.lock);reader.restore(first)
        native.edit=lambda value:value['history']['events'][0].update(revision=7)
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(first,reader.previous)
    def test_unavailable_incomplete_foreign_process_replaced_recorder_and_expected_fields_fail(self):
        faults=(lambda v:v.update(available=False),lambda v:v.update(pid=True),lambda v:v.update(pid=32),
            lambda v:v.update(runId='f'*32),lambda v:v['history'].update(complete=False),
            lambda v:v.update(expectedPending=True),lambda v:v.update(capturedEpochMs=19999))
        for fault in faults:
            native=Boundary();native.edit=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):native.reader(self.lock).capture(RUN)
            self.assertEqual(1,len(native.commands))
    def test_frozen_native_clock_late_copy_and_final_guard_cannot_commit_stale_originals(self):
        for where in ('accept','deepcopy','host','native'):
            native=Boundary();reader=native.reader(self.lock);reader.clock_ms=lambda:native.epoch
            if where in ('accept','deepcopy'):
                original=getattr(source,where)
                def late(*args):
                    result=original(*args);native.time+=2;return result
                with mock.patch.object(source,where,side_effect=late):
                    with self.assertRaises(NativeUIError):reader.capture(RUN)
            else:
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==2:
                        if where=='host':native.time+=2
                        else:native.epoch+=2000
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertIsNone(reader.previous);self.assertIsNone(reader.last_raw)
    def test_v1_archive_has_no_upload_idle_fact_and_cannot_switch_live_source_version(self):
        native=Boundary()
        def legacy(value):value.update(snapshotScriptOriginalsVersion=1);value.pop('activeUploads')
        native.edit=legacy;reader=native.reader(self.lock);first=reader.capture(RUN)
        self.assertNotIn('activeUploads',first)
        native.edit=None
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(first,reader.previous)
        native=Boundary();native.edit=lambda value:value.update(activeUploads=True)
        with self.assertRaises(NativeUIError):native.reader(self.lock).capture(RUN)
    def test_raw_bound_dead_owner_and_lost_query_never_deliver_a_capture_or_resend(self):
        native=Boundary();reader=native.reader(self.lock);reader.read=lambda:' '*65537
        with mock.patch.object(source,'decode',wraps=source.decode) as decoder:
            with self.assertRaises(NativeUIError):reader.capture(RUN)
            decoder.assert_not_called()
        native=Boundary();reader=native.reader(self.lock);reader.read=lambda:None
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(1,len(native.commands))
        native=Boundary();native.okay=False
        with self.assertRaises(NativeUIError):native.reader(self.lock).capture(RUN)
        self.assertEqual([],native.commands)
    def test_independent_compilation_join_refuses_an_actual_foreign_source_with_the_same_url(self):
        value=history();origin=value['events'][0]['caller'];compiled=origin['compilation']
        engine=dict(url=origin['manager']['url'],running=True,stopping=False,finished=False,
            required=dict(instance=origin['manager']['instance'],sequence=0,modules=[]),code=origin['code'],
            compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[compiled]))
        execution=dict(schemaVersion=1,requestId='d'*32,instance='a'*32,sequence=1,requestedEpochMs=100,capturedEpochMs=100,
            processId=31,source=dict(complete=True,engines=[engine],sourceIdentityVersion=1,compiledSourceVersion=1,
            membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[origin['manager']])))
        pin={key:compiled[key] for key in ('encoding','codeUnits','sha256')}
        self.assertEqual(compiled,join_compilation(value,execution,compiled['resourceName'],pin))
        for field in ('sha256','resourceName','manager','duplicate','absent'):
            forged=deepcopy(execution)
            if field=='manager':forged['source']['membership']['managers'][0]['url']='file:///foreign/scripts/defaultScripts.js'
            elif field=='duplicate':forged['source']['engines'].append(deepcopy(engine))
            elif field=='absent':forged['source']['engines'][0]['compiled']['compilations']=[]
            else:forged['source']['engines'][0]['compiled']['compilations'][0][field]='f'*64 if field=='sha256' else 'file:///foreign/scripts/system/snapshot.js'
            with self.subTest(field=field),self.assertRaises(NativeUIError):join_compilation(value,forged,compiled['resourceName'],pin)


if __name__=='__main__':unittest.main()
