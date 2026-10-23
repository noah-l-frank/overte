"""Pico TLS original bytes selected from frozen Phone b62e012f.

The backend and wire files are real; the ordinary native-client producer is an explicit seam."""
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

ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests')]
from self_tests import test_pico_snapshot_upload_service as fixtures
from self_tests.test_pico_snapshot_upload_service import SnapshotUploadServiceTests
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from adapters.pico4.snapshot_upload_fixture import SnapshotUploadFixtureReader
from adapters.pico4.snapshot_upload_bytes import PicoSnapshotUploadBytes


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
        return PicoSnapshotUploadBytes(fixture,lambda:True,lambda:time.time_ns()//1000000,**kwargs)
    def selected(self):
        self.assertEqual(200,self.upload()[0]);return self.status()['requests'][-1]
    def patches(self):
        from contextlib import ExitStack
        stack=ExitStack();stack.enter_context(patch('feature_journeys.witness.build_opener',return_value=self.opener))
        stack.enter_context(patch('adapters.pico4.snapshot_upload_bytes.build_opener',return_value=self.opener));return stack
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

    def test_frozen_native_clock_cannot_hide_two_second_final_guard_or_metadata_copy(self):
        from adapters.pico4 import snapshot_upload_bytes as module
        row=self.selected();epoch=time.time_ns()//1000000
        for mode in ('guard','copy'):
            elapsed=[0.];reader=self.make_reader(monotonic=lambda:elapsed[0]);reader.clock_ms=lambda:epoch
            copy=module.deepcopy
            calls=[0]
            def late_guard():
                calls[0]+=1
                if calls[0]==2:elapsed[0]+=2
                return True
            if mode=='guard':reader.guard=late_guard
            def late(value):
                result=copy(value)
                if type(value) is dict and 'snapshotUploadOriginalVersion' in value:elapsed[0]+=2
                return result
            from contextlib import nullcontext
            with self.subTest(mode=mode),self.patches(),(patch.object(module,'deepcopy',side_effect=late) if mode=='copy' else nullcontext()),self.assertRaises(NativeUIError):reader.acquire(row['requestId'],row['ticket'])
            self.assertIsNone(reader.last)

    def test_last_source_clock_read_is_covered_by_the_final_monotonic_recheck(self):
        row=self.selected();epoch=time.time_ns()//1000000
        for component in ('bytes','provider'):
            elapsed=[0.];calls=[0];reader=self.make_reader(monotonic=lambda:elapsed[0])
            def late_clock():
                calls[0]+=1
                if calls[0]==3:elapsed[0]+=2
                return epoch
            if component=='bytes':reader.clock_ms=late_clock
            else:
                reader.fixture.epoch_ms=late_clock;reader.fixture.monotonic=lambda:elapsed[0]
            with self.subTest(component=component),self.patches(),self.assertRaises(NativeUIError):
                if component=='bytes':reader.acquire(row['requestId'],row['ticket'])
                else:reader.fixture.provider()
            self.assertEqual(3,calls[0])
            self.assertIsNone(reader.last if component=='bytes' else reader.fixture.previous_upload)

    def test_provider_final_copy_age_and_original_physical_history_are_preserved(self):
        from adapters.pico4 import snapshot_upload_fixture as module
        row=self.selected();elapsed=[0.];reader=self.make_reader(monotonic=lambda:elapsed[0]);fixture=reader.fixture;fixture.monotonic=lambda:elapsed[0]
        epoch=time.time_ns()//1000000;fixture.epoch_ms=lambda:epoch;copy=module.deepcopy
        def late(value):
            result=copy(value)
            if type(value) is dict and 'snapshotUploadServiceVersion' in value:elapsed[0]+=2
            return result
        with self.patches(),patch.object(module,'deepcopy',side_effect=late),self.assertRaises(NativeUIError):fixture.provider()
        self.assertIsNone(fixture.previous_upload)
        with self.patches():before=reader.fixture.provider()
        for mode in ('ctimeNs','uid','gid','mode','links','mtimeNs'):
            changed=deepcopy(before);changed['requestId']=secrets.token_hex(16);changed['requests'][0]['body']['physical'][mode]+=1
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):module.validate(changed,self.run,changed['requestId'],changed['capturedEpochMs'],previous=before)
        changed=deepcopy(before);changed['snapshotUploadServiceVersion']=1
        with self.assertRaises(NativeUIError):module.validate(changed,self.run,changed['requestId'],changed['capturedEpochMs'])


# Native file/transport signals below are deliberately synthetic DTO boundaries.
# The separate original Qt harness owns actual native collector bodies. These
# tests only qualify joins against independently received actual TLS wire bytes.
from self_tests.test_pico_snapshot_upload_source import packet
from adapters.pico4.snapshot_upload_fixture import join
from adapters.pico4.snapshot_upload_source import require_retired
JOB='1'*32;PATH='/data/user/0/org.overte.pico/files/Snapshots/original.png'

