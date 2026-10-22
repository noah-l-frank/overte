"""Closed effect joins on explicit synthetic native/VM/Android boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from test_snapshot_capture_facts import originals,RUN
from test_snapshot_capture_source import Boundary as Files
from test_snapshot_os_retirement_source import boundary as Readbacks
from test_snapshot_consumer_source import Boundary as Consumer,ARM
from test_snapshot_settings import Boundary as Settings
from overte_phone_snapshots_measurements import capture,saved,shared,inventory,retired,state,SnapshotPending


def completed():
    vm,before,after=originals();file=Files().source;file.update(sequence=1,capturedEpochMs=20000)
    path=after['snapshot']['source']['history']['events'][1]['path'];id=after['snapshot']['source']['scriptHistory']['events'][0]['id']
    plan=file['plans'][0];plan.update(runId=RUN,prefix='e2e-'+RUN,checkedEpochMs=18900)
    file['captures'][0].update(captureId=id,beganEpochMs=19000,terminalPath=path,terminalEpochMs=19000)
    row=file['rows'][0];row.update(runId=RUN,captureId=id,path=path,createdEpochMs=19000,closedEpochMs=19000)
    acquisition=dict(source='snapshot-capture-original',path=path,captureId=id,bytes=row['bytes'],sha256=row['sha256'],
        device=row['device'],inode=row['inode'],artifact='actual-copy.bin',capturedEpochMs=19000,nativeClosedEpochMs=19000,fileId=row['id'])
    return before,after,file,acquisition


def callbacks(group,action,request,path,rows):
    export=group['snapshot']['source']['androidExport'];export.update(sequence=len(rows),activeRequest='',pendingIo=[])
    export['events']=[dict(sequence=index,kind=kind,request=request,handle='1',ticket='2',generation='1',action=action,source=path,
        value=value,auxiliary='',capturedEpochMs=19000,elapsedMs=0) for index,(kind,value) in enumerate(rows,1)]


def saved_original():
    before,after,file,acquisition=completed();captured=capture(after,before,file,acquisition,run=RUN,pid=31,epoch=20000)
    readback=Readbacks().component;readback.update(sequence=1,capturedEpochMs=20000,copiesRetired=False,workersTerminated=False,removedCopies=[])
    job=readback['jobs'][0];original=deepcopy(job['original']);original.update(bytes=captured['bytes'],sha256=captured['sha256'],capturedEpochMs=19000)
    readback['files']=[original];job.update(original=original,startedEpochMs=19000,completedEpochMs=19000)
    destination=readback['osDestinations']['rows'][0];destination['identity']['displayName']=Path(captured['path']).name;destination.update(phase='qualified',deleteId='',deleteIssued=False,deleteCount=-1,absent=False,checkedEpochMs=0,acquiredEpochMs=19000,
        original={key:captured[key] for key in ('bytes','sha256')})
    request=job['request'];callbacks(after,'save',request,captured['path'],[('request-active',''),('destination-created',readback['destinations'][0]['uri']),('destination-copied',readback['destinations'][0]['uri']),('destination-published',readback['destinations'][0]['uri']),('result-ready','success'),('delivered','success')]);after['snapshot']['source']['androidExport']['events'][3]['auxiliary']='1'
    acquired=dict(source='snapshot-saved-original',request=request,job=job['id'],copy=original['id'],bytes=original['bytes'],sha256=original['sha256'],capturedEpochMs=19000)
    return before,after,readback,acquired,captured


def shared_original():
    before,after,file,acquisition=completed();captured=capture(after,before,file,acquisition,run=RUN,pid=31,epoch=20000)
    boundary=Consumer();boundary.epoch=20000;boundary.original.update(bytes=captured['bytes'],sha256=captured['sha256'],capturedEpochMs=19000)
    boundary.source.update(runId=RUN,original=deepcopy(boundary.original),files=[deepcopy(boundary.original)],startedEpochMs=19000,completedEpochMs=19001)
    reader=boundary.reader();consumer=reader.observe();binding=reader.binding()
    readback=Readbacks().component;readback.update(sequence=1,capturedEpochMs=20000,destinations=[],jobs=[],files=[],removedCopies=[])
    readback['osDestinations']['rows']=[];readback['shareGrants']['rows']=[boundary.native];boundary.native['checkedEpochMs']=20000
    callbacks(after,'share',boundary.native['request'],captured['path'],[('request-active',''),('share-uri',boundary.native['uri']),
        ('share-chosen',boundary.native['component']),('result-ready','success'),('delivered','success')])
    acquired=dict(source='snapshot-receiver-original',request=boundary.native['request'],copy=boundary.original['id'],bytes=captured['bytes'],sha256=captured['sha256'],capturedEpochMs=19001)
    return before,after,readback,consumer,binding,acquired,captured


def public_frame(group,files,acquisitions,readback=None):
    import hashlib
    row=files['rows'][0];absent=row['absent']
    actual=dict(files=[] if absent else [dict(basename=Path(row['path']).name,**{key:row[key] for key in ('device','inode','bytes','uid','links','sha256')})],
        rows=deepcopy(files['rows']),capturedEpochMs=20000)
    provider=dict(snapshotUploadServiceVersion=1,instance='1'*32,runId=RUN,requestId='2'*32,capturedEpochMs=20000,
        domainId='12345678-1234-1234-1234-123456789012',origin='https://127.0.0.1:12345',active=True,ticket='3'*32,
        activations=[dict(ticket='3'*32,verb='capture',capturedEpochMs=19000)],inflight=0,held=False,failedResponses=0,foreignRequests=0,lateRequests=0,requests=[],uploads=0,stories=0)
    xml='<hierarchy><node package="io.github.noah_be.overte.phone" displayed="true" /></hierarchy>'
    return dict(group=group,captureFiles=files,inventory=actual,
        readbacks=readback or dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True),
        upload=dict(snapshotUploadObservationVersion=1,instance='7'*32,complete=True,capturedEpochMs=20000,sequence=0,events=[],jobs=[]),
        provider=provider,platform=dict(requestedEpochMs=20000,capturedEpochMs=20000,source=dict(snapshotAndroidPlatformVersion=1,sdk=29,saveBackend='media-store',savePermission='not-required')),
        system=dict(snapshotSystemUiVersion=1,observationId='4'*32,component='io.github.noah_be.overte.phone/org.overte.Phone',requestedEpochMs=20000,capturedEpochMs=20000,sourceSha256=hashlib.sha256(xml.encode()).hexdigest(),xml=xml),
        resolution=None,consumer=None,consumerBinding=None,acquisitions=acquisitions,cancels=[],settings=None,documents=None,documentsBinding=None,phoneUid=None,documentResolution=None)


class SnapshotsMeasurementsTests(unittest.TestCase):
    def test_capture_requires_original_vm_native_fd_and_independently_acquired_inode(self):
        before,after,files,acquisition=completed();proof=capture(after,before,files,acquisition,run=RUN,pid=31,epoch=20000)
        self.assertEqual(acquisition['sha256'],proof['sha256']);self.assertNotIn('capturedEpochMs',proof)
        for field,value in (('source','snapshot-upload-original'),('captureId','foreign'),('fileId','f'*32),('sha256','f'*64),('inode',999)):
            changed=dict(acquisition,**{field:value})
            with self.subTest(field=field),self.assertRaises(NativeUIError):capture(after,before,files,changed,run=RUN,pid=31,epoch=20000)
        for fault in ('live','foreign','sealed','replaced','missing-native'):
            changed=deepcopy(files)
            if fault=='live':changed['rows'][0].update(closed=False,phase='writing',closedEpochMs=0)
            elif fault=='foreign':changed['plans'][0]['runId']=changed['rows'][0]['runId']='f'*32
            elif fault=='sealed':changed['plans'][0].update(sealed=True,sealId='1'*32,sealedEpochMs=19000)
            elif fault=='replaced':changed['rows'][0]['inode']+=1
            else:changed['captures'][0]['terminal']='error'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):capture(after,before,changed,acquisition,run=RUN,pid=31,epoch=20000)

    def test_save_is_not_a_callback_ack_without_actual_os_destination_and_readback(self):
        before,after,readback,acquired,captured=saved_original()
        self.assertEqual(acquired['request'],saved(after['snapshot'],before['snapshot'],readback,acquired,captured,epoch=20000)['request'])
        for fault in ('not-delivered','wrong-action','wrong-path','unpublished','removed','open-job','changed-bytes','foreign-copy','old-current'):
            a,b,c=deepcopy(after),deepcopy(readback),deepcopy(acquired)
            if fault=='not-delivered':a['snapshot']['source']['androidExport']['events'].pop()
            elif fault=='wrong-action':a['snapshot']['source']['androidExport']['events'][0]['action']='share'
            elif fault=='wrong-path':a['snapshot']['source']['androidExport']['events'][0]['source']+='foreign'
            elif fault=='unpublished':b['destinations'][0]['published']=False
            elif fault=='removed':b['osDestinations']['rows'][0]['phase']='retired'
            elif fault=='open-job':b['jobs'][0]['phase']='reading'
            elif fault=='changed-bytes':c['sha256']='f'*64
            elif fault=='foreign-copy':c['copy']='f'*32
            else:b['capturedEpochMs']=18000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):saved(a['snapshot'],before['snapshot'],b,c,captured,epoch=20000)

    def test_share_requires_separate_consumer_uid_fd_copy_and_actual_chosen_callback(self):
        before,after,readback,consumer,binding,acquired,captured=shared_original()
        self.assertEqual(acquired['copy'],shared(after['snapshot'],before['snapshot'],readback,consumer,binding,acquired,captured,run=RUN,arm=ARM,epoch=20000)['copy'])
        for fault in ('ack-only','foreign-instance','foreign-uid','open-fd','no-choice','changed-uri','changed-bytes','old-current'):
            a,b,c=deepcopy(after),deepcopy(readback),deepcopy(consumer)
            if fault=='ack-only':c.update(phase='armed',identity=None,original=None,files=[],startedEpochMs=0,completedEpochMs=0)
            elif fault=='foreign-instance':c['instance']='f'*32
            elif fault=='foreign-uid':b['shareGrants']['rows'][0]['receiverUid']+=1
            elif fault=='open-fd':c['originalClosed']=False
            elif fault=='no-choice':a['snapshot']['source']['androidExport']['events'][2]['value']='foreign.package/foreign.Activity'
            elif fault=='changed-uri':b['shareGrants']['rows'][0]['uri']='content://io.github.noah_be.overte.phone.snapshot.files/snapshots/foreign.png'
            elif fault=='changed-bytes':c['original']['sha256']='f'*64
            else:c['capturedEpochMs']=18000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):shared(a['snapshot'],before['snapshot'],b,c,binding,acquired,captured,run=RUN,arm=ARM,epoch=20000)

    def test_historical_completions_are_not_retimed_or_subject_to_a_static_metadata_expiry(self):
        before,after,readback,acquired,captured=saved_original();self.assertEqual(19000,acquired['capturedEpochMs'])
        readback['capturedEpochMs']=100000;after['snapshot']['capturedEpochMs']=after['snapshot']['source']['androidExport']['capturedEpochMs']=100000
        saved(after['snapshot'],before['snapshot'],readback,acquired,captured,epoch=100000)
        self.assertEqual(19000,acquired['capturedEpochMs'])
        before,after,readback,consumer,binding,acquired,captured=shared_original()
        readback['capturedEpochMs']=consumer['capturedEpochMs']=100000;after['snapshot']['capturedEpochMs']=after['snapshot']['source']['androidExport']['capturedEpochMs']=100000
        shared(after['snapshot'],before['snapshot'],readback,consumer,binding,acquired,captured,run=RUN,arm=ARM,epoch=100000)
        self.assertEqual(19001,acquired['capturedEpochMs'])

    def test_inventory_keeps_unfinished_unknown_and_replaced_actual_files_red(self):
        before,after,native,acquisition=completed();row=native['rows'][0]
        actual=dict(files=[dict(basename=Path(row['path']).name,**{key:row[key] for key in ('device','inode','bytes','uid','links','sha256')})],rows=deepcopy(native['rows']),capturedEpochMs=20000)
        self.assertEqual(native['rows'],inventory(actual,native,run=RUN,epoch=20000))
        for fault in ('unknown','missing','replaced','unretained','stale'):
            changed=deepcopy(actual)
            if fault=='unknown':changed['files'].append(dict(changed['files'][0],basename='unknown.png'))
            elif fault=='missing':changed['files']=[]
            elif fault=='replaced':changed['files'][0]['inode']+=1
            elif fault=='unretained':changed['rows']=[]
            else:changed['capturedEpochMs']=18000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):inventory(changed,native,run=RUN,epoch=20000)
        native['captures'][0].update(terminal='',terminalPath='',terminalEpochMs=0);native['rows'][0].update(closed=False,phase='writing',closedEpochMs=0,sha256='');actual['rows']=deepcopy(native['rows'])
        with self.assertRaises(SnapshotPending):inventory(actual,native,run=RUN,epoch=20000)

    def retirement(self):
        before,group,native,acquisition=completed();row=native['rows'][0]
        row.update(retireId='4'*32,deleteIssued=True,deleteResult=0,absent=True,checkedEpochMs=20000)
        native['plans'][0].update(sealed=True,sealId='5'*32,sealedEpochMs=20000)
        actual=dict(files=[],rows=deepcopy(native['rows']),capturedEpochMs=20000)
        readback=Readbacks().component;readback.update(sequence=1,capturedEpochMs=20000,destinations=[],jobs=[],files=[],removedCopies=[])
        for key in ('osDestinations','shareGrants'):readback[key].update(rows=[],checkedEpochMs=20000,checkId='6'*32)
        upload=dict(snapshotUploadObservationVersion=1,instance='7'*32,complete=True,capturedEpochMs=20000,sequence=0,events=[],jobs=[])
        settings=Settings();reader=settings.reader();reader.request(RUN,'capture')
        observed=reader.request(RUN,'observe');reader.request(RUN,'restore',restore_id='8'*32,expected_sha256=observed['source']['currentSha256'])
        settings=reader.request(RUN,'retire');settings['processId']=31
        return group,native,actual,readback,upload,settings

    def test_empty_live_scope_requires_actual_files_settings_and_all_worker_absence(self):
        originals=self.retirement();group=originals[0];history=deepcopy(group['snapshot']['source']['scriptHistory'])
        self.assertTrue(retired(*originals,run=RUN,epoch=20000))
        self.assertEqual(history,group['snapshot']['source']['scriptHistory']);self.assertTrue(history['events'])
        for fault in ('unsealed','live-file','host-file','live-workers','unrestored','scope-present','live-export','old-inspection','missing-consumer'):
            rows=deepcopy(originals);group,native,actual,readback,upload,settings=rows
            if fault=='unsealed':native['plans'][0].update(sealed=False,sealId='',sealedEpochMs=0)
            elif fault=='live-file':native['rows'][0]['absent']=False
            elif fault=='host-file':actual['files']=[dict(basename='unexpected.png')]
            elif fault=='live-workers':readback['workersTerminated']=False
            elif fault=='unrestored':settings['source']['currentSha256']='f'*64
            elif fault=='scope-present':settings['source']['scopePresent']=True
            elif fault=='live-export':group['snapshot']['source']['androidExport']['pendingIo']=['e'*32]
            elif fault=='old-inspection':readback['osDestinations']['checkedEpochMs']=18000
            else:
                boundary=Consumer();boundary.native.update(revokeId='9'*32,revokeIssued=True,granted=False,chooserGranted=False,checkedEpochMs=20000)
                readback['shareGrants']['rows']=[boundary.native]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):retired(*rows,run=RUN,epoch=20000)

    def test_current_consumer_retirement_cannot_be_replaced_by_an_archived_terminal(self):
        originals=list(self.retirement());boundary=Consumer();boundary.epoch=20000;boundary.original['capturedEpochMs']=19000
        boundary.source.update(startedEpochMs=19000,completedEpochMs=19001,original=deepcopy(boundary.original),files=[deepcopy(boundary.original)])
        boundary.retired();reader=boundary.reader();consumer=reader.observe();binding=reader.binding()
        self.assertTrue(retired(*originals,run=RUN,epoch=20000,consumer=consumer,consumer_binding=binding))
        for field,value in (('capturedEpochMs',18000),('activityAlive',True),('grantPresent',True),('workersTerminated',False)):
            changed=dict(consumer,**{field:value})
            with self.subTest(field=field),self.assertRaises(NativeUIError):retired(*originals,run=RUN,epoch=20000,consumer=changed,consumer_binding=binding)

    def test_public_projection_keeps_source_acquisition_separate_from_uninitialized_os_inventory(self):
        before,group,files,acquisition=completed();frame=public_frame(group,files,[acquisition])
        measured=state(frame,before,run=RUN,pid=31,epoch=20000)
        self.assertEqual(1,measured['files']);self.assertEqual(['pending','complete'],measured['captureHistory'])
        self.assertEqual((0,0,0),(measured['saved'],measured['shares'],measured['uploads']))
        self.assertEqual(False,frame['readbacks']['initialized']);self.assertNotIn('osDestinations',frame['readbacks'])
        changed=deepcopy(frame);changed['acquisitions']=[]
        with self.assertRaises(NativeUIError):state(changed,before,run=RUN,pid=31,epoch=20000)
        callbacks(group,'save','b'*32,acquisition['path'],[('request-active','')]);group['snapshot']['source']['androidExport']['activeRequest']='b'*32
        with self.assertRaises(NativeUIError):state(frame,before,run=RUN,pid=31,epoch=20000)

    def test_public_saved_count_is_recomputed_from_current_os_ownership(self):
        before,group,readback,acquired,captured=saved_original();_,_,files,original=completed()
        frame=public_frame(group,files,[original,acquired],readback)
        self.assertEqual(1,state(frame,before,run=RUN,pid=31,epoch=20000)['saved'])
        changed=deepcopy(frame);changed['readbacks']['destinations'][0]['published']=False
        # A stale successful private receipt cannot manufacture a currently
        # published destination. The contradictory original job stays red.
        with self.assertRaises(NativeUIError):state(changed,before,run=RUN,pid=31,epoch=20000)

    def test_public_empty_history_requires_live_scope_retirement_without_erasing_raw_events(self):
        group,files,actual,readbacks,upload,settings=self.retirement();before,_,_,_=completed()
        frame=public_frame(group,files,[],readbacks);frame.update(inventory=actual,upload=upload,settings=settings)
        raw=deepcopy(group);measured=state(frame,before,run=RUN,pid=31,epoch=20000)
        self.assertEqual([],measured['captureHistory']);self.assertEqual(0,measured['files']);self.assertEqual(raw,group)
        frame['settings']=None
        with self.assertRaises(NativeUIError):state(frame,before,run=RUN,pid=31,epoch=20000)

    def documents_frame(self):
        from test_snapshot_documents import Boundary as Documents,DOC
        from test_snapshot_documents_ui import Boundary as DocumentsUI
        before,group,readback,acquired,captured=saved_original();_,_,files,original=completed()
        docs=Documents();name=Path(captured['path']).name
        for row in (docs.document,docs.plan,docs.native):row['displayName']=name
        metadata=docs.capture()
        for row in (captured,original,acquired,files['rows'][0],readback['files'][0],readback['jobs'][0]['original']):row.update(metadata)
        destination=readback['osDestinations']['rows'][0]
        destination.update(identity=deepcopy(docs.native),inserted=False,original=metadata)
        readback['osDestinations']['snapshotOsDestinationsVersion']=2
        readback['destinations'][0].update(uri=docs.native['uri'],inserted=False)
        request=acquired['request'];callbacks(group,'save',request,captured['path'],[('request-active',''),('document-launched',''),
            ('document-result',docs.native['uri']),('destination-copied',docs.native['uri']),('result-ready','success'),('delivered','success')])
        group['snapshot']['source']['androidExport']['events'][2]['auxiliary']='411:-1'
        reader=docs.reader();reader.observe();binding=reader.binding();resolution=DocumentsUI().resolve()
        doc_acquisition,raw=reader.acquire(DOC,docs.native,metadata,11000,resolution)
        frame=public_frame(group,files,[original,acquired,doc_acquisition],readback)
        frame.update(documents=deepcopy(reader.last),documentsBinding=binding,documentResolution=resolution,
            phoneUid=dict(snapshotPhoneUidVersion=1,uid=11000,requestedEpochMs=20000,capturedEpochMs=20000))
        frame['platform']['source'].update(sdk=26,saveBackend='document-picker')
        return before,frame

    def test_sdk26_saved_count_retains_independent_documents_provider_and_native_copy(self):
        before,frame=self.documents_frame();self.assertEqual(1,state(frame,before,run=RUN,pid=31,epoch=20000)['saved'])
        self.assertEqual('snapshot-document-original',frame['acquisitions'][-1]['source'])
        self.assertEqual(19002,frame['acquisitions'][-1]['capturedEpochMs'])
        for fault in ('missing-provider','missing-binary','wrong-writer','wrong-creator','open-fd','foreign-instance','stale-provider','missing-native-copy'):
            changed=deepcopy(frame)
            if fault=='missing-provider':changed['documents']=None
            elif fault=='missing-binary':changed['acquisitions'].pop()
            elif fault=='wrong-writer':changed['phoneUid']['uid']+=1
            elif fault=='wrong-creator':changed['documentResolution']['uid']+=1
            elif fault=='open-fd':changed['documents']['fdLifetimes'][0].update(closed=False,closedEpochMs=0)
            elif fault=='foreign-instance':changed['documents']['instance']='f'*32
            elif fault=='stale-provider':changed['documents']['capturedEpochMs']=18000
            else:changed['readbacks']['files']=[]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state(changed,before,run=RUN,pid=31,epoch=20000)

    def test_sdk26_retirement_keeps_both_original_os_and_documents_absence_mandatory(self):
        before,frame=self.documents_frame();_,_,_,_,_,settings=self.retirement();frame['settings']=settings
        native=frame['captureFiles'];native['rows'][0].update(retireId='4'*32,deleteIssued=True,deleteResult=0,absent=True,checkedEpochMs=20000)
        native['plans'][0].update(sealed=True,sealId='5'*32,sealedEpochMs=20000)
        frame['inventory'].update(files=[],rows=deepcopy(native['rows']))
        readbacks=frame['readbacks'];readbacks.update(copiesRetired=True,workersTerminated=True,files=[],removedCopies=[readbacks['files'][0]['id']])
        readbacks['osDestinations']['rows'][0].update(phase='retired',deleteIssued=True,deleteId='6'*32,deleteCount=1,absent=True,checkedEpochMs=20000)
        for key in ('osDestinations','shareGrants'):readbacks[key].update(checkId='7'*32,checkedEpochMs=20000)
        provider=frame['documents'];provider.update(retired=True,workersTerminated=True)
        provider['root'].update(present=False,checkedEpochMs=20000)
        provider['documents'][0].update(deleteCalls=1,deletedEpochMs=19900,absent=True,checkedEpochMs=20000)
        self.assertEqual([],state(frame,before,run=RUN,pid=31,epoch=20000)['captureHistory'])
        for fault in ('missing-provider','live-root','live-worker','old-check','wrong-native-original'):
            changed=deepcopy(frame)
            if fault=='missing-provider':changed['documents']=None
            elif fault=='live-root':changed['documents']['root']['present']=True
            elif fault=='live-worker':changed['documents']['workersTerminated']=False
            elif fault=='old-check':changed['documents']['root']['checkedEpochMs']=18000
            else:changed['readbacks']['osDestinations']['rows'][0]['original']['sha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state(changed,before,run=RUN,pid=31,epoch=20000)


class SnapshotUploadedMeasurementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_snapshot_upload_source as original
        cls.original=original
        original.SnapshotUploadSourceTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cls.original.SnapshotUploadSourceTests.tearDownClass.__func__(cls)
    def setUp(self):self.original.SnapshotUploadSourceTests.setUp(self)
    def stop(self):return self.original.SnapshotUploadSourceTests.stop(self)
    def request(self,*args,**kwargs):return self.original.SnapshotUploadSourceTests.request(self,*args,**kwargs)
    def activate(self,*args,**kwargs):return self.original.SnapshotUploadSourceTests.activate(self,*args,**kwargs)
    def status(self,*args,**kwargs):return self.original.SnapshotUploadSourceTests.status(self,*args,**kwargs)
    def upload(self,*args,**kwargs):return self.original.SnapshotUploadSourceTests.upload(self,*args,**kwargs)
    def story(self,*args,**kwargs):return self.original.SnapshotUploadSourceTests.story(self,*args,**kwargs)
    def test_actual_retained_multipart_metadata_native_replies_and_captured_bytes_join(self):
        import hashlib
        from overte_phone_snapshots_measurements import uploaded
        native,provider=self.original.SnapshotUploadSourceTests.complete(self)
        row=next(row for row in provider['requests'] if row['target']=='/api/v1/snapshots')
        metadata,raw=self.service.image_original(self.run,row['requestId'],'a'*32)
        acquisition=dict(source='snapshot-upload-original',request=row['requestId'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            capturedEpochMs=metadata['capturedEpochMs'],originalCompletedEpochMs=metadata['originalCompletedEpochMs'],metadata=metadata)
        captured=dict(path=native['jobs'][0]['path'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        epoch=metadata['capturedEpochMs'];self.assertTrue(uploaded(native,provider,acquisition,captured,ticket=row['ticket'],epoch=epoch)['storyId'])
        for fault in ('private-relabel','foreign-body','foreign-provider','foreign-ticket','old-current','changed-bytes','wrong-native-file','wrong-reply'):
            a,b,c=deepcopy(native),deepcopy(provider),deepcopy(acquisition)
            if fault=='private-relabel':c['source']='snapshot-capture-original'
            elif fault=='foreign-body':c['metadata']['body']['inode']+=1
            elif fault=='foreign-provider':c['metadata']['instance']='f'*32
            elif fault=='foreign-ticket':c['metadata']['ticket']='f'*32
            elif fault=='old-current':a['capturedEpochMs']=epoch-2000
            elif fault=='changed-bytes':c['sha256']='f'*64
            elif fault=='wrong-native-file':a['jobs'][0]['file']['readSha256']='f'*64
            else:a['jobs'][0]['requests'][0]['responseId']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):uploaded(a,b,c,captured,ticket=row['ticket'],epoch=epoch)


if __name__=='__main__':unittest.main()
