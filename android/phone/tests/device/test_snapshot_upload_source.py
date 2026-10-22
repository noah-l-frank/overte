"""Original upload reader/receiver joins with explicitly synthetic native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests'),str(ROOT/'tests/device/adapters/android-phone')]
import test_snapshot_upload_service as service_tests
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_upload_source import PhoneSnapshotUploadSource,command,source,continuity,require_retired
from overte_phone_snapshot_upload_fixture import join

JOB='1'*32;RUN='2'*32;PATH='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/original.png'


def native(provider):
    records=[row for row in provider['requests'] if row['method']=='POST']
    image=service_tests.png();requests=[]
    for index,row in enumerate(records):
        response=row['response'];stage='image' if row['target'].endswith('/snapshots') else 'story'
        requests.append(dict(id=str(index+3)*32,stage=stage,url=provider['origin']+row['target'],operation=4,authRequired=True,authorizationPresent=True,multipart=stage=='image',boundary='owned-qt-boundary' if stage=='image' else '',bodyBytes=row['body']['bytes'] if stage=='story' else 0,bodySha256=row['body']['sha256'] if stage=='story' else hashlib.sha256(b'').hexdigest(),dispatchCurrent=True,sentBytes=row['body']['bytes'],totalBytes=row['body']['bytes'],finished=True,destroyed=True,status=response['status'],networkError=0 if response['status']==200 else 2,responseId=response['responseId'] or '',replyBytes=response['body']['bytes'],replySha256=response['body']['sha256'],replyBase64=response['bodyBase64']))
    epoch=provider['capturedEpochMs'];events=[dict(sequence=index+1,jobId=JOB,kind=kind,capturedEpochMs=epoch) for index,kind in enumerate(('begin','file-open','multipart-created','terminal','uploader-destroyed','file-destroyed','multipart-destroyed'))]
    return dict(snapshotUploadObservationVersion=1,instance='9'*32,complete=True,capturedEpochMs=epoch,sequence=len(events),events=events,jobs=[dict(id=JOB,path=PATH,href='hifi://owned/1,2,3',uploaderAlive=False,fileAlive=False,multipartAlive=False,file=dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),device=1,inode=2,readBytes=len(image),readSha256=hashlib.sha256(image).hexdigest()),cancelRequested=False,terminal='success' if len(requests)==2 else 'error',requests=requests)])


class SnapshotUploadSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):service_tests.SnapshotUploadServiceTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):service_tests.SnapshotUploadServiceTests.tearDownClass.__func__(cls)
    setUp=service_tests.SnapshotUploadServiceTests.setUp
    stop=service_tests.SnapshotUploadServiceTests.stop
    request=service_tests.SnapshotUploadServiceTests.request
    activate=service_tests.SnapshotUploadServiceTests.activate
    status=service_tests.SnapshotUploadServiceTests.status
    upload=service_tests.SnapshotUploadServiceTests.upload
    story=service_tests.SnapshotUploadServiceTests.story
    def complete(self):
        from urllib.parse import urlencode
        query=urlencode(dict(now='2026-10-22T12:00:00Z',include_actions='concurrency',domain_id=service_tests.DOMAIN,restriction='open,hifi'))
        self.request('/api/v1/user_stories?'+query)
        image=self.upload()[1]['data'];self.story(image);provider=self.status();return native(provider),provider
    def joined(self,native,provider,success=True):return join(native,provider,JOB,ticket=service_tests.TICKET,image_bytes=len(service_tests.png()),image_sha256=hashlib.sha256(service_tests.png()).hexdigest(),path=PATH,success=success)
    def test_original_native_file_and_both_real_tls_receipts_join_without_expected_ids(self):
        observed,provider=self.complete();proof=self.joined(observed,provider);self.assertIsInstance(proof['storyId'],int);self.assertEqual(2,len(proof['requests']));require_retired(observed)
        for field in ('fileAlive','multipartAlive','uploaderAlive'):
            broken=deepcopy(observed);broken['jobs'][0][field]=True
            with self.subTest(field=field),self.assertRaises(NativeUIError):require_retired(broken)
        broken=deepcopy(observed);broken['jobs'][0]['requests'][0]['finished']=False
        with self.assertRaises(NativeUIError):require_retired(broken)
    def test_borrowed_response_file_bytes_domain_permission_or_cancelled_job_stays_red(self):
        observed,provider=self.complete()
        cases=[]
        changed=deepcopy(observed);changed['jobs'][0]['requests'][0]['responseId']='a'*32;cases.append((changed,provider))
        changed=deepcopy(observed);changed['jobs'][0]['file']['readSha256']='0'*64;cases.append((changed,provider))
        changed=deepcopy(observed);changed['jobs'][0]['cancelRequested']=True;cases.append((changed,provider))
        changed=deepcopy(provider);changed['requests']=changed['requests'][1:];cases.append((observed,changed))
        for actual,receiver in cases:
            with self.subTest(actual=actual['jobs'][0]['cancelRequested']),self.assertRaises(NativeUIError):self.joined(actual,receiver)
    def test_readonly_native_reader_freshness_closed_grammar_and_history_rollback(self):
        observed,provider=self.complete();epoch=observed['capturedEpochMs'];clock=[0.];calls=[];packet=[''];sequence=[0]
        def send(request):
            calls.append(request);sequence[0]+=1;packet[0]=json.dumps(dict(schemaVersion=1,requestId=request['commandId'],runId=self.run,instance='8'*32,sequence=sequence[0],processId=31,requestedEpochMs=epoch,capturedEpochMs=epoch,source=observed))
        reader=PhoneSnapshotUploadSource(send,lambda:packet[0],lambda:epoch,lambda:True,31,monotonic=lambda:clock[0],sleep=lambda s:clock.__setitem__(0,clock[0]+s))
        first=reader.read(self.run);reader.read(self.run);self.assertTrue(all(row['action']=='phone-snapshot-upload-observe' for row in calls));self.assertNotEqual(calls[0]['commandId'],calls[1]['commandId'])
        changed=deepcopy(first);changed['sequence']+=1;changed['source']['events'][0]['kind']='terminal'
        with self.assertRaises(NativeUIError):continuity(first,changed)
        for field in ('expected','url','operation'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(dict(calls[0],**{field:'success'}))
        observed['complete']=False
        with self.assertRaises(NativeUIError):reader.read(self.run)
    def test_actual_offline_socket_close_joins_only_original_error_job(self):
        self.service.control(self.run,'offline')
        with self.assertRaises(Exception):self.upload()
        provider=self.status();observed=native(provider);self.assertTrue(self.joined(observed,provider,success=False)['offline'])
        with self.assertRaises(NativeUIError):self.joined(observed,provider)


if __name__=='__main__':unittest.main()
