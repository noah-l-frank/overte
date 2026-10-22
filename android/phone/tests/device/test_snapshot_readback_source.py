"""Strict original readback/cleanup packets on synthetic source transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import PhoneSnapshotReadbacks,command

RUN='a'*32;REQUEST='b'*32;JOB='c'*32;COPY='d'*32
PATH='/data/user/0/io.github.noah_be.overte.phone/files/overte-snapshot-e2e-'+'e'*32+'/'+COPY+'.bin'


class Boundary:
    def __init__(self):
        self.epoch=10000;self.clock=0.;self.sequence=0;self.raw='';self.okay=True;self.ignore=False;self.fault=None;self.sent=[]
        self.component=dict(snapshotExportReadbacksVersion=1,instance='f'*32,sequence=0,elapsedMs=0,complete=True,
            copiesRetired=False,capturedEpochMs=self.epoch,workersTerminated=False,destinations=[],jobs=[],files=[],removedCopies=[])
    def complete(self):
        original=dict(id=COPY,request=REQUEST,path=PATH,phase='complete',bytes=4,sha256='1'*64,capturedEpochMs=self.epoch)
        self.component.update(destinations=[dict(request=REQUEST,uri='content://media/external/images/media/418',inserted=True,published=True)],
            jobs=[dict(id=JOB,request=REQUEST,phase='complete',startedEpochMs=self.epoch-1,completedEpochMs=self.epoch,original=deepcopy(original))],files=[original])
    def send(self,request):
        self.sent.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;self.epoch+=10;self.component.update(sequence=self.sequence,capturedEpochMs=self.epoch,elapsedMs=int(self.clock*1000))
        value=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance='2'*32,sequence=self.sequence,
            processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=dict(accepted=True,source=deepcopy(self.component)))
        if self.fault:self.fault(value)
        self.raw=json.dumps(value)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return PhoneSnapshotReadbacks(self.send,lambda:self.raw,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotReadbackSourceTests(unittest.TestCase):
    def test_readonly_native_transport_cannot_remove_copies_or_retire_workers(self):
        from appium_adapter import readonly_feature_command
        baseline=dict(schemaVersion=1,commandId='4'*32,action='phone-snapshot-readback',runId=RUN,
            operation='observe',exportRequest='',resourceId='')
        readonly_feature_command(baseline)
        readonly_feature_command(baseline|dict(operation='read',exportRequest=REQUEST,resourceId=JOB))
        for operation in ('cancel','remove-copy','retire-copies'):
            fields=dict(operation=operation,resourceId='' if operation=='retire-copies' else JOB)
            with self.subTest(operation=operation),self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(baseline|fields)

    def test_complete_job_is_distinct_from_ack_and_original_copy_retirement(self):
        b=Boundary();b.complete();reader=b.reader();first=reader.request(RUN,'read',REQUEST,JOB)
        self.assertEqual('complete',first['source']['source']['jobs'][0]['phase'])
        b.component.update(files=[],removedCopies=[COPY],copiesRetired=True,workersTerminated=True)
        retired=reader.request(RUN);self.assertEqual([COPY],retired['source']['source']['removedCopies'])
        self.assertEqual(first['source']['source']['jobs'],retired['source']['source']['jobs'])
    def test_queued_read_ack_does_not_supply_an_original_file(self):
        b=Boundary();b.complete();b.component['jobs'][0].update(phase='queued',startedEpochMs=0,completedEpochMs=0,original=None);b.component['files']=[]
        value=b.reader().request(RUN,'read',REQUEST,JOB)['source']['source']
        self.assertEqual([],value['files']);self.assertIsNone(value['jobs'][0]['original'])
    def test_uninitialized_recorder_is_unavailable_and_cannot_claim_an_empty_destination_inventory(self):
        b=Boundary()
        def unavailable(v):v['source']=dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True))
        b.fault=unavailable;source=b.reader().request(RUN)['source']
        self.assertFalse(source['accepted']);self.assertNotIn('destinations',source['source'])
    def test_missing_foreign_incomplete_and_stale_originals_fail(self):
        for fault in ('run','pid','outer-stale','source-stale','incomplete','path','hash','request','missing-file','unknown-status','uri','unpublished','no-original','false-retire'):
            with self.subTest(fault=fault):
                b=Boundary();b.complete()
                def mutate(v):
                    c=v['source']['source']
                    if fault=='run':v['runId']='3'*32
                    elif fault=='pid':v['processId']=99
                    elif fault=='outer-stale':v['requestedEpochMs']=v['capturedEpochMs']=1
                    elif fault=='source-stale':c['capturedEpochMs']=1
                    elif fault=='incomplete':c['complete']=False
                    elif fault=='path':c['files'][0]['path']='/tmp/foreign.png'
                    elif fault=='hash':c['files'][0]['sha256']='expected'
                    elif fault=='request':c['jobs'][0]['request']='3'*32
                    elif fault=='missing-file':c['files']=[]
                    elif fault=='unknown-status':c['jobs'][0]['phase']='success'
                    elif fault=='uri':c['destinations'][0]['uri']='file:///private/capture.png'
                    elif fault=='unpublished':c['destinations'][0]['published']=False
                    elif fault=='no-original':c['jobs'][0]['original']=None
                    else:c['copiesRetired']=True
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().request(RUN)
    def test_terminal_jobs_and_uris_cannot_be_rewritten_on_reconstruction(self):
        for fault in ('instance','job','lost-job','uri','removed-prefix','initialized'):
            with self.subTest(fault=fault):
                b=Boundary();b.complete();reader=b.reader();reader.request(RUN)
                def mutate(v):
                    c=v['source']['source']
                    if fault=='instance':c['instance']='3'*32
                    elif fault=='job':c['jobs'][0]['startedEpochMs']-=1
                    elif fault=='lost-job':c['jobs']=[]
                    elif fault=='uri':c['destinations'][0]['uri']='content://media/external/images/media/999'
                    elif fault=='removed-prefix':c['files']=[];c['removedCopies']=['3'*32]
                    else:v['source']=dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True))
                b.fault=mutate
                with self.assertRaises(NativeUIError):reader.request(RUN)
    def test_ignored_request_cannot_reuse_a_previous_job_observation(self):
        b=Boundary();reader=b.reader();reader.request(RUN);b.ignore=True
        with self.assertRaises(NativeUIError):reader.request(RUN)
    def test_returned_sources_cannot_mutate_retained_continuity(self):
        b=Boundary();b.complete();reader=b.reader();value=reader.request(RUN);value['source']['source']['jobs'].clear()
        self.assertEqual(1,len(reader.request(RUN)['source']['source']['jobs']))
    def test_command_rejects_expected_results_external_uris_and_foreign_file_paths(self):
        baseline=dict(schemaVersion=1,commandId='4'*32,action='phone-snapshot-readback',runId=RUN,operation='read',exportRequest=REQUEST,resourceId=JOB)
        for extra in ({'uri':'content://expected/file'},{'path':'/tmp/expected.png'},{'sha256':'1'*64},{'saved':1}):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):command(baseline|extra)
        for fields in ({'operation':'delete-destination'},{'operation':'read','exportRequest':''},{'operation':'observe','resourceId':JOB}):
            with self.subTest(fields=fields),self.assertRaises(NativeUIError):command(baseline|fields)


if __name__=='__main__':unittest.main()
