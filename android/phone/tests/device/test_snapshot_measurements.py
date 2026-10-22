"""Snapshot source joins at explicit synthetic native/VM boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.emote_admission import catalog,KEYS
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_roots import RootBoundary
from self_tests.test_native_script_observation import Boundary as Scripts
from test_snapshot_source import Boundary as Snapshot,RUN
from overte_phone_snapshot_measurements import validate,callers,PhoneSnapshotMeasurements,PATH


class Boundary:
    def __init__(self):
        self.roots=RootBoundary();self.scripts=Scripts();self.snapshot=Snapshot();self.snapshot.epoch=19990
        self.clock=0.;self.epoch=20000;self.okay=True
        expected=next(row for row in catalog()['files'] if row['runtimePath']==PATH)
        self.manager=dict(instance='c'*32,assigned=True,url=self.roots.root+'/'+PATH,loadGeneration=1,assignedEpochMs=14000)
        self.code=dict(submitted=True,submittedEpochMs=15000,**{key:expected[key] for key in KEYS})
        self.compilation=dict(scriptId=5,resourceName=self.manager['url'],compiledEpochMs=15001,**{key:expected[key] for key in KEYS})
        self.scripts.engine.update(url='file:///~//'+PATH,required=dict(instance='c'*32,sequence=0,modules=[]))
        def script(value):
            value['instance']='a'*32
            source=value['source'];source.update(sourceIdentityVersion=1,compiledSourceVersion=1,membershipSourceVersion=1,
                membership=dict(complete=True,revision=1,managers=[deepcopy(self.manager)]))
            source['engines'][0].update(code=deepcopy(self.code),compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[deepcopy(self.compilation)]))
        self.scripts.mutate=script
        self.snapshot.fault=lambda value:value.update(instance='a'*32)
        self.root_reader=self.roots.reader();self.script_reader=self.scripts.reader();self.snapshot_reader=self.snapshot.reader()
        for reader in (self.root_reader,self.script_reader,self.snapshot_reader):
            reader.clock_ms=lambda:self.epoch;reader.monotonic=lambda:self.clock;reader.sleep=self.sleep;reader.guard=lambda:self.okay
        self.reader=PhoneSnapshotMeasurements(self.root_reader,self.script_reader,self.snapshot_reader,
            lambda:self.okay,lambda:self.epoch,31,monotonic=lambda:self.clock)
    def sleep(self,value):self.clock+=value
    def event(self,kind,index):
        return dict(sequence=index,kind=kind,id='snap_19000_1',mode='animated',revision=1,capturedEpochMs=19000,elapsedMs=0,
            caller=dict(callerVersion=2,method='featureCaptureEvent',sequence=index,invokedEpochMs=19000,
                manager=deepcopy(self.manager),code=deepcopy(self.code),compilation=deepcopy(self.compilation),
                snapshotWork=dict(snapshotScriptWorkVersion=1,scriptId=5,capturedEpochMs=19000,timers=[],signalCallbacks=1,
                    timerCallbacks=0,signalInvocations=1,timerInvocations=0,timerRegistrations=2)))
    def group(self):
        before=self.root_reader.read(0)
        script=self.script_reader.read(0,require_code_identity=True,require_membership=True)
        snapshot=self.snapshot_reader.read(RUN)
        after=self.root_reader.read(before['sequence'])
        snapshot['source']['scriptHistory'].update(sequence=2,events=[self.event('pending',1),self.event('cancelled',2)])
        return dict(rootsBefore=before,script=script,snapshot=snapshot,rootsAfter=after)


class SnapshotMeasurementsTests(unittest.TestCase):
    def test_original_manager_code_compilation_and_historical_times_are_returned_unchanged(self):
        b=Boundary();group=b.group();selected=validate(group,run=RUN,pid=31,epoch=20000)
        self.assertEqual(dict(manager=b.manager,code=b.code,compilation=b.compilation),selected)
        original=deepcopy(group);history=callers(group['snapshot']['source']['scriptHistory'],selected,20000)
        self.assertEqual(19000,history['events'][0]['capturedEpochMs']);self.assertEqual(original,group)
        selected['code']['sha256']='f'*64;self.assertEqual(b.code,group['script']['source']['engines'][0]['code'])

    def test_fresh_request_does_not_qualify_a_foreign_changed_or_missing_vm_caller(self):
        for fault in ('manager','code','compiled','id','url','missing'):
            b=Boundary();group=b.group();origin=group['snapshot']['source']['scriptHistory']['events'][0]['caller']
            if fault=='manager':origin['manager']['instance']='d'*32
            elif fault=='code':origin['code']['sha256']='d'*64
            elif fault=='compiled':origin['compilation']['sha256']='d'*64
            elif fault=='id':origin['compilation']['scriptId']=origin['snapshotWork']['scriptId']=6
            elif fault=='url':origin['compilation']['resourceName']='file:///foreign/scripts/'+PATH
            else:origin.pop('compilation')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(group,run=RUN,pid=31,epoch=20000)

    def test_matching_names_and_consistent_changed_bytes_cannot_replace_fixed_reviewed_pins(self):
        b=Boundary();group=b.group();engine=group['script']['source']['engines'][0]
        engine['code']['sha256']=engine['compiled']['compilations'][0]['sha256']='d'*64
        for row in group['snapshot']['source']['scriptHistory']['events']:
            row['caller']['code']['sha256']=row['caller']['compilation']['sha256']='d'*64
        with self.assertRaises(NativeUIError):validate(group,run=RUN,pid=31,epoch=20000)

    def test_missing_ambiguous_unassigned_or_stopped_original_engine_cannot_qualify(self):
        for fault in ('missing','ambiguous','unassigned','stopped','pending-manager','missing-compile','foreign-root','legacy'):
            b=Boundary();group=b.group();source=group['script']['source'];engine=source['engines'][0]
            if fault=='missing':source['engines']=[]
            elif fault=='ambiguous':
                engine=deepcopy(engine);engine['required']['instance']='d'*32;source['engines'].append(engine)
                manager=deepcopy(b.manager);manager['instance']='d'*32;source['membership']['managers'].append(manager);source['membership']['revision']=2
            elif fault=='unassigned':source['membership']['managers'][0].update(assigned=False,url='',loadGeneration=0,assignedEpochMs=0)
            elif fault=='stopped':engine['stopping']=True
            elif fault=='pending-manager':
                manager=deepcopy(b.manager);manager['instance']='d'*32;source['membership']['managers'].append(manager);source['membership']['revision']=2
            elif fault=='missing-compile':engine['compiled']['compilations']=[]
            elif fault=='foreign-root':
                for key in ('rootsBefore','rootsAfter'):group[key]['source']['defaultScriptsUrl']='file:///another/scripts'
            else:source.pop('compiledSourceVersion');engine.pop('compiled')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(group,run=RUN,pid=31,epoch=20000)

    def test_foreign_process_instance_run_stale_or_out_of_order_acquisitions_are_rejected(self):
        for fault in ('pid','instance','run','stale','order','root-counter','root-reuse'):
            b=Boundary();group=b.group()
            if fault=='pid':group['snapshot']['processId']=32
            elif fault=='instance':group['snapshot']['instance']='d'*32
            elif fault=='run':group['snapshot']['runId']='d'*32
            elif fault=='stale':
                for key in ('requestedEpochMs','capturedEpochMs'):group['rootsBefore'][key]=18000
            elif fault=='order':group['snapshot']['requestedEpochMs']=19999
            elif fault=='root-counter':group['rootsAfter']['sequence']=group['rootsBefore']['sequence']
            else:group['rootsAfter']['commandId']=group['rootsBefore']['commandId']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(group,run=RUN,pid=31,epoch=20000)

    def test_reader_sends_only_original_read_requests_and_preserves_real_acquisition_order(self):
        b=Boundary();group,selected=b.reader.read(RUN)
        self.assertEqual(b.manager,selected['manager']);self.assertEqual(2,len(b.roots.commands))
        self.assertEqual(1,len(b.scripts.commands));self.assertEqual(1,len(b.snapshot.calls))
        self.assertEqual({'schemaVersion','commandId','action'},set(b.scripts.commands[0]))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.snapshot.calls[0]))
        validate(group,run=RUN,pid=31,epoch=20000)

    def test_frozen_epoch_does_not_hide_slow_group_or_ignored_reads_and_foreign_guard(self):
        for fault in ('slow','ignored','guard'):
            b=Boundary()
            if fault=='slow':
                original=b.snapshot.fault
                def slow(value):original(value);b.clock+=1.6
                b.snapshot.fault=slow
            elif fault=='ignored':b.snapshot.ignore=True
            else:b.okay=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader.read(RUN)
            self.assertLessEqual(len(b.snapshot.calls),1)


if __name__=='__main__':unittest.main()
