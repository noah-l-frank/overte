"""Declared Combined XHR consumers over actual protected serializer bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_combined_preflight_http as source,snapshot_preflight_http,avatar_social_http
from ios.self_tests.snapshot_combined_preflight_http_fixture import CombinedPreflightHttpBoundary,RUN


class SnapshotCombinedPreflightHttpTests(unittest.TestCase):
    def setUp(self):self.f=CombinedPreflightHttpBoundary(self);self.value=self.f.value

    def test_original_default_manager_callback_read_joins_actual_protected_serialized_body(self):
        source.original(self.value);reads=source.response_reads(self.value,'qrc:/scripts/');self.assertEqual(1,len(reads));read=reads[0]
        self.assertEqual('qrc:/scripts/defaultScripts.js',read['engine']['url']);self.assertTrue(read['combinedSourceAdmitted'])
        self.assertTrue(read['sameCaptureManagerRequired']);self.assertTrue(read['authenticatedBackendOriginalRequired']);self.assertTrue(read['normalUploadEffectRequired'])
        self.assertEqual(self.f.backend.provider.concurrency.snapshot(RUN)['requests'][0]['requestId'],read['backendResponseId'])
        self.assertEqual(self.value['events'][5]['details']['body'],read['body'])
        self.assertNotEqual(self.f.backend.provider.concurrency.snapshot(RUN)['requests'][0]['entered']['epochMs'],read['readClock']['epochMs'])

    def test_separate_and_social_literal_profiles_cannot_adopt_combined_original_or_command(self):
        query=dict(schemaVersion=1,commandId=self.value['requestId'],action=source.ACTION,runId=RUN)
        for old in (snapshot_preflight_http,avatar_social_http):
            with self.subTest(profile=old.ACTION),self.assertRaises(NativeUIError):old.original(self.value)
            with self.subTest(command=old.ACTION),self.assertRaises(NativeUIError):old.command(query)
            with self.subTest(opposite=old.ACTION),self.assertRaises(NativeUIError):source.command(dict(query,action=old.ACTION))

    def test_incomplete_unknown_or_noncontiguous_actual_indexed_frame_cannot_supply_expected_parent(self):
        for fault in ('unknown','missing','gap','foreign','engine'):
            value=deepcopy(self.value);entry=value['callerStacks'][0]
            if fault=='unknown':entry['callerStack']['frames'].append(deepcopy(entry['callerStack']['frames'][-1]))
            elif fault=='missing':entry['callerModules'].pop()
            elif fault=='gap':entry['callerModules'][1]['frame']=2
            elif fault=='foreign':entry['callerModules'][1]['url']='qrc:/scripts/system/pal.js'
            else:value['callerStacks'][1]['callerStack']['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)

    def test_source_facts_remain_readable_but_foreign_consistent_compiled_main_cannot_pass_pins(self):
        value=deepcopy(self.value);created=value['events'][0]['details'];created['submitted']['sha256']='0'*64
        created['codeSources']['evaluations'][0]['sha256']='0'*64
        value['callerStacks'][0]['callerStack']['frames'][2]['compiled']['sha256']='0'*64
        source.original(value)
        with self.assertRaises(NativeUIError):source.response_reads(value,'qrc:/scripts/')
        with self.assertRaises(NativeUIError):source.response_reads(self.value,'qrc:/foreign/')

    def test_missing_duplicate_late_or_preassignment_evaluation_cannot_qualify_four_actual_sources(self):
        for fault in ('missing','duplicate','late','assignment','incomplete'):
            value=deepcopy(self.value);created=value['events'][0]['details'];code=created['codeSources']
            if fault=='missing':code['evaluations'].pop()
            elif fault=='duplicate':code['evaluations'].append(dict(code['evaluations'][-1],sequence=5))
            elif fault=='late':code['evaluations'][-1]['submittedEpochMs']=value['clockBefore']['epochMs']
            elif fault=='assignment':created['engine']['assignedEpochMs']=created['submitted']['submittedEpochMs']+1
            else:code['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.response_reads(value,'qrc:/scripts/')

    def test_text_read_outside_original_DONE_callback_cannot_become_consumer_effect(self):
        value=deepcopy(self.value);value['events'][7]['kind'],value['events'][8]['kind']='callback-leave','text-read'
        value['events'][7]['details'],value['events'][8]['details']=value['events'][8]['details'],value['events'][7]['details']
        source.original(value);self.assertEqual([],source.response_reads(value,'qrc:/scripts/'))

    def test_reply_body_or_caller_identity_cannot_be_replaced_after_original_consumption(self):
        for index,key,value in ((7,'replyId','0'*32),(5,'body',dict(bytes=0,sha256='0'*64,contentBase64='')),
            (7,'sha256','0'*64),(3,'url','https://foreign.invalid/api/v1/user_stories')):
            changed=deepcopy(self.value);changed['events'][index]['details'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.original(changed)

    def test_actual_reply_callback_timer_and_XHR_death_are_each_required_for_drain(self):
        self.assertFalse(source.drained(self.value,[self.f.xhr]));self.f.add('reply-destroyed',dict(replyId=self.f.reply));self.f.add('callbacks-released')
        self.assertFalse(source.drained(self.value,[self.f.xhr]));self.f.add('timer-destroyed');self.assertFalse(source.drained(self.value,[self.f.xhr]))
        self.f.add('xhr-destroyed');self.assertTrue(source.drained(self.value,[self.f.xhr]))
        with self.assertRaises(NativeUIError):source.drained(self.value,['0'*32])

    def test_original_clock_PID_typed_profile_and_immutable_event_caller_prefix_remain_bound(self):
        newer=deepcopy(self.value);newer.update(requestId='ios-'+'c'*32,sequence=2,
            clockBefore=dict(epochMs=self.f.epoch+1002,monotonicMs=1002),clockAfter=dict(epochMs=self.f.epoch+1003,monotonicMs=1003))
        query=dict(schemaVersion=1,commandId=newer['requestId'],action=source.ACTION,runId=RUN);source.validate(newer,query,42,previous=self.value)
        for fault in ('pid','clock','schema','event','table','birth','sequence'):
            changed=deepcopy(newer)
            if fault=='pid':changed['processId']=43
            elif fault=='clock':changed['clockAfter']['monotonicMs']+=1501
            elif fault=='schema':changed['iosSnapshotCombinedPreflightHttpVersion']=True
            elif fault=='event':changed['events'][4]['details']['active']=True
            elif fault=='table':changed['callerStacks'][1]['id']='a5'*16;changed['events'][7]['details']['callerStackId']='a5'*16
            elif fault=='birth':changed['instance']='d'*32
            else:changed['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query,42,previous=self.value)


if __name__=='__main__':unittest.main()
