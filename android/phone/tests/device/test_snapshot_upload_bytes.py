"""Actual TLS wire originals with explicit native-client request producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import secrets
import sys
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests'),str(ROOT/'tests/device/adapters/android-phone')]
from self_tests import test_snapshot_upload_service as fixtures
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from overte_phone_snapshot_upload_fixture import SnapshotUploadFixtureReader
from overte_phone_snapshot_upload_bytes import PhoneSnapshotUploadBytes


class SnapshotUploadBytesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.SnapshotUploadServiceTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):fixtures.SnapshotUploadServiceTests.tearDownClass.__func__(cls)
    setUp=fixtures.SnapshotUploadServiceTests.setUp
    stop=fixtures.SnapshotUploadServiceTests.stop
    request=fixtures.SnapshotUploadServiceTests.request
    activate=fixtures.SnapshotUploadServiceTests.activate
    upload=fixtures.SnapshotUploadServiceTests.upload
    status=fixtures.SnapshotUploadServiceTests.status
    def make_reader(self,token=None,**kwargs):
        fixture=SnapshotUploadFixtureReader(Client(self.origin+fixtures.PREFIX,token or self.actor),self.run)
        return PhoneSnapshotUploadBytes(fixture,lambda:True,lambda:time.time_ns()//1000000,**kwargs)
    def selected(self):
        self.assertEqual(200,self.upload()[0]);return self.status()['requests'][-1]
    def patches(self):
        from contextlib import ExitStack
        stack=ExitStack();stack.enter_context(patch('feature_journeys.witness.build_opener',return_value=self.opener))
        stack.enter_context(patch('overte_phone_snapshot_upload_bytes.build_opener',return_value=self.opener));return stack
    def test_actual_wire_payload_is_independently_acquired_by_both_readonly_roles(self):
        row=self.selected()
        with self.patches():
            primary=self.make_reader(self.adapter).acquire(row['requestId'],row['ticket']);actor=self.make_reader().acquire(row['requestId'],row['ticket'])
        for original,raw in (primary,actor):
            self.assertEqual(fixtures.png(),raw);self.assertEqual('snapshot-upload-original',original['source'])
            self.assertEqual(row['body'],original['metadata']['body']);self.assertEqual(row['completedEpochMs'],original['originalCompletedEpochMs'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),original['sha256'])
        self.assertNotEqual(primary[0]['readId'],actor[0]['readId']);self.assertEqual(1,len(self.status()['requests']))
    def test_separate_binary_ceiling_preserves_existing_one_megabyte_json_limit(self):
        import io,random
        from PIL import Image
        output=io.BytesIO();Image.frombytes('RGB',(1024,1024),random.Random(9).randbytes(1024*1024*3)).save(output,format='PNG');raw=output.getvalue()
        self.assertGreater(len(raw),1024*1024);self.assertEqual(200,self.upload(raw)[0]);row=self.status()['requests'][-1]
        with self.patches():original,body=self.make_reader().acquire(row['requestId'],row['ticket'])
        self.assertEqual(raw,body);self.assertEqual(len(raw),original['bytes'])

    def test_missing_or_foreign_role_run_request_ticket_and_retirement_cannot_supply_bytes(self):
        row=self.selected()
        with self.patches():
            for token,run,request,ticket in ((secrets.token_hex(32),self.run,row['requestId'],row['ticket']),
                    (self.actor,'f'*32,row['requestId'],row['ticket']),(self.actor,self.run,'f'*32,row['ticket']),(self.actor,self.run,row['requestId'],'f'*32)):
                reader=self.make_reader(token);reader.fixture.run=run
                with self.subTest(run=run,request=request,ticket=ticket),self.assertRaises(NativeUIError):reader.acquire(request,ticket)
            self.service.retire(self.run)
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
    def test_original_body_mutation_replacement_mode_link_or_missing_file_is_red(self):
        row=self.selected();record=row['body'];path=self.root/record['name'];raw=path.read_bytes()
        with self.patches():
            path.write_bytes(raw[:-1]+b'x')
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
            path.write_bytes(raw);path.chmod(0o644)
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
            path.chmod(0o600);link=self.root/'alias';os.link(path,link)
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
            link.unlink();held=self.root/'held';path.rename(held)
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
            path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
    def test_wrong_nonce_source_identity_ticket_old_acquisition_or_changed_wire_metadata_is_red(self):
        row=self.selected();original=self.service.image_original
        for change in (dict(readId='f'*32),dict(instance='f'*32),dict(runId='f'*32),dict(requestId='f'*32),dict(ticket='f'*32),
                dict(capturedEpochMs=1),dict(body=row['body']|dict(inode=row['body']['inode']+1))):
            def faulty(*args):
                metadata,raw=original(*args);metadata.update(deepcopy(change));return metadata,raw
            with self.subTest(change=change),self.patches(),patch.object(self.service,'image_original',side_effect=faulty),self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
    def test_fresh_provider_cannot_hide_slow_binary_acquisition_or_changed_actual_payload(self):
        row=self.selected();original=self.service.image_original;elapsed=[0.]
        def slow(*args):
            result=original(*args);elapsed[0]=5.001;return result
        with self.patches(),patch.object(self.service,'image_original',side_effect=slow),self.assertRaises(NativeUIError):self.make_reader(monotonic=lambda:elapsed[0]).acquire(row['requestId'],row['ticket'])
        def changed(*args):
            metadata,raw=original(*args);return metadata,raw[:-1]+b'x'
        with self.patches(),patch.object(self.service,'image_original',side_effect=changed),self.assertRaises(NativeUIError):self.make_reader().acquire(row['requestId'],row['ticket'])
    def test_binary_route_rejects_mutations_bad_nonces_queries_and_product_access_token(self):
        row=self.selected();path=fixtures.PREFIX+'/runs/'+self.run+'/snapshot-upload/original/'+row['requestId']+'/'
        for tail,token,method in (('not-a-nonce',self.actor,'GET'),(secrets.token_hex(16)+'?foreign=1',self.actor,'GET'),
                (secrets.token_hex(16),self.token,'GET'),(secrets.token_hex(16),self.actor,'POST'),(secrets.token_hex(16),self.adapter,'DELETE')):
            with self.subTest(tail=tail,method=method),self.assertRaises(HTTPError) as failure:
                self.opener.open(Request(self.origin+path+tail,method=method,headers={'Authorization':'Bearer '+token}),timeout=3)
            self.assertIn(failure.exception.code,(400,403,404));failure.exception.close()

if __name__=='__main__':unittest.main()
