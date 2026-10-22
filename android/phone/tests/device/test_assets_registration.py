"""Default-off Assets facade and unchanged controlled load foundation.

Only the SDK/probe consumer is synthetic. The inherited Phone/shared dispatch,
common load module/session, actual loopback PNG GET/decode and server telemetry
run unchanged. This supplies no real client renderer/device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from urllib.request import urlopen
from PIL import Image
import test_account_fixture_launch
import test_feature_adapters as bound
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.scenarios import VERSION
from overte_phone_assets_feature import configuration
from script_observer import configuration as observer_configuration
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'tests/device/self_tests'))
from self_tests import test_asset_load as foundation_fixture
from self_tests.test_vertical_locomotion import snapshot

ROOT=Path(__file__).resolve().parents[4]

class AssetsRegistrationTests(unittest.TestCase):
    def setUp(self):
        setup=test_account_fixture_launch.AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);self.f=setup.f
        temp=tempfile.TemporaryDirectory(prefix='assets-registration-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.path=self.root/'configuration.json';self.access=self.root/'access.json'
        sha=lambda text:hashlib.sha256(text.encode()).hexdigest()
        self.config=dict(assetsFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],
            imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595]),domainId='12345678-1234-4234-8234-123456789abc',
            permissionsControlUrl='http://127.0.0.1:40123/v1/assets-permissions',permissionsControlToken='z'*64,
            originalsControlUrl='http://127.0.0.1:40123/v1/assets-originals',originalsReadToken='p'*64,
            originalsPrimaryTokenSha256=sha('p'*64),originalsActorTokenSha256=sha('q'*64))
        PrivateFeatureState(self.path).write(self.config,None)
        PrivateFeatureState(self.access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl='http://controlled.invalid/feature-fixture/v1',adapterToken='d'*64),None)
        self.env=dict(OVERTE_PHONE_FEATURE_ASSETS='1',OVERTE_PHONE_ASSETS_CONFIGURATION=str(self.path),
            OVERTE_E2E_FEATURE_FIXTURE_URL='http://controlled.invalid/feature-fixture/v1',OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(self.access))
    def test_only_complete_explicit_triple_and_existing_foundation_are_advertised(self):
        with patch.dict(os.environ,self.env):
            values=self.f.adapter.advertised_capabilities(self.f.target)
            self.assertEqual({'feature.assets.'+key for key in ('act','observe','cleanup')},{value for value in values if value.startswith('feature.assets.')})
            self.assertIn('asset.load',values)
    def test_default_off_bad_flag_missing_private_config_or_unbound_debug_candidate_fail_closed(self):
        with patch.dict(os.environ,self.env|dict(OVERTE_PHONE_FEATURE_ASSETS='0')),patch.object(self.f.adapter,'_assets_feature') as owner:
            self.assertFalse(any(value.startswith('feature.assets.') for value in self.f.adapter.advertised_capabilities(self.f.target)))
            with self.assertRaisesRegex(ValueError,'NOT_ENABLED'):self.f.adapter.invoke(bound.SELECTOR,'feature.assets.observe',dict(contractVersion=VERSION,runId='a'*32,afterSequence=0))
            owner.assert_not_called()
        for change in (dict(OVERTE_PHONE_FEATURE_ASSETS=''),dict(OVERTE_PHONE_ASSETS_CONFIGURATION=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG='')):
            with self.subTest(change=change),patch.dict(os.environ,self.env|change),self.assertRaises((ValueError,RuntimeError)):self.f.adapter.advertised_capabilities(self.f.target)
        with patch.dict(os.environ,self.env),patch.object(self.f.adapter,'candidate',None),self.assertRaises(ValueError):self.f.adapter.advertised_capabilities(self.f.target)
    def test_expected_facts_writer_token_reuse_and_actor_primary_reader_reuse_are_rejected(self):
        for change in (dict(expectedMappings=[]),dict(assetsFeatureVersion=True),dict(originalsReadToken='z'*64),dict(originalsActorTokenSha256=self.config['originalsPrimaryTokenSha256'])):
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):configuration(self.config|change)
        actor={key:item for key,item in self.config.items() if key!='permissionsControlToken'};actor['permissionsTokenSha256']=hashlib.sha256(('z'*64).encode()).hexdigest()
        with self.assertRaises((ValueError,RuntimeError)):configuration(actor,actor=True)
        actor['originalsReadToken']='q'*64;self.assertEqual(actor,configuration(actor,actor=True))
    def test_retirement_factory_keeps_original_policy_and_needs_only_original_read_token(self):
        from feature_journeys.witness import Client
        public={key:deepcopy(value) for key,value in self.config.items() if key not in ('permissionsControlToken','originalsReadToken')}
        public['permissionsTokenSha256']=hashlib.sha256(('z'*64).encode()).hexdigest();run='a'*32
        with patch.dict(os.environ,self.env):
            store=self.f.adapter.assets_feature_store(bound.SELECTOR)
            store.write(dict(runId=run,fixtureUrl='http://controlled.invalid/feature-fixture/v1/runs/'+run+'/',configuration=public),None)
            # The writer secret and replacement policy are deliberately absent
            # from the input adopted by the retirement-only constructor.
            source=PrivateFeatureState(self.path);source.write(dict(artifactRoot='/foreign',imageExtent=[1,1],originalsReadToken='p'*64),source.read())
            feature=self.f.adapter._assets_feature(bound.SELECTOR,run,retirement=True)
            self.assertEqual(public,feature.public_configuration());self.assertNotIn('permissionsControlToken',feature.config)
            source.write(dict(originalsReadToken='q'*64),source.read())
            with self.assertRaises((ValueError,RuntimeError)):self.f.adapter._assets_feature(bound.SELECTOR,run,retirement=True)

    def test_assets_actor_uses_v5_without_writer_or_primary_reader_credentials(self):
        value=dict(featureObserverVersion=5,area='assets',target='synthetic',candidateArguments=['--record','private'],fixtureUrl='http://controlled.invalid/feature-fixture/v1',actorToken='a'*64,durationSeconds=120)
        store=PrivateFeatureState(self.root/'actor.json');store.write(value,None);self.assertEqual(value,observer_configuration(store.path))
        for change in (dict(featureObserverVersion=4),dict(originalsReadToken='p'*64),dict(permissionsControlToken='z'*64)):
            store.write(value|change,store.read())
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):observer_configuration(store.path)

class AssetsFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):foundation_fixture.AssetLoadTest.setUpClass();cls.metadata=foundation_fixture.AssetLoadTest.metadata
    @classmethod
    def tearDownClass(cls):foundation_fixture.AssetLoadTest.tearDownClass()
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='assets-foundation-env-');self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(ROOT/'tests/device/adapters/android/phone.json'),OVERTE_DEVICE_TARGET_SELECTOR='synthetic',OVERTE_DEVICE_ARTIFACT_DIR=temp.name))
        env.start();self.addCleanup(env.stop)
    def run_foundation(self,fault=None):
        setup=test_account_fixture_launch.AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);adapter=setup.f.adapter
        temp=tempfile.TemporaryDirectory(prefix='assets-foundation-');self.addCleanup(temp.cleanup);root=Path(temp.name);asset=self.metadata['asset'];request=uuid.uuid4().hex
        env=dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(ROOT/'tests/device/adapters/android/phone.json'),OVERTE_DEVICE_TARGET_SELECTOR='synthetic',OVERTE_DEVICE_ARTIFACT_DIR=str(root),
            OVERTE_E2E_TIMEOUT_SECONDS='1',OVERTE_E2E_POLL_SECONDS='.05',OVERTE_E2E_ASSET_REQUEST_ID=request,OVERTE_E2E_ASSET_ID=asset['id'],OVERTE_E2E_ASSET_URL=asset['url'],
            OVERTE_E2E_ASSET_TELEMETRY_URL=asset['telemetryUrl'],OVERTE_E2E_ASSET_CONTENT_TYPE=asset['contentType'],OVERTE_E2E_ASSET_SHA256=asset['sha256'],
            OVERTE_E2E_ASSET_BYTES=str(asset['bytes']),OVERTE_E2E_ASSET_WIDTH=str(asset['width']),OVERTE_E2E_ASSET_HEIGHT=str(asset['height']),OVERTE_E2E_ASSET_ENTITY_NAME=asset['entityName'])
        observed=[None];commands=[];sequence=[0]
        def consume(_client,_session,_target,command):
            commands.append(deepcopy(command));self.assertEqual('load-asset',command['action'])
            if fault=='ack-only':return
            if fault=='no-http':width,height=asset['width'],asset['height']
            else:
                with urlopen(command['url'],timeout=2) as reply:body=reply.read()
                with Image.open(io.BytesIO(body)) as image:image.load();width,height=image.size
            observed[0]=dict(assetId=command['assetId'],resource=dict(url=command['url'],state='finished'),entity=dict(id='independent-consumer-image',name=command['entityName'],type='Image',imageURL=command['url'],
                naturalDimensions=dict(x=1.0 if width>=height else width/height,y=height/width if width>=height else 1.0,z=.01)))
            if fault=='wrong-dimensions':observed[0]['entity']['naturalDimensions']['x']=.1
        def operation(name,arguments):
            if name=='asset.load':return adapter.invoke(bound.SELECTOR,name,arguments)
            self.assertEqual('probe.snapshot',name);sequence[0]+=1;value=snapshot();value.update(sampleSequence=sequence[0],sampleEpochMs=time.time_ns()//1000000,asset=deepcopy(observed[0]));return value
        with patch.dict(os.environ,env):
            import module_support
            import overte_session
            namespace={'__name__':'assets_foundation_contract'}
            with patch.object(module_support,'module_main',lambda _main:None):exec(compile((ROOT/'tests/device/modules/asset_load.py').read_text(),'asset_load.py','exec'),namespace)
            with patch.object(adapter,'write_android_client_command',side_effect=consume),patch.object(overte_session,'operation',side_effect=operation),patch.object(overte_session,'assert_process'),patch.object(overte_session,'assert_foreground'),patch.object(module_support,'ARTIFACT_DIR',root):
                namespace['process_identity']=lambda:'actual-host-contract-process';namespace['assert_process']=lambda *_:None;namespace['assert_foreground']=lambda *_:None
                namespace['main']()
        self.assertEqual(1,len(commands));self.assertTrue((root/'asset-ready.json').is_file());self.assertTrue((root/'asset-delivery.json').is_file())
    def test_inherited_phone_dispatch_full_common_foundation_fetch_decode_probe_and_telemetry(self):self.run_foundation()
    def test_ack_only_fabricated_ready_without_http_and_wrong_dimensions_are_red(self):
        from module_support import AssertionFailure
        for fault in ('ack-only','no-http','wrong-dimensions'):
            with self.subTest(fault=fault),self.assertRaises(AssertionFailure):self.run_foundation(fault)

if __name__=='__main__':unittest.main()
