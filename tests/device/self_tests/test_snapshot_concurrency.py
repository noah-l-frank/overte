"""Controlled concurrency GET derives from actual declared domain source only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.snapshot_concurrency import SnapshotConcurrency,query
from self_tests.snapshot_domain_fixture import PolicyFixture,RUN,DOMAIN
from self_tests.test_snapshot_upload_provider import SnapshotUploadProviderTests


def actual_query(domain=DOMAIN):return 'now=2026-10-27T00:00:00.000Z&include_actions=concurrency&domain_id='+domain+'&restriction=open,hifi'


class SnapshotConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.f=SnapshotUploadProviderTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.domain=PolicyFixture(self);self.projection=SnapshotConcurrency(self.f.provider,self.domain.client())
    def response(self,raw=None,authorization=None,*,write=True):
        with self.projection.response(actual_query() if raw is None else raw,self.f.authorization if authorization is None else authorization) as response:
            status,body,identity,written=response
            if write and written is not None:written(dict(status=status,responseId=identity,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
            return status,json.loads(body)
    def test_native_get_observes_actual_open_hifi_acl_and_foreign_domain_without_relabel(self):
        for anonymous,logged_in,count in ((True,True,1),(False,True,1),(False,False,0)):
            self.domain.policy(anonymous,logged_in);status,value=self.response();self.assertEqual((200,count),(status,value['total_entries']))
        self.domain.policy(True,True);status,value=self.response(actual_query('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'));self.assertEqual(0,value['total_entries']);self.assertEqual(DOMAIN,value['fixtureConcurrency']['domainId'])
        snapshot=self.projection.snapshot(RUN);self.assertEqual(4,len(snapshot['requests']));self.assertTrue(all(row['written'] and row['left'] is not None for row in snapshot['requests']))
        self.assertNotIn(self.f.authorization,json.dumps(snapshot));self.assertNotIn(self.domain.config['token'],json.dumps(snapshot));self.assertNotIn('NEVER-RETAIN',json.dumps(snapshot))
    def test_foreign_or_revoked_actual_account_never_reads_domain_or_creates_upload_story(self):
        self.assertEqual(401,self.response(authorization='Bearer foreign')[0]);self.f.accounts.control(RUN,'revoke-issued');self.assertEqual(401,self.response()[0]);self.assertEqual([],self.domain.calls)
        self.assertEqual([],self.f.source()['uploads']);self.assertEqual([],self.f.source()['stories'])
    def test_closed_native_query_rejects_desired_count_restriction_override_and_duplicates(self):
        for raw in (actual_query()+'&total_entries=1',actual_query()+'&domain_id='+DOMAIN,actual_query().replace('open,hifi','acl'),actual_query().replace('concurrency','snapshot')):
            with self.subTest(raw=raw[-30:]),self.assertRaises((NativeUIError,ValueError)):query(raw)
        self.assertEqual([],self.domain.calls)
    def test_missing_actual_write_stays_owned_and_blocks_fence_quiet(self):
        self.response(write=False)
        with self.f.provider.lock,self.assertRaises(NativeUIError):self.projection.assert_quiet_locked(RUN)
        self.assertFalse(self.projection.snapshot(RUN)['requests'][0]['written'])
    def test_optional_provider_actual_HTTP_get_serializes_measured_projection_without_upload_rows(self):
        from email.message import Message
        from io import BytesIO
        import ssl
        from types import SimpleNamespace
        from unittest.mock import Mock
        from urllib.parse import urlsplit
        from feature_journeys.avatar_social_http import AccountAuthenticator
        from feature_journeys.snapshot_upload_provider import SnapshotUploadProvider
        from feature_journeys.snapshot_upload_http import handle
        from feature_journeys.server import Handler
        provider=SnapshotUploadProvider(AccountAuthenticator(self.f.accounts),epoch_ms=lambda:self.f.epoch,monotonic=lambda:self.f.mono,domain_client=self.domain.client());provider.provision(RUN);provider.activate(RUN,'b'*32)
        handler=object.__new__(Handler);handler.command='GET';handler.path='/api/v1/user_stories?'+actual_query();handler.request_version='HTTP/1.1';handler.requestline='GET '+handler.path+' HTTP/1.1'
        handler.server=SimpleNamespace(snapshot_upload_provider=provider);handler.connection=Mock(spec=ssl.SSLSocket);handler.connection.version.return_value='TLSv1.3';handler.rfile=BytesIO();handler.wfile=BytesIO();handler.headers=Message()
        handler.headers['Host']='controlled.invalid';handler.headers['Authorization']=self.f.authorization
        self.assertTrue(handle(handler,urlsplit(handler.path)));head,body=handler.wfile.getvalue().split(b'\r\n\r\n',1);self.assertIn(b' 200 ',head.split(b'\r\n',1)[0]);self.assertEqual(1,json.loads(body)['total_entries'])
        self.assertEqual({},provider.runs[RUN]['uploads']);self.assertEqual({},provider.runs[RUN]['stories']);self.assertTrue(provider.concurrency.snapshot(RUN)['requests'][0]['written'])


if __name__=='__main__':unittest.main()
