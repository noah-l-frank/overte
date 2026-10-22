"""Private owner/preflight cleanup with original fixture owners and real journals.

Native/SDK transport is an explicit synthetic boundary. No public feature PASS
or physical device qualification is claimed by these narrow recovery tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.account_provider import AccountProvider
from feature_journeys.snapshot_upload_service import SnapshotUploadService
from feature_journeys.witness import Client,Journal
from feature_journeys.scenarios import VERSION
from overte_phone_snapshot_upload_fixture import SnapshotUploadFixtureReader
from overte_phone_snapshots_feature import PhoneSnapshotsFeature,configuration
from overte_phone_script_history import pack,unpack

BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:123',sessionId='own-session',generation=4,targetFingerprint='3'*64)
DOMAIN='12345678-1234-1234-1234-123456789012'


class OriginalClient(Client):
    def __init__(self,root):
        super().__init__('https://owned.invalid:443/feature-fixture/v1','r'*64)
        self.journal=Journal();self.run=self.journal.register('snapshots');self.accounts=AccountProvider()
        self.service=SnapshotUploadService(self.accounts,DOMAIN,root,'https://owned.invalid:443');self.service.provision(self.run)
    def request(self,path,value=None,method=None,**kwargs):
        if path=='/runs/'+self.run+'/phase':return self.journal.phase(self.run,kwargs['phase_nonce'])
        need(path=='/runs/'+self.run+'/snapshot-upload')
        return self.service.snapshot(self.run,kwargs['snapshot_upload_nonce'])
    def activate(self,verb):
        ticket=uuid.uuid4().hex;self.journal.activate(self.run,ticket,verb,{});self.service.activate(self.run,ticket,verb);return ticket
    def retire(self):self.service.retire(self.run);self.journal.close(self.run)


class Adapter:
    def __init__(self,root):self.root=root;self.foreign_ui_open=True;self.calls=[];self.alive=True;self.binding=deepcopy(BINDING)
    def state_path(self,_):return self.root/'session.json'
    def normal_feature_runtime(self,*_,**kwargs):return None,None,deepcopy(self.binding),lambda:True,dict(sha256='a'*64)
    def _snapshot_measurements(self,_):
        def fail(_run):self.calls.append('readonly-preflight');raise NativeUIError('Explicit unavailable initial source')
        return SimpleNamespace(read=fail)
    def _graphics_lifecycle_status(self,*_):return dict(binding=deepcopy(self.binding),foreground=True,running=self.alive,appState=4)
    @contextmanager
    def existing_input_session(self,_):yield


class SnapshotsFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='snapshots-feature-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);wire=self.root/'wire';wire.mkdir(mode=0o700)
        self.client=OriginalClient(wire);self.addCleanup(self.client.accounts.shutdown);self.run=self.client.run
        self.client.activate('baseline');self.phase=SnapshotUploadFixtureReader(self.client,self.run)
        self.adapter=Adapter(self.root)
        self.config=dict(snapshotsFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1280,720],markerRoi=[0,0,160,40],
            imagePolicy=dict(source='world-render-target',marker=[4,4,132,36],subject=[200,100,500,400]),
            fileImagePolicy=dict(source='world-render-target',marker=[4,4,132,36],subject=[200,100,500,400]),domainId=DOMAIN,receiverApkSha256='a'*64)
    def feature(self):return PhoneSnapshotsFeature(self.adapter,'synthetic',self.phase,self.config)
    def failed_preflight(self):
        f=self.feature()
        with f.lock.held():
            f.load()
            with self.assertRaises(NativeUIError):f.initialize()
        return f
    def call(self):return dict(contractVersion=VERSION,runId=self.run)
    def test_failed_first_original_read_retains_owner_but_cleans_no_foreign_ui_or_unissued_scope(self):
        f=self.failed_preflight();header=f.store.read();self.assertEqual('preparing',unpack(header['payload'])[0]['phase'])
        self.client.activate('cleanup');self.assertEqual({'performed':True},f.cleanup(self.call()))
        self.assertTrue(self.adapter.foreign_ui_open);self.assertEqual(['readonly-preflight'],self.adapter.calls)
        self.assertEqual('partial-cleaned',f.state['phase']);self.assertEqual([],f.state['actions']);self.assertEqual([],f.state['inputs'])
        self.assertEqual('no-issued-lease',f.partial_restored()['kind'])
        self.assertFalse(f.partial_restored()['provider']['requests'])
    def test_partial_cleanup_reconstructs_and_repeats_without_a_public_baseline_or_any_input(self):
        self.failed_preflight();self.client.activate('cleanup');f=self.feature();f.cleanup(self.call())
        another=self.feature();self.assertEqual({'performed':True},another.cleanup(self.call()))
        self.assertTrue(self.adapter.foreign_ui_open);self.assertEqual(['readonly-preflight'],self.adapter.calls)
    def test_partial_cannot_adopt_foreign_lease_or_changed_original_process(self):
        f=self.failed_preflight();self.client.activate('cleanup');f.cleanup(self.call())
        for fault in ('settings','files','process'):
            with self.subTest(fault=fault):
                original=deepcopy(f.state);binding=deepcopy(self.adapter.binding)
                if fault=='settings':f.state['settingsIntent']=dict(issued=True,requestedEpochMs=1)
                elif fault=='files':
                    state=PrivateFeatureState(f.store.path.with_name('phone-snapshots-files-owner.json'));state.write(dict(foreign=True),None)
                else:self.adapter.binding['processIdentity']='99:1'
                with self.assertRaises(NativeUIError):f.partial_restored()
                f.state=original;self.adapter.binding=binding
                if fault=='files':state.discard(state.read())
    def test_fixed_configuration_rejects_unknown_truth_fields_overlap_and_unowned_paths(self):
        configuration(self.config)
        for fault in ('expected','version','marker','domain','apk','file'):
            changed=deepcopy(self.config)
            if fault=='expected':changed['expectedSaved']=1
            elif fault=='version':changed['snapshotsFeatureVersion']=True
            elif fault=='marker':changed['imagePolicy']['subject']=changed['imagePolicy']['marker']
            elif fault=='domain':changed['domainId']='00000000-0000-0000-0000-000000000000'
            elif fault=='apk':changed['receiverApkSha256']='unknown'
            else:changed['fileImagePolicy']['source']='desired-pixels'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,RuntimeError)):configuration(changed)
    def test_changed_journal_configuration_cannot_reconstruct_even_before_native_input(self):
        f=self.failed_preflight();header=f.store.read();changed=deepcopy(header);changed['configuration']['receiverApkSha256']='b'*64
        f.store.write(changed,header)
        with self.assertRaises(NativeUIError):self.feature()

if __name__=='__main__':unittest.main()
