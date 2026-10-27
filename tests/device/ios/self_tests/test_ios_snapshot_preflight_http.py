"""Closed Snapshot source parsing, actual response bytes and weak boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_social_http,avatar_call_stack,snapshot_preflight_http as source
from ios.self_tests.snapshot_preflight_http_fixture import SnapshotPreflightHttpBoundary,RUN


class SnapshotPreflightHttpTests(unittest.TestCase):
    def setUp(self):self.f=SnapshotPreflightHttpBoundary(self);self.value=self.f.value
    def test_actual_serialized_reply_bytes_read_in_original_request_callback_keep_effects_separate(self):
        source.original(self.value);reads=source.response_reads(self.value);self.assertEqual(1,len(reads));read=reads[0]
        self.assertEqual(self.f.backend.provider.concurrency.snapshot(RUN)['requests'][0]['requestId'],read['backendResponseId'])
        self.assertEqual(self.value['events'][5]['details']['body'],read['body']);self.assertTrue(read['authenticatedBackendOriginalRequired']);self.assertTrue(read['normalUploadEffectRequired'])
        self.assertNotEqual(self.f.backend.provider.concurrency.snapshot(RUN)['requests'][0]['entered']['epochMs'],read['readClock']['epochMs'])
    def test_foreign_missing_or_noncontiguous_initial_snapshot_frame_is_rejected(self):
        for fault in ('missing','foreign','gap','top'):
            value=deepcopy(self.value);caller=value['callerStacks'][0]
            if fault=='missing':caller['callerModules'].pop()
            elif fault=='foreign':caller['callerModules'][1]['url']='qrc:/scripts/system/pal.js'
            elif fault=='gap':caller['callerModules'][1]['frame']=3
            else:caller['callerModules'][0]['frame']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_compiled_bytes_and_actual_submitted_code_cannot_be_substituted(self):
        for fault in ('compiled','submitted','late','incomplete','manager-code'):
            value=deepcopy(self.value);created=value['events'][0]['details']
            if fault=='compiled':value['callerStacks'][0]['callerStack']['frames'][1]['compiled']['sha256']='0'*64
            elif fault=='submitted':created['codeSources']['evaluations'][1]['sha256']='0'*64
            elif fault=='late':created['codeSources']['evaluations'][1]['submittedEpochMs']=value['clockBefore']['epochMs']
            elif fault=='incomplete':created['codeSources']['complete']=False
            else:created['submitted']['sha256']='0'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_reply_and_original_response_body_cannot_be_replaced(self):
        for index,key,value in ((7,'replyId','0'*32),(5,'body',dict(bytes=0,sha256='0'*64,contentBase64='')),(7,'sha256','0'*64),(3,'url','https://foreign.invalid/api/v1/user_stories')):
            changed=deepcopy(self.value);changed['events'][index]['details'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.original(changed)
    def test_text_read_outside_DONE_callback_is_retained_but_not_a_response_read_proof(self):
        value=deepcopy(self.value);value['events'][7]['kind'],value['events'][8]['kind']='callback-leave','text-read'
        value['events'][7]['details'],value['events'][8]['details']=value['events'][8]['details'],value['events'][7]['details']
        source.original(value);self.assertEqual([],source.response_reads(value))
    def test_every_actual_reply_callback_timer_and_XHR_resource_must_retire(self):
        self.assertFalse(source.drained(self.value,[self.f.xhr]));self.f.add('reply-destroyed',dict(replyId=self.f.reply));self.f.add('callbacks-released')
        self.assertFalse(source.drained(self.value,[self.f.xhr]));self.f.add('timer-destroyed');self.assertFalse(source.drained(self.value,[self.f.xhr]));self.f.add('xhr-destroyed')
        self.assertTrue(source.drained(self.value,[self.f.xhr]))
        with self.assertRaises(NativeUIError):source.drained(self.value,['0'*32])
    def test_social_and_snapshot_literal_namespaces_reject_profile_substitution(self):
        with self.assertRaises(NativeUIError):avatar_social_http.original(self.value)
        query=dict(schemaVersion=1,commandId=self.value['requestId'],action=source.ACTION,runId=RUN)
        with self.assertRaises(NativeUIError):avatar_social_http.command(query)
        with self.assertRaises(NativeUIError):source.command(dict(query,action=avatar_social_http.ACTION))
        caller=self.value['callerStacks'][0]
        with self.assertRaises(NativeUIError):avatar_call_stack.validate(caller['callerStack'],caller['callerModules'],self.value['clockBefore']['epochMs'])
        original_url=self.value['events'][0]['details']['requestUrl']
        for url in (original_url+'#',original_url.replace(self.f.policy.binding['domainId'],'00000000-0000-0000-0000-000000000000')):
            value=deepcopy(self.value);value['events'][0]['details']['requestUrl']=value['events'][3]['details']['url']=url
            with self.subTest(url=url[-38:]),self.assertRaises(NativeUIError):source.original(value)
        value=deepcopy(self.value);value['events'][0]['details']['engine']['url']='qrc:/scripts/defaultScripts.js'
        with self.assertRaises(NativeUIError):source.original(value)
    def test_foreign_process_clock_or_typed_schema_does_not_validate_a_bound_read(self):
        query=dict(schemaVersion=1,commandId=self.value['requestId'],action=source.ACTION,runId=RUN)
        for fault in ('pid','clock','schema'):
            changed=deepcopy(self.value)
            if fault=='pid':changed['processId']=43
            elif fault=='clock':changed['clockAfter']['monotonicMs']+=1501
            else:changed['iosSnapshotPreflightHttpVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query,42)
    def test_absent_fixture_identity_is_unknown_and_acl_response_read_is_not_upload_effect(self):
        value=deepcopy(self.value);value['events'][5]['details'].update(responseId='',body=None)
        source.original(value);self.assertEqual([],source.response_reads(value))
        denied=SnapshotPreflightHttpBoundary(self,anonymous=False,logged_in=False);read=source.response_reads(denied.value)[0]
        self.assertEqual(0,json.loads(base64.b64decode(read['body']['contentBase64']))['total_entries']);self.assertTrue(read['normalUploadEffectRequired'])
        self.assertNotIn('canShare',read);self.assertNotIn('nativeUploadObserved',read)
    def test_new_sampler_cannot_change_old_caller_table_event_prefix_or_birth(self):
        newer=deepcopy(self.value);newer.update(requestId='ios-'+'c'*32,sequence=2,
            clockBefore=dict(epochMs=self.f.epoch+1002,monotonicMs=1002),clockAfter=dict(epochMs=self.f.epoch+1003,monotonicMs=1003))
        query=dict(schemaVersion=1,commandId=newer['requestId'],action=source.ACTION,runId=RUN);source.validate(newer,query,42,previous=self.value)
        for fault in ('event','table','birth','sequence'):
            changed=deepcopy(newer)
            if fault=='event':changed['events'][4]['details']['active']=True
            elif fault=='table':changed['callerStacks'][1]['id']='a5'*16;changed['events'][7]['details']['callerStackId']='a5'*16
            elif fault=='birth':changed['instance']='d'*32
            else:changed['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query,42,previous=self.value)


if __name__=='__main__':unittest.main()
