"""Normal captured-file Upload against actual authenticated protocol bytes.

Qt/TLS/socket boundaries are explicit models; no listener/device is executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import unittest
from ios.self_tests.snapshot_upload_backend_domain import SnapshotUploadBackendFlow


class SnapshotUploadBackendFlowTests(unittest.TestCase):
    def test_normal_capture_upload_consumes_actual_authenticated_backend_responses_and_same_body(self):
        d=SnapshotUploadBackendFlow(self);d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32);result=owner.finish();native=owner.packet('uploads',owner.state['decision'])
        backend=d.backend.source();self.assertEqual((1,1),(len(backend['uploads']),len(backend['stories'])))
        uploaded=backend['uploads'][0];fact,body=d.backend.independent_body(uploaded['instance']);self.assertEqual(d.f.bytes,body)
        self.assertEqual(hashlib.sha256(body).hexdigest(),fact['sha256']);self.assertEqual(d.f.f.h.path.name,fact['filename'])
        for stage in ('upload','story'):
            request=next(row for row in native['source']['requests'] if row['stage']==stage)
            response=next(row for row in native['source']['events'] if row['kind']=='response-original' and row['detail']['reply']==request['reply'])
            original=next(row for row in backend['requests'] if row['path']==('/api/v1/snapshots' if stage=='upload' else '/api/v1/user_stories'))
            self.assertEqual((original['responseBytes'],original['responseSha256']),(response['detail']['byteCount'],response['detail']['sha256']))
            self.assertTrue(original['written']);self.assertIsNotNone(original['left'])
        self.assertEqual(uploaded['instance'],backend['stories'][0]['upload']);self.assertEqual('success',result['nativeDecision']['status'])
        self.assertIsNone(backend['stories'][0]['deleted']);self.assertIsNone(uploaded['retired'])
        self.assertTrue(result['authenticatedBackendOriginalRequired']);self.assertTrue(result['transportProcessProofRequired'])
        self.assertNotIn(d.backend._authorization,json.dumps(backend))


if __name__=='__main__':unittest.main()
