"""Actual Pico factory/normal transport/file scripts; JNI and OS provider seams.

Native QML/JNI and original Java owners have separate compiler/host checks.
This composition creates and hashes independent real files but is not a device
run, an Android MediaStore run or whole Snapshot acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
import test_snapshot_cancel_owner as prefix
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.snapshot_exports import FILE as EXPORT_FILE
from adapters.pico4.snapshot_export_originals import IDENTITY
from adapters.script_journey.history import pack,unpack
from self_tests.test_pico_snapshot_save_owner import SnapshotSaveAdmissionTests,SnapshotSaveEnvelopeTests,SnapshotSaveFenceTests,SnapshotSaveOriginalsTests,SnapshotSavePreparationRecoveryTests,SnapshotSaveAcquisitionTests,SnapshotOriginalFrameMemoTests,SnapshotSavePublicationTests


class ExportProviderBoundary:
    """Explicit JNI/provider model backed by new real files, never wanted facts."""
    def __init__(self,host):
        self.h=host;self.sequence=0;self.events=[];self.initialized=False;self.body=None;self.last=None
        self.handle='42';self.ticket=0;self.saves=0;self.reads=0;self.inspections=0;self.ignore=False;self.lose_save=False;self.lose_read=False
        self.destination=None;self.source=None
    def epoch(self):return self.h.clock()
    def event(self,identity,kind,value='',auxiliary=''):
        self.events.append(dict(identity,kind=kind,value=value,auxiliary=auxiliary,sequence=len(self.events)+1,
            capturedEpochMs=self.epoch(),elapsedMs=round(self.h.adb.clock*1000)))
    def initialize(self):
        self.initialized=True
        self.body=dict(snapshotExportReadbacksVersion=2,instance='4'*32,sequence=0,elapsedMs=0,complete=True,copiesRetired=False,capturedEpochMs=self.epoch(),workersTerminated=False,
            destinations=[],jobs=[],files=[],removedCopies=[],osDestinations=dict(snapshotOsDestinationsVersion=3,complete=True,pending=0,checkId='',checkedEpochMs=0,rows=[]),
            shareGrants=dict(snapshotShareGrantsVersion=1,complete=True,checkId='',checkedEpochMs=0,rows=[]))
    def save(self,command):
        self.saves+=1
        if self.ignore:return
        self.initialize();self.ticket+=1;file=self.h.owner.state['capture']['file'];self.source=self.h.adb.files/Path(file['path']).name
        identity=dict(request=uuid.uuid4().hex,handle=self.handle,ticket=str(self.ticket),generation='7',action='save',source=file['path'])
        self.event(identity,'request-active');uri='content://media/external/images/media/'+str(self.saves)
        provider=self.h.adb.app/'independent-media-provider';provider.mkdir(mode=0o700,exist_ok=True);self.destination=provider/Path(file['path']).name
        # The provider row and all digests come from these original new files.
        # The JNI and Android owner/UID are explicitly synthetic boundaries.
        descriptor=os.open(self.destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        self.event(identity,'destination-created',uri)
        with os.fdopen(descriptor,'wb') as output,self.source.open('rb') as original:
            while data:=original.read(65536):output.write(data)
            output.flush();os.fsync(output.fileno())
        self.event(identity,'destination-copied',uri);self.event(identity,'destination-published',uri,'1')
        info=self.destination.stat();content=self.destination.read_bytes();request=identity['request']
        self.body['destinations']=[dict(request=request,uri=uri,inserted=True,published=True)]
        self.body['osDestinations']['rows']=[dict(request=request,inserted=True,phase='qualified',identity=dict(uri=uri,providerUid=99,ownerPackage='org.overte.pico',
            displayName=self.destination.name,device=info.st_dev,inode=info.st_ino),original=dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest()),
            acquiredEpochMs=self.epoch(),verifiedEpochMs=self.epoch(),deleteId='',deleteIssued=False,deleteCount=-1,checkedEpochMs=0,absent=False)]
        self.event(identity,'result-ready','success');self.event(identity,'delivered','success')
        if self.lose_save:raise RuntimeError('Explicit lost original Save transport return')
    def query(self,request):
        self.sequence+=1;operation=request['operation']
        if operation=='read':
            self.reads+=1;self.assert_destination();id=request['resourceId'];export=request['exportRequest']
            directory=self.h.adb.app/'files'/('overte-snapshot-e2e-'+prefix.RUN);directory.mkdir(mode=0o700,exist_ok=True)
            copy=uuid.uuid4().hex;target=directory/(copy+'.bin');descriptor=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(descriptor,'wb') as output,self.destination.open('rb') as original:
                while data:=original.read(65536):output.write(data)
                output.flush();os.fsync(output.fileno())
            content=target.read_bytes();original=dict(id=copy,request=export,path='/data/user/0/org.overte.pico/files/'+directory.name+'/'+target.name,
                phase='complete',bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),capturedEpochMs=self.epoch())
            self.body['files']=[original];self.body['jobs']=[dict(id=id,request=export,phase='complete',startedEpochMs=self.epoch(),completedEpochMs=self.epoch(),original=deepcopy(original))]
        elif operation=='inspect-destinations':
            self.inspections+=1;self.assert_destination();os_source=self.body['osDestinations'];os_source['checkId']=request['resourceId'];os_source['checkedEpochMs']=self.epoch()
            for row in os_source['rows']:row.update(checkedEpochMs=self.epoch(),verifiedEpochMs=self.epoch())
        else:assert operation=='observe'
        events=dict(snapshotExportObservationVersion=2,instance='5'*32,complete=True,capturedEpochMs=self.epoch(),elapsedMs=round(self.h.adb.clock*1000),
            sequence=len(self.events),activeRequest='',pendingIo=[],events=deepcopy(self.events))
        if self.initialized:
            self.body.update(sequence=self.sequence,capturedEpochMs=self.epoch(),elapsedMs=round(self.h.adb.clock*1000));copies=dict(accepted=True,source=deepcopy(self.body))
        else:copies=dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True))
        self.last=dict(picoSnapshotExportsVersion=1,requestId=request['commandId'],runId=request['runId'],instance='6'*32,sequence=self.sequence,processId=123,
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),lease=dict(present=True,componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml',
            native=dict(snapshotExportLeaseVersion=1,handle=self.handle,ticket='',busy=False)),exportsRaw=json.dumps(events),readbacksRaw=json.dumps(copies))
        if operation=='read' and self.lose_read:raise RuntimeError('Explicit lost original read publication return')
    def assert_destination(self):
        info=self.destination.stat();row=self.body['osDestinations']['rows'][0];content=self.destination.read_bytes()
        if ((info.st_dev,info.st_ino)!=(row['identity']['device'],row['identity']['inode'])
                or dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest())!=row['original']):
            self.body['complete']=self.body['osDestinations']['complete']=False


class SnapshotSaveFlowTests(unittest.TestCase):
    def setUp(self):
        self.h=prefix.SnapshotCancelOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.boundary=ExportProviderBoundary(self.h);self.write=self.h.adb.write_debug_app_file;self.read=self.h.adb.read_debug_app_file;self.snapshot=self.h.adb.snapshot
        prop=self.h.adb.prop
        def sdk(target,name):return '34' if name=='ro.build.version.sdk' else prop(target,name)
        for change in (patch.object(self.h.adb,'prop',side_effect=sdk),patch.object(self.h.adb,'write_debug_app_file',side_effect=self.send),
                patch.object(self.h.adb,'read_debug_app_file',side_effect=self.receive),patch.object(self.h.adb,'snapshot',side_effect=self.view)):
            change.start();self.addCleanup(change.stop)
    def view(self):
        value=self.snapshot();value['snapshotExportControlsVersion']=1
        if self.h.adb.screen=='snapshot':
            for path in self.h.adb.files.glob('*.png'):
                original='/data/user/0/org.overte.pico/files/Snapshots/'+path.name
                value['controls'].append(dict(id='snapshot.save.'+hashlib.sha256(original.encode()).hexdigest(),path=original,
                    token='33333333-3333-4333-8333-000000000077',enabled=True,focused=False,inputReady=True,
                    profile='native-pico-snapshot-export-v1',componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml'))
        return value
    def send(self,target,package,path,raw):
        value=json.loads(raw)
        if value.get('action')=='feature-pico-snapshot-exports':self.boundary.query(value);return
        if value.get('controlId','').startswith('snapshot.save.'):
            assert value['sequence']==self.h.adb.sequence+1;self.h.adb.sequence+=1;self.h.adb.inputs.append(deepcopy(value))
            self.boundary.save(value)
            self.h.adb.status=dict(schemaVersion=1,bridgeId=self.h.adb.bridge_id,commandId=value['commandId'],sequence=value['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.h.clock());return
        return self.write(target,package,path,raw)
    def receive(self,target,package,path,**options):
        if path.endswith('/'+EXPORT_FILE):return json.dumps(self.boundary.last)
        return self.read(target,package,path,**options)
    def ready(self):
        self.h.cancelled();self.h.owner.quiet();self.h.owner.retire_job();self.h.activate('capture',dict(mode='still',format='png'))
        self.h.owner.capture_still();self.h.owner.quiet_still();self.h.activate('save')
        return self.make(parent=self.h.owner)
    def make(self,**options):
        owner=self.h.adapter._snapshot_save_owner(self.h.adb.target,prefix.RUN,self.h.phase,source_lock=self.h.lock,**options)
        owner.exports.monotonic=lambda:self.h.adb.clock;owner.exports.sleep=self.h.adb.sleep;return owner
    def test_normal_cancel_still_save_independent_provider_png_and_current_original_quiet(self):
        owner=self.ready();self.assertEqual('prepared',owner.prepare()['stage']);self.assertEqual('exported',owner.send()['stage'])
        self.assertEqual('acquired',owner.start_read()['stage']);report=owner.quiet();self.assertEqual('partial-ready',report['stage'])
        self.assertFalse(report['fullSnapshotRecipe']);self.assertFalse(report['deviceAcceptance']);self.assertFalse(report['productExportExecutorRetired'])
        self.assertEqual(1,self.boundary.saves);self.assertEqual(1,self.boundary.reads);self.assertGreaterEqual(self.boundary.inspections,13)
        self.assertTrue(owner.store.path.exists());self.assertTrue(owner.parent.store.path.exists());self.assertTrue(self.boundary.destination.exists())
        original=owner.parent.state['capture']['file'];saved=owner.state['saved']['file'];self.assertEqual(original['sha256'],saved['sha256'])
        self.assertEqual(self.boundary.destination.read_bytes(),owner.host_read(owner.state['artifacts'][saved['copy']]))
        before=(len(self.h.adb.inputs),self.boundary.saves,self.boundary.reads,self.boundary.inspections);cold=self.make()
        self.assertEqual(report,cold.report());self.assertEqual(before,(len(self.h.adb.inputs),self.boundary.saves,self.boundary.reads,self.boundary.inspections))
        with self.assertRaises((ValueError,RuntimeError)):cold.send()


class SnapshotSaveFactoryTests(unittest.TestCase):
    def fixture(self):
        fixture=prefix.SnapshotCancelOwnerTests();fixture.setUp();self.addCleanup(fixture.doCleanups);return fixture
    def test_actual_factory_refuses_an_unfinished_parent_without_an_export_query_or_another_normal_input(self):
        fixture=self.fixture();before=len(fixture.adb.inputs);writer=fixture.adb.write_debug_app_file
        def refuse_export(target,package,path,raw):
            if json.loads(raw).get('action')=='feature-pico-snapshot-exports':raise AssertionError('Export query before owned Still')
            return writer(target,package,path,raw)
        with patch.object(fixture.adb,'write_debug_app_file',side_effect=refuse_export),self.assertRaises((ValueError,RuntimeError)):
            fixture.adapter._snapshot_save_owner(fixture.adb.target,prefix.RUN,fixture.phase,parent=fixture.owner)
        self.assertEqual(before,len(fixture.adb.inputs));self.assertIsNone(fixture.owner.save_owner)
        self.assertFalse(fixture.lock.path.with_name('snapshot-save-owner.json').exists())
    def test_original_save_manifest_or_chunk_alone_blocks_public_input_and_base_cleanup(self):
        fixture=self.fixture()
        for name in ('snapshot-save-originals.json','snapshot-save-originals.json.frame-000.json'):
            path=fixture.lock.path.with_name(name);path.write_text('{}');path.chmod(0o600)
            try:
                self.assertTrue(fixture.adapter._snapshot_originals_owned(fixture.adb.target))
                with patch.object(fixture.adb,'write_debug_app_file',side_effect=AssertionError('Orphan input')):
                    with self.assertRaises((ValueError,RuntimeError)):fixture.adapter.invoke(fixture.adb.target,'snapshot.open',{})
            finally:path.unlink()


if __name__=='__main__':unittest.main()
