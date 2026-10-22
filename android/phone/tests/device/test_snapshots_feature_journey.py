"""Ordinary Snapshot common-replay harness with explicit target producers.

Full-profile qualification remains pending until its complete tests pass.

Real host TLS/OAuth/upload, witness transport, public Phone facade/role/actor,
immutable originals and actual filesystem bytes execute unchanged. Native,
render, Android SDK/OS sources are explicit producer seams, never devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
import os
import json
import subprocess
import time
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests'),str(ROOT/'tests/device/adapters/android-phone')]
import test_account_fixture_launch
from create_feature_target import Handler,RUN,DOMAIN,POLICY
from snapshots_journey_producers import SnapshotTarget,SnapshotProxy,HostOnlyBoundary
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.test_phone_navigation import NativePhone
from self_tests import test_snapshot_upload_service as wire
from feature_journeys.account_provider import AccountProvider
from feature_journeys.snapshot_upload_service import SnapshotUploadService
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.scenarios import VERSION


ACTOR=r'''
import json,sys,time,traceback
from pathlib import Path
sys.path[:0]=json.loads(sys.argv[1])
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client
from snapshots_journey_producers import SnapshotActorProxy,RUN,HostOnlyBoundary
host_only=HostOnlyBoundary();host_only.__enter__()
from overte_phone_script_lock import PhoneScriptSourceBusy
from overte_phone_snapshot_upload_fixture import SnapshotUploadFixtureReader
import overte_phone_snapshot_upload_fixture
configuration=PrivateFeatureState(Path(sys.argv[2])).read()
adapter=SnapshotActorProxy(configuration['targetUrl'],configuration['root'])
class TargetClockPhase(SnapshotUploadFixtureReader):
    def __init__(self,client,run):super().__init__(client,run,epoch_ms=adapter.clock_ms)
overte_phone_snapshot_upload_fixture.SnapshotUploadFixtureReader=TargetClockPhase
client=Client(configuration['fixtureUrl'],configuration['actorToken'])
started=time.monotonic()
while time.monotonic()-started<240:
    try:
        if adapter.actor('synthetic',RUN,client).step():sys.exit(0)
    except PhoneScriptSourceBusy:pass
    except Exception as error:
        current=error.__context__
        while current is not None:
            traceback.print_exception(type(current),current,current.__traceback__,chain=False);current=current.__context__
        raise
    time.sleep(.1)
raise RuntimeError('Explicit synthetic actor lifetime exceeded')
'''


class SnapshotJourneyTests(unittest.TestCase):
    SDK=29
    @classmethod
    def setUpClass(cls):
        boundary=HostOnlyBoundary();boundary.__enter__();cls.addClassCleanup(boundary.close)
        wire.SnapshotUploadServiceTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):wire.SnapshotUploadServiceTests.tearDownClass.__func__(cls)
    def setUp(self):
        host_only=HostOnlyBoundary();host_only.__enter__();self.addCleanup(host_only.close)
        temporary=tempfile.TemporaryDirectory(prefix='snapshots-common-');self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.model=SnapshotTarget(self.root,sdk=self.SDK);self.addCleanup(self.model.close)
        self.rpc=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.rpc.target=self.model;self.rpc.errors=[]
        thread=threading.Thread(target=self.rpc.serve_forever,daemon=True);thread.start()
        def stop_rpc():self.rpc.shutdown();self.rpc.server_close();thread.join(3)
        self.addCleanup(stop_rpc)
        self.accounts=AccountProvider(epoch_ms=self.model.now);self.addCleanup(self.accounts.shutdown)
        self.server=make_server('r'*64,'a'*64,account_provider=self.accounts,tls_context=self.server_context,adapter_token='d'*64)
        self.server.journal.clock=self.model.now
        self.origin='https://localhost:'+str(self.server.server_port);self.base=self.origin+wire.PREFIX
        wire_root=self.root/'wire';wire_root.mkdir(mode=0o700)
        self.service=SnapshotUploadService(self.accounts,DOMAIN,wire_root,self.origin);self.server.snapshot_upload_service=self.service;self.model.service=self.service
        thread2=threading.Thread(target=self.server.serve_forever,daemon=True);thread2.start()
        def stop_server():self.server.shutdown();self.server.server_close();thread2.join(3)
        self.addCleanup(stop_server)
        env=patch.dict(os.environ,dict(SSL_CERT_FILE=str(self.cert)));env.start();self.addCleanup(env.stop)
        self.client=Client(self.base,'r'*64)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):run,self.fixture_url=self.client.register('snapshots')
        self.assertEqual(RUN,run)
        self.model.fixture=self.fixture_url;self.model.origin=self.origin
        self.setup=test_account_fixture_launch.AccountFixtureLaunchTests();self.setup.setUp();self.addCleanup(self.setup.doCleanups)
        self.adapter=self.setup.f.adapter;target=self.setup.f.target
        p=patch.object(self.adapter,'state_path',return_value=self.root/'session.json');p.start();self.addCleanup(p.stop)
        target['controls']={'normalNavigation':deepcopy(NativePhone().profile)}
        self.adapter.read_session('test-only-appium')['targetFingerprint']=self.adapter.snapshot_fingerprint(target)
        self.model.model_binding=deepcopy(self.adapter.normal_feature_runtime('test-only-appium',read_only=True)[2])
        self.proxy=SnapshotProxy('http://127.0.0.1:'+str(self.rpc.server_port),self.root)
        # Only the explicit external target epoch source is synthetic. Actual
        # readers, host monotonic bounds and quiet windows remain unchanged.
        from overte_phone_snapshot_upload_fixture import SnapshotUploadFixtureReader
        epoch=self.model.now
        class TargetClockPhase(SnapshotUploadFixtureReader):
            def __init__(inner,client,run):super().__init__(client,run,epoch_ms=epoch)
        p=patch('overte_phone_snapshot_upload_fixture.SnapshotUploadFixtureReader',TargetClockPhase);p.start();self.addCleanup(p.stop)
        from feature_journeys.phase_fixture import PhaseFixtureReader
        class TargetDispatchPhase(PhaseFixtureReader):
            def __init__(inner,client,run,area):super().__init__(client,run,area,epoch_ms=epoch)
        p=patch('overte_phone_feature_dispatch.PhaseFixtureReader',TargetDispatchPhase);p.start();self.addCleanup(p.stop)


        self.config=dict(snapshotsFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],
            imagePolicy=deepcopy(POLICY),fileImagePolicy=deepcopy(POLICY),domainId=DOMAIN,receiverApkSha256='e'*64)
        self.config_path=self.root/'snapshot-config.json';self.access_path=self.root/'adapter-access.json'
        PrivateFeatureState(self.config_path).write(self.config,None)
        PrivateFeatureState(self.access_path).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.base,adapterToken='d'*64),None)
        env=patch.dict(os.environ,dict(OVERTE_PHONE_FEATURE_SNAPSHOTS='1',OVERTE_PHONE_NORMAL_SNAPSHOT='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',
            OVERTE_PHONE_SNAPSHOTS_CONFIGURATION=str(self.config_path),OVERTE_E2E_FEATURE_FIXTURE_URL=self.base,OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(self.access_path)))
        env.start();self.addCleanup(env.stop)
        for name in ('_snapshot_source','_snapshot_measurements','_snapshot_normal_controls','_snapshot_capture_file_source','_snapshot_capture_files','_snapshot_settings','_snapshot_platform',
                     '_snapshot_share_resolution','_snapshot_share_ui','_snapshot_saved_files','_snapshot_consumer','_snapshot_system_consumer','_snapshot_system_context','_snapshot_handoff_control','_snapshot_handoff_source','_snapshot_system_files','_snapshot_system_platform','_graphics_surface','_create_fixture_input','_create_fixture_observer','_world_render_capture','_web_runtime_observer','_snapshot_cancel','_script_work','_login_controls','_account_menu','_snapshot_readbacks','_snapshot_upload_source','_native_feature_observer','_create_source','_avatar_render_observer',
                     '_graphics_subject_observer','_touch_state_observer'):
            p=patch.object(self.adapter,name,getattr(self.proxy,name));p.start();self.addCleanup(p.stop)
        p=patch.object(self.adapter,'query_app_state',side_effect=lambda *_:self.model.app_state);p.start();self.addCleanup(p.stop)
        p=patch.object(self.setup.f.fixture.adb,'epoch_milliseconds',side_effect=lambda _:self.proxy.clock_ms());p.start();self.addCleanup(p.stop)
        def client_identity(client,session,target):
            self.assertIs(client,self.setup.f.native)
            self.assertEqual('native-session',session)
            self.assertIs(target,self.setup.f.target)
            self.assertEqual(4,self.model.app_state)
            self.adapter.normal_feature_runtime('test-only-appium',read_only=True)[3]()
            # Explicit kernel producer: fresh mutable process state from the
            # provisioned native boundary, never a requested expected identity.
            native=self.setup.f.native
            if not native.running:raise AssertionError('Synthetic target process stopped')
            return dict(running=native.running,identity=native.identity)
        p=patch.object(self.adapter,'android_client_identity',side_effect=client_identity);p.start();self.addCleanup(p.stop)
        old_read=self.setup.f.fixture.adb.read_debug_app_file
        def read(device,package,path,**kwargs):
            from overte_phone_snapshot_controls import FILE
            if path=='files/overte-e2e/'+FILE:return self.model.product.raw
            return old_read(device,package,path,**kwargs)
        def write(_device,_package,path,raw):
            self.assertEqual(self.adapter.ANDROID_CLIENT_COMMAND,path)
            self.proxy.call('source',dict(key='snapshot-ui',request=__import__('json').loads(raw)))
        for p in (patch.object(self.setup.f.fixture.adb,'read_debug_app_file',side_effect=read),
                  patch.object(self.setup.f.fixture.adb,'write_debug_app_file',side_effect=write,create=True)):
            p.start();self.addCleanup(p.stop)
        old_execute=self.setup.f.native.execute
        def execute(session,operation,values):
            if operation=='mobile: pressKey':
                self.assertEqual({'keycode':3},values);self.proxy.call('lifecycle-input','background');return None
            if operation=='mobile: activateApp' and self.model.app_state==3:
                self.proxy.call('lifecycle-input','resume');return None
            return old_execute(session,operation,values)
        p=patch.object(self.setup.f.native,'execute',side_effect=execute);p.start();self.addCleanup(p.stop)
        self.model.account['observation']['endpointSha256']=__import__('hashlib').sha256(self.origin.encode()).hexdigest()
    def start_actor(self):
        path=self.root/'actor-configuration.json'
        PrivateFeatureState(path).write(dict(targetUrl=self.proxy.url,root=str(self.root),fixtureUrl=self.base,actorToken='a'*64),None)
        self.actor=subprocess.Popen([sys.executable,'-c',ACTOR,json.dumps(sys.path),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def stop():
            if self.actor.poll() is None:self.actor.terminate()
            self.actor.communicate(timeout=5)
        self.addCleanup(stop)
    def actor_ok(self):
        if self.actor.poll() is not None:
            out,err=self.actor.communicate();self.fail('Independent synthetic actor exited: '+str(self.actor.returncode)+' '+err[-5000:])
    def invoke(self,operation,arguments):
        try:return self.adapter.invoke('test-only-appium',operation,arguments)
        except Exception as error:
            import traceback
            current=error.__context__
            while current is not None:
                traceback.print_exception(type(current),current,current.__traceback__,chain=False);current=current.__context__
            raise
    def test_original_public_baseline_before_any_input_or_capture(self):
        self.client.activate('c'*32)
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(0,result['state']['files']);self.assertEqual([],result['state']['captureHistory'])
        self.assertEqual([],self.model.product.calls and [r for r in self.model.product.calls if r['request']['action']!='observe'])

    def act(self,verb,inputs=None):
        ticket=os.urandom(16).hex();inputs={} if inputs is None else inputs;self.client.activate(ticket,verb,inputs)
        return self.invoke('feature.snapshots.act',dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs))
    def test_real_oauth_reply_and_normal_snapshot_entry_are_independent_sources(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertTrue(result['state']['open']);self.assertTrue(self.model.account['loggedIn'])
        self.assertEqual(0,result['state']['files']);self.assertEqual([],result['state']['captureHistory'])

    def test_normal_cancel_then_capture_joins_independent_vm_native_fd_and_png(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture-cancel',dict(mode='animated',format='png'))
        cancelled=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual(['pending','cancelled'],cancelled['state']['captureHistory']);self.assertEqual(0,cancelled['state']['files'])
        self.act('capture',dict(mode='still',format='png'))
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=cancelled['sequence']))
        self.assertEqual(1,result['state']['files']);self.assertEqual(['pending','cancelled','pending','complete'],result['state']['captureHistory'])
        self.assertTrue(any(row['kind']=='file' for row in result['artifacts']))

    def test_normal_media_store_save_requires_actual_separate_destination_copy(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual(1,result['state']['saved']);self.assertEqual(1,len(self.model.os_files))
        self.assertTrue(all(path.read_bytes()==self.model.raw_png for path in self.model.os_files.values()))

    def test_actual_offline_reply_then_new_normal_upload_clears_error_and_publishes(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save')
        self.act('upload-fail')
        failed=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual('offline',failed['state']['error']);self.assertEqual(0,failed['state']['uploads'])
        self.act('upload')
        uploaded=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=failed['sequence']))
        self.assertEqual('none',uploaded['state']['error']);self.assertEqual(1,uploaded['state']['uploads'],uploaded['state'])
        self.assertEqual(1,self.service.snapshot(RUN,os.urandom(16).hex())['stories'])

    def test_normal_upload_story_deleted_by_cleanup_before_logout(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save');self.act('upload')
        provider=self.service.snapshot(RUN,os.urandom(16).hex())
        self.assertEqual(1,provider['stories'])
        self.client.activate('d'*32,'cleanup',{})
        self.invoke('feature.snapshots.cleanup',dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(0,self.service.snapshot(RUN,os.urandom(16).hex())['stories'])
        self.assertFalse(self.model.account['loggedIn'])
        self.assertTrue(all(not path.exists() for path in self.model.os_files.values()))
        self.assertTrue(all(row['retired'] for row in self.model.job_sources.values()))

    def test_closed_finalizer_requires_actual_independent_actor_exit_and_repeats(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save');self.act('upload')
        self.client.activate('d'*32,'cleanup',{})
        self.invoke('feature.snapshots.cleanup',dict(contractVersion=VERSION,runId=RUN))
        self.start_actor();deadline=time.monotonic()+30
        while not self.client.request('/runs/'+RUN)['entries']:
            self.actor_ok();self.assertLess(time.monotonic(),deadline);time.sleep(.1)
        self.client.close()
        out,err=self.actor.communicate(timeout=30);self.assertEqual(0,self.actor.returncode,err[-5000:])
        for attempt in range(2):self.assertEqual({'performed':True},self.invoke('feature.snapshots.cleanup',dict(contractVersion=VERSION,runId=RUN)))
        self.assertTrue(list(self.root.glob('emote-frame-snapshots-retirement-*.json')))
        self.assertIsNone(PrivateFeatureState(self.root/'phone-snapshots-feature.json').read())
        self.assertIsNone(PrivateFeatureState(self.root/'phone-snapshots-retirement.json').read())

    def test_inactive_work_source_has_no_invented_zero_activity_row(self):
        from adapters.native_script_work import scope
        reader=self.proxy._script_work(None)
        packet=reader.read(self.model.vm.manager['instance'])
        self.assertEqual([],packet['source']['work']['activity'])
        self.assertEqual(0,scope(packet,self.model.vm.compilation)['signalInvocations'])

    def test_saved_original_remains_independently_readable_inside_share_scope(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save');self.act('share-open')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual(1,result['state']['saved']);self.assertTrue(result['state']['shareSheet'])
        self.assertTrue(all(path.read_bytes()==self.model.raw_png for path in self.model.os_files.values()))

    def test_ignored_ordinary_capture_does_not_become_measured_effect(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.model.product.ignored.add('snapshot.capture')
        self.act('capture',dict(mode='still',format='png'))
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual(0,result['state']['files']);self.assertEqual([],result['state']['captureHistory'])
        self.assertIsNone(self.model.current_path)

    def test_missing_external_original_bytes_cannot_be_observed_as_saved(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('save')
        copy=self.model.readbacks['files'][0]
        (self.root/'snapshot-app/files'/Path(copy['path']).parent.name/Path(copy['path']).name).unlink()
        with self.assertRaises(Exception):self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertIsNotNone(PrivateFeatureState(self.root/'phone-snapshots-feature.json').read())

    def test_separate_actor_publishes_only_its_own_original_baseline(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.start_actor();deadline=time.monotonic()+15
        while True:
            self.actor_ok();value=self.client.request('/runs/'+RUN)
            if value['entries']:break
            self.assertLess(time.monotonic(),deadline);time.sleep(.1)
        self.assertEqual(0,value['entries'][-1]['facts']['files'])
        from overte_phone_script_history import unpack
        owner=PrivateFeatureState(self.adapter.state_path('test-only-appium').with_name('phone-snapshots-actor-lifecycle.json')).read()
        self.assertNotEqual(os.getpid(),unpack(owner['payload'])[0]['process']['pid'])

    def common(self):
        from feature_journeys.engine import Journey
        reports=[];initialized=[False];timings=[]
        def invoke(operation,fields):
            started=time.monotonic();before=self.model.rpc_counts.copy();result=self.invoke(operation,fields)
            counts=self.model.rpc_counts-before
            timings.append((operation.rsplit('.',1)[1],fields.get('verb'),round(time.monotonic()-started,3),dict(counts)))
            if operation.endswith('.observe') and not initialized[0]:initialized[0]=True;self.start_actor()
            return result
        witness_clocks=[]
        def witness():
            self.actor_ok();value=self.client.observe();epoch=self.model.now()
            witness_clocks[:]=[(epoch-row['capturedEpochMs'],row['receivedEpochMs']-row['capturedEpochMs'],epoch-row['receivedEpochMs']) for row in value['entries'][-3:]]
            return value
        def sleep(seconds):self.actor_ok();time.sleep(seconds)
        journey=Journey('snapshots',RUN,self.fixture_url,invoke=invoke,witness=witness,activate=self.client.activate,
            read_artifact=lambda name:(self.root/name).read_bytes(),image_policy=dict(screen=POLICY,file=POLICY),
            continuity=lambda *_:None,monotonic=time.monotonic,epoch_ms=self.model.now,sleep=sleep,report=reports.append)
        try:journey.execute()
        except BaseException:
            print('Explicit Snapshot producer replay stopped; recent source calls '+repr(timings[-8:])+'; original witness age/transport/receipt ages '+repr(witness_clocks)+'; actual final measured samples '+repr([(row['phase'],row['state']) for row in journey.samples[-4:]]),file=sys.stderr)
            if initialized[0]:self.actor_ok()
            raise
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.client.close();out,err=self.actor.communicate(timeout=20);self.assertEqual(0,self.actor.returncode,err[-5000:])
        for attempt in range(2):self.assertEqual({'performed':True},self.invoke('feature.snapshots.cleanup',dict(contractVersion=VERSION,runId=RUN)))
        for name in ('feature','retirement','primary-originals','actor-originals','actor-lifecycle','files-owner','primary-files-observer','actor-files-observer'):
            self.assertIsNone(PrivateFeatureState(self.root/('phone-snapshots-'+name+'.json')).read())
        self.assertTrue(list(self.root.glob('emote-frame-snapshots-retirement-*.json')))
        self.assertEqual(0,self.server.internal_errors);self.assertEqual([],self.rpc.errors)
        return reports[-1]
    def test_complete_media_store_common_journey_and_closed_repeated_cleanup(self):
        self.assertEqual('media-store',self.common()['sourceProfile'])

    def test_cancelled_share_grant_cannot_be_adopted_by_the_next_normal_choice(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'))
        self.act('share-open');cancelled=self.model.vm.snapshot.export_active;self.act('share-cancel')
        self.act('share-open');selected=self.model.vm.snapshot.export_active
        self.assertNotEqual(cancelled,selected);self.act('share-select-owned')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertEqual(1,result['state']['shares'])
        grants={row['request']:row for row in self.model.readbacks['shareGrants']['rows']}
        self.assertEqual('',grants[cancelled]['component']);self.assertEqual(0,grants[cancelled]['receiverUid'])
        self.assertTrue(grants[selected]['component']);self.assertEqual(10002,grants[selected]['receiverUid'])

    def test_normal_share_handoff_requires_separate_receiver_original_bytes(self):
        self.client.activate('c'*32);self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'));self.act('share-open')
        opened=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=1))
        self.assertTrue(opened['state']['shareSheet']);self.assertEqual(0,opened['state']['shares'])
        self.act('share-select-owned')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=opened['sequence']))
        self.assertEqual(1,result['state']['shares']);self.assertFalse(result['state']['shareSheet'])
        self.assertEqual(self.model.raw_png,self.model.consumer.path.read_bytes())


class HostBoundaryTests(unittest.TestCase):
    def test_unprovisioned_transport_and_direct_adb_stop_before_subprocess(self):
        from adb_transport import AdbTransport
        with patch('subprocess.Popen',side_effect=AssertionError('Escaped host boundary')) as original:
            with HostOnlyBoundary():
                with self.assertRaisesRegex(AssertionError,'Unprovisioned Android'):AdbTransport()
                for command in (['adb','get-state'],['/unavailable/adb','get-state'],['sh','-c','adb get-state'],['env','adb','get-state']):
                    with self.assertRaisesRegex(AssertionError,'Device subprocess forbidden'):subprocess.run(command)
                with self.assertRaisesRegex(AssertionError,'Device subprocess forbidden'):subprocess.run(['python3','--version'],executable='/unavailable/adb')
                with self.assertRaisesRegex(AssertionError,'Device subprocess forbidden'):subprocess.run(['adb','get-state'],shell=True)
            original.assert_not_called()


if __name__=='__main__':unittest.main()
