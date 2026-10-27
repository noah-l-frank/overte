"""Actual host wire + declared native weak-buffer/body counterexamples, no Qt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json,subprocess,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader_processing as source,assets_image_processing_lifecycle as lifecycle
from ios.self_tests.assets_image_processing_small_fixture import Boundary,RUN
from self_tests.test_native_feature_observation import probe_source


class AssetsImageProcessingTests(unittest.TestCase):
    def test_held_independent_input_owner_blocks_after_actual_marker_and_body_return(self):
        b=Boundary(held=True);b.release_product();packet,parent=b.read();row=packet['source']['calls'][0]
        self.assertIsNotNone(row['processingReturned']);self.assertFalse(packet['source']['tasks'][0]['derivedMarkerAlive'])
        self.assertTrue(row['deviceOwnersAlive']);self.assertIsNone(row['deviceDestroyedObserved'])
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
        b.release_test_buffers();facts=lifecycle.closed(*b.read(),[b.task_id])
        self.assertTrue(facts['observedProcessingAndInputDeviceEdgesClosed'])
        for key in source.UNAVAILABLE:self.assertFalse(facts[key])
    def test_two_actual_calls_on_one_resource_keep_distinct_input_object_identities(self):
        from ios.self_tests.assets_image_reader_queue_fixture import Holder
        b=Boundary();other=b.images.create();second_id=other.id;gpu=Holder()
        b.images.invoke(other,gpu);b.images.finish(other);b.images.parent.deliver()
        other=None;gpu=None;b.release_product();packet,parent=b.read();calls=packet['source']['calls']
        self.assertEqual(2,len(calls));self.assertEqual(1,len({row['resourceId'] for row in calls}))
        self.assertEqual(2,len({row['deviceId'] for row in calls}));self.assertEqual(2,len({row['taskId'] for row in calls}))
        facts=lifecycle.closed(packet,parent,[b.task_id,second_id]);self.assertEqual(2,len(facts['deviceIds']))

    def test_input_object_destruction_can_precede_reset_and_processing_returns(self):
        b=Boundary();b.release_product();packet,parent=b.read();row=packet['source']['calls'][0]
        self.assertLessEqual(row['contentResetEntered']['epochMs'],row['deviceDestroyedObserved']['epochMs'])
        self.assertLess(row['deviceDestroyedObserved']['epochMs'],row['contentResetReturned']['epochMs'])
        self.assertLess(row['deviceDestroyedObserved']['epochMs'],row['processingReturned']['epochMs'])
        lifecycle.closed(packet,parent,[b.task_id])
    def test_cache_branch_requires_actual_expired_marker_and_never_invents_input_or_decode(self):
        b=Boundary(cached=True);packet,parent=b.read();self.assertEqual([],packet['source']['calls'])
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
        b.release_product();packet,parent=b.read();facts=lifecycle.closed(packet,parent,[b.task_id])
        self.assertEqual([],facts['deviceIds']);self.assertEqual([b.task_id],facts['noProcessingTaskIds'])
        self.assertFalse(facts['decoderCompletionAvailable'])
    def test_buffered_destructor_clock_is_published_without_retimenative_phase(self):
        b=Boundary(held=True);b.release_product();b.processing.defer_destruction=True;b.release_test_buffers()
        clock=deepcopy(b.processing.delayed[0][1]);first,_=b.read()
        self.assertIsNone(first['source']['calls'][0]['deviceDestroyedObserved'])
        self.assertLess(clock['epochMs'],first['source']['clock']['epochMs']);b.processing.publish_destruction()
        last,parent=b.read();self.assertEqual(clock,last['source']['calls'][0]['deviceDestroyedObserved'])
        lifecycle.closed(last,parent,[b.task_id])
    def test_unknown_fields_types_threads_bounds_and_forged_completion_are_refused(self):
        faults=('version','future-version','call-cap','task-cap','unknown','thread','missing-enter','return-before-reset','null-device','completion')
        for fault in faults:
            b=Boundary();b.release_product();packet,_=b.read();h=packet['source'];row=h['calls'][0]
            if fault=='version':h['assetImageReaderProcessingHistoryVersion']=True
            elif fault=='future-version':h['assetImageReaderProcessingHistoryVersion']=2
            elif fault=='call-cap':h['calls']*=65
            elif fault=='task-cap':h['tasks']*=65
            elif fault=='unknown':row['wantedInputHash']='f'*64
            elif fault=='thread':row['rawEntered']['threadContextId']='7'*32
            elif fault=='missing-enter':row['processingEntered']=None
            elif fault=='return-before-reset':row['contentResetReturned']=None
            elif fault=='null-device':row['deviceId']=None
            else:h['byteCopyCompletionAvailable']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(packet)
    def test_actual_parent_instance_task_resource_and_missing_prefix_are_required(self):
        for fault in ('parent','task','resource','prefix','fake-parent'):
            b=Boundary();b.release_product();packet,parent=b.read()
            if fault=='parent':packet['source']['source1Instance']='7'*32
            elif fault=='task':packet['source']['tasks'][0]['taskId']='7'*32
            elif fault=='resource':packet['source']['tasks'][0]['resourceId']='7'*32
            elif fault=='prefix':packet['source']['tasks']=[]
            else:
                reader=b.processing.reader()
                with self.assertRaises(NativeUIError):reader.read(RUN,source1={'instance':parent['source']['instance']})
                continue
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.parent_links(packet,parent)
    def test_weak_resurrection_phase_rewrite_loss_rebind_and_failure_healing_are_refused(self):
        for fault in ('resurrect','rewrite','drop','rebind','heal'):
            b=Boundary();b.release_product();first,_=b.read();old=first['source'];last=deepcopy(old)
            if fault=='resurrect':last['calls'][0]['deviceOwnersAlive']=True
            elif fault=='rewrite':last['calls'][0]['rawReturned']['epochMs']+=1
            elif fault=='drop':last['calls']=[]
            elif fault=='rebind':last['calls'][0]['deviceId']='7'*32
            else:old['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.successor(old,last)
    def test_return_without_normal_raw_or_device_destruction_cannot_close(self):
        for fault in ('raw-unwind','processing-unwind','body-pending','destroy-pending'):
            b=Boundary();b.release_product();packet,parent=b.read();row=packet['source']['calls'][0]
            if fault=='raw-unwind':row['rawUnwound']=row['rawReturned'];row['rawReturned']=None
            elif fault=='processing-unwind':row['processingUnwound']=row['processingReturned'];row['processingReturned']=None
            elif fault=='body-pending':row['processingReturned']=None
            else:row['deviceDestroyedObserved']=None
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
    def test_full_probe_consumes_nonce_once_and_missing_api_is_not_input_end(self):
        b=Boundary();packet,_=b.read();query=b.processing.queries[-1]
        for key in ('taskId','resourceId','deviceId','expectedHash','destroy'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{key:'wanted'}))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsImageReaderProcessing:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-image-reader-processing.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('processing source rewritten or replayed');
delete Test.featureIOSAssetsImageReaderProcessing;applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing API invented input end');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
    def test_pure_closed_join_has_no_getter_write_process_socket_or_input_effect(self):
        b=Boundary();b.release_product();packet,parent=b.read();saved=deepcopy((packet,parent));commands=deepcopy(b.processing.queries)
        with (patch.object(b.reader,'read',side_effect=AssertionError('query')),patch.object(b.parent,'read',side_effect=AssertionError('parent query')),
                patch('subprocess.Popen',side_effect=AssertionError('process')),patch('socket.socket',side_effect=AssertionError('socket'))):
            lifecycle.closed(packet,parent,[b.task_id])
        self.assertEqual(saved,(packet,parent));self.assertEqual(commands,b.processing.queries)
    def test_native_source_keeps_weak_device_and_task_marker_without_foreign_qobject_reads(self):
        # Static source contract only, never native compile/runtime qualification.
        root=Path(__file__).resolve().parents[4];cpp=(root/'libraries/image/src/image/IOSImageProcessingObservation.cpp').read_text()
        header=(root/'libraries/image/src/image/IOSImageProcessingObservation.h').read_text()
        self.assertLess(header.index('#include <QtCore/qglobal.h>'),header.index('#if defined(Q_OS_IOS)'))
        self.assertIn('std::weak_ptr<QIODevice> device',cpp);self.assertIn('std::weak_ptr<void> marker',cpp)
        snapshot=cpp.split('QVariantMap Observation::snapshot()',1)[1]
        for forbidden in ('device->','device.get()','device.lock()','->property(','->thread()'):
            self.assertNotIn(forbidden,snapshot)
        self.assertIn('pending=this;++depth;_pushed=true;',cpp)
        self.assertLess(cpp.index('pending=this;++depth;_pushed=true;'),cpp.index('const auto connected=QObject::connect(object'))
        self.assertIn('std::atomic_exchange_explicit(publication(),Pin{}',cpp)
        self.assertIn('pending && pending->_ready && !pending->_claimed',cpp)
        self.assertLess(cpp.index('if (!connected) {fail();return;}'),cpp.index('_ready=true;'))