def native(provider):
    records=[row for row in provider['requests'] if row['method']=='POST']
    image=fixtures.png();requests=[]
    for index,row in enumerate(records):
        response=row['response'];stage='image' if row['target'].endswith('/snapshots') else 'story'
        requests.append(dict(id=str(index+3)*32,stage=stage,url=provider['origin']+row['target'],operation=4,authRequired=True,authorizationPresent=True,multipart=stage=='image',boundary='owned-qt-boundary' if stage=='image' else '',jsonBytes=row['body']['bytes'] if stage=='story' else 0,jsonSha256=row['body']['sha256'] if stage=='story' else hashlib.sha256(b'').hexdigest(),dispatchCurrent=True,sentBytes=row['body']['bytes'],totalBytes=row['body']['bytes'],finished=True,destroyed=True,status=response['status'],networkError=0 if response['status']==200 else 2,responseId=response['responseId'] or '',replyBytes=response['body']['bytes'],replySha256=response['body']['sha256'],replyBase64=response['bodyBase64']))
    epoch=provider['capturedEpochMs'];events=[dict(sequence=index+1,jobId=JOB,kind=kind,capturedEpochMs=epoch) for index,kind in enumerate(('begin','file-open','multipart-created','terminal','uploader-destroyed','file-destroyed','multipart-destroyed'))]
    return dict(snapshotUploadObservationVersion=2,instance='9'*32,complete=True,capturedEpochMs=epoch,sequence=len(events),events=events,jobs=[dict(id=JOB,path=PATH,href='hifi://owned/1,2,3',uploaderAlive=False,fileAlive=False,multipartAlive=False,file=dict(packet(dict(commandId='a'*32,runId=provider['runId']))['source']['jobs'][0]['file'],bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),readBytes=len(image),readSha256=hashlib.sha256(image).hexdigest()),cancelRequested=False,terminal='success' if len(requests)==2 else 'error',requests=requests)])


class SnapshotUploadJoinTests(unittest.TestCase):
    setUpClass=SnapshotUploadBytesTests.__dict__['setUpClass']
    tearDownClass=SnapshotUploadBytesTests.__dict__['tearDownClass']
    setUp=SnapshotUploadBytesTests.setUp
    stop=SnapshotUploadBytesTests.stop
    request=SnapshotUploadBytesTests.request
    activate=SnapshotUploadBytesTests.activate
    upload=SnapshotUploadBytesTests.upload
    status=SnapshotUploadBytesTests.status
    # Restrict this class to join cases; inherited byte cases stay in their
    # original owning class without duplicate catalog execution.
    def complete(self):
        from urllib.parse import urlencode
        query=urlencode(dict(now='2026-10-22T12:00:00Z',include_actions='concurrency',domain_id=fixtures.DOMAIN,restriction='open,hifi'))
        self.request('/api/v1/user_stories?'+query)
        image=self.upload()[1]['data'];fixtures.SnapshotUploadServiceTests.story(self,image);provider=self.status();return native(provider),provider
    def joined(self,value,provider,success=True):
        return join(value,provider,JOB,ticket=fixtures.TICKET,image_bytes=len(fixtures.png()),image_sha256=hashlib.sha256(fixtures.png()).hexdigest(),path=PATH,success=success)
    def test_explicit_native_boundary_joins_actual_image_story_and_domain_wire_originals(self):
        observed,provider=self.complete();proof=self.joined(observed,provider)
        self.assertIsInstance(proof['storyId'],int);self.assertEqual(2,len(proof['requests']));require_retired(observed)
        story='/api/v1/user_stories/'+str(proof['storyId'])
        self.assertEqual(200,self.request(story,token=self.token,method='DELETE')[0])
        live=self.status();self.assertEqual(0,live['stories']);self.assertEqual(1,live['uploads'])
        # Direct HTTP DELETE is a fixture seam, not a normal Pico control proof.
        self.service.retire(self.run);self.assertFalse(self.status()['active']);self.assertEqual([],list(self.root.iterdir()))
    def test_borrowed_response_consumed_file_domain_or_retained_native_owner_is_red(self):
        observed,provider=self.complete()
        for fault in ('response','file','domain','cancelled','alive'):
            changed=deepcopy(observed);backend=deepcopy(provider)
            if fault=='response':changed['jobs'][0]['requests'][0]['responseId']='f'*32
            elif fault=='file':changed['jobs'][0]['file']['readSha256']='0'*64
            elif fault=='domain':backend['requests']=backend['requests'][1:]
            elif fault=='cancelled':changed['jobs'][0]['cancelRequested']=True
            else:changed['jobs'][0]['uploaderAlive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                if fault=='alive':require_retired(changed)
                else:self.joined(changed,backend)
    def test_actual_offline_disconnect_joins_only_error_without_retrying_upload(self):
        self.service.control(self.run,'offline')
        with self.assertRaises(Exception):self.upload()
        provider=self.status();observed=native(provider);self.assertTrue(self.joined(observed,provider,False)['offline'])
        self.assertEqual(1,len(provider['requests']))
        with self.assertRaises(NativeUIError):self.joined(observed,provider)


if __name__=='__main__':unittest.main()
