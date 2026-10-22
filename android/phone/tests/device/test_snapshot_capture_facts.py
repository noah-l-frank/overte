"""Independent synthetic original VM/native histories; no capture verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from test_snapshot_measurements import Boundary,RUN
from overte_phone_snapshot_capture_facts import capture_facts


def originals():
    b=Boundary();before=b.group();before['snapshot']['source']['scriptHistory'].update(sequence=0,events=[])
    after=deepcopy(before)
    after['rootsBefore']['sequence']=3;after['rootsBefore']['commandId']='d'*32
    after['rootsAfter']['sequence']=4;after['rootsAfter']['commandId']='e'*32
    after['script'].update(requestId='f'*32,sequence=2);after['snapshot'].update(requestId='1'*32,sequence=2)
    script=after['snapshot']['source']['scriptHistory']
    pending=b.event('pending',1);complete=b.event('complete',2);pending['mode']=complete['mode']='still'
    script.update(sequence=2,events=[pending,complete])
    native=after['snapshot']['source']['history']
    native.update(sequence=2,events=[dict(sequence=1,kind='capture-begin',id=pending['id'],phase='',path='',error='',capturedEpochMs=19000,elapsedMs=0),
        dict(sequence=2,kind='capture-status',id=pending['id'],phase='complete',path=after['snapshot']['source']['storageRoot']+'/e2e-'+RUN+'-snap_19000_1.png',error='',capturedEpochMs=19000,elapsedMs=0)])
    return b,before,after


class SnapshotCaptureFactsTests(unittest.TestCase):
    def test_actual_vm_and_native_complete_paths_remain_raw_originals_without_file_verdict(self):
        b,before,after=originals();result=capture_facts(before,after,run=RUN,pid=31,epoch=20000)
        self.assertEqual(['pending','complete'],result['history']);self.assertFalse(result['pending'])
        self.assertEqual(19000,result['contexts'][0]['pending']['capturedEpochMs']);self.assertNotIn('files',result)
        result['contexts'][0]['native'][1]['path']='foreign';self.assertNotEqual('foreign',after['snapshot']['source']['history']['events'][1]['path'])
    def test_vm_success_without_native_allocation_original_path_or_completion_is_rejected(self):
        for fault in ('empty','missing-begin','missing-complete','empty-path','native-error','late-native'):
            b,before,after=originals();native=after['snapshot']['source']['history']
            if fault=='empty':native.update(sequence=0,events=[])
            elif fault=='missing-begin':native['events']=native['events'][1:];native['events'][0]['sequence']=native['sequence']=1
            elif fault=='missing-complete':native['events']=native['events'][:1];native['sequence']=1
            elif fault=='empty-path':native['events'][1]['path']=''
            elif fault=='native-error':native['events'][1]['phase']='error'
            else:native['events'][1]['capturedEpochMs']=19500
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)
    def test_unrelated_native_capture_or_foreign_vm_bytes_cannot_join_a_matching_file_name(self):
        for fault in ('native-id','script-id','code'):
            b,before,after=originals()
            if fault=='native-id':
                for row in after['snapshot']['source']['history']['events']:row['id']='snap_19000_999'
            elif fault=='script-id':
                for row in after['snapshot']['source']['scriptHistory']['events']:row['id']='snap_19000_999'
            else:
                for row in after['snapshot']['source']['scriptHistory']['events']:row['caller']['code']['sha256']='d'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)
    def test_original_pre_render_cancel_timeline_does_not_claim_input_or_file_success(self):
        b,before,after=originals();script=after['snapshot']['source']['scriptHistory']
        script['events'][1]['kind']='cancelled';after['snapshot']['source']['history'].update(sequence=0,events=[])
        result=capture_facts(before,after,run=RUN,pid=31,epoch=20000)
        self.assertEqual(['pending','cancelled'],result['history']);self.assertEqual([],result['contexts'][0]['native'])
        self.assertNotIn('cancelSucceeded',result)
    def test_queued_native_work_cannot_disappear_behind_vm_cancel_or_completion(self):
        b,before,after=originals();after['snapshot']['source']['captures']=[dict(id='snap_19000_1',state='completed',announced=True)]
        with self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)
        after['snapshot']['source']['captures']=[];after['snapshot']['source']['scriptHistory']['events'][1]['kind']='cancelled'
        with self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)
    def test_empty_fresh_input_receipt_is_not_a_capture_event(self):
        b,before,after=originals();after['snapshot']['source']['scriptHistory'].update(sequence=0,events=[])
        after['snapshot']['source']['history'].update(sequence=0,events=[])
        result=capture_facts(before,after,run=RUN,pid=31,epoch=20000)
        self.assertEqual([],result['history']);self.assertEqual([],result['contexts']);self.assertFalse(result['pending'])
    def test_same_reviewed_bytes_cannot_adopt_another_root_after_an_empty_baseline(self):
        b,before,after=originals();old=b.roots.root;new='file:///another/configured/scripts'
        for key in ('rootsBefore','rootsAfter'):after[key]['source']['defaultScriptsUrl']=new
        manager=after['script']['source']['membership']['managers'][0];manager['url']=manager['url'].replace(old,new)
        compilation=after['script']['source']['engines'][0]['compiled']['compilations'][0]
        compilation['resourceName']=compilation['resourceName'].replace(old,new)
        for event in after['snapshot']['source']['scriptHistory']['events']:
            event['caller']['manager']['url']=event['caller']['manager']['url'].replace(old,new)
            event['caller']['compilation']['resourceName']=event['caller']['compilation']['resourceName'].replace(old,new)
        with self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)

    def test_original_baseline_or_retained_prefix_cannot_be_replaced(self):
        b,before,after=originals();before['snapshot']['source']['history'].update(instance='2'*32)
        with self.assertRaises(NativeUIError):capture_facts(before,after,run=RUN,pid=31,epoch=20000)


if __name__=='__main__':unittest.main()
