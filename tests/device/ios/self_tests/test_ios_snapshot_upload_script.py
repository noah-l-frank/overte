"""Normal Script policy preflight precedes native ownership and real body IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from feature_journeys.snapshot_concurrency import SnapshotConcurrency
from ios.self_tests.snapshot_upload_backend_domain import SnapshotBackendDomain,RUN
from ios.self_tests.snapshot_upload_script_domain import OriginalUploadScript,SnapshotUploadScriptFlow
from self_tests.snapshot_domain_fixture import PolicyFixture,DOMAIN


class SnapshotUploadScriptBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.backend=SnapshotBackendDomain();self.policy=PolicyFixture(self)
        self.backend.provider.concurrency=SnapshotConcurrency(self.backend.provider,self.policy.client());self.script=OriginalUploadScript(self,self.backend)
    def dispatch(self,**kwargs):return self.script.dispatch('/private/actual-capture.png',**kwargs)
    def test_actual_script_and_request_module_create_share_only_after_actual_open_policy_GET(self):
        result=self.dispatch();self.assertEqual([dict(path='/private/actual-capture.png',href='hifi://controlled.invalid/snapshot-fixture')],result['shares'])
        self.assertEqual((1,1,True,'actual-capture.png'),(result['pendingUploads'],result['permissionUpdates'],result['xhrCallbackReleased'],result['filename']))
        self.assertEqual(['http','returned','result'],[event['event'] for event in self.script.events]);self.assertEqual(0,self.script.events[1]['pendingUploads'])
        self.assertEqual(['/id','/settings.json'],self.policy.calls);self.assertEqual('GET',self.backend.sent[0]['method'])
        ledger=self.backend.provider.concurrency.snapshot(RUN);self.assertTrue(ledger['requests'][0]['written']);self.assertIsNotNone(ledger['requests'][0]['left'])
        self.assertEqual({},self.backend.provider.runs[RUN]['uploads']);self.assertNotIn(self.backend._authorization,json.dumps(self.script.events))
    def test_actual_script_rejects_measured_acl_before_native_creation(self):
        self.policy.policy(False,False);result=self.dispatch();self.assertEqual([],result['shares']);self.assertEqual(0,result['pendingUploads'])
        self.assertEqual('snapshotError',result['messages'][0]['action']);self.assertEqual(0,json.loads(self.backend.sent[0]['response'])['total_entries'])
    def test_foreign_requested_domain_never_relabels_actual_policy_source(self):
        result=self.dispatch(domain='{aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee}');self.assertEqual([],result['shares'])
        source=self.backend.provider.concurrency.snapshot(RUN)['requests'][0]['source']['packet'];self.assertEqual(DOMAIN,source['domainId'])
    def test_revoked_account_is_rejected_before_domain_read_and_native_creation(self):
        self.backend.accounts.control(RUN,'revoke-issued');result=self.dispatch();self.assertEqual([],result['shares']);self.assertEqual([],self.policy.calls)
        self.assertEqual(401,self.backend.sent[0]['status']);self.assertTrue(result['xhrCallbackReleased'])
    def test_actual_revision_wrapper_drops_late_preflight_callback(self):
        result=self.dispatch(replace_review=True);self.assertEqual([],result['shares']);self.assertEqual([],result['messages']);self.assertEqual(0,result['permissionUpdates'])
        self.assertTrue(result['xhrCallbackReleased']);self.assertTrue(self.backend.provider.concurrency.snapshot(RUN)['requests'][0]['written'])
    def test_absent_domain_does_not_dispatch_a_request_or_create_native_upload(self):
        result=self.dispatch(domain='');self.assertEqual([],result['shares']);self.assertEqual([],self.backend.sent);self.assertEqual([],self.policy.calls)
    def test_missing_optional_policy_stays_unavailable_to_actual_script(self):
        self.backend.provider.concurrency=None;result=self.dispatch();self.assertEqual([],result['shares']);self.assertEqual(503,self.backend.sent[0]['status']);self.assertEqual([],self.policy.calls)


class SnapshotUploadScriptFlowTests(unittest.TestCase):
    def test_normal_capture_actual_script_preflight_native_upload_and_authenticated_same_body(self):
        d=SnapshotUploadScriptFlow(self);d.prepare()
        with d.upload_owner() as owner:owner.start('a'*32);result=owner.finish()
        self.assertEqual(1,d.upload_count);self.assertEqual(1,len(d.native_birth_preflight));self.assertEqual(1,len(d.script_results[0]['shares']))
        source=d.backend.source();self.assertEqual((1,1),(len(source['uploads']),len(source['stories'])))
        fact,body=d.backend.independent_body(source['uploads'][0]['instance']);self.assertEqual(d.f.bytes,body);self.assertEqual(d.f.f.h.path.name,fact['filename'])
        preflight=d.backend.provider.concurrency.snapshot(RUN)['requests'][0];self.assertEqual(d.native_birth_preflight,[preflight['requestId']])
        # Backend UTC and the existing declared native fixture clock are
        # distinct sources. The producer checks actual written/departed state
        # before calling new_upload(); neither clock is rewritten to match.
        self.assertTrue(preflight['written']);self.assertIsNotNone(preflight['left']);self.assertEqual('GET',d.backend.sent[0]['method'])
        self.assertTrue(result['knownObjectsAndBodyFDQuiet']);self.assertTrue(result['transportProcessProofRequired']);self.assertTrue(preflight['source']['packet']['externalRegistrationRequired'])
        self.assertEqual(0,next(event for event in d.script.events if event['event']=='returned')['pendingUploads'])
    def test_actual_script_preflight_then_normal_cancel_releases_native_body_but_retains_backend(self):
        d=SnapshotUploadScriptFlow(self);d.auto_complete=False;d.prepare()
        with d.upload_owner() as owner:owner.start('a'*32);result=owner.cancel()
        self.assertEqual((1,1),(d.upload_count,d.upload_cancel_count));self.assertEqual('cancelled',result['nativeDecision']['status'])
        self.assertTrue(result['knownObjectsAndBodyFDQuiet']);self.assertFalse(d.upload.open_fds)
        source=d.backend.source();self.assertEqual((1,0),(len(source['uploads']),len(source['stories'])))
        self.assertIsNone(source['uploads'][0]['retired']);self.assertTrue(result['authenticatedBackendOriginalRequired'])
        self.assertEqual(d.f.bytes,d.backend.independent_body(source['uploads'][0]['instance'])[1]);self.assertEqual(1,len(d.native_birth_preflight))


if __name__=='__main__':unittest.main()
