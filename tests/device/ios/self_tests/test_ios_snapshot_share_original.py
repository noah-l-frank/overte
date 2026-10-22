"""Actual private host bytes/codecs; UIKit/provider callbacks are modeled.

No native compilation, CMake configuration, installation or device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_share_original as source
from ios.self_tests.test_ios_snapshot_exports import Native,RUN
from ios.self_tests.test_ios_snapshot_destination import completed


def received():
    native=Native();operation=native.start('share');operation.state['phase']=3
    native.event(operation,'share-created');native.event(operation,'share-presentation-requested');created=native.clock()
    _n,_o,_e,_p,raw=completed()
    record=dict(iosSnapshotShareOriginalVersion=1,runId=RUN,basename=operation.file,instance='d'*32,processId=84,
        receiverBundleId='org.example.snapshot.receiver',clockDomain='native-share-extension',createdClock=created,
        phase='complete',artifact='original.bytes',attachmentCount=1,registeredTypes=['public.png'],selectedType='public.png',
        receivedFilename=operation.file,byteCount=len(raw),sha256=hashlib.sha256(raw).hexdigest(),events=[],queries=[])
    for kind in ('read-issued','callback-enter','read-completed','callback-left','weak-expired'):
        record['events'].append(dict(sequence=len(record['events'])+1,kind=kind,clock=native.clock()))
    record['queries'].append(dict(requestId='ios-'+'e'*32,clock=native.clock(),operationAlive=False))
    native.callback(operation,'share-completion',lambda:native.event(operation,'share-completed',completed=True,hasError=False))
    native.finish(operation);exports=native.reader().read(RUN)
    return native,operation,exports,record,raw


def imported(record,raw):
    value=deepcopy(record);clock=deepcopy(value['queries'][-1]['clock'])
    clock={key:n+1 for key,n in clock.items()};value['events'].append(dict(sequence=6,kind='finish-issued',clock=clock))
    metadata=json.dumps(value,separators=(',',':')).encode()
    transfer=dict(iosSnapshotShareImportVersion=1,runId=RUN,phase='complete',clockBefore=dict(epochMs=200000,monotonicMs=7),
        clockAfter=dict(epochMs=200010,monotonicMs=17),instance='c'*32,processId=85,bundleId='org.example.snapshot',clockDomain='native-share-archive',
        originalMetadataSha256=hashlib.sha256(metadata).hexdigest(),byteCount=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return transfer,metadata,value


class SnapshotShareOriginalTests(unittest.TestCase):
    def test_real_received_file_matches_actual_capture_bytes_and_successful_native_share(self):
        _native,operation,exports,record,raw=received()
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'original.bytes';original.write_bytes(raw);original.chmod(0o600)
            receipt=source.received_original(record,exports,operation.id,original.read_bytes(),raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['sha256'])
            self.assertTrue(receipt['cleanupRequired']);self.assertTrue(receipt['extensionCompletionRequired'])
            self.assertEqual(84,receipt['receiverProcessId']);self.assertEqual(42,exports['processId'])
        for payload in (b'',raw[:-1],raw+b'x'):
            with self.subTest(payload=payload[:4]),self.assertRaises(NativeUIError):source.received_original(record,exports,operation.id,payload,raw)
        with self.assertRaises(NativeUIError):source.received_original(record,exports,operation.id,raw,raw+b'converted')

    def test_ack_cancelled_or_failed_native_share_never_establishes_a_destination_original(self):
        native,operation,exports,record,raw=received()
        for fault in ('native-error','cancelled','missing-result','wrong-operation','only-ack'):
            current=deepcopy(exports);destination=deepcopy(record);identifier=operation.id
            if fault in ('native-error','cancelled'):
                kind='share-completed';next(row for row in current['source']['events'] if row['kind']==kind)['detail']['completed']=False
            elif fault=='missing-result':next(row for row in current['source']['events'] if row['kind']=='share-completed')['kind']='share-created'
            elif fault=='wrong-operation':identifier='00000000-0000-4000-8000-000000000000'
            else:destination=dict(performed=True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.received_original(destination,current,identifier,raw,raw)

    def test_original_queries_reject_reused_nonce_stale_clock_foreign_pid_and_held_callback(self):
        _native,_operation,_exports,record,_raw=received();query=record['queries'][-1]
        source.observation(record,query['requestId'],pid=84,instance='d'*32,epoch_ms=query['clock']['epochMs']+1)
        for fault in ('stale','future','pid','birth','nonce','early-query','weak-resurrection'):
            changed=deepcopy(record);kwargs=dict(pid=84,instance='d'*32,epoch_ms=query['clock']['epochMs']+1);request=query['requestId']
            if fault=='stale':kwargs['epoch_ms']+=1600
            elif fault=='future':kwargs['epoch_ms']-=1000
            elif fault=='pid':kwargs['pid']=42
            elif fault=='birth':kwargs['instance']='a'*32
            elif fault=='nonce':request='ios-'+'f'*32
            elif fault=='early-query':changed['queries'][-1]['clock']=deepcopy(record['events'][-2]['clock'])
            else:changed['queries'][-1]['operationAlive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.observation(changed,request,**kwargs)
        with self.assertRaises(NativeUIError):source.observation(record,query['requestId'],pid=84,instance='d'*32,epoch_ms=query['clock']['epochMs'],previous=record)

    def test_callback_body_return_does_not_establish_actual_capture_release(self):
        _native,operation,exports,record,raw=received();held=deepcopy(record)
        held['events'].pop();held['queries'][0]['operationAlive']=True
        source.original(held)
        with self.assertRaises(NativeUIError):source.received_original(held,exports,operation.id,raw,raw)
        for fault in ('missing-left','repeated-read','late-callback','converted-type','wrong-name','foreign-run','extra-attachment'):
            changed=deepcopy(record)
            if fault=='missing-left':changed['events'][3]['kind']='weak-expired'
            elif fault=='repeated-read':changed['events'][4]['kind']='read-issued'
            elif fault=='late-callback':changed['events'].append(dict(sequence=6,kind='callback-enter',clock=deepcopy(changed['queries'][0]['clock'])))
            elif fault=='converted-type':changed['selectedType']='public.image';changed['registeredTypes'].append('public.image')
            elif fault=='wrong-name':changed['receivedFilename']='foreign.png'
            elif fault=='foreign-run':changed['runId']='f'*32
            else:changed['attachmentCount']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.received_original(changed,exports,operation.id,raw,raw)

    def test_source_history_and_original_bytes_remain_immutable_across_inspections(self):
        _native,_operation,_exports,record,_raw=received();later=deepcopy(record)
        clock={k:v+1 for k,v in later['queries'][0]['clock'].items()}
        later['queries'].append(dict(requestId='ios-'+'f'*32,clock=clock,operationAlive=False));source.original(later,record)
        for fault in ('event','query','bytes','pid','type','terminal'):
            changed=deepcopy(later)
            if fault=='event':changed['events'][0]['clock']['epochMs']+=1
            elif fault=='query':changed['queries'][0]['clock']['epochMs']+=1
            elif fault=='bytes':changed['sha256']='0'*64
            elif fault=='pid':changed['processId']=85
            elif fault=='type':changed['registeredTypes'].append('public.data')
            else:changed['phase']='issued';changed['sha256']='';changed['byteCount']=0
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(changed,record)

    def test_archive_import_binds_raw_metadata_and_file_without_retiming_extension_source(self):
        _native,_operation,_exports,record,raw=received();transfer,metadata,finished=imported(record,raw)
        result=source.imported_original(transfer,metadata,raw,pid=85,bundle_id='org.example.snapshot',receiver_bundle_id='org.example.snapshot.receiver')
        self.assertEqual(finished,result);self.assertEqual(record['createdClock'],result['createdClock'])
        self.assertNotEqual(transfer['clockBefore']['monotonicMs'],result['createdClock']['monotonicMs'])
        for fault in ('metadata','bytes','pid','bundle','receiver','not-finished','before-receipt'):
            envelope=deepcopy(transfer);original=metadata;payload=raw;kwargs=dict(pid=85,bundle_id='org.example.snapshot',receiver_bundle_id='org.example.snapshot.receiver')
            if fault=='metadata':original+=b' '
            elif fault=='bytes':payload+=b'x'
            elif fault=='pid':kwargs['pid']=42
            elif fault=='bundle':kwargs['bundle_id']='org.foreign.app'
            elif fault=='receiver':kwargs['receiver_bundle_id']='org.foreign.receiver'
            elif fault=='not-finished':original=json.dumps(record).encode();envelope['originalMetadataSha256']=hashlib.sha256(original).hexdigest()
            else:envelope['clockBefore']=dict(epochMs=1,monotonicMs=0);envelope['clockAfter']=dict(epochMs=2,monotonicMs=1)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.imported_original(envelope,original,payload,**kwargs)

    def test_cross_process_monotonic_origins_are_not_interchanged_and_wrong_utc_order_fails(self):
        _native,operation,exports,record,raw=received()
        changed=deepcopy(record)
        for clock in [changed['createdClock'],*[row['clock'] for row in changed['events']],*[row['clock'] for row in changed['queries']]]:clock['monotonicMs']+=1000000
        source.received_original(changed,exports,operation.id,raw,raw)
        for clock in [changed['createdClock'],*[row['clock'] for row in changed['events']],*[row['clock'] for row in changed['queries']]]:clock['epochMs']+=1000000
        with self.assertRaises(NativeUIError):source.received_original(changed,exports,operation.id,raw,raw)

    def test_native_source_and_plists_are_separate_opt_in_original_file_targets(self):
        folder=Path(__file__).resolve().parents[1]/'snapshot_share_companion'
        info=plistlib.loads((folder/'ExtensionInfo.plist.in').read_bytes());self.assertEqual('com.apple.share-services',info['NSExtension']['NSExtensionPointIdentifier'])
        for path in ('AppInfo.plist.in','Shared.entitlements.in'):plistlib.loads((folder/path).read_bytes())
        native=(folder/'ShareReceiver.m').read_text();journal=(folder/'ShareJournal.m').read_text();archive=(folder/'ArchiveApp.m').read_text()
        self.assertIn('loadFileRepresentationForTypeIdentifier:',native);self.assertIn('OVTShareCopyFile(url,',native)
        self.assertNotIn('loadPreviewImage',native);self.assertNotIn('UIImagePNGRepresentation',native)
        self.assertIn('@property(nonatomic,weak) NSObject* operation', (folder/'ShareJournal.h').read_text())
        self.assertIn('O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW',journal);self.assertIn('before.st_ctimespec.tv_nsec!=after.st_ctimespec.tv_nsec',journal)
        self.assertIn('if (self.journal)',native);self.assertIn('Existing responsibility; import will not repeat',archive)
        cmake=(folder/'CMakeLists.txt').read_text();self.assertLess(cmake.index('NOT OVERTE_E2E_FEATURE_TESTS'),cmake.index('project('))


if __name__=='__main__':unittest.main()
