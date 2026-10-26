"""Durable backend owner with real original segments and modeled input/PID.

The ordinary upload object is a typed boundary model in this focused selection;
actual mapping QML and candidate composition require their separate whole flow.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.asset_backend_client import AssetsBackendClient
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_session_owners import inspect_directory
from asset_backend_evidence_fixture import Fixture


class AssetsBackendOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.addCleanup(self.f.close);self.path=self.f.b.root/'ios';self.path.mkdir(mode=0o700);self.lock=ScriptSourceLock(self.path/'source.lock')
        self.scope=self.lock.held();self.scope.__enter__();self.addCleanup(self.scope.__exit__,None,None,None)
        self.upload=object.__new__(OwnedAssetsUpload);self.upload.files=SimpleNamespace(run=self.f.host.run,url='http://127.0.0.1:43210/feature-fixture/v1',state=None)
        self.upload.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-existing-session',generation=1,targetFingerprint='c'*64)
        self.upload.role='primary';self.upload.monotonic=time.monotonic;self.upload.sleep=time.sleep;self.upload.guard=lambda:True;self.upload.state=None
        self.store=PrivateFeatureState(self.path/('ios-assets-'+self.f.host.run+'-primary-backend.json'));self.queries=[];self.lost=False
        self.opener=patch('adapters.asset_backend_client.build_opener',return_value=self);self.opener.start();self.addCleanup(self.opener.stop);self.owner=self.create()
    def create(self):
        client=AssetsBackendClient(self.f.config,lambda:True);return OwnedAssetsBackend(self.upload,client,self.store,lock=self.lock)
    def open(self,request,timeout):
        query=json.loads(request.data);self.queries.append(deepcopy(query));native=dict(schemaVersion=1,action='feature-assets-backend-observe',commandId=query['commandId'],runId=query['runId'],ticket=query['ticket'],processId=123,instance=self.f.host.admission['instance'])
        if query['operation']=='observe':self.f.host.transport.send(native);self.f.host.publish();self.f.host.transport.poll()
        original=self.f.host.transport.export(query['commandId'])
        if self.lost:self.lost=False;raise OSError('modeled lost reader response')
        raw=json.dumps(dict(assetsBackendControlVersion=1,requestId=query['commandId'],runId=query['runId'],ticket=query['ticket'],status='original',original=original)).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_args):pass
            def read(self,limit):return raw[:limit]
        return Response()
    def attach(self):
        self.owner.admit('d'*32);self.upload.files.state=dict(token='f'*64)
        self.upload.state=dict(phase='ready',page='11111111-1111-4111-8111-111111111111',picker='22222222-2222-4222-8222-222222222222',destination='/e2e-'+self.f.host.run+'/',readback=None,aborted=False);self.owner.attach()
    def uploaded(self):
        path,digest,_=self.f.baked(holders=False);raw=(self.f.b.files/digest).read_bytes();self.upload.state.update(phase='uploaded',readback=dict(binding=dict(server=self.f.b.server,domainId=self.f.b.domain,serverInstance='1'*32),
            mappings=[dict(path=path,hash=digest,status=4,bakingErrors='')],files=[dict(hash=digest,body=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))]))
        self.owner.sample('uploaded','d'*32);self.owner.uploaded('uploaded');return path,digest
    def test_durable_originals_join_upload_then_exact_restoration_and_independent_quiet(self):
        self.attach();self.uploaded();self.f.restore();self.upload.state['phase']='retired';self.owner.sample('quiet-first','d'*32);self.f.advance();self.owner.sample('quiet-last','d'*32)
        proof=self.owner.restore('quiet-first','quiet-last');self.assertIsNotNone(proof);self.assertEqual('restored',self.owner.state['phase']);self.assertEqual('restored',self.create().state['phase'])
        self.assertEqual(4,len(self.queries));self.assertNotIn(self.f.config['token'],self.store.path.read_text());self.assertTrue(list(self.path.glob('assets-backend-primary-parts-frame-*')))
    def test_lost_response_keeps_intent_and_recovers_without_new_native_query(self):
        self.owner.reserve();self.lost=True
        with self.assertRaises(OSError):self.owner.admit('d'*32)
        self.assertEqual(1,len(self.queries));self.owner=self.create();self.assertIsNotNone(self.owner.admit('d'*32));self.assertEqual(['observe','poll'],[q['operation'] for q in self.queries]);self.assertEqual(1,len(self.f.host.published))
    def test_fresh_baseline_is_acquired_after_busy_original_instead_of_retiming_it(self):
        path,digest,task=self.f.baked();self.assertIsNone(self.owner.admit('d'*32));self.assertEqual('reserved',self.owner.state['phase'])
        task.expire('lease','owner','object');self.f.restore();self.assertIsNotNone(self.owner.admit('d'*32));self.assertEqual(2,len(self.queries));self.assertEqual(2,self.owner.state['baseline'])
    def test_changed_file_owner_or_page_cannot_adopt_the_existing_server_successor(self):
        self.attach();self.upload.files.state['token']='e'*64
        with self.assertRaises(NativeUIError):self.create()
        self.upload.files.state['token']='f'*64;self.upload.state['page']='33333333-3333-4333-8333-333333333333'
        with self.assertRaises(NativeUIError):self.create()
    def test_replacing_an_original_segment_inode_cannot_reuse_its_valid_bytes(self):
        self.owner.admit('d'*32);path=next(self.path.glob('assets-backend-primary-parts-frame-*'));raw=path.read_bytes();path.rename(self.path/'old-retained-original');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.create()
    def test_partial_opened_original_retains_uncertain_ownership_without_resend(self):
        self.owner.reserve();original=self.owner.parts.intent
        def fail(value):
            result=original(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='opened':raise OSError('modeled evidence write interruption')
            return result
        with patch.object(self.owner.parts,'intent',side_effect=fail),self.assertRaises(OSError):self.owner.admit('d'*32)
        self.owner=self.create();self.assertEqual('reserved',self.owner.state['phase']);self.assertFalse(self.owner.state['samples'][0]['parts']['complete'])
        count=len(self.queries)
        with self.assertRaises(NativeUIError):self.owner.recover(self.owner.state['samples'][0]['slot'])
        self.assertEqual(count,len(self.queries))
        observed=inspect_directory(self.path);self.assertEqual(['server-retirement'],observed[0]['responsibilities']);self.assertFalse(observed[0]['successor'])
    def test_mapping_restoration_with_a_live_original_body_cannot_retire_server(self):
        self.attach();path,digest,task=self.f.baked(returned=False,holders=False);self.f.restore();self.upload.state.update(phase='retired',aborted=True)
        self.owner.sample('quiet-first','d'*32);self.f.advance();self.owner.sample('quiet-last','d'*32);self.assertIsNone(self.owner.restore('quiet-first','quiet-last'));self.assertEqual('attached',self.owner.state['phase'])
    def test_original_open_or_journal_failure_cannot_be_followed_by_reader_delivery(self):
        self.owner.reserve()
        with patch.object(self.store,'write',side_effect=OSError('modeled denied journal')),self.assertRaises(OSError):self.owner.sample('baseline-1','d'*32)
        self.assertEqual([],self.queries)

    def test_historical_backend_admission_inspection_only_retains_responsibility(self):
        self.owner.admit('d'*32);before=len(self.queries);rows=inspect_directory(self.path)
        self.assertEqual(['server-retirement'],rows[0]['responsibilities']);self.assertFalse(rows[0]['successor']);self.assertEqual(before,len(self.queries))
