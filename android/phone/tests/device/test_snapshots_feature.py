"""Private owner/preflight cleanup with original fixture owners and real journals.

Native/SDK transport is an explicit synthetic boundary. No public feature PASS
or physical device qualification is claimed by these narrow recovery tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import base64
import hashlib
import os
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
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
        self.journal=Journal(clock=lambda:20000);self.run=self.journal.register('snapshots');self.accounts=AccountProvider(epoch_ms=lambda:20000)
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
    def _world_render_capture(self,_selector,**kwargs):
        return SimpleNamespace(owner=SimpleNamespace(store=PrivateFeatureState(self.root/('render-'+kwargs['role']+'.json'))))
    def _graphics_lifecycle_status(self,*_):return dict(binding=deepcopy(self.binding),foreground=True,running=self.alive,appState=4)
    @contextmanager
    def existing_input_session(self,_):yield


class LeasedAdapter(Adapter):
    """Original native readers with actual host file transport, no UI inputs."""
    def __init__(self,root):
        super().__init__(root)
        from test_snapshot_measurements import Boundary as VM
        from test_snapshot_capture_files import Producer
        from test_snapshot_settings import Boundary as Settings
        from self_tests.test_native_feature_observation import Boundary as Native
        from self_tests.test_native_account_observation import account_source
        from self_tests.test_native_script_work import ScopedWorkBoundary
        self.vm=VM();self.settings=Settings();self.native=Native();self.work=ScopedWorkBoundary()
        snapshot_send=self.vm.snapshot_reader.send
        def snapshot_request(request):self.vm.snapshot.epoch=19990;snapshot_send(request)
        self.vm.snapshot_reader.send=snapshot_request
        self.app=root/'target';self.app.mkdir(mode=0o700);self.producer=Producer(self.app);self.producer.epoch=20000
        self.work.member=deepcopy(self.vm.manager);self.work.code=deepcopy(self.vm.code)
        self.work.compiled['compilations']=[deepcopy(self.vm.compilation)];self.work.activity=[]
        def native(value):value['processId']=31;account_source(value)
        self.native.mutate=native;self.reply={};self.sequences={};self.fail_plan=False
    def _snapshot_measurements(self,_):
        original=self.vm.reader.read
        def read(run):self.vm.snapshot.epoch=19990;return original(run)
        return SimpleNamespace(read=read)
    def _native_feature_observer(self,*_,**kwargs):
        from adapters.native_feature_observation import NativeFeatureObservation
        return NativeFeatureObservation(self.native.send,self.native.original,lambda:20000,self.native.guard,31)
    def _script_work(self,*_,**kwargs):return self.work.reader()
    def _snapshot_settings(self,_,*,read_only):
        from overte_phone_snapshot_settings import PhoneSnapshotSettings
        def raw():
            packet=json.loads(self.settings.raw);packet['processId']=31;return json.dumps(packet)
        return PhoneSnapshotSettings(self.settings.send,raw,lambda:20000,lambda:True,31,read_only=read_only)
    def _snapshot_capture_file_source(self,_,*,read_only):
        from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource
        def raw():
            packet=json.loads(self.producer.read());packet['processId']=31;return json.dumps(packet)
        return PhoneSnapshotCaptureFileSource(self.producer.send,raw,lambda:20000,lambda:True,31,read_only=read_only)
    def _snapshot_capture_files(self,_,root,path,*,read_only):
        from test_snapshot_capture_files import LocalTransport
        from overte_phone_snapshot_capture_files import PhoneSnapshotCaptureFiles
        if self.fail_plan:raise NativeUIError('Explicit failure after original native settings capture')
        root.mkdir(mode=0o700,exist_ok=True)
        return PhoneSnapshotCaptureFiles(LocalTransport(self.app,root),self._snapshot_capture_file_source(None,read_only=read_only),BINDING,path,read_only=read_only)
    def _snapshot_source(self,_):return self.vm.snapshot_reader
    def original(self,request,kind):
        self.sequences[kind]=self.sequences.get(kind,0)+1
        body=(dict(snapshotUploadObservationVersion=1,instance='7'*32,complete=True,capturedEpochMs=20000,sequence=0,events=[],jobs=[])
            if kind=='upload' else dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True)))
        self.reply[kind]=json.dumps(dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequences[kind],processId=31,requestedEpochMs=20000,capturedEpochMs=20000,source=body))
    def _snapshot_upload_source(self,_):
        from overte_phone_snapshot_upload_source import PhoneSnapshotUploadSource
        return PhoneSnapshotUploadSource(lambda row:self.original(row,'upload'),lambda:self.reply['upload'],lambda:20000,lambda:True,31)
    def _snapshot_readbacks(self,_,*,read_only):
        from overte_phone_snapshot_readbacks import PhoneSnapshotReadbacks
        return PhoneSnapshotReadbacks(lambda row:self.original(row,'readbacks'),lambda:self.reply['readbacks'],lambda:20000,lambda:True,31)
    def _snapshot_normal_controls(self,*_,**kwargs):
        def forbidden(*_args,**_kwargs):raise AssertionError('Partial preparation may not send any normal UI input')
        return SimpleNamespace(input=forbidden,close=forbidden,release=forbidden)


class BackgroundAdapter(LeasedAdapter):
    """Explicit SDK/lifecycle producer; recovery may only send an owed resume."""
    def __init__(self,root):
        super().__init__(root);self.app_state=3;self.lifecycle=dict(backgrounds=1,activations=1,launches=1)
        original=self.native.mutate
        def mutate(value):original(value);value['lifecycle']=deepcopy(self.lifecycle)
        self.native.mutate=mutate
    def _graphics_lifecycle_status(self,*_):
        return dict(binding=deepcopy(self.binding),foreground=self.app_state==4,running=self.alive,appState=self.app_state)
    def invoke(self,_selector,operation,value):
        need(operation=='app.launch' and value=={} and self.app_state in (2,3))
        self.calls.append(operation);self.app_state=4;self.lifecycle['activations']+=1


class NoExportAdapter(LeasedAdapter):
    """Qualified readonly baseline sources with a never initialized exporter."""
    def __init__(self,root):
        super().__init__(root)
        from self_tests.test_native_avatar_render import Boundary as Avatar
        from self_tests.test_native_phone_touch_state import Boundary as Touch
        from self_tests.test_native_graphics_subject import Boundary as World
        self.avatar=Avatar();self.touch=Touch();self.world=World()
        self.world.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,0,-2],orientation=[0,0,0,1],modelScale=1))
        send=self.world.send
        def sample(request):
            from feature_journeys.graphics_fixture import subject_ids
            self.world.source['absentIds']=list(subject_ids(request['runId']).values());send(request)
        self.world.send=sample
    def _avatar_render_observer(self,*_,**kwargs):return self.avatar.reader()
    def _touch_state_observer(self,*_,**kwargs):return self.touch.reader()
    def _graphics_subject_observer(self,*_,**kwargs):return self.world.reader()


class HandoffAdapter(Adapter):
    """Original handoff/control/input readers over explicit native IO producers."""
    def __init__(self,root,run):
        super().__init__(root)
        from test_snapshot_handoff import Boundary as NativeHandoff
        from test_snapshot_handoff_input import Handoff
        self.run=run;self.native=NativeHandoff();self.input=Handoff();self.input.epoch=20000
        io=self.input.io();original=io.capture();request=io._prepare(self.input.controls[0]['id'],'activate',reference=original)
        self.input.plan=dict(request=request,original=original);self.input.epoch=20020
        self.control_calls=[];self.absent=False;self.runtime_calls=0;self.system_calls=[];self.system=True
        original_frame=self.native.frame
        def frame(retired=False):
            value=original_frame(retired);source=value['source'];source['runId']=run
            source['source']['group']['snapshot']['runId']=run
            for key in ('readbacks','captureFiles','upload'):source['source'][key]['runId']=run
            value['jobs'][0]['runId']=run;return value
        self.native.frame=frame
    def normal_feature_runtime(self,*args,**kwargs):
        self.runtime_calls+=1;need(self.input.foreground)
        return None,None,deepcopy(self.binding),lambda:self.input.foreground,dict(sha256='a'*64)
    def _snapshot_handoff_control(self,_,*,read_only=False):
        from overte_phone_snapshot_handoff import PhoneSnapshotHandoffControl
        def send(request):
            need(not read_only or request['operation']=='observe');self.control_calls.append(deepcopy(request))
            need(not self.absent and request['runId']==self.run)
            self.native.send(request);self.native.result['runId']=self.run
        return PhoneSnapshotHandoffControl(send,lambda:json.dumps(self.native.result),lambda:self.native.epoch,lambda:True,31,
            monotonic=lambda:self.native.time,sleep=self.native.sleep)
    def _snapshot_system_context(self,_selector,binding,resolution,authority):
        self.system_calls.append(deepcopy((binding,resolution)))
        def guard():authority();return self.system
        return SimpleNamespace(guard=guard)
    def _snapshot_handoff_input(self,_selector,_binding,_resolution,_authority,owner,admit,*,read_only=False):
        need(read_only);self.input.owner=deepcopy(owner);reader=self.input.reader()
        reader.send=lambda *_:(_ for _ in ()).throw(AssertionError('Recovery may not repeat a write'))
        reader.admit=lambda *_:(_ for _ in ()).throw(AssertionError('Recovery may not admit'))
        return reader


class SnapshotsFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='snapshots-feature-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);wire=self.root/'wire';wire.mkdir(mode=0o700)
        self.client=OriginalClient(wire);self.addCleanup(self.client.accounts.shutdown);self.run=self.client.run
        self.client.activate('baseline');self.phase=SnapshotUploadFixtureReader(self.client,self.run,epoch_ms=lambda:20000)
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
    def test_lost_partial_settings_setup_is_restored_with_actual_files_and_real_quiet_windows(self):
        self.adapter=LeasedAdapter(self.root);f=self.feature()
        with f.lock.held():
            f.load()
            # Initial failure happened before a source was available. No UI
            # or lease was touched; persist a now available original preflight.
            old=f.adapter._snapshot_measurements
            f.adapter._snapshot_measurements=lambda _:SimpleNamespace(read=lambda _:(_ for _ in ()).throw(NativeUIError('Missing preflight')))
            with self.assertRaises(NativeUIError):f.initialize()
            f.adapter._snapshot_measurements=old
            group,_=old(None).read(self.run);native=self.adapter._native_feature_observer(None,read_only=True).read(0,require_account=True)
            baseline=dict(group=group,native=native,avatar=dict(source=dict(cameraMode='selfie')),documentResolution=None)
            f.state['original']=dict(avatar=dict(source=dict(cameraMode='selfie')));f.save();f.archive_input(dict(snapshotsBaseline=baseline))
            self.adapter.fail_plan=True
            with self.assertRaises(NativeUIError):f.prepare_owned_leases()
            self.assertIsNotNone(f.state['settingsIndex']);self.assertIsNone(f.state['filesIndex']);self.assertGreater(self.adapter.settings.opened,0)
        self.adapter.fail_plan=False;self.client.activate('cleanup')
        started=time.monotonic();self.assertEqual({'performed':True},self.feature().cleanup(self.call()))
        self.assertGreaterEqual(time.monotonic()-started,6)
        f=self.feature()
        with f.lock.held():
            f.load();proof=f.partial_restored();self.assertEqual('retired-own-leases',proof['kind'])
            self.assertTrue(proof['proof']['settings']['source']['retired']);self.assertFalse(proof['proof']['inventory']['files'])
            self.assertFalse(proof['proof']['readbacks']['source']['source']['initialized'])
        self.assertTrue(self.adapter.foreign_ui_open);self.assertFalse(any(row['operation'] not in ('capture','observe','restore','retire') for row in self.adapter.settings.calls))

    def unsupported_settings_journal(self,*,legacy,index_saved):
        """Archive a coherent old/incomplete producer packet in real originals."""
        f=self.failed_preflight();self.adapter=LeasedAdapter(self.root);f=self.feature()
        with f.lock.held():
            f.load()
            f.state['original']=dict(avatar=dict(source=dict(cameraMode='selfie')))
            f.archive_input(dict(snapshotsBaseline=deepcopy(f.state['original'])))
            f.state['settingsIntent']=dict(issued=True,requestedEpochMs=20000);f.save()
            packet=self.adapter._snapshot_settings(None,read_only=False).request(self.run,'capture')
            self.assertEqual(2,packet['snapshotSettingsLeaseVersion'])
            source=packet['source'];del source['current']['entries']['previousAnimatedSnapUrl']
            # Preserve the serialization/hash relationship: rejection must be
            # the unsupported lease/scope, not unrelated corrupt byte evidence.
            raw=self.adapter.settings.serialized(source['current'])
            source['currentSerializedBase64']=base64.b64encode(raw).decode()
            source['currentSha256']=source['originalSha256']=hashlib.sha256(raw).hexdigest()
            if legacy:packet['snapshotSettingsLeaseVersion']=1
            index=f.archive_input(dict(snapshotsSettingsCaptured=packet))
            if index_saved:f.state['settingsIndex']=index;f.save()
        return f

    def assert_unsupported_settings_blocks_before_native_or_owner_change(self,*,legacy):
        for index_saved in (False,True):
            # Each subcase has a distinct genuine private journal/lease; no old
            # owner is rewritten to set up another counter or migrated on error.
            with self.subTest(index_saved=index_saved),tempfile.TemporaryDirectory(dir=self.root) as temporary:
                outer_root,outer_adapter,outer_config=self.root,self.adapter,self.config
                try:
                    self.root=Path(temporary);self.root.chmod(0o700);self.adapter=Adapter(self.root)
                    self.config=deepcopy(outer_config);self.config['artifactRoot']=str(self.root)
                    f=self.unsupported_settings_journal(legacy=legacy,index_saved=index_saved)
                    before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*')
                        if p.is_file() and not p.name.endswith('.lock')}
                    issued=deepcopy(self.adapter.settings.calls)
                    runtime=self.adapter.normal_feature_runtime;settings=self.adapter._snapshot_settings
                    controls=self.adapter._snapshot_normal_controls
                    with patch.object(self.adapter,'normal_feature_runtime',wraps=runtime) as native_factory,\
                            patch.object(self.adapter,'_snapshot_settings',wraps=settings) as settings_factory,\
                            patch.object(self.adapter,'_snapshot_normal_controls',wraps=controls) as ui_factory:
                        for operation in ('load','act'):
                            resumed=self.feature()
                            with self.subTest(operation=operation),self.assertRaises(NativeUIError):
                                if operation=='load':
                                    with resumed.lock.held():resumed.load()
                                else:
                                    resumed.act(dict(contractVersion=VERSION,runId=self.run,fixtureUrl=f.fixture_url,
                                        ticket=uuid.uuid4().hex,verb='open',inputs={}))
                            native_factory.assert_not_called();settings_factory.assert_not_called();ui_factory.assert_not_called()
                            after={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*')
                                if p.is_file() and not p.name.endswith('.lock')}
                            self.assertEqual(before,after)
                            self.assertEqual(issued,self.adapter.settings.calls)
                            self.assertTrue(self.adapter.foreign_ui_open)
                finally:self.root,self.adapter,self.config=outer_root,outer_adapter,outer_config

    def test_archived_v1_settings_reject_load_and_act_before_native_or_owner_change(self):
        self.assert_unsupported_settings_blocks_before_native_or_owner_change(legacy=True)

    def test_archived_v2_missing_key_rejects_load_and_act_before_native_or_owner_change(self):
        self.assert_unsupported_settings_blocks_before_native_or_owner_change(legacy=False)

    def test_qualified_baseline_failure_before_first_export_retires_actual_leases_without_empty_os_facts(self):
        self.failed_preflight();self.adapter=NoExportAdapter(self.root);f=self.feature()
        with f.lock.held():
            f.load();group,_=self.adapter._snapshot_measurements(None).read(self.run)
            native=self.adapter._native_feature_observer(None,read_only=True).read(0,require_account=True)
            avatar=self.adapter._avatar_render_observer(None,read_only=True).read()
            world=self.adapter._graphics_subject_observer(None,read_only=True).read(self.run,require_avatar=True)
            f.state['original']=dict(avatar=dict(source=dict(cameraMode=avatar['source']['cameraMode'])));f.save()
            f.archive_input(dict(snapshotsBaseline=dict(group=group,native=native,avatar=avatar,world=world,documentResolution=None)))
            f.prepare_owned_leases();f.state.update(partial=False,phase='baseline',current=None);f.save()
        self.client.activate('cleanup');started=time.monotonic()
        self.assertEqual({'performed':True},self.feature().cleanup(self.call()));self.assertGreaterEqual(time.monotonic()-started,6)
        f=self.feature()
        with f.lock.held():
            f.load();self.assertEqual('cleaned',f.state['phase']);self.assertFalse(f.state['partial'])
            proof=f.restored();self.assertFalse(proof['readbacks']['initialized']);self.assertNotIn('osDestinations',proof['readbacks'])
            rows=f.input_originals();original=next(row['snapshotNoOwnedExports'] for row in rows if 'snapshotNoOwnedExports' in row)
            self.assertFalse(original['readbacksUnavailable']['initialized']);self.assertEqual(2,len(f.state['quiet']))
            import overte_phone_snapshots_measurements as reductions
            original_retired=reductions.retired;original_inputs=f.input_originals
            events=[]
            def inputs():events.append('actual-input-history');return original_inputs()
            def proof(*args,**kwargs):events.append('current-retirement-proof');return original_retired(*args,**kwargs)
            with patch.object(f,'input_originals',inputs),patch.object(reductions,'retired',proof):f.restored()
            self.assertEqual(['actual-input-history','current-retirement-proof','actual-input-history'],events[-3:])
            first=f.inputs.expand(f.inputs.manifest(f.state['inputs'][0])[0]);path=f.inputs.path(first);raw=path.read_bytes()
            for fault in ('actual-original-bytes','actual-feature-header'):
                with self.subTest(lateRestorationFault=fault):
                    header=deepcopy(f.previous);changed=[]
                    def interrupted(*args,**kwargs):
                        result=original_retired(*args,**kwargs)
                        if fault=='actual-original-bytes':path.write_bytes(raw+b' ');changed.append(raw+b' ')
                        else:
                            foreign=deepcopy(header);state=unpack(foreign['payload']);state[0]['phase']='retiring';foreign['payload']=pack(state)
                            f.store.write(foreign,header);changed.append(foreign)
                        return result
                    try:
                        with patch.object(reductions,'retired',interrupted),self.assertRaises(NativeUIError):f.restored()
                        if fault=='actual-original-bytes':self.assertEqual(changed[0],path.read_bytes())
                        else:self.assertEqual(changed[0],f.store.read())
                        self.assertEqual('cleaned',f.state['phase'])
                    finally:
                        if fault=='actual-original-bytes':path.write_bytes(raw)
                        else:f.store.write(header,changed[0])
        self.assertTrue(self.adapter.foreign_ui_open)

    def test_partial_finalize_requires_real_actor_exit_and_retires_exact_journals_idempotently(self):
        from fixture.messages_mixer import start_identity
        from overte_phone_snapshots_retirement import PhoneSnapshotsRetirement,completed_archive,NAMES
        f=self.failed_preflight();self.client.activate('cleanup');f.cleanup(self.call());self.client.retire()
        child=subprocess.Popen([sys.executable,'-c',"import os,sys;print(os.getpid(),flush=True);sys.stdin.read()"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        self.addCleanup(lambda:child.poll() is None and child.kill());self.assertEqual(str(child.pid),child.stdout.readline().strip())
        process=dict(pid=child.pid,start=start_identity(child.pid));need(process['start'] is not None)
        with f.lock.held():
            proof=f.partial_restored();closure=f.phase.status()
            actor=dict(process=process,phase='retired',pending=None,last=None,dropped=[],quiet=None,closure=closure,partialClosure=proof)
            header=dict(snapshotsActorVersion=1,runId=f.run,binding=f.binding,payload=pack([actor]))
            store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-actor-lifecycle.json'));store.write(header,None)
            archive=dict(owner=deepcopy(f.previous),controls={name:PrivateFeatureState(f.store.path.with_name(name)).read() for name in NAMES},proof=proof,closure=closure)
            with self.assertRaises(NativeUIError):PhoneSnapshotsRetirement(f).validate_archive(archive)
        child.stdin.close();self.assertEqual(0,child.wait(timeout=5));child.stdout.close()
        self.assertEqual({'performed':True},f.finalize())
        self.assertTrue(all(PrivateFeatureState(f.store.path.with_name(name)).read() is None for name in NAMES))
        result=completed_archive(f.root,f.binding,f.run,lambda:True)
        self.assertEqual('no-issued-lease',result['proof']['kind']);self.assertFalse(result['closure']['active'])
        rebuilt=self.feature();self.assertEqual({'performed':True},rebuilt.finalize());self.assertTrue(self.adapter.foreign_ui_open)

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

    def background_journal(self,stage,*,foreground=False):
        self.failed_preflight();self.adapter=BackgroundAdapter(self.root);f=self.feature()
        with f.lock.held():
            self.adapter.lifecycle['backgrounds']=0
            f.load();before=self.adapter._native_feature_observer(None,read_only=True).read(0,require_account=True)
            self.adapter.lifecycle['backgrounds']=1
            f.state['original']=dict(avatar=dict(source=dict(cameraMode='selfie')))
            f.archive_input(dict(snapshotsBaseline=dict(avatar=deepcopy(f.state['original']['avatar']))))
            call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=f.fixture_url,ticket=uuid.uuid4().hex,verb='background-resume',inputs={})
            f.state.update(phase='acting',current=dict(call=call,phase='issuing',pending=dict(kind='background',stage=stage,before=before,startedMonotonic=100.)))
            f.save()
        self.adapter.app_state=4 if foreground else 3
        if foreground:self.adapter.lifecycle['activations']=2
        return PhoneSnapshotsFeature(self.adapter,'synthetic',self.phase,self.config,monotonic=lambda:101.)

    def test_background_recovery_sends_only_the_not_yet_issued_resume(self):
        f=self.background_journal('background-issued')
        with f.lock.held():
            f.load();f.recover_handoff_input()
            self.assertIsNone(f.state['current']['pending']);self.assertEqual(['app.launch'],self.adapter.calls)
            originals=f.inputs.restore(f.state['inputs'],f.state['inputSequence'])
            self.assertIn('snapshotBackground',originals[-2]);self.assertIn('snapshotResumed',originals[-1])
        # A subsequent instance cannot replay either Home or launch.
        again=self.feature()
        with again.lock.held():again.load();again.recover_handoff_input()
        self.assertEqual(['app.launch'],self.adapter.calls)

    def test_saved_resume_is_recovered_without_repeating_input(self):
        f=self.background_journal('resume-issued',foreground=True)
        with f.lock.held():f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
        self.assertEqual([],self.adapter.calls)

    def test_uncertain_home_return_is_recovered_without_repeating_input(self):
        f=self.background_journal('background-issued',foreground=True)
        with f.lock.held():
            f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
            originals=f.inputs.restore(f.state['inputs'],f.state['inputSequence'])
            self.assertIn('snapshotBackgroundUncertain',originals[-1])
        self.assertEqual([],self.adapter.calls)

    def test_expired_background_recovery_preserves_pending_journal_and_sends_nothing(self):
        f=self.background_journal('resume-issued');original=f.store.read()
        f.monotonic=lambda:120.
        with f.lock.held(),self.assertRaises(NativeUIError):f.load()
        self.assertEqual(original,f.store.read());self.assertEqual([],self.adapter.calls)
        self.adapter.binding['processIdentity']='99:1';f.monotonic=lambda:101.
        with f.lock.held(),self.assertRaises(NativeUIError):f.load()
        self.assertEqual(original,f.store.read());self.assertEqual([],self.adapter.calls)

    def handoff_journal(self,stage,*,stale_constructor=False):
        self.failed_preflight();self.adapter=HandoffAdapter(self.root,self.run);f=self.feature()
        with f.lock.held():
            f.load();resolution=dict(component='android/ExplicitSyntheticChooser')
            f.state['original']=dict(avatar=dict(source=dict(cameraMode='selfie')))
            f.archive_input(dict(snapshotsBaseline=dict(avatar=deepcopy(f.state['original']['avatar']),resolution=resolution)))
            call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=f.fixture_url,ticket=uuid.uuid4().hex,verb='share-open',inputs={})
            f.state.update(phase='acting',current=dict(call=call,phase='issuing',pending=None))
            f.archive_input(dict(snapshotInput=self.adapter.input.plan))
            stale=self.feature() if stale_constructor else None
            identifier='b'*32;start=self.adapter._snapshot_handoff_control(None).request(self.run,'start',identifier)
            from overte_phone_snapshot_handoff import bound
            self.adapter.input.owner=bound(start)
            if stage=='start':f.state['current']['pending']=dict(kind='handoff-start',id=identifier,mode='share',plan=self.adapter.input.plan)
            else:
                index=f.archive_input(dict(handoffStart=start,handoffPlan=self.adapter.input.plan))
                f.state['handoff']=dict(id=identifier,kind='share',resolution=resolution,binding=bound(start),sourceIndex=index)
                f.state['current']['pending']=dict(kind='handoff-input',issued=True,binding=bound(start),plan=self.adapter.input.plan)
                f.guard=self.adapter._snapshot_system_context('synthetic',f.binding,resolution,f.header_authority).guard
                self.adapter.input.reader().deliver(self.adapter.input.plan)
            f.save()
        return stale if stale_constructor else f

    def test_lost_native_start_return_observes_owned_job_without_restarting_or_delivering(self):
        self.handoff_journal('start');f=self.feature()
        with f.lock.held():
            f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
            self.assertEqual('b'*32,f.state['handoff']['id'])
        self.assertEqual(['start','observe'],[row['operation'] for row in self.adapter.control_calls]);self.assertEqual([],self.adapter.input.sent)
        again=self.feature()
        with again.lock.held():again.load();again.recover_handoff_input()
        self.assertEqual(2,len(self.adapter.control_calls));self.assertEqual([],self.adapter.input.sent)

    def test_issued_handoff_recovers_original_receipt_without_readmission_or_write(self):
        self.handoff_journal('issued');f=self.feature()
        with f.lock.held():
            f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
            originals=f.inputs.restore(f.state['inputs'],f.state['inputSequence'])
            self.assertIn('snapshotHandoffRecovered',originals[-1]);self.assertEqual(self.adapter.input.plan,originals[-1]['plan'])
        self.assertEqual(1,len(self.adapter.input.sent));self.assertEqual(1,len(self.adapter.input.admissions))

    def test_missing_native_start_preserves_unadmitted_authority(self):
        self.handoff_journal('start');f=self.feature();header=f.store.read();self.adapter.absent=True
        with f.lock.held():
            f.load()
            with self.assertRaises(NativeUIError):f.recover_handoff_input()
        self.assertEqual(header,f.store.read());self.assertEqual([],self.adapter.input.sent)

    def test_missing_original_receipt_preserves_issued_authority_and_never_retries(self):
        self.handoff_journal('issued');self.adapter.input.raw='';f=self.feature();header=f.store.read()
        with f.lock.held():
            f.load()
            with self.assertRaises(NativeUIError):f.recover_handoff_input()
        self.assertEqual(header,f.store.read());self.assertEqual(1,len(self.adapter.input.sent));self.assertEqual(1,len(self.adapter.input.admissions))

    def test_receipt_already_archived_before_pending_clear_rechecks_without_retry(self):
        f=self.handoff_journal('issued')
        with f.lock.held():
            f.load();f.archive_input(dict(snapshotHandoffInput=self.adapter.input.plan,receipt=json.loads(self.adapter.input.raw)))
        f=self.feature()
        with f.lock.held():f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
        self.assertEqual(1,len(self.adapter.input.sent));self.assertEqual(1,len(self.adapter.input.admissions))

    def test_changed_pending_plan_cannot_reconstruct_original_issued_authority(self):
        f=self.handoff_journal('issued');header=f.store.read();changed=deepcopy(header);rows=unpack(changed['payload'])
        rows[0]['current']['pending']['plan']['request']['commandId']='e'*32;changed['payload']=pack(rows);f.store.write(changed,header)
        rebuilt=self.feature()
        with rebuilt.lock.held(),self.assertRaises(NativeUIError):rebuilt.load()
        self.assertEqual(changed,f.store.read());self.assertEqual(1,len(self.adapter.input.sent))

    def test_foreground_constructed_owner_selects_current_original_os_authority_under_lock(self):
        f=self.handoff_journal('issued',stale_constructor=True);calls=self.adapter.runtime_calls
        self.assertFalse(self.adapter.input.foreground)
        with f.lock.held():
            f.load();f.recover_handoff_input();self.assertIsNone(f.state['current']['pending'])
        self.assertEqual(calls,self.adapter.runtime_calls);self.assertEqual(1,len(self.adapter.input.sent))
        self.assertEqual(f.binding,self.adapter.system_calls[-1][0])

    def test_os_constructed_owner_selects_fresh_foreground_after_actual_scope_closure(self):
        self.handoff_journal('issued');stale=self.feature();current=self.feature()
        with current.lock.held():
            current.load();current.recover_handoff_input()
            # Explicit SDK producer returns to the primary Activity; the exact
            # owner then persists the end of its scope. No new input is sent.
            self.adapter.input.foreground=True
            current.state['handoff']=None;current.state['current']=None;current.save()
        calls=self.adapter.runtime_calls;systems=len(self.adapter.system_calls)
        with stale.lock.held():stale.load();stale.bound()
        self.assertEqual(calls+1,self.adapter.runtime_calls);self.assertEqual(systems,len(self.adapter.system_calls))

    def test_foreign_or_unavailable_current_os_scope_has_no_foreground_fallback(self):
        f=self.handoff_journal('issued',stale_constructor=True);header=f.store.read();calls=self.adapter.runtime_calls
        self.adapter.system=False
        with f.lock.held(),self.assertRaises(NativeUIError):f.load()
        self.assertEqual(calls,self.adapter.runtime_calls);self.assertEqual(header,f.store.read());self.assertEqual(1,len(self.adapter.input.sent))

    def input_history(self):
        f=self.failed_preflight()
        with f.lock.held():
            f.load();f.state['original']=dict(avatar=dict(source=dict(cameraMode='selfie')))
            f.archive_input(dict(snapshotsBaseline=deepcopy(f.state['original'])))
            for index in range(12):f.archive_input(dict(explicitHistoricalInput=index))
        return f

    def test_immutable_input_replay_brackets_actual_target_identity_and_checks_every_old_file(self):
        f=self.input_history();calls=[]
        f.guard=lambda:calls.append(deepcopy(self.adapter.binding)) or self.adapter.binding==BINDING
        with f.lock.held():
            original=f.original();self.assertEqual('selfie',original['avatar']['source']['cameraMode'])
            self.assertEqual(2,len(calls))
            from overte_phone_snapshots_evidence import SnapshotsOriginals
            read=SnapshotsOriginals.read
            def changed(reader,value):
                result=read(reader,value)
                if value['index']==13:self.adapter.binding['artifactSha256']='9'*64
                return result
            with patch.object(SnapshotsOriginals,'read',changed),self.assertRaises(NativeUIError):f.original()
            self.adapter.binding=deepcopy(BINDING)
            # Corrupt old actual bytes without changing the pinned inode.
            path=next(f.root.glob('emote-frame-snapshots-input-'+f.run+'-primary-0001-*.json'))
            raw=path.read_bytes();path.write_bytes(raw.replace(b'selfie',b'broken',1))
            with self.assertRaises(NativeUIError):f.original()

if __name__=='__main__':unittest.main()
