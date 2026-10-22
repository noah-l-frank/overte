"""Hard counterexamples for actual original ownership, byte and bake joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import sys
import unittest
import json
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_assets_backend import PhoneAssetsBackend,baseline,responsibility,owned_inventory,bake,reader_chain,sha
from overte_phone_assets_fixture import documents
from overte_phone_assets_measurements import model
from test_assets_source import DOMAIN,RUN
from test_assets_uploads import EPOCH


def packet(rows):return dict(source=dict(phoneAssetsObservationVersion=2,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,canWrite=True,complete=True,mappings=sorted(rows,key=lambda row:row['path'])))
def row(path,digest,status=0):return dict(path=path,hash=digest,bakeStatus=status,bakeError='')
def body(data):return dict(source=dict(phoneAssetsDownloadVersion=2,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,hash=sha(data),bytes=len(data),base64=base64.b64encode(data).decode(),loadedFromCache=False))
def backend(rows=(),blobs=(),jobs=()):
    return dict(source=dict(assetsBakeOriginalsVersion=2,instance='b'*32,sequence=1,processId=321,processStart='123',domainId=DOMAIN,assetServerId=DOMAIN,capturedEpochMs=EPOCH,contextCapturedEpochMs=EPOCH,valid=True,
        jobs=list(jobs),mappings=[dict(path=item['path'],hash=item['hash']) for item in rows],blobs=[dict(hash=sha(data),actualSha256=sha(data),bytes=len(data)) for data in blobs],pending=sum(job['terminalEpochMs'] is None for job in jobs)))
def resolution(path,digest,redirect=''):return dict(source=dict(phoneAssetsResolveVersion=1,domainId=DOMAIN,sessionId=DOMAIN,assetServerId=DOMAIN,requestedPath=path,hash=digest,redirected=bool(redirect),redirectedPath=redirect))
def worker(digest,path):return dict(instance='c'*32,hash=digest,path=path,version=7,queuedEpochMs=EPOCH-10,startedEpochMs=EPOCH-9,runExitedEpochMs=EPOCH-5,ovenProcessId=999,
    ovenFinishedEpochMs=EPOCH-8,exitCode=0,exitStatus=0,terminalEpochMs=EPOCH-7,outcome='complete',destroyedEpochMs=EPOCH-6)

class AssetsBackendTests(unittest.TestCase):
    def test_fresh_http_receipt_cannot_retime_old_network_context_or_slow_source(self):
        value=dict(schemaVersion=1,runId=RUN,source=backend()['source']);elapsed=[0.]
        class Reply:
            status=200
            def geturl(self):return 'http://127.0.0.1:40123/v1/assets-originals'
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,_limit):return json.dumps(value).encode()
        def read(fault):
            source=PhoneAssetsBackend('http://127.0.0.1:40123/v1/assets-originals','p'*64,RUN,DOMAIN,lambda:True,lambda:EPOCH,monotonic=lambda:elapsed[0])
            def opened(*_args,**_kwargs):
                if fault=='slow':elapsed[0]=5.001
                return Reply()
            with patch('overte_phone_assets_backend.build_opener',return_value=SimpleNamespace(open=opened)):return source.read()
        self.assertEqual(value,read(None));value['source']['contextCapturedEpochMs']=EPOCH-1501
        with self.assertRaises(NativeUIError):read('stale')
        value['source']['contextCapturedEpochMs']=EPOCH
        with self.assertRaises(NativeUIError):read('slow')

    def test_initial_collision_and_unmapped_foreign_blob_fail_before_authority(self):
        for rows,blobs in (([row('/e2e-'+RUN+'/main.gltf','a'*64)],()),([row('/foreign/alias',sha(documents()['gltf-bundle/main.gltf']))],()),([], [b'foreign orphan'])):
            with self.subTest(rows=rows),self.assertRaises(NativeUIError):baseline(packet(rows),backend(rows,blobs),RUN)
    def test_outside_inventory_is_preserved_and_unclaimed_alias_is_red_even_with_owned_hash(self):
        before=baseline(packet([]),backend(),RUN);digest=sha(b'actual')
        claim=dict(uploads={'main.gltf':dict(returnedHash=digest)},published={'main.gltf':dict(path='/e2e-'+RUN+'/main.gltf',hash=digest)},currentPaths={'/e2e-'+RUN+'/main.gltf':digest})
        current=[row('/e2e-'+RUN+'/main.gltf',digest)]
        self.assertEqual(set(current[0]['path'] for _ in [0]),set(owned_inventory(packet(current),backend(current,[b'actual']),before,[claim],RUN)))
        for addition in (row('/renamed-'+RUN+'/main.gltf',digest),row('/foreign/alias',digest),row('/e2e-'+RUN+'/mesh/triangle.bin',digest)):
            rows=current+[addition]
            with self.subTest(addition=addition),self.assertRaises(NativeUIError):owned_inventory(packet(rows),backend(rows,[b'actual']),before,[claim],RUN)
        claim['currentPaths']={}
        with self.assertRaises(NativeUIError):owned_inventory(packet(current),backend(current,[b'actual']),before,[claim],RUN)
    def test_ready_bake_requires_successful_new_original_worker_meta_and_download(self):
        import json
        primary='/e2e-'+RUN+'/stand.fbx';original=sha(b'original');redirect='/.baked/'+original+'/stand.baked.fst';data=b'filename = stand.baked.fbx\n';digest=sha(data)
        meta=json.dumps(dict(bake_version=7,failed_last_bake=False,last_bake_errors='',redirect_target=redirect)).encode();meta_hash=sha(meta)
        rows=[row(primary,original,4),row(redirect,digest,4),row('/.baked/'+original+'/meta.json',meta_hash,4)]
        job=worker(original,primary);b=backend(rows,[data,meta],[job]);downloads={digest:body(data),meta_hash:body(meta)};r=resolution(primary,digest,redirect)
        self.assertEqual('ready',bake(primary,packet(rows),b,r,downloads))
        for change in ('old-worker','missing-worker','missing-output','failed-worker','wrong-meta','active-worker'):
            bb=deepcopy(b);dd=deepcopy(downloads);barrier=None
            if change=='old-worker':barrier=dict(instance='b'*32,sequence=0,jobs=['c'*32],epochMs=EPOCH-20)
            elif change=='missing-worker':bb['source']['jobs']=[]
            elif change=='missing-output':dd.pop(digest)
            elif change=='failed-worker':bb['source']['jobs'][0]['outcome']='failed'
            elif change=='wrong-meta':bb['source']['jobs'][0]['version']=8
            else:bb['source']['jobs'][0]['runExitedEpochMs']=None
            with self.subTest(change=change),self.assertRaises((NativeUIError,KeyError)):bake(primary,packet(rows),bb,r,dd,barrier)
    def test_disabled_bake_needs_actual_nonredirect_original_and_no_running_worker(self):
        primary='/e2e-'+RUN+'/stand.fbx';digest=sha(b'original');path='/.baked/'+digest+'/asset.fbx';rows=[row(primary,digest,1),row(path,digest,4)]
        self.assertEqual('disabled',bake(primary,packet(rows),backend(rows),resolution(primary,digest),{}))
        with self.assertRaises(NativeUIError):bake(primary,packet(rows),backend(rows),resolution(primary,digest,path),{})
    def test_actual_fst_chain_can_only_reach_readable_current_owned_output(self):
        primary='/e2e-'+RUN+'/stand.fbx';original=sha(b'original');fst='/.baked/'+original+'/stand.fst';geometry='/.baked/'+original+'/stand.baked.fbx'
        data=b'filename = stand.baked.fbx\n';mesh=b'explicit synthetic model input';rows=[row(primary,original,4),row(fst,sha(data),4),row(geometry,sha(mesh),4)]
        chain=reader_chain(primary,packet(rows),resolution(primary,sha(data),fst),{sha(data):body(data),sha(mesh):body(mesh)})
        self.assertEqual('atp:'+geometry,chain['url']);self.assertEqual(mesh,chain['body'])
        wrong=b'filename = ../../foreign.fbx\n';rows[1]['hash']=sha(wrong)
        with self.assertRaises(NativeUIError):reader_chain(primary,packet(rows),resolution(primary,sha(wrong),fst),{sha(wrong):body(wrong)})

if __name__=='__main__':unittest.main()
