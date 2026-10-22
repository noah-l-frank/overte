"""Real Assets facade with explicit synthetic target endpoints and actual files.

Common actions/HTTP witness and separate original actor run unchanged. This is
host composition, not real server/oven/renderer/device acceptance or latency.
Evidence uses an own tmpfs directory to exercise unchanged real fsync/inode/file
operations without measuring the workstation disk's per-fsync latency. Separate
native filesystem counterexamples also execute on the ordinary build filesystem.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from assets_feature_target import Target,Proxy,Handler,POLICY,RUN,DOMAIN,ROOT,sha
import test_assets_files as native_files
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION
from overte_phone_assets_feature import PhoneAssetsFeature
from overte_phone_assets_role import PhoneAssetsRole
from overte_phone_script_history import unpack,pack

ACTOR=r'''
import json,sys,time
from pathlib import Path
sys.path[:0]=json.loads(sys.argv[1])
from assets_feature_target import Proxy,RUN
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_assets_feature import PhoneAssetsFeature
from overte_phone_assets_actor import PhoneAssetsActor
from overte_phone_script_lock import PhoneScriptSourceBusy
config=PrivateFeatureState(Path(sys.argv[2])).read();adapter=Proxy(config['targetUrl'],config['root'])
client=Client(config['fixtureUrl'],config['actorToken'])
flow=PhoneAssetsActor(PhoneAssetsFeature(adapter,'synthetic',PhaseFixtureReader(client,RUN,'assets',epoch_ms=adapter.clock_ms),config['configuration'],role='actor'))
started=time.monotonic()
while time.monotonic()-started<config['durationSeconds']:
    try:
        if flow.step():sys.exit(0)
    except PhoneScriptSourceBusy:pass
    except Exception as error:
        import traceback
        context=error.__context__
        while context is not None:
            traceback.print_exception(type(context),context,context.__traceback__,chain=False);context=context.__context__
        raise
    time.sleep(.25)
raise RuntimeError('Synthetic actor lifetime exceeded')
'''

class AssetsHarness:
    @classmethod
    def setUpClass(cls):native_files.AssetsFilesTests.setUpClass();cls.executable=native_files.AssetsFilesTests.executable
    @classmethod
    def tearDownClass(cls):native_files.AssetsFilesTests.tearDownClass()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='assets-facade-',dir='/dev/shm');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        native_root=self.root/'native-inputs';native_root.mkdir(mode=0o700)
        self.files=native_files.NativeFiles(self.executable,native_root);self.addCleanup(self.files.close);self.target=Target(self.root,self.files);self.addCleanup(self.target.close)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.target=self.target;self.server.errors=[]
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def close_target():self.server.shutdown();self.server.server_close();thread.join(2)
        self.addCleanup(close_target);self.url='http://127.0.0.1:'+str(self.server.server_port);self.adapter=Proxy(self.url,self.root)
        self.fixture=make_server('r'*64,'a'*64,adapter_token='b'*64);self.fixture.journal.clock=self.adapter.clock_ms
        thread2=threading.Thread(target=self.fixture.serve_forever,daemon=True);thread2.start()
        def close_fixture():self.fixture.shutdown();self.fixture.server_close();thread2.join(2)
        self.addCleanup(close_fixture);self.base='http://127.0.0.1:'+str(self.fixture.server_port)+'/feature-fixture/v1';self.client=Client(self.base,'r'*64)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):_run,self.fixture_url=self.client.register('assets')
        self.target.fixture=self.fixture_url
        self.config=dict(assetsFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],imagePolicy=POLICY,domainId=DOMAIN,
            permissionsControlUrl=self.url+'/v1/assets-permissions',permissionsControlToken='z'*64,originalsControlUrl=self.url+'/v1/assets-originals',originalsReadToken='p'*64,
            originalsPrimaryTokenSha256=sha('p'*64),originalsActorTokenSha256=sha('q'*64));self.actor=None
    def feature(self):
        feature=PhoneAssetsFeature(self.adapter,'synthetic',PhaseFixtureReader(Client(self.base,'b'*64),RUN,'assets',epoch_ms=self.adapter.clock_ms),self.config)
        return feature
    def call(self,verb,inputs=None):
        ticket=os.urandom(16).hex();inputs={} if inputs is None else inputs;self.client.activate(ticket,verb,inputs);self.target.ticket=ticket
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs)
    def observe(self,after=0):return self.feature().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=after))
    def start_actor(self):
        path=self.root/'assets-actor-test-configuration.json';config=self.feature().public_configuration();config['originalsReadToken']='q'*64
        PrivateFeatureState(path).write(dict(targetUrl=self.url,root=str(self.root),fixtureUrl=self.base,actorToken='a'*64,configuration=config,durationSeconds=next(row['timeoutSeconds'] for row in json.loads((ROOT/'tests/device/catalog.json').read_text())['modules'] if row['id']=='feature-assets')),None)
        self.actor=subprocess.Popen([sys.executable,'-c',ACTOR,json.dumps(sys.path),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def close():
            if self.actor.poll() is None:self.actor.terminate()
            self.actor.communicate(timeout=5)
        self.addCleanup(close)
    def actor_ok(self):
        if self.actor is not None and self.actor.poll() is not None:
            out,err=self.actor.communicate();self.fail('Synthetic Assets actor stopped: '+str(self.actor.returncode)+' '+err[-6000:])

class AssetsFeatureTests(AssetsHarness,unittest.TestCase):
    def test_baseline_reads_fresh_actual_sources_without_staging_or_inputs(self):
        self.call('baseline');a=self.observe();b=self.observe(a['sequence']);self.assertEqual([],b['resources']);self.assertEqual([],self.target.inputs)
        self.assertEqual(2,b['sequence']);self.assertLess(a['capturedEpochMs'],b['capturedEpochMs']);self.assertFalse(list(self.files.directory.glob('feature-assets-*')))
    def test_open_picker_cancel_and_upload_use_actual_files_and_retired_generations(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'))
        self.feature().act(self.call('upload-picker-open',dict(resource='gltf-bundle/main.gltf')));self.assertTrue(self.observe()['state']['stagedAvailable'])
        self.feature().act(self.call('upload-picker-cancel'));self.assertFalse(self.observe()['state']['stagedAvailable']);self.assertFalse(list(self.files.directory.glob('feature-assets-*')))
        self.feature().act(self.call('upload',dict(resource='gltf-bundle/main.gltf')));measured=self.observe()['state']
        self.assertEqual(3,len(measured['mappings']));self.assertEqual('unsupported',measured['bakeState']);self.assertFalse(list(self.files.directory.glob('feature-assets-*')))

    def test_mutable_claim_and_baseline_cannot_authorize_foreign_deletion(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'));self.feature().act(self.call('upload',dict(resource='gltf-bundle/main.gltf')))
        store=PrivateFeatureState(self.root/'phone-assets-feature.json');original=store.read();state=unpack(original['payload'])[0];before=len(self.target.inputs)
        for kind in ('baseline','claim','omitted-stage'):
            changed=deepcopy(state)
            if kind=='baseline':changed['backendOriginal']['connection']['domainId']='ffffffff-ffff-4fff-8fff-ffffffffffff'
            elif kind=='claim':changed['claims'][0]['currentPaths']['/foreign/model.fbx']='a'*64
            else:changed.update(stages=[],stageTickets={})
            bad=dict(original,payload=pack([changed]));store.write(bad,store.read())
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):self.observe()
            self.assertEqual(before,len(self.target.inputs));store.write(original,bad)
        self.assertEqual(3,len(self.observe()['state']['mappings']))

    def test_saved_original_before_manifest_is_recovered_without_reissuing_input(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'));before=len(self.target.inputs)
        original=PhoneAssetsRole.storage_intent;failed=[False]
        def stop(role,kind,value):
            result=original(role,kind,value)
            if kind=='original' and value['phase']=='saved' and not failed[0]:failed[0]=True;raise RuntimeError('Synthetic saved-frame boundary')
            return result
        with patch.object(PhoneAssetsRole,'storage_intent',stop):
            with self.assertRaises(NativeUIError):self.observe()
        self.assertTrue(failed[0]);measured=self.observe();self.assertTrue(measured['state']['open']);self.assertEqual(before,len(self.target.inputs))

    def test_interrupted_actual_rename_receipt_resumes_cleanup_and_missing_actor_cannot_finalize(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'));self.feature().act(self.call('upload',dict(resource='gltf-bundle/main.gltf')))
        original=PhoneAssetsFeature.archive_input;failed=[False]
        def stop(feature,frame):
            result=original(feature,frame)
            if 'renameResponsibility' in frame and not failed[0]:failed[0]=True;raise RuntimeError('Synthetic completed rename archive boundary')
            return result
        with patch.object(PhoneAssetsFeature,'archive_input',stop):
            with self.assertRaises(NativeUIError):self.feature().act(self.call('rename-folder',dict(name='renamed-'+RUN)))
        self.assertTrue(failed[0]);self.assertTrue(all(path.startswith('/renamed-'+RUN+'/') for path in self.target.mappings))
        self.call('cleanup');call=dict(contractVersion=VERSION,runId=RUN)
        self.assertEqual({'performed':True},self.feature().cleanup(call));self.assertEqual({'performed':True},self.feature().cleanup(call))
        self.assertEqual([],self.observe()['resources']);self.assertEqual({},self.target.mappings);self.assertFalse(list(self.files.directory.glob('feature-assets-*')))
        self.client.close()
        with self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertIsNotNone(PrivateFeatureState(self.root/'phone-assets-feature.json').read())

    def test_old_reader_texture_bytes_and_wrong_model_url_are_red_despite_fresh_png(self):
        self.call('baseline');self.observe();self.feature().act(self.call('open'));self.feature().act(self.call('upload',dict(resource='gltf-bundle/main.gltf')))
        self.feature().act(self.call('import-selected'));self.assertTrue(self.observe()['state']['sceneModel']);row=deepcopy(self.target.rows[0])
        for fault in ('reader','texture','url'):
            changed=deepcopy(row)
            if fault=='reader':changed['render']['geometry']['reader']['originalSha256']='f'*64
            elif fault=='texture':changed['render']['geometry']['textures']['rows'][0]['originalSha256']='f'*64
            else:changed['modelUrl']='atp:/foreign/main.gltf'
            self.target.rows[0]=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.observe()
            self.target.rows[0]=deepcopy(row)
        self.assertTrue(self.observe()['state']['sceneModel'])


class AssetsFeatureJourneyTests(AssetsHarness,unittest.TestCase):
    def test_complete_common_journey_independent_actor_and_actual_final_retirement(self):
        reports=[];initialized=[False];last=['baseline'];timings=[]
        def invoke(operation,fields):
            if operation.endswith('.act'):last[0]=fields['verb']
            started=time.monotonic();value=getattr(self.feature(),operation.rsplit('.',1)[1])(fields);timings.append((operation,last[0],round(time.monotonic()-started,3)))
            if operation.endswith('.observe') and not initialized[0]:initialized[0]=True;self.start_actor()
            return value
        def activate(ticket,verb='baseline',inputs=None):self.client.activate(ticket,verb,inputs);self.target.ticket=ticket
        def sleep(seconds):self.actor_ok();time.sleep(seconds)
        def witness():self.actor_ok();return self.client.observe()
        journey=Journey('assets',RUN,self.fixture_url,invoke=invoke,witness=witness,activate=activate,read_artifact=lambda name:(self.root/name).read_bytes(),image_policy=dict(screen=POLICY),continuity=lambda *_:None,
            monotonic=time.monotonic,epoch_ms=self.adapter.clock_ms,sleep=sleep,report=reports.append)
        try:journey.execute()
        except Exception:
            print('Synthetic Assets journey stopped after '+last[0]+'; timings '+repr(timings[-8:]),file=sys.stderr);self.actor_ok();raise
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded']);self.assertEqual(29,len(reports[-1]['phases'])-2)
        self.client.close();out,err=self.actor.communicate(timeout=10);self.assertEqual(0,self.actor.returncode,err[-6000:]);original_discard=PrivateFeatureState.discard;store=PrivateFeatureState(self.root/'phone-assets-actor-originals.json');discard=store.discard;failed=[False]
        def interrupted(previous):
            discard(previous)
            if not failed[0]:failed[0]=True;raise RuntimeError('Synthetic lost child unlink receipt')
        with patch.object(PrivateFeatureState,'discard',lambda owned,previous:interrupted(previous) if owned.path==store.path else original_discard(owned,previous)):
            with self.assertRaises(NativeUIError):self.feature().finalize()
        self.assertTrue(failed[0]);self.assertEqual({'performed':True},self.feature().finalize());self.assertEqual({'performed':True},self.feature().finalize())
        from overte_phone_assets_retirement import NAMES
        for name in (*NAMES,'phone-assets-retirement.json'):self.assertIsNone(PrivateFeatureState(self.root/name).read())
        self.assertEqual([],self.server.errors);self.assertFalse(list(self.files.directory.glob('feature-assets-*')));self.assertEqual([],self.target.rows);self.assertEqual({},self.target.mappings);self.assertEqual({},self.target.blobs)

if __name__=='__main__':unittest.main()
