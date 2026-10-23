"""Normal Pico transport + real PNG/TLS recovery; native/JS/renderer seams.

The original Qt/Settings/uploader bodies have separate owning compiler tests.
Here those client producers, Auth adoption and virtual device time are explicit
models; no Android, physical Pico input, Share or whole Snapshot is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from datetime import datetime,timezone
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import unittest
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,HTTPSHandler,ProxyHandler,build_opener
from unittest.mock import patch
import uuid
import test_snapshot_save_owner as prefix

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.pico4.snapshot_upload_source import FILE as UPLOAD_FILE
from adapters.native_feature_observation import FILE as ACCOUNT_FILE
from feature_journeys.account_provider import AccountProvider
from feature_journeys.server import make_server
from feature_journeys.snapshot_upload_service import SnapshotUploadService
from feature_journeys.witness import NoRedirect
from self_tests import test_account_provider as tls
from self_tests.test_pico_snapshot_upload_service import body,DOMAIN,PREFIX
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_account_observation import account as account_model


RUN=prefix.prefix.RUN


class SnapshotUploadFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.saved=prefix.SnapshotSaveFlowTests();self.saved.setUp();self.addCleanup(self.saved.doCleanups);self.h=self.saved.h
        self.root=self.h.h.h.state_root/'snapshot-owned-tls';self.root.mkdir(mode=0o700)
        self.accounts=AccountProvider(epoch_ms=self.h.clock,monotonic=lambda:self.h.adb.clock)
        self.reader,self.actor,self.adapter_token=(secrets.token_hex(32) for _ in range(3))
        self.server=make_server(self.reader,self.actor,account_provider=self.accounts,tls_context=self.server_context,adapter_token=self.adapter_token)
        self.origin='https://localhost:'+str(self.server.server_port)
        self.service=SnapshotUploadService(self.accounts,DOMAIN,self.root,self.origin);self.service.provision(RUN)
        self.server.snapshot_upload_service=self.service;self.server.journal=self.h.h.journal
        baseline=self.server.journal.runs[RUN]['phaseActivations'][-1];self.service.activate(RUN,baseline['ticket'],'baseline')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context),NoRedirect())
        for change in (patch('feature_journeys.witness.build_opener',return_value=self.opener),
                patch('adapters.pico4.snapshot_upload_bytes.build_opener',return_value=self.opener)):
            change.start();self.addCleanup(change.stop)
        self.h.phase.client=AdapterFixtureClient(self.origin+PREFIX,self.adapter_token)
        self.h.phase.fixture_url=self.h.phase.client.url+'/runs/'+RUN+'/'
        # The independent actor's phase and actual backend activate atomically.
        activate=self.h.activate
        def phase(verb,inputs=None):
            with self.server.journal.lock:
                activate(verb,inputs);active=self.server.journal.runs[RUN]
                self.service.activate(RUN,active['ticket'],verb)
        self.h.activate=phase
        credentials=self.service.credentials(RUN)
        status,grant,_=self.wire('/oauth/token',urlencode(dict(grant_type='password',scope='owner',**credentials)).encode(),content_type='application/x-www-form-urlencoded')
        self.assertEqual(200,status);self.token=grant['access_token'];credentials.clear()
        self.settings=dict(previousSnapshotDomainID='{'+DOMAIN+'}',previousSnapshotHref='hifi://original/owned')
        self.context_birth=uuid.uuid4().hex;self.normal_uploads=0;self.upload_sequence=0;self.upload_raw='';self.account_raw='';self.feature=FeatureBoundary()
        self.upload_events=[];self.jobs=[];self.upload_error=False;self.story_present=False
        event=self.h.event;script=self.h.script;review=self.h.review;write=self.h.adb.write_debug_app_file;read=self.h.adb.read_debug_app_file;view=self.h.adb.snapshot
        def original_event(*args,**kwargs):
            event(*args,**kwargs)
            files=list(self.h.adb.files.glob('*.png'))
            if files:self.settings['previousStillSnapPath']='/data/user/0/org.overte.pico/files/Snapshots/'+files[0].name
            self.h.events[-1]['context']=self.context()
        def original_script():
            value=script();value['snapshotScriptOriginalsVersion']=3;value['history']['snapshotScriptHistoryVersion']=2;value['captureContext']=self.context();return value
        def original_review():
            value=review()
            if value['present']:
                value['review'].update(loggedIn=bool(self.token),canShare=self.can_share,statusError=self.upload_error)
                for image in value['review']['images']:image['storyPresent']=self.story_present
            return value
        def original_view():
            value=view()
            for item in deepcopy(value['controls']):
                if item['id'].startswith('snapshot.save.'):
                    item['id']=item['id'].replace('snapshot.save.','snapshot.upload.');item['token']='33333333-3333-4333-8333-000000000078';value['controls'].append(item)
            return value
        def send(target,package,path,raw):
            command=json.loads(raw)
            if command.get('action')=='feature-pico-snapshot-upload':self.observe_upload(command);return
            if command.get('action')=='feature-native-observe':self.observe_account(command);return
            if command.get('controlId','').startswith('snapshot.upload.'):
                self.assertEqual(self.h.adb.sequence+1,command['sequence']);self.h.adb.sequence+=1;self.h.adb.inputs.append(deepcopy(command));self.normal_uploads+=1;self.perform_upload()
                self.h.adb.status=dict(schemaVersion=1,bridgeId=self.h.adb.bridge_id,commandId=command['commandId'],sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.h.clock());return
            return write(target,package,path,raw)
        def receive(target,package,path,**kwargs):
            if path.endswith('/'+UPLOAD_FILE):return self.upload_raw
            if path.endswith('/'+ACCOUNT_FILE):return self.account_raw
            return read(target,package,path,**kwargs)
        for change in (patch.object(self.h,'event',side_effect=original_event),patch.object(self.h,'script',side_effect=original_script),
                patch.object(self.h,'review',side_effect=original_review),patch.object(self.h.adb,'snapshot',side_effect=original_view),
                patch.object(self.h.adb,'write_debug_app_file',side_effect=send),patch.object(self.h.adb,'read_debug_app_file',side_effect=receive)):
            change.start();self.addCleanup(change.stop)
        self.can_share=self.permission()

    def stop(self):
        self.accounts.shutdown();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def context(self):
        keys=('previousSnapshotDomainID','previousSnapshotHref','previousStillSnapPath')
        return dict(snapshotCaptureContextVersion=1,instance=self.context_birth,capturedEpochMs=self.h.clock(),
            entries={key:dict(present=key in self.settings,value=self.settings.get(key)) for key in keys},normalizedHref=self.settings['previousSnapshotHref'])

    def wire(self,path,raw=None,*,content_type='application/json',authorization=False):
        headers={'Content-Type':content_type}
        if authorization:headers['Authorization']='Bearer '+self.token
        request=Request(self.origin+path,data=raw,headers=headers)
        try:response=self.opener.open(request,timeout=3)
        except HTTPError as error:response=error
        with response:
            raw=response.read(16385);self.assertLessEqual(len(raw),16384)
            return response.code,json.loads(raw),dict(raw=raw,response=response.headers.get('X-Overte-Fixture-Response',''))

    def permission(self):
        status,value,_=self.wire('/api/v1/user_stories?'+urlencode(dict(now=datetime.fromtimestamp(self.h.clock()/1000,timezone.utc).isoformat(),include_actions='concurrency',domain_id=DOMAIN,restriction='open,hifi')))
        return status==200 and value['total_entries']==1

    def observe_upload(self,command):
        self.upload_sequence+=1;epoch=self.h.clock()
        source=dict(snapshotUploadObservationVersion=2,instance='3'*32,complete=True,capturedEpochMs=epoch,
            sequence=len(self.upload_events),events=deepcopy(self.upload_events),jobs=sorted(deepcopy(self.jobs),key=lambda row:row['id']))
        self.upload_raw=json.dumps(dict(schemaVersion=1,requestId=command['commandId'],runId=RUN,instance=self.h.producer.outer,
            sequence=self.upload_sequence,processId=123,requestedEpochMs=epoch,capturedEpochMs=epoch,source=source))

    def observe_account(self,command):
        self.feature.send(command);value=self.feature.sample;value.update(instance=self.h.producer.outer,capturedEpochMs=self.h.clock())
        account=account_model();account.update(loggedIn=bool(self.token),principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
        account['observation'].update(capturedEpochMs=self.h.clock(),endpointSha256=hashlib.sha256(self.origin.encode()).hexdigest(),tokenPresent=bool(self.token),tokenValid=bool(self.token))
        value['account']=account;self.account_raw=json.dumps(value)

    def perform_upload(self):
        # This native/JS model is explicit. Wire/files/replies below are real.
        path=self.h.owner.state['capture']['file']['path'];local=self.h.adb.files/Path(path).name
        raw=local.read_bytes();info=local.stat();job_id=uuid.uuid4().hex
        file=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),device=str(info.st_dev),inode=str(info.st_ino),
            readBytes=len(raw),readSha256=hashlib.sha256(raw).hexdigest(),mode=info.st_mode,uid=info.st_uid,gid=info.st_gid,links=info.st_nlink,
            mtimeSeconds=info.st_mtime_ns//10**9,mtimeNanoseconds=info.st_mtime_ns%10**9,ctimeSeconds=info.st_ctime_ns//10**9,ctimeNanoseconds=info.st_ctime_ns%10**9)
        job=dict(id=job_id,path=path,href=self.settings['previousSnapshotHref'],uploaderAlive=False,fileAlive=False,multipartAlive=False,
            file=file,cancelRequested=False,terminal='',requests=[])
        def event(kind):self.upload_events.append(dict(sequence=len(self.upload_events)+1,jobId=job_id,kind=kind,capturedEpochMs=self.h.clock()))
        event('begin');event('file-open');self.assertTrue(self.permission())
        boundary='owned-qt-boundary';payload=body(raw,filename=local.name,boundary=boundary);status=0;response={};reply=dict(raw=b'',response='')
        try:status,response,reply=self.wire('/api/v1/snapshots',payload,content_type='multipart/form-data; boundary='+boundary,authorization=True)
        except (URLError,ConnectionError,__import__('http.client').client.RemoteDisconnected):pass
        def request(stage,status,reply,payload,boundary=''):
            return dict(id=uuid.uuid4().hex,stage=stage,url=self.origin+('/api/v1/snapshots' if stage=='image' else '/api/v1/user_stories'),operation=4,
                authRequired=True,authorizationPresent=True,multipart=stage=='image',boundary=boundary,jsonBytes=0 if stage=='image' else len(payload),
                jsonSha256=hashlib.sha256(b'' if stage=='image' else payload).hexdigest(),dispatchCurrent=True,sentBytes=len(payload),totalBytes=len(payload),finished=True,destroyed=True,
                status=status,networkError=0 if status==200 else 2,responseId=reply['response'] or '',replyBytes=len(reply['raw']),
                replySha256=hashlib.sha256(reply['raw']).hexdigest(),replyBase64=base64.b64encode(reply['raw']).decode())
        job['requests'].append(request('image',status,reply,payload,boundary))
        if status==200:
            image=response['data'];details=dict(image_url=image['image_url'],original_image_file_name=image['original_image_file_name'],snapshot_id=image['id'])
            payload=json.dumps(dict(user_story=dict(details=json.dumps(details),thumbnail_url=image['thumbnail_url'],place_name='Owned domain',path='/owned',action='snapshot',audience='for_url'))).encode()
            status,response,reply=self.wire('/api/v1/user_stories',payload,authorization=True)
            job['requests'].append(request('story',status,reply,payload));self.story_present=status==200
        self.upload_error=status!=200;job['terminal']='error' if self.upload_error else 'success';event('terminal');event('file-destroyed');event('uploader-destroyed');self.jobs.append(job)

    def owner(self,parent,verb,**kwargs):
        owner=self.h.adapter._snapshot_upload_owner(self.h.adb.target,RUN,self.h.phase,verb,parent=parent,source_lock=self.h.lock,**kwargs)
        owner.uploads.monotonic=owner.account.monotonic=lambda:self.h.adb.clock;owner.uploads.sleep=owner.account.sleep=self.h.adb.sleep
        return owner

    def test_normal_cancel_still_save_offline_upload_then_success_independent_png_quiet_and_cold_no_resend(self):
        # Real host capture originals are private from their creation; no chmod
        # or metadata repair is performed after the capture has been observed.
        original_umask=os.umask(0o077)
        try:saved=self.saved.ready()
        finally:os.umask(original_umask)
        saved.prepare();saved.send();saved.start_read();saved.quiet()
        for verb in ('share-open','share-cancel','share-open','share-select-owned','upload-fail'):self.h.activate(verb)
        failed=self.owner(saved,'upload-fail');self.assertEqual('prepared',failed.prepare()['stage']);self.assertEqual('observed',failed.send()['stage']);failed.quiet()
        self.h.activate('upload');owner=self.owner(saved,'upload',failure=failed)
        self.assertEqual('prepared',owner.prepare()['stage']);self.assertEqual('observed',owner.send()['stage']);self.assertEqual('acquired',owner.start_read()['stage'])
        report=owner.quiet();self.assertEqual('partial-ready',report['stage']);self.assertFalse(report['fullSnapshotRecipe']);self.assertFalse(report['precedingShareQualified'])
        self.assertEqual(2,self.normal_uploads);self.assertTrue(report['backendStoryRetained']);self.assertTrue(owner.store.path.exists());self.assertTrue(failed.store.path.exists())
        before=(len(self.h.adb.inputs),self.normal_uploads,self.upload_sequence);cold_saved=self.saved.make()
        cold_failure=self.owner(cold_saved,'upload-fail');cold=self.owner(cold_saved,'upload',failure=cold_failure)
        self.assertEqual(report,cold.report());self.assertEqual(before,(len(self.h.adb.inputs),self.normal_uploads,self.upload_sequence))
        with self.assertRaises((ValueError,RuntimeError)):cold.send()
        self.assertEqual(0,self.server.internal_errors)


if __name__=='__main__':unittest.main()
