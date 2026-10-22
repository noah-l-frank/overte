"""Snapshot role composition over explicit native producers and actual files.

Kernel/SDK/native signals here are synthetic; the unchanged readers, reducer,
private files, hashes, inodes and immutable archives execute on the real host.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_observation import NativeScriptObservation
from feature_journeys.fixtures import marker_bytes
from feature_journeys.graphics_fixture import subject_ids
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshot_capture_files import PhoneSnapshotCaptureFiles
from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource
from overte_phone_snapshot_platform import PhoneSnapshotPlatform
from overte_phone_snapshots_role import PhoneSnapshotsRole
from overte_phone_snapshots_evidence import SnapshotsBinary,SnapshotsImages
from test_snapshot_capture_facts import originals,RUN
from test_snapshot_capture_files import Producer,LocalTransport
from test_snapshots_measurements import public_frame
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_account_observation import account_source
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests.test_native_phone_touch_state import Boundary as TouchBoundary
from self_tests.test_native_graphics_subject import Boundary as WorldBoundary

TICKET='c'*32
BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:123',sessionId='own-session',generation=4,targetFingerprint='3'*64)
POLICY=dict(source='world-render-target',marker=[4,4,132,36],subject=[0,48,160,144])


def pixels():
    image=Image.new('RGBA',(160,144),(128,128,128,255));image.paste(Image.open(io.BytesIO(marker_bytes(RUN,TICKET))).convert('RGBA'),(0,0));draw=ImageDraw.Draw(image)
    for y in range(48,144,12):
        for x in range(0,160,16):draw.rectangle((x,y,x+15,y+11),fill=(240,80,20,255) if (x//16+y//12)%2 else (20,80,210,255))
    raw=io.BytesIO();image.save(raw,format='PNG');return raw.getvalue()


class SnapshotRolesBoundary:
    """Reusable original-source capture producer; no public-state preset."""
    def __init__(self,root):
        self.root=Path(root);self.root.chmod(0o700);self.epoch=20000;self.clock=0.;self.raw=pixels();self.fault='';self.calls=[]
        self.vm,self.before,self.after=originals();self.vm.snapshot.epoch=self.epoch
        self.app=self.root/'app';self.app.mkdir(mode=0o700);self.producer=Producer(self.app);self.producer.epoch=18999;self.producer.outer='a'*32
        self.primary=self.owner('producer',False);self.primary.plan(RUN,'e2e-'+RUN)
        self.row,self.path=self.producer.capture();self.path.write_bytes(self.raw)
        self.row.update(bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),captureId='snap_19000_1')
        self.producer.body['captures'][0].update(captureId='snap_19000_1');self.producer.epoch=self.epoch
        self.after['snapshot']['source']['history']['events'][1]['path']=self.row['path']
        self.binding=self.primary.binding()
        def original_snapshot(value):
            value['instance']='a'*32;value['source']['scriptHistory']=deepcopy(self.after['snapshot']['source']['scriptHistory'])
        self.vm.snapshot.fault=original_snapshot;self.vm.snapshot.events=deepcopy(self.after['snapshot']['source']['history']['events'])
        send=self.vm.snapshot_reader.send
        def sample(request):self.vm.snapshot.epoch=self.epoch-10;send(request)
        self.vm.snapshot_reader.send=sample
        self.native_source=NativeBoundary()
        def native(value):value['processId']=31;account_source(value)
        self.native_source.mutate=native
        self.avatar_source=AvatarBoundary();self.touch_source=TouchBoundary();self.world_source=WorldBoundary()
        self.world_source.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,0,-2],orientation=[0,0,0,1],modelScale=1),absentIds=list(subject_ids(RUN).values()))
        self.lock=PhoneScriptSourceLock(self.root/'sources.lock');self.store=PrivateFeatureState(self.root/'feature.json')
        self.feature=SimpleNamespace(adapter=self,selector='synthetic',binding=BINDING,pid=31,root=self.root,run=RUN,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/',
            config=dict(imageExtent=[160,144],fileImagePolicy=POLICY),policy=POLICY,lock=self.lock,store=self.store,bound=lambda:True,
            state=dict(handoff=None,docArm=None,docBinding=None,consumerArm=None,consumerBinding=None,captureTicket=TICKET,cancelJobs=[],marker=None,phase='active'),
            phase=SimpleNamespace(status=lambda *_:self.phase(),provider=lambda:deepcopy(self.provider),epoch_ms=lambda:self.epoch),header_authority=lambda:True)
        seed=public_frame(self.after,self.producer.body,[]);self.provider=seed['provider'];self.provider.update(ticket=TICKET,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000)])
        self.system=seed['system'];self.upload_body=seed['upload'];self.readbacks_body=seed['readbacks']
        self.baseline=dict(group=self.before,native=self.native_reader().read(0,require_account=True),avatar=self.avatar_source.reader().read(),
            platform=self._snapshot_platform(None).read(),resolution=dict(component='android/android.ChooserActivity'),documentResolution=None)
        self.feature.monotonic=lambda:self.clock;self.feature.sleep=lambda seconds:setattr(self,'clock',self.clock+seconds)
        self.feature.original=lambda:deepcopy(self.baseline)
        self.feature.observer_files=lambda role,**kwargs:self.observer(role,**kwargs)
        self.feature.settings=lambda **_:SimpleNamespace(request=lambda *_:None)
        self.readback_sequence=0;self.upload_sequence=0
    def clean(self):
        """Explicit original native close/lease/file producers for actor tests."""
        from test_snapshot_settings import Boundary as Settings
        from overte_phone_snapshot_settings import PhoneSnapshotSettings
        from self_tests.test_native_script_work import WorkBoundary,activity
        from test_snapshot_os_retirement_source import boundary as Readbacks
        self.primary.retire();self.feature.state['phase']='cleaned';self.feature.state['partial']=False
        self.settings_source=Settings()
        def reader(read_only):
            source=self.settings_source
            def raw():
                value=json.loads(source.raw);value['processId']=31;return json.dumps(value)
            return PhoneSnapshotSettings(source.send,raw,lambda:self.epoch,lambda:True,31,read_only=read_only,monotonic=lambda:self.clock,sleep=lambda _:None)
        settings=reader(False);self.baseline['settings']=settings.request(RUN,'capture');last=settings.request(RUN,'observe')
        settings.request(RUN,'restore',restore_id='9'*32,expected_sha256=last['source']['currentSha256']);settings.request(RUN,'retire')
        def observe_settings(**kwargs):
            result=reader(True);result.restore_source(self.baseline['settings']);return result
        self.feature.settings=observe_settings
        self.readbacks_body=Readbacks().component;self.readbacks_body.update(sequence=1,capturedEpochMs=self.epoch,destinations=[],jobs=[],files=[],removedCopies=[])
        for key in ('osDestinations','shareGrants'):self.readbacks_body[key].update(rows=[],checkedEpochMs=self.epoch,checkId='6'*32)
        self.work_source=WorkBoundary();source=self.work_source
        source.member=deepcopy(self.vm.manager);source.code=deepcopy(self.vm.code)
        source.compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[deepcopy(self.vm.compilation)]);source.activity=[activity(5,signal_calls=1)]
        def work_packet(value):
            value['source']['compiled']=deepcopy(source.compiled)
            value['source']['work'].update(scriptWorkVersion=2,activity=deepcopy(source.activity),timerEntries=len(source.timers),activityEntries=len(source.activity))
        source.mutate=work_packet
        self._script_work=lambda *_args,**_kwargs:source.reader()
        def restored(*,snapshot):
            from overte_phone_snapshots_measurements import retired
            from adapters.native_phone_touch_state import released
            measurement=snapshot['measurement']
            retired(measurement['group'],measurement['captureFiles'],measurement['inventory'],measurement['readbacks'],measurement['upload'],measurement['settings'],run=RUN,epoch=self.epoch)
            released(snapshot['touch']);assert snapshot['nativeAfter']['account']['loggedIn'] is False
            assert snapshot['observerFilesRetirement']['retired'] and snapshot['scriptWork'] is not None
            return dict(snapshotSequence=measurement['group']['snapshot']['sequence'],nativeSequence=snapshot['nativeAfter']['sequence'],scriptWork=deepcopy(snapshot['scriptWork']),fileRetirement=deepcopy(snapshot['observerFilesRetirement']))
        self.feature.restored=restored

    def source(self,read_only):
        def read():
            value=json.loads(self.producer.read());value['processId']=31
            if self.fault=='files-pid':value['processId']=32
            return json.dumps(value)
        return PhoneSnapshotCaptureFileSource(self.producer.send,read,lambda:self.producer.epoch,lambda:True,31,read_only=read_only,monotonic=lambda:self.clock,sleep=lambda _:None)
    def owner(self,role,read_only):
        root=self.root/(role+'-files');root.mkdir(mode=0o700,exist_ok=True);transport=LocalTransport(self.app,root)
        return PhoneSnapshotCaptureFiles(transport,self.source(read_only),BINDING,self.root/(role+'-files.json'),read_only=read_only)
    def observer(self,role,*,handoff_source=None):
        if handoff_source is None:owner=self.owner(role,True)
        else:
            from overte_phone_snapshot_system_files import SnapshotSystemFileSource
            root=self.root/(role+'-files');root.mkdir(mode=0o700,exist_ok=True)
            owner=PhoneSnapshotCaptureFiles(LocalTransport(self.app,root),SnapshotSystemFileSource(handoff_source),BINDING,self.root/(role+'-files.json'),read_only=True)
        owner.attach(self.binding);return owner
    def system_mode(self):
        from test_snapshot_handoff import Boundary as HandoffBoundary
        from overte_phone_snapshot_handoff import PhoneSnapshotHandoff
        native=HandoffBoundary();native.group=deepcopy(self.after)
        for packet in native.group.values():packet.update(requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
        def raw():
            value=native.frame();batch=value['source']['source']
            self.producer.sequence+=1;self.producer.body.update(sequence=self.producer.sequence,capturedEpochMs=self.epoch)
            batch['captureFiles']=dict(schemaVersion=1,requestId=uuid.uuid4().hex,runId=RUN,instance='a'*32,sequence=self.producer.sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,accepted=True,source=deepcopy(self.producer.body))
            self.vm.scripts.sequence=batch['group']['script']['sequence'];self.vm.roots.sequence=batch['group']['rootsAfter']['sequence'];self.vm.snapshot.sequence=batch['group']['snapshot']['sequence']
            return json.dumps(value)
        self.feature.state['handoff']=dict(id=native.owner['handoffId'],kind='share',resolution=self.baseline['resolution'],binding=native.owner,sourceIndex=1)
        self._snapshot_handoff_source=lambda *_:PhoneSnapshotHandoff(raw,lambda:self.epoch,lambda:True,native.owner,monotonic=lambda:self.clock,sleep=lambda _:None)
        self._snapshot_system_platform=lambda *_:self._snapshot_platform(None)
        self.passive=native

    def phase(self):return dict(active=True,activations=[dict(ticket=TICKET,stimulus=dict(verb='capture'))])
    def native_reader(self):
        source=self.native_source
        return NativeFeatureObservation(source.send,source.original,lambda:self.epoch,source.guard,31,monotonic=lambda:self.clock,sleep=lambda _:None)
    def _native_feature_observer(self,*_,**kwargs):self.calls.append('native');assert kwargs==dict(read_only=True);return self.native_reader()
    def _snapshot_measurements(self,*_):self.calls.append('measurements');return self.vm.reader
    def _avatar_render_observer(self,*_,**kwargs):self.calls.append('avatar');assert kwargs==dict(read_only=True);return self.avatar_source.reader()
    def _graphics_subject_observer(self,*_,**kwargs):self.calls.append('world');assert kwargs==dict(read_only=True);return self.world_source.reader()
    def _touch_state_observer(self,*_,**kwargs):self.calls.append('touch');assert kwargs==dict(read_only=True);return self.touch_source.reader()
    def _create_fixture_observer(self,*_,**kwargs):return SimpleNamespace(read=lambda *_:None)
    def _snapshot_readbacks(self,*_,**kwargs):
        assert kwargs==dict(read_only=True);return SimpleNamespace(last=None,request=lambda *_:self.readback())
    def readback(self):
        self.readback_sequence+=1
        return dict(schemaVersion=1,requestId=uuid.uuid4().hex,runId=RUN,instance='a'*32,sequence=self.readback_sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=dict(accepted=False,source=deepcopy(self.readbacks_body)))
    def _snapshot_upload_source(self,*_):return SimpleNamespace(last=None,read=lambda *_:self.upload())
    def upload(self):
        self.upload_sequence+=1
        return dict(schemaVersion=1,requestId=uuid.uuid4().hex,runId=RUN,instance='a'*32,sequence=self.upload_sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.upload_body))
    def _snapshot_platform(self,*_):return PhoneSnapshotPlatform(lambda:'29',lambda:True,lambda:self.epoch,monotonic=lambda:self.clock)
    def _snapshot_share_ui(self,*_):return SimpleNamespace(capture=lambda:deepcopy(self.system))
    @contextmanager
    def role(self,role='primary'):
        with self.lock.held():yield PhoneSnapshotsRole(self.feature,role)


class SnapshotsRoleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='snapshot-roles-');self.addCleanup(self.temp.cleanup);self.boundary=SnapshotRolesBoundary(self.temp.name)
    def test_real_source_readers_actual_png_inodes_and_closed_state_archive_survive_reconstruction(self):
        b=self.boundary
        with b.role() as role:
            measured=role.read(0);self.assertEqual(1,measured['state']['files']);self.assertEqual(['pending','complete'],measured['state']['captureHistory'])
            file=next(row for row in measured['artifacts'] if row['kind']=='file');self.assertEqual('snapshot-private-original',file['source'])
            record=role.frames[-1]['binaries'][0];self.assertEqual(b.raw,SnapshotsBinary.archive(b.root,record));self.assertEqual(b.row['inode'],record['acquisition']['inode'])
        with b.role() as role:
            second=role.read(measured['sequence']);self.assertEqual(2,second['sequence']);self.assertEqual(2,len(role.frames))
            self.assertEqual(19000,role.frames[-1]['binaries'][0]['acquisition']['nativeClosedEpochMs'])
    def test_actor_acquires_its_own_binary_and_cannot_reuse_primary_inode(self):
        b=self.boundary
        with b.role() as role:role.read(0);primary=role.frames[-1]['binaries'][0]
        with b.role('actor') as role:
            role.read(0);actor=role.frames[-1]['binaries'][0]
            self.assertNotEqual(primary['file'],actor['file']);self.assertNotEqual(primary['name'],actor['name']);self.assertEqual(b.raw,SnapshotsBinary.archive(b.root,actor))
    def test_matching_foreign_original_inode_or_changed_actual_bytes_cannot_be_acquired(self):
        b=self.boundary;b.path.rename(str(b.path)+'.foreign');b.path.write_bytes(b.raw)
        with b.role() as role,self.assertRaises(NativeUIError):role.read(0)
        self.assertEqual(b.raw,b.path.read_bytes())
    def test_archive_replacement_same_bytes_missing_png_or_missing_binary_stays_red(self):
        b=self.boundary
        with b.role() as role:role.read(0);record=role.frames[-1]['binaries'][0]
        path=b.root/record['name'];replacement=b.root/'foreign';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError),b.role() as role:role.retire()
    def test_fresh_clock_cannot_hide_original_vm_history_rollback_after_restart(self):
        b=self.boundary
        with b.role() as role:role.read(0)
        b.vm.snapshot.events=[]
        with b.role() as role,self.assertRaises(NativeUIError):role.read(1)
    def test_partial_open_binary_is_a_retained_cleanup_obligation(self):
        b=self.boundary
        with b.role() as role:
            original=role.binary_intent
            def fail(value):
                result=original(value)
                if value['phase']=='opened':raise NativeUIError('Explicit lost host publication response')
                return result
            role.binary_intent=fail
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual('reading',role.state['phase']);self.assertEqual('opened',role.state['pending']['binaries'][0]['phase'])
            role.binary_intent=original;role.recover()
            self.assertEqual('ready',role.state['phase']);self.assertEqual('saved',role.frames[-1]['binaries'][0]['phase'])
            self.assertEqual(b.raw,SnapshotsBinary.archive(b.root,role.frames[-1]['binaries'][0]))

    def test_passive_handoff_retains_all_intermediate_groups_and_never_constructs_a_foreground_reader(self):
        b=self.boundary;b.system_mode();before=len(b.producer.sent)
        with b.role() as role:
            measured=role.read(0);self.assertEqual(1,measured['state']['files']);self.assertGreater(len(role.frames[-1]['handoffOriginals']),4)
        self.assertFalse(b.calls);self.assertEqual(before,len(b.producer.sent));self.assertFalse(b.passive.commands)
        with b.role() as role:
            value=role.read(1);self.assertEqual(2,value['sequence']);self.assertGreater(role.frames[-1]['handoffOriginals'][0]['source']['sequence'],role.frames[-2]['handoffOriginals'][-1]['source']['sequence'])
    def test_resume_from_passive_handoff_keeps_original_vm_native_and_files_floors(self):
        b=self.boundary;b.system_mode()
        with b.role() as role:role.read(0)
        b.feature.state['handoff']=None
        with b.role() as role:
            observed=role.read(1);self.assertEqual(2,observed['sequence']);self.assertEqual(1,observed['state']['files'])
            self.assertIsNotNone(role.frames[-1]['nativeAfter']);self.assertFalse(role.frames[-1]['handoffOriginals'])
    def test_documents_own_original_history_outlives_the_initial_empty_primary_floor(self):
        from test_snapshot_documents import Boundary as Documents,ARM
        b=self.boundary;source=Documents();originals=(source.row['plans'],source.row['documents'],source.row['fdLifetimes'])
        source.row.update(plans=[],documents=[],fdLifetimes=[])
        primary=source.reader();primary.observe();binding=primary.binding()
        b.feature.state.update(docArm=ARM,docBinding=binding);b.feature.documents=lambda **_:source.reader(True,binding)
        with b.role() as role:
            role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
            role.save();source.row.update(plans=originals[0],documents=originals[1],fdLifetimes=originals[2]);role.documents.observe()
            role.finish_archive(dict(diagnostic=True,documentOriginals=deepcopy(role.state['pending']['work']['documentOriginals']),binaries=[]))
        source.row.update(plans=[],documents=[],fdLifetimes=[],retired=True,workersTerminated=True);source.root['present']=False
        with b.role() as role,self.assertRaises(NativeUIError):role.documents.require_retired()
    def test_world_and_touch_source_births_remain_pinned_after_role_reconstruction(self):
        for key in ('world','touch'):
            with self.subTest(key=key):
                temporary=tempfile.TemporaryDirectory(prefix='snapshot-birth-');self.addCleanup(temporary.cleanup);b=SnapshotRolesBoundary(temporary.name)
                with b.role() as role:role.read(0)
                source=b.world_source if key=='world' else b.touch_source
                source.edit=lambda value:value.update(instance='9'*32)
                with b.role() as role,self.assertRaises(NativeUIError):role.read(1)
    def test_current_script_work_sequence_and_retired_settings_cannot_rollback_after_restart(self):
        for fault in ('work','settings'):
            with self.subTest(fault=fault):
                temporary=tempfile.TemporaryDirectory(prefix='snapshot-quiet-floors-');self.addCleanup(temporary.cleanup);b=SnapshotRolesBoundary(temporary.name);b.clean()
                with b.role() as role:
                    measured=role.read(0);self.assertEqual([],measured['resources']);self.assertTrue(role.frames[-1]['observerFilesRetirement']['retired'])
                if fault=='work':b.work_source.sequence=0
                else:b.settings_source.retired=False
                with b.role() as role,self.assertRaises(NativeUIError):role.read(1)
    def test_saved_original_and_planned_manifest_resume_without_another_target_acquisition(self):
        b=self.boundary
        with b.role() as role:
            original=role.storage_intent
            def fail(kind,value):
                result=original(kind,value)
                if kind=='manifest' and value['phase']=='planned':raise NativeUIError('Explicit lost manifest publication response')
                return result
            role.originals.intent=fail
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual('saved',role.state['pending']['original']['phase'])
            calls=len(b.vm.snapshot.calls)
        with b.role() as role:
            role.recover();self.assertEqual(1,role.state['sequence']);self.assertEqual(1,len(role.frames))
            self.assertEqual(calls,len(b.vm.snapshot.calls));self.assertEqual(1,role.frames[-1]['state']['files'])
    def test_native_owner_retires_target_and_role_retires_only_its_own_copies_idempotently(self):
        b=self.boundary
        with b.role() as role:
            role.read(0);b.primary.retire();unlinks=b.producer.unlinks
            role.retire();role.retire();self.assertEqual('retired',role.state['phase']);self.assertEqual(1,unlinks);self.assertEqual(unlinks,b.producer.unlinks)
            self.assertTrue(all(row['phase']=='saved' for row in role.frames[-1]['binaries']))
            self.assertTrue(all((b.root/row['name']).exists() for row in role.frames[-1]['binaries']))
        late=b.root/'snapshots-primary-transfer-foreign';late.mkdir(mode=0o700)
        with b.role() as role,self.assertRaises(NativeUIError):role.retire()
    def test_png_original_file_is_rechecked_before_any_resumed_native_acquisition(self):
        from test_graphics_measurements import Sources
        b=self.boundary;source=Sources()
        with b.role() as role:
            role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
            role.save();value=role.image_engine().write(TICKET,source.capture,source.pixels)
            role.finish_archive(dict(diagnostic=True,image=value,binaries=[]));path=b.root/value['name']
        path.unlink();before=len(b.calls)
        with self.assertRaises(NativeUIError),b.role():pass
        self.assertEqual(before,len(b.calls))
    def test_transfer_unlink_interruption_resumes_only_exact_original_inode_and_rejects_replacement(self):
        b=self.boundary
        with b.role() as role:
            role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}))
            role.save();root=b.root/'snapshots-primary-transfer-1';root.mkdir(mode=0o700);info=root.stat();path=root/'original.bin';path.write_bytes(b.raw);path.chmod(0o600);file=path.stat()
            transfer=dict(name=root.name,phase='owned',root=dict(device=info.st_dev,inode=info.st_ino),files=[dict(name=path.name,device=file.st_dev,inode=file.st_ino,bytes=len(b.raw),sha256=hashlib.sha256(b.raw).hexdigest())])
            role.checkpoint(transfer=transfer);unlink=Path.unlink
            def lost(path,*args,**kwargs):
                result=unlink(path,*args,**kwargs)
                if path.name=='original.bin':raise OSError('Explicit loss after actual unlink')
                return result
            with patch.object(Path,'unlink',lost),self.assertRaises(OSError):role.retire_transfer(transfer)
            self.assertEqual('deleting',role.state['pending']['work']['transfer']['phase']);self.assertFalse(path.exists())
            role.retire_transfer(role.state['pending']['work']['transfer']);self.assertFalse(root.exists())
            self.assertEqual('removed',role.state['pending']['work']['transfer']['phase'])

if __name__=='__main__':unittest.main()
