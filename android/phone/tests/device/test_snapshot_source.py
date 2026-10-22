"""Original Snapshot reader counterexamples; synthetic IO, no Android verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_source import PhoneSnapshotSource,command,source,continuity

RUN='a'*32;STORAGE='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots'


class Boundary:
    def __init__(self):
        self.epoch=10000;self.clock=0.;self.sequence=0;self.okay=True;self.ignore=False;self.fault=None;self.raw=''
        self.events=[];self.captures=[];self.uploads=[];self.calls=[]
        self.review=dict(snapshotReviewObservationVersion=1,present=False,review=None)
        self.export_events=[];self.export_active='';self.export_pending=[]
    def export_event(self,kind,value='',auxiliary='',*,request='e'*32,action='save',ticket='1'):
        self.export_events.append(dict(request=request,handle='1',ticket=ticket,generation='1',action=action,
            source=STORAGE+'/owned.png',sequence=len(self.export_events)+1,kind=kind,value=value,auxiliary=auxiliary,
            capturedEpochMs=self.epoch,elapsedMs=int(self.clock*1000)))
        if kind=='request-active':self.export_active=request
        elif kind in ('delivered','cancelled'):self.export_active=''
    def event(self,kind,id,phase='',path='',error=''):
        self.events.append(dict(sequence=len(self.events)+1,kind=kind,id=id,phase=phase,path=path,error=error,
            capturedEpochMs=self.epoch,elapsedMs=int(self.clock*1000)))
    def send(self,request):
        self.calls.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;self.epoch+=10
        value=dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(phoneSnapshotObservationVersion=4,nativeReview=True,storageRoot=STORAGE,
                androidExport=dict(snapshotExportObservationVersion=2,instance='d'*32,complete=True,capturedEpochMs=self.epoch,
                    elapsedMs=int(self.clock*1000),sequence=len(self.export_events),activeRequest=self.export_active,pendingIo=self.export_pending[:],
                    events=deepcopy(self.export_events)),
                review=deepcopy(self.review),
                captures=deepcopy(self.captures),uploads=self.uploads[:],history=dict(snapshotHistoryVersion=1,
                instance='c'*32,complete=True,sequence=len(self.events),events=deepcopy(self.events))))
        if self.fault:self.fault(value)
        self.raw=json.dumps(value)
    def original(self):return self.raw
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return PhoneSnapshotSource(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=self.sleep)


class SnapshotSourceTests(unittest.TestCase):
    def test_original_io_survives_lease_cancellation_until_its_actual_worker_finishes(self):
        b=Boundary();work='f'*32;b.export_event('request-active');b.export_event('io-submit',work);b.export_pending=[work]
        b.export_event('io-started',work);b.export_event('cancelled','cancelled');reader=b.reader();pending=reader.read(RUN)
        self.assertEqual('',pending['source']['androidExport']['activeRequest'])
        self.assertEqual([work],pending['source']['androidExport']['pendingIo'])
        b.export_event('io-finished',work);b.export_event('io-accepted',work);b.export_pending=[]
        self.assertEqual([],reader.read(RUN)['source']['androidExport']['pendingIo'])

    def test_missing_foreign_duplicate_or_forged_io_quietness_is_rejected(self):
        for fault in ('hidden','foreign','missing-start','duplicate','rejected-active','legacy'):
            with self.subTest(fault=fault):
                b=Boundary();work='f'*32;b.export_event('request-active');b.export_event('io-submit',work);b.export_pending=[work]
                if fault=='hidden':b.export_pending=[]
                elif fault=='foreign':b.export_event('io-finished','1'*32)
                elif fault=='missing-start':b.export_event('io-finished',work);b.export_pending=[]
                elif fault=='duplicate':
                    b.export_event('io-started',work);b.export_event('io-finished',work);b.export_event('io-finished',work);b.export_pending=[]
                elif fault=='rejected-active':b.export_event('io-started',work);b.export_event('io-rejected',work);b.export_pending=[]
                else:b.fault=lambda v:v['source']['androidExport'].update(snapshotExportObservationVersion=1)
                with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_android_callback_originals_keep_actual_file_identity_and_retirement(self):
        b=Boundary();b.export_event('request-active');reader=b.reader();pending=reader.read(RUN)
        self.assertEqual('e'*32,pending['source']['androidExport']['activeRequest'])
        b.export_event('destination-copied','content://media/external/images/media/418')
        b.export_event('destination-published','content://media/external/images/media/418','1')
        b.export_event('result-ready','success');b.export_event('delivered','success')
        result=reader.read(RUN)['source']['androidExport']
        self.assertEqual('',result['activeRequest']);self.assertEqual(5,result['sequence'])
        self.assertNotIn('savedBytes',result)

    def test_android_export_missing_foreign_incomplete_or_stale_source_remains_red(self):
        for fault in ('missing','version','incomplete','stale','future','path','ticket','request','kind','active','uri'):
            with self.subTest(fault=fault):
                b=Boundary();b.export_event('request-active');b.export_event('destination-copied','content://media/owned/418')
                def mutate(v):
                    e=v['source']['androidExport']
                    if fault=='missing':v['source'].pop('androidExport')
                    elif fault=='version':e['snapshotExportObservationVersion']=99
                    elif fault=='incomplete':e['complete']=False
                    elif fault=='stale':e['capturedEpochMs']=1
                    elif fault=='future':e['events'][0]['capturedEpochMs']=v['capturedEpochMs']+1
                    elif fault=='path':e['events'][1]['source']='/tmp/foreign.png'
                    elif fault=='ticket':e['events'][1]['ticket']='2'
                    elif fault=='request':e['events'][1]['request']='f'*32
                    elif fault=='kind':e['events'][1]['kind']='expected-success'
                    elif fault=='active':e['activeRequest']=''
                    else:e['events'][1]['value']='file:///tmp/foreign.png'
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_android_export_reconstructed_or_rewritten_original_prefix_cannot_be_reused(self):
        for fault in ('instance','sequence','row','lost'):
            with self.subTest(fault=fault):
                b=Boundary();b.export_event('request-active');reader=b.reader();reader.read(RUN)
                def mutate(v):
                    e=v['source']['androidExport']
                    if fault=='instance':e['instance']='f'*32
                    elif fault=='sequence':e['sequence']=0
                    elif fault=='row':e['events'][0]['ticket']='2'
                    else:e.update(sequence=0,events=[],activeRequest='')
                b.fault=mutate
                with self.assertRaises(NativeUIError):reader.read(RUN)

    def test_android_export_chosen_component_is_only_an_original_acknowledgement(self):
        b=Boundary();b.export_event('request-active',action='share')
        b.export_event('share-uri','content://io.github.noah_be.overte.phone.snapshot.files/snapshot/owned.png',action='share')
        b.export_event('share-chosen','org.example.receiver/.Receive',action='share')
        result=b.reader().read(RUN)['source']['androidExport']
        self.assertEqual('e'*32,result['activeRequest'])
        self.assertNotIn('destination-copied',[row['kind'] for row in result['events']])

    def test_android_export_delivery_requires_its_original_result_and_cannot_borrow_a_retired_ticket(self):
        for fault in ('missing-ready','mismatched-ready','duplicate-ticket'):
            with self.subTest(fault=fault):
                b=Boundary();b.export_event('request-active')
                if fault!='missing-ready':b.export_event('result-ready','error' if fault=='mismatched-ready' else 'success')
                b.export_event('delivered','success')
                if fault=='duplicate-ticket':b.export_event('request-active',request='f'*32)
                with self.assertRaises(NativeUIError):b.reader().read(RUN)

    @staticmethod
    def review_state():
        return dict(componentUrl='qrc:/system/snapshot/NativeSnapshotReview.qml',visible=True,
            capturing=False,processing=False,loggedIn=False,canShare=False,canBlast=False,statusError=False,
            captureSettingsLoaded=True,statusText='',uploadPath='',exportTicket='',mode=0,format='png',
            capabilities=['save','share'],exportBusy=False,exportError='',images=[])

    def test_actual_pending_and_cancelled_review_samples_are_distinct_from_native_capture_allocation(self):
        b=Boundary();row=self.review_state();row['capturing']=True
        b.review.update(present=True,review=row);reader=b.reader();pending=reader.read(RUN)
        self.assertTrue(pending['source']['review']['review']['capturing']);self.assertEqual([],pending['source']['captures'])
        row['capturing']=False;cancelled=reader.read(RUN)
        self.assertFalse(cancelled['source']['review']['review']['capturing'])
        self.assertGreater(cancelled['sequence'],pending['sequence'])

    def test_missing_foreign_or_inconsistent_review_source_is_not_observed_absence(self):
        for fault in ('missing','foreign','processing','image','duplicate','busy-type','capability','absence','version'):
            with self.subTest(fault=fault):
                b=Boundary();row=self.review_state();b.review.update(present=True,review=row)
                if fault=='missing':row.pop('capturing')
                elif fault=='foreign':row['componentUrl']='https://foreign.invalid/system/snapshot/NativeSnapshotReview.qml'
                elif fault=='processing':row['processing']=True
                elif fault=='image':row['images']=[dict(path='/tmp/foreign.png',storyPresent=False)]
                elif fault=='duplicate':row['images']=[dict(path=STORAGE+'/x.png',storyPresent=False)]*2
                elif fault=='busy-type':row['exportBusy']=1
                elif fault=='capability':row['capabilities']=['capture']
                elif fault=='absence':b.review['present']=False
                else:b.review['snapshotReviewObservationVersion']=2
                with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_fresh_reads_reopen_actual_source_and_keep_history_separate_from_commands(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN)
        b.event('capture-begin','snap_10010_1');b.captures=[dict(id='snap_10010_1',state='active',announced=False)]
        second=reader.read(RUN)
        self.assertGreater(second['sequence'],first['sequence']);self.assertEqual(1,len(second['source']['captures']))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.calls[-1]))
        self.assertNotEqual(b.calls[0]['commandId'],b.calls[1]['commandId'])
    def test_actual_cancel_and_upload_histories_are_retained_without_assuming_a_file_exists(self):
        b=Boundary();b.event('capture-begin','snap_1');b.event('capture-status','snap_1','cancelled')
        name=STORAGE+'/owned.png';b.event('upload-begin',name,path=name);b.event('upload-status',name,'error',name,'upload-failed')
        value=b.reader().read(RUN)
        self.assertEqual(4,value['source']['history']['sequence']);self.assertEqual([],value['source']['captures'])
        self.assertNotIn('files',value['source'])
    def test_ignored_request_cannot_return_an_older_original(self):
        b=Boundary();reader=b.reader();reader.read(RUN);b.ignore=True
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_missing_result_remains_red(self):
        b=Boundary();b.ignore=True
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_stale_foreign_or_incomplete_packets_fail(self):
        for fault in ('run','pid','stale','complete','extra','future-event','root'):
            with self.subTest(fault=fault):
                b=Boundary();b.event('capture-begin','snap_1')
                def mutate(v):
                    if fault=='run':v['runId']='f'*32
                    elif fault=='pid':v['processId']=99
                    elif fault=='stale':v['requestedEpochMs']=v['capturedEpochMs']=1
                    elif fault=='complete':v['source']['history']['complete']=False
                    elif fault=='extra':v['source']['saved']=1
                    elif fault=='future-event':v['source']['history']['events'][0]['capturedEpochMs']=b.epoch+1
                    else:v['source']['storageRoot']='/tmp/Snapshots'
                b.fault=mutate
                with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_reconstructed_or_changed_history_cannot_borrow_a_prior_sequence(self):
        for fault in ('instance','history-instance','sequence','event','truncated'):
            with self.subTest(fault=fault):
                b=Boundary();b.event('capture-begin','snap_1');reader=b.reader();reader.read(RUN)
                def mutate(v):
                    if fault=='instance':v['instance']='f'*32
                    elif fault=='history-instance':v['source']['history']['instance']='f'*32
                    elif fault=='sequence':v['sequence']=1
                    elif fault=='event':v['source']['history']['events'][0]['id']='snap_foreign'
                    else:v['source']['history'].update(sequence=0,events=[])
                b.fault=mutate
                with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_original_capture_inventory_cannot_invent_an_unrecorded_responsibility(self):
        b=Boundary();b.captures=[dict(id='snap_unknown',state='active',announced=False)]
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_foreign_paths_and_duplicate_current_rows_fail(self):
        for uploads in ([STORAGE+'/..'],[STORAGE+'/sub/file.png'],[STORAGE+'/x.png']*2,['/tmp/x.png']):
            with self.subTest(uploads=uploads):
                b=Boundary();b.uploads=uploads
                with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_candidate_or_clock_changes_during_original_io_fail(self):
        for fault in ('guard','slow','backwards'):
            with self.subTest(fault=fault):
                b=Boundary();reader=b.reader();original=reader.original
                def read():
                    if fault=='guard':b.okay=False
                    elif fault=='slow':b.clock+=5.1
                    else:b.clock-=.1
                    return original()
                reader.original=read
                with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_returned_graph_cannot_change_retained_continuity(self):
        b=Boundary();reader=b.reader();row=reader.read(RUN);row['source']['storageRoot']='/tmp/foreign'
        self.assertEqual(STORAGE,reader.read(RUN)['source']['storageRoot'])
    def test_command_cannot_set_product_state_or_select_an_expected_file(self):
        for extra in ({'saved':1},{'prefix':'expected'},{'operation':'capture'}):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):
                command(dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-observe',runId=RUN)|extra)


if __name__=='__main__':unittest.main()
