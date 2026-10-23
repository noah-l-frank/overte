"""Independent Pico uploaded bytes selected from frozen Phone b62e012f.

Version two pins the complete original physical multipart file metadata.

This reader never opens or relabels a private native capture. Request/ticket are
query identities; fresh independent provider receipts supply the actual result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import time
import uuid
from urllib.request import Request,ProxyHandler,build_opener

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import json_document,typed_equal,number
from feature_journeys.snapshot_upload_service import MAX_BODY
from feature_journeys.witness import NoRedirect
from adapters.pico4.snapshot_originals import nonce
from adapters.pico4.snapshot_upload_fixture import SnapshotUploadFixtureReader,file
from snapshot_observation import inspect_snapshot


class PicoSnapshotUploadBytes:
    def __init__(self,fixture,guard,clock_ms,*,monotonic=time.monotonic):
        need(isinstance(fixture,SnapshotUploadFixtureReader) and all(callable(fn) for fn in (guard,clock_ms,monotonic)))
        self.fixture,self.guard,self.clock_ms,self.monotonic=fixture,guard,clock_ms,monotonic
        self.reads=set();self.last=None

    @staticmethod
    def selected(provider,request,ticket):
        need(provider['active'] and nonce(request) and nonce(ticket))
        rows=[row for row in provider['requests'] if row['requestId']==request]
        need(len(rows)==1);row=rows[0]
        need(row['ticket']==ticket and row['method']=='POST' and row['target']=='/api/v1/snapshots' and row['authenticated']
            and row['state']=='written' and row['response'] is not None and row['response']['status']==200 and row['image'] is not None)
        return row

    def acquire(self,request,ticket):
        try:
            need(self.guard() is not False and len(self.reads)<256);start=number(self.monotonic(),0);requested=self.clock_ms();need(integer(requested,1))
            before=self.fixture.provider();row=self.selected(before,request,ticket)
            read=uuid.uuid4().hex;need(read not in self.reads);self.reads.add(read)
            url=self.fixture.client.url+'/runs/'+self.fixture.run+'/snapshot-upload/original/'+request+'/'+read
            query=Request(url,headers={'Authorization':'Bearer '+self.fixture.client.token})
            remaining=5-(self.monotonic()-start);need(remaining>0)
            with build_opener(ProxyHandler({}),NoRedirect()).open(query,timeout=remaining) as reply:
                need(reply.status==200 and reply.geturl()==url)
                for key in ('Content-Type','Content-Length','Cache-Control','X-Content-Type-Options','X-Overte-Snapshot-Original'):
                    need(len(reply.headers.get_all(key,[]))==1)
                encoded=reply.headers['X-Overte-Snapshot-Original'];need(len(encoded)<=8192)
                raw_meta=base64.b64decode(encoded,validate=True);need(base64.b64encode(raw_meta).decode()==encoded)
                meta=json_document(raw_meta)
                exact(meta,{'snapshotUploadOriginalVersion','instance','runId','requestId','readId','ticket','capturedEpochMs','originalCompletedEpochMs','domainId','origin','body','image'})
                need(type(meta['snapshotUploadOriginalVersion']) is int and meta['snapshotUploadOriginalVersion']==2
                    and meta['instance']==before['instance'] and meta['runId']==self.fixture.run and meta['requestId']==request and meta['readId']==read
                    and meta['ticket']==ticket and meta['domainId']==before['domainId'] and meta['origin']==before['origin']
                    and typed_equal(meta['body'],row['body']) and typed_equal(meta['image'],row['image']) and meta['originalCompletedEpochMs']==row['completedEpochMs'])
                file(meta['body']);fresh(meta['capturedEpochMs'],self.clock_ms());need(meta['capturedEpochMs']>=requested-1500)
                need(reply.headers['Content-Type']==meta['image']['mime'] and reply.headers['Content-Length']==str(meta['image']['bytes'])
                    and reply.headers['Cache-Control']=='no-store' and reply.headers['X-Content-Type-Options']=='nosniff')
                content=reply.read(MAX_BODY+1)
            need(0<len(content)<=MAX_BODY and len(content)==meta['image']['bytes'] and hashlib.sha256(content).hexdigest()==meta['image']['sha256'])
            kind={'image/png':'png','image/jpeg':'jpg','image/webp':'webp','image/gif':'gif'}[meta['image']['mime']]
            decoded=inspect_snapshot(content,mode='animated' if kind=='gif' else 'still',file_format=kind)
            after=self.fixture.provider(before);need(self.selected(after,request,ticket)==row and after['ticket']==before['ticket'])
            retained=deepcopy(meta)
            result=dict(source='snapshot-upload-original',request=request,readId=read,bytes=len(content),sha256=meta['image']['sha256'],
                capturedEpochMs=meta['capturedEpochMs'],originalCompletedEpochMs=meta['originalCompletedEpochMs'],metadata=deepcopy(meta),decoded=decoded)
            need(self.guard() is not False)
            epoch=self.clock_ms();fresh(meta['capturedEpochMs'],epoch);completed=number(self.monotonic(),start,start+5)
            need(completed-start<5 and max(epoch-meta['capturedEpochMs'],requested-meta['capturedEpochMs']+(completed-start)*1000)<=1500)
            self.last=retained;return result,content

        except Exception as error:
            if hasattr(error,'close'):error.close()
            raise NativeUIError('Independent original Snapshot upload bytes are unavailable or invalid') from None
