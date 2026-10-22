"""Real host original bytes/transaction codecs; Photos/companion are modeled.

No compiler, application, device, SDK server or installation is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_destination as destination
from ios.self_tests.test_ios_snapshot_exports import Native,RUN


def completed():
    native=Native();operation=native.start();native.save(operation);exports=native.reader().read(RUN)
    image=BytesIO();Image.new('RGB',(32,24),(30,100,210)).save(image,format='PNG');raw=image.getvalue()
    record=dict(iosSnapshotDestinationVersion=1,runId=RUN,kind='photos-resource',basename=operation.file,
        photosIdentifier='actual-native-placeholder/L0/001',instance='d'*32,processId=84,clockDomain='native-companion-photos',
        createdClock=dict(epochMs=200000,monotonicMs=7),events=[],queries=[],phase='complete',
        resource=dict(originalFilename=operation.file,type=1),byteCount=len(raw),sha256=hashlib.sha256(raw).hexdigest(),artifact='original.bytes',deletion=None)
    for kind,detail in [('read-issued',{}),('resource-selected',{}),('callback-enter',dict(name='data')),
        ('callback-left',dict(name='data')),('callback-enter',dict(name='completion')),('read-completed',{}),
        ('callback-left',dict(name='completion')),('weak-expired',{})]:
        index=len(record['events'])+1
        record['events'].append(dict(sequence=index,kind=kind,clock=dict(epochMs=200000+index,monotonicMs=7+index),detail=detail))
    record['queries'].append(dict(requestId='ios-'+'e'*32,clock=dict(epochMs=200020,monotonicMs=27),operationAlive=False,
        deletionAlive=False,assetPresent=True,authorization=3))
    return native,operation,exports,record,raw


class SnapshotDestinationTests(unittest.TestCase):
    def test_real_file_bytes_join_native_photos_placeholder_but_ack_or_different_bytes_cannot(self):
        _native,operation,exports,record,raw=completed()
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'original.bytes';path.write_bytes(raw);path.chmod(0o600)
            actual=path.read_bytes();receipt=destination.saved_original(record,exports,operation.id,actual)
            self.assertEqual(hashlib.sha256(actual).hexdigest(),receipt['sha256']);self.assertTrue(receipt['cleanupRequired'])
            self.assertEqual(84,receipt['destinationProcessId']);self.assertEqual(42,exports['processId'])
            for payload in (b'',raw[:-1],raw[:-1]+b'x',dict(performed=True)):
                with self.subTest(payload_type=type(payload)),self.assertRaises(NativeUIError):
                    destination.saved_original(record,exports,operation.id,payload)

    def test_foreign_run_asset_or_original_name_never_becomes_a_saved_capture(self):
        _native,operation,exports,record,raw=completed()
        for fault in ('asset','run','name','digest','missing-resource','permission','weak-owner','clock-order'):
            changed=deepcopy(record)
            if fault=='asset':changed['photosIdentifier']='foreign-placeholder/L0/001'
            elif fault=='run':changed['runId']='f'*32
            elif fault=='name':changed['basename']=changed['basename'].replace('_1.png','_2.png');changed['resource']['originalFilename']=changed['basename']
            elif fault=='digest':changed['sha256']='0'*64
            elif fault=='missing-resource':changed['resource']=None
            elif fault=='permission':changed['queries'][0]['authorization']=2
            elif fault=='weak-owner':changed['queries'][0]['operationAlive']=True
            else:changed['createdClock']['epochMs']=90000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.saved_original(changed,exports,operation.id,raw)

    def test_original_fresh_query_keeps_its_own_process_clock_and_never_uses_client_monotonic_time(self):
        _native,_operation,_exports,record,_raw=completed();request=record['queries'][-1]['requestId']
        observed=destination.observation(record,request,pid=84,instance='d'*32,epoch_ms=200025)
        self.assertEqual(27,observed['queries'][-1]['clock']['monotonicMs'])
        for fault in ('old','future','pid','instance','query','early-query'):
            changed=deepcopy(record);kwargs=dict(pid=84,instance='d'*32,epoch_ms=200025);query=request
            if fault=='old':kwargs['epoch_ms']=202000
            elif fault=='future':kwargs['epoch_ms']=199000
            elif fault=='pid':kwargs['pid']=42
            elif fault=='instance':kwargs['instance']='c'*32
            elif fault=='query':query='ios-'+'f'*32
            else:changed['queries'][0]['clock']=dict(epochMs=200002,monotonicMs=9)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.observation(changed,query,**kwargs)

    def test_unreturned_callback_and_late_data_cannot_claim_a_drained_original(self):
        _native,operation,exports,record,raw=completed()
        for fault in ('unreturned','late-data','resurrected','missing-completion','query-before-expiry'):
            changed=deepcopy(record)
            if fault=='unreturned':changed['events'][6]['detail']['name']='data'
            elif fault=='late-data':changed['events'][-1].update(kind='callback-enter',detail=dict(name='data'))
            elif fault=='resurrected':changed['events'].append(dict(sequence=9,kind='resource-selected',clock=dict(epochMs=200009,monotonicMs=16),detail={}))
            elif fault=='missing-completion':changed['events'][5]['kind']='read-failed'
            else:changed['queries'][0]['clock']=dict(epochMs=200007,monotonicMs=14)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.saved_original(changed,exports,operation.id,raw)

    def test_later_inspection_preserves_original_event_prefix_and_terminal_bytes(self):
        _native,_operation,_exports,record,_raw=completed();later=deepcopy(record)
        later['queries'].append(dict(requestId='ios-'+'f'*32,clock=dict(epochMs=200030,monotonicMs=37),operationAlive=False,
            deletionAlive=False,assetPresent=True,authorization=3))
        destination.original(later,record)
        destination.observation(later,'ios-'+'f'*32,pid=84,instance='d'*32,epoch_ms=200031,previous=record)
        with self.assertRaises(NativeUIError):
            destination.observation(record,'ios-'+'e'*32,pid=84,instance='d'*32,epoch_ms=200025,previous=record)
        for fault in ('event-clock','old-query','byte-count','terminal-state','source-birth'):
            changed=deepcopy(later)
            if fault=='event-clock':changed['events'][0]['clock']['epochMs']+=1
            elif fault=='old-query':changed['queries'][0]['clock']['epochMs']+=1
            elif fault=='byte-count':changed['byteCount']+=1
            elif fault=='terminal-state':changed['phase']='issued';changed['sha256']=''
            else:changed['instance']='c'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.original(changed,record)

    def test_separate_source_uses_photos_original_resource_and_keeps_client_add_only(self):
        root=Path(__file__).resolve().parents[4];folder=root/'tests/device/ios/snapshot_companion'
        native=(folder/'PhotosOriginal.m').read_text();cmake=(folder/'CMakeLists.txt').read_text()
        self.assertIn('requestDataForAssetResource:resource',native);self.assertIn('resource.originalFilename',native)
        self.assertIn('options.networkAccessAllowed=NO',native);self.assertIn('@property(nonatomic,weak) OVTPhotosRead* operation',native)
        self.assertIn('if (self.journal)',native);self.assertIn('O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW',native)
        self.assertNotIn('requestImageForAsset',native);self.assertNotIn('UIImagePNGRepresentation',native)
        self.assertIn('NOT OVERTE_E2E_FEATURE_TESTS',cmake)
        for info in ('ios/resources/InterfaceInfo.plist.in','ios/resources/InterfaceE2EInfo.plist.in'):
            path=root/info
            self.assertIn('NSPhotoLibraryAddUsageDescription',path.read_text())
            self.assertNotIn('NSPhotoLibraryUsageDescription',path.read_text())

    @staticmethod
    def deleted(record):
        value=deepcopy(record);value['deletion']=dict(phase='complete')
        for kind,detail in [('delete-issued',{}),('delete-changes-enter',{}),('delete-changes-left',{}),
            ('delete-completion-enter',{}),('delete-completed',dict(success=True,hasError=False)),
            ('delete-completion-left',{}),('delete-weak-expired',{})]:
            index=len(value['events'])+1
            value['events'].append(dict(sequence=index,kind=kind,clock=dict(epochMs=200020+index,monotonicMs=27+index),detail=detail))
        value['queries'].append(dict(requestId='ios-'+'f'*32,clock=dict(epochMs=200050,monotonicMs=57),operationAlive=False,
            deletionAlive=False,assetPresent=False,authorization=3))
        return value

    def test_successful_delete_requires_distinct_full_access_absence_and_actual_callback_expiry(self):
        _native,operation,exports,record,raw=completed();deleted=self.deleted(record)
        destination.original(deleted,record)
        proof=destination.photos_absent(deleted,exports,operation.id,raw)
        self.assertTrue(proof['quietWindowRequired']);self.assertEqual(record['sha256'],proof['savedOriginal']['sha256'])
        for fault in ('ignored-delete','limited','callback-held','weak-held','delete-failed','only-read'):
            changed=deepcopy(deleted)
            if fault=='ignored-delete':changed['queries'][-1]['assetPresent']=True
            elif fault=='limited':changed['queries'][-1].update(authorization=4,assetPresent=None)
            elif fault=='callback-held':changed['events'][-2]['kind']='delete-changes-left'
            elif fault=='weak-held':changed['queries'][-1]['deletionAlive']=True
            elif fault=='delete-failed':changed['deletion']['phase']='failed';changed['events'][-3]['detail']['success']=False
            else:changed=record
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.photos_absent(changed,exports,operation.id,raw)

    def test_delete_history_and_original_absence_cannot_be_rewritten_or_reused(self):
        _native,_operation,_exports,record,_raw=completed();deleted=self.deleted(record)
        for fault in ('changed-read','changed-query','repeated-delete','retimed-absence'):
            changed=deepcopy(deleted)
            if fault=='changed-read':changed['sha256']='0'*64
            elif fault=='changed-query':changed['queries'][0]['assetPresent']=False
            elif fault=='repeated-delete':changed['events'][-1]['kind']='delete-issued'
            else:changed['queries'][-1]['clock']=dict(epochMs=200010,monotonicMs=17)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):destination.original(changed,record)


if __name__=='__main__':unittest.main()
