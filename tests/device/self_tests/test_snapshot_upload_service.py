"""Real loopback TLS/multipart originals; no target or device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPSHandler,ProxyHandler
from unittest.mock import patch
from PIL import Image,ImageDraw

DEVICE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(DEVICE),str(DEVICE/'adapters/android-phone')]
import test_account_provider as account_tests
from feature_journeys.account_provider import AccountProvider
from feature_journeys.server import make_server
from feature_journeys.snapshot_upload_service import SnapshotUploadService,multipart
from feature_journeys.witness import Client,NoRedirect
from overte_phone_snapshot_upload_fixture import validate

TICKET='a'*32;NEXT='b'*32;DOMAIN='12345678-1234-4234-8234-123456789012';PREFIX='/feature-fixture/v1'


def png():
    image=Image.new('RGB',(320,180),'blue');ImageDraw.Draw(image).rectangle((10,10,150,120),fill='red');out=BytesIO();image.save(out,format='PNG');return out.getvalue()


def body(raw=None,filename='original.png',boundary='owned-qt-boundary'):
    raw=png() if raw is None else raw
    return ('--'+boundary+'\r\nContent-Type: image/png\r\nContent-Disposition: form-data; name="image"; filename="'+filename+'"\r\n\r\n').encode()+raw+('\r\n--'+boundary+'--\r\n').encode()


class SnapshotUploadServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):account_tests.AccountProviderTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):account_tests.AccountProviderTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.accounts=AccountProvider();self.reader,self.actor,self.adapter=(secrets.token_hex(32) for _ in range(3))
        self.server=make_server(self.reader,self.actor,account_provider=self.accounts,tls_context=self.server_context,adapter_token=self.adapter)
        self.origin='https://localhost:'+str(self.server.server_port)
        self.service=SnapshotUploadService(self.accounts,DOMAIN,self.root,self.origin);self.server.snapshot_upload_service=self.service
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context),NoRedirect())
        self.run=self.request(PREFIX+'/runs',{'area':'snapshots'},self.reader)[1]['runId']
        self.activate(TICKET,'open')
        credentials=self.request(PREFIX+'/runs/'+self.run+'/snapshot-upload/credentials',token=self.reader)[1]
        self.token=self.request('/oauth/token',urlencode(dict(grant_type='password',scope='owner',**credentials)).encode(),content_type='application/x-www-form-urlencoded')[1]['access_token']
    def stop(self):
        self.accounts.shutdown();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
    def request(self,path,value=None,token=None,*,content_type='application/json',nonce=None,method=None,host=None):
        headers={'Content-Type':content_type}
        if token:headers['Authorization']='Bearer '+token
        if nonce:headers['X-Overte-Snapshot-Upload-Read']=nonce
        if host:headers['Host']=host
        raw=json.dumps(value).encode() if isinstance(value,dict) else value
        request=Request(self.origin+path,data=raw,method=method,headers=headers)
        try:response=self.opener.open(request,timeout=3)
        except HTTPError as error:response=error
        with response:
            data=response.read(1024*1024);self.response_id=response.headers.get('X-Overte-Fixture-Response');return response.code,json.loads(data)
    def activate(self,ticket,verb):self.assertEqual(200,self.request(PREFIX+'/runs/'+self.run+'/active',dict(ticket=ticket,verb=verb,inputs={}),self.reader)[0])
    def status(self,token=None):
        nonce=secrets.token_hex(16);status,value=self.request(PREFIX+'/runs/'+self.run+'/snapshot-upload',token=token or self.actor,nonce=nonce);self.assertEqual(200,status);validate(value,self.run,nonce,int(__import__('time').time()*1000));return value
    def upload(self,raw=None):return self.request('/api/v1/snapshots',body(raw),self.token,content_type='multipart/form-data; boundary=owned-qt-boundary')
    def story(self,image,**changes):
        details={k:image[k] for k in ('image_url','original_image_file_name')};details['snapshot_id']=image['id'];details.update(changes)
        return self.request('/api/v1/user_stories',dict(user_story=dict(details=json.dumps(details),thumbnail_url=image['thumbnail_url'],place_name='Owned domain',path='/1,2,3',action='snapshot',audience='for_url')),self.token)

    def test_actual_tls_multipart_story_ids_bytes_and_fresh_readonly_roles(self):
        query=urlencode(dict(now='2026-10-22T12:00:00Z',include_actions='concurrency',domain_id=DOMAIN,restriction='open,hifi'))
        self.assertEqual(1,self.request('/api/v1/user_stories?'+query)[1]['total_entries'])
        status,image=self.upload();self.assertEqual(200,status);image=image['data'];self.assertEqual(200,self.story(image)[0])
        value=self.status();self.assertEqual(1,value['uploads']);self.assertEqual(1,value['stories']);self.assertEqual(3,len(value['requests']))
        original=value['requests'][1];self.assertEqual(body(),self.service.original(original['body']));self.assertEqual(hashlib.sha256(png()).hexdigest(),original['image']['sha256'])
        self.assertEqual(200,original['response']['status']);self.assertEqual(0,self.server.internal_errors)
        self.assertEqual(value['requests'],self.status(self.adapter)['requests'])
        self.assertEqual(400,self.request(PREFIX+'/runs/'+self.run+'/snapshot-upload',token=self.actor)[0])
        self.assertEqual(403,self.request(PREFIX+'/runs/'+self.run+'/snapshot-upload/control',{'operation':'offline'},self.actor)[0])
        self.assertEqual(403,self.request(PREFIX+'/runs/'+self.run+'/snapshot-upload/credentials',token=self.actor)[0])
        self.assertEqual(200,self.request(PREFIX+'/runs/'+self.run,token=self.reader,method='DELETE')[0]);retired=self.status();self.assertFalse(retired['active']);self.assertEqual([],list(self.root.iterdir()))
        self.service.retire(self.run)

    def test_real_connection_close_404_domain_denial_and_recovery(self):
        self.activate(NEXT,'upload-fail')
        with self.assertRaises((URLError,ConnectionError,__import__('http.client').client.RemoteDisconnected)):self.upload()
        first=self.status()['requests'][0];self.assertEqual('connection-closed',first['state']);self.assertEqual(0,first['response']['status'])
        for fault in ('404','503'):
            self.service.control(self.run,fault);self.assertEqual(int(fault),self.upload()[0])
        self.service.control(self.run,'normal');self.service.control(self.run,'deny-domain');self.assertEqual(403,self.upload()[0])
        self.service.control(self.run,'allow-domain');self.assertEqual(200,self.upload()[0])
        self.assertEqual(5,len(self.status()['requests']))

    def test_missing_modified_inode_and_incomplete_owner_never_retire(self):
        self.upload();row=self.status()['requests'][0];record=row['body'];path=self.root/record['name'];raw=path.read_bytes();backup=path.with_suffix('.held')
        path.rename(backup)
        with self.assertRaises((ValueError,RuntimeError,OSError)):self.service.retire(self.run)
        backup.rename(path);path.write_bytes(raw[:-1]+b'x')
        with self.assertRaises(ValueError):self.service.retire(self.run)
        path.write_bytes(raw)
        from adapters.normal_feature_state import PrivateFeatureState
        owner=PrivateFeatureState(self.root/(record['name']+'.json'));original=owner.read();broken=dict(original,phase='opened');owner.write(broken,original)
        with self.assertRaises(ValueError):self.service.retire(self.run)
        owner.write(original,broken);self.service.retire(self.run)
        path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(ValueError):self.service.retire(self.run)

    def test_foreign_story_token_and_late_request_remain_red(self):
        image=self.upload()[1]['data'];self.assertEqual(403,self.story(image,snapshot_id='c'*32)[0])
        self.assertEqual(401,self.request('/api/v1/snapshots',body(),secrets.token_hex(32),content_type='multipart/form-data; boundary=owned-qt-boundary')[0])
        with self.assertRaises((ValueError,RuntimeError)):self.status()
        with self.assertRaises(ValueError):self.service.retire(self.run)
    def test_partial_multipart_and_duplicate_headers_cannot_claim_original_image(self):
        for raw in (body()[:-5],body(b'not an encoded PNG'),body(filename='../foreign.png'),body()+body()):
            with self.subTest(raw=hashlib.sha256(raw).hexdigest()),self.assertRaises((ValueError,UnicodeError)):multipart('multipart/form-data; boundary=owned-qt-boundary',raw)
    def test_pending_actual_request_prevents_retirement_until_original_write(self):
        self.service.control(self.run,'hold');values=[]
        worker=threading.Thread(target=lambda:values.append(self.upload()),daemon=True);worker.start()
        with self.accounts.changed:self.assertTrue(self.accounts.changed.wait_for(lambda:self.service.runs[self.run]['held'],timeout=2))
        with self.assertRaises(ValueError):self.service.retire(self.run)
        self.service.control(self.run,'release');worker.join(3);self.assertFalse(worker.is_alive());self.assertEqual(200,values[0][0]);self.service.retire(self.run)
        self.assertEqual(410,self.upload()[0])
        with self.assertRaises(ValueError):self.service.retire(self.run)


if __name__=='__main__':unittest.main()
