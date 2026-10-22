"""Original Snapshot reader counterexamples; synthetic IO, no Android verdict."""
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
from overte_phone_snapshot_source import PhoneSnapshotSource,command,source,continuity

RUN='a'*32;STORAGE='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots'


class Boundary:
    def __init__(self):
        self.epoch=10000;self.clock=0.;self.sequence=0;self.okay=True;self.ignore=False;self.fault=None;self.raw=''
        self.events=[];self.captures=[];self.uploads=[];self.calls=[]
    def event(self,kind,id,phase='',path='',error=''):
        self.events.append(dict(sequence=len(self.events)+1,kind=kind,id=id,phase=phase,path=path,error=error,
            capturedEpochMs=self.epoch,elapsedMs=int(self.clock*1000)))
    def send(self,request):
        self.calls.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;self.epoch+=10
        value=dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(phoneSnapshotObservationVersion=1,nativeReview=True,storageRoot=STORAGE,
                captures=deepcopy(self.captures),uploads=self.uploads[:],history=dict(snapshotHistoryVersion=1,
                instance='c'*32,complete=True,sequence=len(self.events),events=deepcopy(self.events))))
        if self.fault:self.fault(value)
        self.raw=json.dumps(value)
    def original(self):return self.raw
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return PhoneSnapshotSource(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotSourceTests(unittest.TestCase):
    def test_fresh_reads_reopen_actual_source_and_keep_history_separate_from_commands(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN)
        b.event('capture-begin','snap_10010_1');b.captures=[dict(id='snap_10010_1',state='active',announced=False)]
        second=reader.read(RUN)
        self.assertGreater(second['sequence'],first['sequence']);self.assertEqual(1,len(second['source']['captures']))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.calls[-1]))
        self.assertNotEqual(b.calls[0]['commandId'],b.calls[1]['commandId'])
    def test_actual_cancel_and_upload_histories_are_retained_without_assuming_a_file_exists(self):
        b=Boundary();b.event('capture-begin','snap_1');b.event('capture-status','snap_1','cancelled')
        name=STORAGE+'/owned.png';b.event('upload-begin',name,path=name);b.event('upload-status',name,'error',name,'upload-failed')
        value=b.reader().read(RUN)
        self.assertEqual(4,value['source']['history']['sequence']);self.assertEqual([],value['source']['captures'])
        self.assertNotIn('files',value['source'])
    def test_ignored_request_cannot_return_an_older_original(self):
        b=Boundary();reader=b.reader();reader.read(RUN);b.ignore=True
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_missing_result_remains_red(self):
        b=Boundary();b.ignore=True
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_stale_foreign_or_incomplete_packets_fail(self):
        for fault in ('run','pid','stale','complete','extra','future-event','root'):
            with self.subTest(fault=fault):
                b=Boundary();b.event('capture-begin','snap_1')
                def mutate(v):
                    if fault=='run':v['runId']='f'*32
                    elif fault=='pid':v['processId']=99
                    elif fault=='stale':v['requestedEpochMs']=v['capturedEpochMs']=1
                    elif fault=='complete':v['source']['history']['complete']=False
                    elif fault=='extra':v['source']['saved']=1
                    elif fault=='future-event':v['source']['history']['events'][0]['capturedEpochMs']=b.epoch+1
                    else:v['source']['storageRoot']='/tmp/Snapshots'
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_reconstructed_or_changed_history_cannot_borrow_a_prior_sequence(self):
        for fault in ('instance','history-instance','sequence','event','truncated'):
            with self.subTest(fault=fault):
                b=Boundary();b.event('capture-begin','snap_1');reader=b.reader();reader.read(RUN)
                def mutate(v):
                    if fault=='instance':v['instance']='f'*32
                    elif fault=='history-instance':v['source']['history']['instance']='f'*32
                    elif fault=='sequence':v['sequence']=1
                    elif fault=='event':v['source']['history']['events'][0]['id']='snap_foreign'
                    else:v['source']['history'].update(sequence=0,events=[])
                b.fault=mutate
                with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_original_capture_inventory_cannot_invent_an_unrecorded_responsibility(self):
        b=Boundary();b.captures=[dict(id='snap_unknown',state='active',announced=False)]
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_foreign_paths_and_duplicate_current_rows_fail(self):
        for uploads in ([STORAGE+'/..'],[STORAGE+'/sub/file.png'],[STORAGE+'/x.png']*2,['/tmp/x.png']):
            with self.subTest(uploads=uploads):
                b=Boundary();b.uploads=uploads
                with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_candidate_or_clock_changes_during_original_io_fail(self):
        for fault in ('guard','slow','backwards'):
            with self.subTest(fault=fault):
                b=Boundary();reader=b.reader();original=reader.original
                def read():
                    if fault=='guard':b.okay=False
                    elif fault=='slow':b.clock+=5.1
                    else:b.clock-=.1
                    return original()
                reader.original=read
                with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_returned_graph_cannot_change_retained_continuity(self):
        b=Boundary();reader=b.reader();row=reader.read(RUN);row['source']['storageRoot']='/tmp/foreign'
        self.assertEqual(STORAGE,reader.read(RUN)['source']['storageRoot'])
    def test_command_cannot_set_product_state_or_select_an_expected_file(self):
        for extra in ({'saved':1},{'prefix':'expected'},{'operation':'capture'}):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):
                command(dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-observe',runId=RUN)|extra)


if __name__=='__main__':unittest.main()
