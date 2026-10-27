"""Actual preflight query/reply byte retention and same-backend chronology."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from feature_journeys.snapshot_upload_provider import encode
from ios.adapters import snapshot_upload_backend_source as source
from self_tests.test_snapshot_concurrency import SnapshotConcurrencyTests,actual_query
from self_tests.snapshot_domain_fixture import RUN


def replacement(value,change):
    result=deepcopy(value);packet=json.loads(base64.b64decode(result['original']['base64']));change(packet);raw=encode(packet)
    result['original']=dict(base64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());return result


class SnapshotConcurrencyOriginalTests(unittest.TestCase):
    def setUp(self):
        self.f=SnapshotConcurrencyTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.projection=self.f.projection
        self.query=dict(snapshotUploadBackendQueryVersion=2,kind='preflight',runId=RUN,requestId=uuid.uuid4().hex,upload=None,offset=None)
        self.domain=self.projection.client.public()
    def original(self):return self.projection.original(RUN,self.query['requestId'])
    def packet(self,value=None):return source.concurrency_export(self.original() if value is None else value,self.query,self.domain)
    def test_same_nonce_retains_exact_original_query_response_policy_and_clock_after_later_requests(self):
        self.f.response();first=self.original();packet=self.packet(first);reply=packet['responses'][0];raw=base64.b64decode(reply['original']['base64'])
        self.assertEqual(actual_query().encode(),base64.b64decode(reply['requestQueryOriginal']['base64']));self.assertEqual(1,json.loads(raw)['total_entries'])
        self.assertEqual(reply['original']['sha256'],packet['snapshot']['requests'][0]['responseSha256'])
        self.f.f.epoch+=500;self.f.f.mono+=.5;self.f.domain.epoch+=500;self.f.domain.mono+=.5;self.f.domain.policy(False,False);self.f.response()
        self.assertEqual(first,self.original());self.assertEqual(1,len(self.packet()['snapshot']['requests']))
        self.assertNotIn(self.f.f.authorization,json.dumps(first));self.assertNotIn(self.f.domain.config['token'],json.dumps(first))
    def test_actual_backend_request_after_original_write_and_leave_joins_with_consumer_obligation(self):
        self.f.response();upload,request=self.f.f.upload();backend=self.f.f.source();packet=self.packet()
        joined=source.concurrency_joined(packet,backend,dict(upload=dict(request=request)),backend['ticket'])
        self.assertTrue(joined['frontendResponseConsumptionRequired']);self.assertTrue(joined['externalMetaverseRegistrationRequired'])
        self.assertEqual(packet['responses'][0]['original']['sha256'],joined['responseSha256'])
    def test_missing_original_write_cannot_join_even_when_backend_later_receives_upload(self):
        self.f.response(write=False);_upload,request=self.f.f.upload();backend=self.f.f.source();packet=self.packet()
        with self.assertRaises(NativeUIError):source.concurrency_joined(packet,backend,dict(upload=dict(request=request)),backend['ticket'])
        self.assertIsNone(packet['responses'][0]['written']);self.assertIsNotNone(packet['responses'][0]['original'])
    def test_substituted_response_bytes_query_bytes_or_policy_binding_are_rejected(self):
        self.f.response();original=self.original()
        changes=(lambda packet:packet['responses'][0]['original'].update(sha256='0'*64),
            lambda packet:packet['responses'][0]['requestQueryOriginal'].update(sha256='0'*64),
            lambda packet:packet['snapshot']['configuration']['binding'].update(processId=74))
        for change in changes:
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.packet(replacement(original,change))
    def test_foreign_backend_PID_and_other_ticket_cannot_be_reanchored(self):
        self.f.response();_upload,request=self.f.f.upload();backend=self.f.f.source();packet=self.packet();joined=dict(upload=dict(request=request))
        for field,value in (('processId',backend['processId']+1),('instance','0'*32),('accountProvider','1'*32)):
            changed=deepcopy(backend);changed[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.concurrency_joined(packet,changed,joined,backend['ticket'])
        with self.assertRaises(NativeUIError):source.concurrency_joined(packet,backend,joined,'2'*32)
    def test_original_reply_clock_after_actual_upload_request_cannot_qualify(self):
        _upload,request=self.f.f.upload();self.f.f.epoch+=1;self.f.f.mono+=.001;self.f.domain.epoch+=1;self.f.domain.mono+=.001;self.f.response()
        backend=self.f.f.source()
        with self.assertRaises(NativeUIError):source.concurrency_joined(self.packet(),backend,dict(upload=dict(request=request)),backend['ticket'])
    def test_failed_policy_read_retains_original_request_and_unresolved_response_fields(self):
        self.f.domain.drift='/id'
        with self.assertRaises(NativeUIError):self.f.response()
        packet=self.packet();self.assertTrue(packet['snapshot']['requests'][0]['failed']);self.assertIsNone(packet['responses'][0]['original'])
        self.assertEqual(actual_query().encode(),base64.b64decode(packet['responses'][0]['requestQueryOriginal']['base64']))


if __name__=='__main__':unittest.main()
