"""Existing HTTP serializer and closed optional routes without a listener."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from email.message import Message
from io import BytesIO
import json
import ssl
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import AccountAuthenticator
from feature_journeys.snapshot_upload_provider import SnapshotUploadProvider,UPLOAD,STORIES
from feature_journeys.snapshot_upload_http import handle,run_handle
from feature_journeys import server
from ios.self_tests.snapshot_upload_backend_domain import SnapshotBackendDomain
from self_tests.test_snapshot_upload_provider import form_body,RUN


class SnapshotUploadHTTPTests(unittest.TestCase):
    def test_existing_serializer_retains_actual_response_headers_body_and_write(self):
        d=SnapshotBackendDomain();image=b'\x89PNG\r\n\x1a\nactual owned native body';filename='parity-'+RUN[:16]+'-still-png-snap_20000_1.png';mime,raw=form_body(filename,image)
        status,body=d.call('POST',UPLOAD,raw,mime);self.assertEqual(200,status);source=d.source()
        request=source['requests'][0];self.assertEqual(len(body),request['responseBytes']);self.assertTrue(request['written']);self.assertIsNotNone(request['left'])
        self.assertEqual(filename,json.loads(body)['data']['original_image_file_name']);self.assertEqual(1,len(source['uploads']))
    def test_optional_source_does_not_activate_an_account_or_accept_adapter_mutation(self):
        accounts=AccountProvider();provider=SnapshotUploadProvider(AccountAuthenticator(accounts));sent=[]
        handler=SimpleNamespace(command='POST',server=SimpleNamespace(snapshot_upload_provider=provider,journal=SimpleNamespace(runs={RUN:dict(area='snapshots',ticket='a'*32)})),
            headers=Message(),send=lambda status,value:sent.append((status,value)))
        self.assertTrue(run_handle(handler,['runs',RUN,'snapshots','prepare'],dict(accountRun=RUN),reader=False,actor=False,adapter_reader=True))
        # The existing outer HTTP adapter gate rejects POST before this helper.
        # Its direct unprepared boundary is unavailable and cannot allocate.
        self.assertEqual(503,sent[-1][0]);self.assertEqual({},accounts.runs);self.assertEqual({},provider.runs)
        with self.assertRaises(KeyError):run_handle(handler,['runs',RUN,'snapshots','prepare'],dict(accountRun=RUN),reader=True,actor=False,adapter_reader=False)
        self.assertEqual({},accounts.runs);self.assertEqual({},provider.runs)
    def test_missing_optional_provider_and_nonTLS_leave_existing_product_route_unavailable(self):
        for provider,connection in ((None,object()),(SnapshotBackendDomain().provider,object())):
            sent=[];handler=SimpleNamespace(server=SimpleNamespace(snapshot_upload_provider=provider),connection=connection,send=lambda status,value:sent.append(status))
            self.assertTrue(handle(handler,urlsplit(UPLOAD)));self.assertEqual([404],sent)
    def test_duplicate_native_headers_reject_before_any_backend_row_or_response(self):
        d=SnapshotBackendDomain();sent=[]
        from unittest.mock import Mock
        headers=Message()
        for name,value in (('Host','controlled.invalid'),('Authorization',d._authorization),('Content-Length','10'),('Content-Length','10'),('Content-Type','application/json')):headers[name]=value
        connection=Mock(spec=ssl.SSLSocket);connection.version.return_value='TLSv1.3'
        handler=SimpleNamespace(server=SimpleNamespace(snapshot_upload_provider=d.provider),connection=connection,headers=headers,command='POST',rfile=BytesIO(b'{}'),send=lambda status,value:sent.append(status))
        with self.assertRaises(ValueError):handle(handler,urlsplit(STORIES))
        self.assertEqual([],sent);self.assertEqual([],d.source()['requests'])
    def test_factory_preserves_disabled_default_and_rejects_foreign_authority_before_attachment(self):
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
        accounts=AccountProvider();provider=SnapshotUploadProvider(AccountAuthenticator(accounts));reader,actor='r'*64,'p'*64
        for authority,optional,context in ((None,provider,tls),(AccountProvider(),provider,tls),(accounts,object(),tls),(accounts,provider,None)):
            with self.subTest(kind=type(optional).__name__),patch.object(server,'FixtureServer',side_effect=AssertionError('Listener forbidden')),self.assertRaises(ValueError):
                server.make_server(reader,actor,account_provider=authority,snapshot_upload_provider=optional,tls_context=context)
            if authority is not None:self.assertFalse(authority._attached)
        with patch.object(server,'FixtureServer',return_value=SimpleNamespace()) as constructor:
            default=server.make_server(reader,actor);self.assertIsNone(default.snapshot_upload_provider);self.assertEqual(1,constructor.call_count)


if __name__=='__main__':unittest.main()
