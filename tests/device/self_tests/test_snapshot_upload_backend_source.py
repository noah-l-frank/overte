"""Strict original backend bytes, source lineage and bounded body frames."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import os
import unittest
import uuid
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import snapshot_upload_backend_source as source
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
from self_tests.test_snapshot_upload_provider import SnapshotUploadProviderTests,form_body,RUN


class SnapshotUploadBackendSourceTests(unittest.TestCase):
    def setUp(self):self.f=SnapshotUploadProviderTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def query(self,kind,**values):return dict(kind=kind,runId=RUN,requestId=uuid.uuid4().hex,**values)
    def test_actual_source_and_body_exports_keep_first_original_clock_and_reject_query_substitution(self):
        f=self.f;upload,_=f.upload();f.create_story(upload);query=self.query('source');export=f.provider.original(RUN,query['requestId'],'source');packet=source.export(export,query)
        self.assertEqual(1,len(packet['uploads']));f.epoch+=5000;f.mono+=5
        self.assertEqual(export,f.provider.original(RUN,query['requestId'],'source'))
        with self.assertRaises(ValueError):f.provider.original(RUN,query['requestId'],'body',identity=upload['id'],offset=0)
        body_query=self.query('body',upload=upload['id'],offset=0);body_export=f.provider.original(RUN,body_query['requestId'],'body',identity=upload['id'],offset=0);body=source.export(body_export,body_query)
        self.assertEqual(f.image,base64.b64decode(body['data']));self.assertTrue(body['readerClosed']);self.assertTrue(body['sourceJournalRetirementRequired'])
        for changed in (dict(body_query,requestId='c'*32),dict(body_query,upload='c'*32),dict(body_query,offset=source.PART)):
            with self.assertRaises(NativeUIError):source.export(body_export,changed)
        invalid=deepcopy(export);bad=b'\xff\xff';invalid['original']=dict(base64=base64.b64encode(bad).decode(),bytes=len(bad),sha256=hashlib.sha256(bad).hexdigest())
        with self.assertRaises(NativeUIError):source.export(invalid,query)
    def test_original_write_history_and_process_identity_cannot_be_forgotten_or_reanchored(self):
        f=self.f;f.upload();first=f.source();source.source(first);current=f.source();source.accept(first,current)
        for fault in ('history','pid','account','write'):
            changed=deepcopy(current)
            if fault=='history':changed['history']=[row for row in changed['history'] if row['kind']!='response-written']
            elif fault=='pid':changed['processId']+=1
            elif fault=='account':changed['accountProvider']='c'*32
            else:changed['requests'][0]['responseSha256']='c'*64
            with self.assertRaises(NativeUIError):source.accept(first,changed)
    def test_actual_large_PNG_two_chunks_keep_frame_limit_and_exact_private_originals(self):
        f=self.f;output=BytesIO();Image.frombytes('RGB',(768,384),os.urandom(768*384*3)).save(output,format='PNG');image=output.getvalue();self.assertGreater(len(image),source.PART)
        mime,raw=form_body(f.filename,image);status,body,_=f.response('POST','/api/v1/snapshots',raw,mime);self.assertEqual(200,status);identity=json.loads(body)['data']['id']
        store_fixture=SnapshotManifestTests();store_fixture.setUp();self.addCleanup(store_fixture.doCleanups);intents=[]
        frames=OriginalFrameStore(store_fixture.root,store_fixture.binding,RUN,'primary',lambda:True,lambda kind,value:intents.append(value),namespace='snapshot-upload-backend',schema_prefix='snapshotUploadBackend')
        chunks=[]
        for index,offset in enumerate(range(0,len(image),source.PART),1):
            query=self.query('body',upload=identity,offset=offset);value=f.provider.original(RUN,query['requestId'],'body',identity=identity,offset=offset);part=source.export(value,query)
            frame=dict(query=query,response=value,acquisition=dict(hostBeforeEpochMs=20000,hostAfterEpochMs=20000,hostBeforeMonotonic=10.,hostAfterMonotonic=10.))
            reference=frames.write(index,frame);path=frames.path(frames.expand(reference));self.assertLess(path.stat().st_size,1024*1024);self.assertEqual(0o600,path.stat().st_mode&0o777)
            self.assertEqual(frame,frames.read(frames.expand(reference)));chunks.append(base64.b64decode(part['data']))
        self.assertEqual(image,b''.join(chunks));self.assertEqual(hashlib.sha256(image).hexdigest(),part['sha256'])


if __name__=='__main__':unittest.main()
