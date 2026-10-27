"""Original bounded Snapshot HTTP bytes; no listener, TLS install or device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest
import uuid
from urllib.parse import urlencode
from PIL import Image
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import AccountAuthenticator
from feature_journeys.snapshot_upload_provider import SnapshotUploadProvider,UPLOAD,STORIES,BODY,encode
from feature_journeys.snapshot_upload_protocol import multipart

RUN='a'*32
TICKET='b'*32
ORIGIN='https://controlled.invalid'


def form_body(filename,image,boundary='actual-snapshot-body'):
    raw=(b'--'+boundary.encode()+b'\r\nContent-Type: image/png\r\nContent-Disposition: form-data; name="image"; filename="'+filename.encode()+b'"\r\n\r\n'+image+b'\r\n--'+boundary.encode()+b'--\r\n')
    return 'multipart/form-data; boundary="'+boundary+'"',raw


class SnapshotUploadProviderTests(unittest.TestCase):
    def setUp(self):
        self.epoch=20000;self.mono=10.;self.accounts=AccountProvider(epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
        self.accounts.provision(RUN);self.accounts.activate(RUN,TICKET);credentials=self.accounts.credentials(RUN,'owned')
        status,grant=self.accounts.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode());self.assertEqual(200,status)
        self.authorization='Bearer '+grant['access_token'];self.provider=SnapshotUploadProvider(AccountAuthenticator(self.accounts),epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
        self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        output=BytesIO();Image.new('RGB',(8,8),(10,20,30)).save(output,format='PNG');self.image=output.getvalue()
        self.filename='parity-'+RUN[:16]+'-still-png-snap_20000_1.png';self.content_type,self.raw=form_body(self.filename,self.image)
    def response(self,method,path,raw=b'',content_type='',*,written=True,authorization=None):
        with self.provider.response(method,path,content_type,raw,self.authorization if authorization is None else authorization,ORIGIN) as response:
            status,body,identity,write=response
            if written and write is not None:write(dict(status=status,responseId=identity,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
            return status,body,identity
    def upload(self):
        status,body,request=self.response('POST',UPLOAD,self.raw,self.content_type);self.assertEqual(200,status);return json.loads(body)['data'],request
    def create_story(self,upload):
        details=dict(image_url=upload['image_url'],snapshot_id=upload['id'],original_image_file_name=upload['original_image_file_name'])
        raw=encode(dict(user_story=dict(details=json.dumps(details,indent=4)+'\n',thumbnail_url=upload['thumbnail_url'],place_name='controlled.invalid',path='/snapshot-fixture',action='snapshot',audience='for_url')))
        status,body,request=self.response('POST',STORIES,raw,'application/json');self.assertEqual(200,status);return json.loads(body)['user_story'],request
    def source(self):return self.provider.snapshot(RUN,uuid.uuid4().hex)
    def test_repeated_source_nonce_recovers_exact_original_time_bytes_and_cursor(self):
        before=self.provider.snapshot(RUN,'e'*32);self.upload();self.epoch+=1000;self.mono+=1
        self.assertEqual(before,self.provider.snapshot(RUN,'e'*32));current=self.source();self.assertEqual(1,len(current['uploads']));self.assertGreater(current['sequence'],before['sequence'])
        changed=deepcopy(before);changed['history'].append(dict(foreign=True));self.assertEqual(before,self.provider.snapshot(RUN,'e'*32))
    def test_actual_multipart_story_body_readback_and_native_delete_keep_original_server_rows(self):
        metadata,raw=multipart(self.content_type,self.raw);self.assertEqual(self.image,raw);self.assertEqual(self.filename,metadata['filename'])
        upload,upload_request=self.upload();story,story_request=self.create_story(upload)
        self.assertEqual((200,self.image),self.response('GET',BODY+upload['id']+'/image')[:2]);before=self.source()
        self.assertEqual({upload_request,story_request},{row['request'] for row in before['uploads']+before['stories']})
        self.assertTrue(all(row['written'] and row['left'] is not None for row in before['requests']))
        self.assertEqual(200,self.response('DELETE',STORIES+'/'+str(story['id']))[0]);after=self.source()
        self.assertIsNotNone(after['stories'][0]['deleted']);self.assertIsNone(after['stories'][0]['retired'])
        self.assertEqual(404,self.response('GET',STORIES+'/'+str(story['id']))[0])
        self.assertNotIn(self.authorization,json.dumps(after));self.assertNotIn(self.authorization[7:],json.dumps(after))
    def test_foreign_revoked_or_missing_authority_never_creates_a_backend_body(self):
        for authorization in ('Bearer invalid',''):
            with self.subTest(authorization=bool(authorization)):self.assertEqual(401,self.response('POST',UPLOAD,self.raw,self.content_type,authorization=authorization)[0])
        foreign='c'*32;self.accounts.provision(foreign);self.accounts.activate(foreign,TICKET);credentials=self.accounts.credentials(foreign,'owned')
        status,value=self.accounts.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode());self.assertEqual(200,status)
        self.assertEqual(401,self.response('POST',UPLOAD,self.raw,self.content_type,authorization='Bearer '+value['access_token'])[0])
        self.accounts.control(RUN,'revoke-issued');self.assertEqual(401,self.response('POST',UPLOAD,self.raw,self.content_type)[0]);self.assertEqual([],self.source()['uploads'])
    def test_duplicate_parts_headers_or_foreign_private_filename_cannot_create_owned_rows(self):
        for raw in (self.raw.replace(b'name="image"',b'name="other"'),self.raw.replace(b'Content-Type: image/png',b'Content-Type: image/png\r\nContent-Type: image/png'),self.raw+b'foreign',self.raw.replace(b'image/png',b'image/jpeg'),self.raw.replace(b'\r\n--actual-snapshot-body--',b'\r\n--actual-snapshot-body\r\nforeign\r\n--actual-snapshot-body--')):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):multipart(self.content_type,raw)
        content_type,raw=form_body(self.filename.replace(RUN[:16],'c'*16),self.image)
        self.assertEqual(403,self.response('POST',UPLOAD,raw,content_type)[0]);self.assertEqual([],self.source()['uploads'])
    def test_missing_original_write_blocks_authority_fence_and_preserves_body(self):
        self.assertEqual(200,self.response('POST',UPLOAD,self.raw,self.content_type,written=False)[0]);self.accounts.control(RUN,'revoke-issued')
        with self.assertRaises(ValueError):self.provider.fence(RUN)
        source=self.source();self.assertFalse(source['requests'][0]['written']);self.assertIsNotNone(source['requests'][0]['left']);self.assertIsNone(source['uploads'][0]['retired'])
    def test_fixture_cleanup_needs_actual_authority_revocation_and_both_backend_quiet_clocks(self):
        upload,_=self.upload();story,_=self.create_story(upload)
        with self.assertRaises(ValueError):self.provider.fence(RUN)
        self.accounts.control(RUN,'revoke-issued');self.provider.fence(RUN)
        self.epoch+=3001
        with self.assertRaises(ValueError):self.provider.retire_upload(RUN,upload['id'])
        self.mono+=3.001
        with self.assertRaises(ValueError):self.provider.retire_upload(RUN,upload['id'])
        self.provider.retire_story(RUN,str(story['id']));self.provider.retire_upload(RUN,upload['id']);source=self.source()
        self.assertIsNone(source['stories'][0]['deleted']);self.assertIsNotNone(source['stories'][0]['retired']);self.assertIsNotNone(source['uploads'][0]['retired'])
        self.assertIsNone(self.provider.runs[RUN]['uploads'][upload['id']]['body']);self.assertTrue(source['transportProcessProofRequired'])


if __name__=='__main__':unittest.main()
