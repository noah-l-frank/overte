"""Existing private reader, role gates and HTTP serializer over modeled TLS.

No listener or certificate is opened. Bearer and adapter-role credentials stay
in separate modeled endpoint boundaries; original journals receive neither.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from email.message import Message
from io import BytesIO
import json
import secrets
import ssl
from types import SimpleNamespace
from unittest.mock import Mock,patch
from urllib.parse import urlsplit
from urllib.error import HTTPError
from adapters.native_feature_observation import need
from feature_journeys import witness
from feature_journeys.server import Handler
from ios.adapters.snapshot_upload_backend_owner import backend_context
from ios.self_tests.snapshot_upload_backend_domain import SnapshotUploadBackendFlow,RUN,REAL_TIME,REAL_MONOTONIC


class SnapshotBackendOriginalDomain(SnapshotUploadBackendFlow):
    def __init__(self,case):
        super().__init__(case);self.private_calls=[];self.lost_source=False;self.foreign_authority=False
        self._adapter=secrets.token_hex(32);self.control_server=SimpleNamespace(snapshot_upload_provider=self.backend.provider,account_provider=self.backend.accounts,
            avatar_social_provider=None,navigation_resources=None,browser_peer=False,adapter_token=self._adapter,reader_token=secrets.token_hex(32),actor_token=secrets.token_hex(32),
            internal_errors=0,journal=SimpleNamespace(runs={RUN:dict(area='snapshots',ticket='a'*32)}))
        domain=self
        class Reader(witness.Client):
            def request(inner,*args,**kwargs):
                # Preserve the production reader, NoRedirect selection, header
                # validation, timeout, role marker and bounded byte decode.
                with patch.object(witness,'build_opener',side_effect=domain.opener):return super().request(*args,**kwargs)
        self.reader=Reader('https://controlled.invalid/feature-fixture/v1',self._adapter,monotonic=REAL_MONOTONIC,sleep=self.sleep)
    def opener(self,*handlers):
        need(handlers==(witness.NoRedirect,));return SimpleNamespace(open=self.private_open)
    def private_open(self,request,timeout):
        parsed=urlsplit(request.full_url);need(parsed.scheme=='https' and parsed.hostname=='controlled.invalid' and timeout==5 and request.get_method()=='GET')
        handler=object.__new__(Handler);handler.command=request.get_method();handler.path=parsed.path;handler.request_version='HTTP/1.1';handler.requestline=handler.command+' '+handler.path+' HTTP/1.1'
        handler.rfile=BytesIO(request.data or b'');handler.wfile=BytesIO();handler.connection=Mock(spec=ssl.SSLSocket);handler.connection.version.return_value='TLSv1.3';handler.server=self.control_server
        handler.headers=Message();handler.headers['Host']=parsed.netloc
        for key,value in request.header_items():handler.headers[key]=value
        self.private_calls.append(dict(path=parsed.path,method=request.get_method(),nonce=handler.headers.get('X-Overte-Snapshot-Read')))
        handler.handle_request();header,body=handler.wfile.getvalue().split(b'\r\n\r\n',1);status=int(header.split(b'\r\n',1)[0].split(b' ',2)[1])
        if self.foreign_authority and parsed.path.endswith('/account-provider'):
            value=json.loads(body);value['instance']='d'*32;body=json.dumps(value).encode()
        if self.lost_source and parsed.path.endswith('/snapshots/source'):
            self.lost_source=False;raise OSError('Declared original source response returned after native server query but caller lost it')
        if status!=200:raise HTTPError(request.full_url,status,'Declared closed source unavailable',{},BytesIO(body))
        return BytesIO(body)
    def prepare_native(self):
        self.prepare()
        with self.upload_owner() as owner:owner.start('a'*32);return owner.finish()
    def backend_owner(self):
        return backend_context(self.runtime,'primary',RUN,self.reader,self.ctx.binding,epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
