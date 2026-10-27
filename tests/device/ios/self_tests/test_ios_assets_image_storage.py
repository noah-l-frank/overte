"""Declared allocation/Qt boundary models and real host weak/block histories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json,re,subprocess,unittest,weakref
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader_storage as source,assets_image_storage_lifecycle as lifecycle
from ios.self_tests.assets_image_storage_fixture import Boundary,RUN
from self_tests.test_native_feature_observation import probe_source


class AssetsImageStorageTests(unittest.TestCase):
    def boundary(self):
        value=Boundary();self.addCleanup(value.release_product);return value
    def test_actual_marker_expiry_and_derived_body_do_not_stand_for_unreturned_global_delete(self):
        b=self.boundary();b.allocator.paused=True;block=weakref.ref(b.allocator.blocks[b.slot]);b.release_product()
        packet,parent=b.read();row=packet['source']['allocations'][0]
        self.assertFalse(row['derivedMarkerAlive']);self.assertIsNotNone(row['destructorBodyEntered'])
        self.assertIsNotNone(row['deleteEntered']);self.assertIsNone(row['deleteReturned']);self.assertIsNotNone(block())
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
        b.allocator.release_pending();self.assertIsNone(block());facts=lifecycle.closed(*b.read(),[b.task_id])
        self.assertTrue(facts['observedRunnableDestructorAndDeallocationEdgesClosed'])
        for key in source.UNAVAILABLE:self.assertFalse(facts[key])
    def test_same_private_address_slot_new_generation_cannot_receive_the_old_delete_return(self):
        b=self.boundary();b.allocator.buffer_returns=True;b.release_product()
        original=deepcopy(b.storage.buffered[0][1]);old_id=b.storage.rows[0]['id']
        b.allocator.allocate(b.slot);new_id=b.storage.rows[1]['id'];self.assertNotEqual(old_id,new_id)
        b.storage.publish_returns();packet,parent=b.read();rows=packet['source']['allocations']
        self.assertEqual(original,rows[0]['deleteReturned']);self.assertIsNone(rows[1]['deleteEntered'])
        self.assertIsNone(rows[1]['deleteReturned']);self.assertIn(b.slot,b.allocator.blocks)
        result=lifecycle.closed(packet,parent,[b.task_id]);self.assertEqual([old_id],result['allocationIds'])
        self.assertFalse(result['poolCompletionAvailable']);self.assertFalse(result['resourceRetirementAvailable'])
    def test_failed_global_allocation_never_creates_storage_task_or_deletion_observations(self):
        b=self.boundary();b.allocator.failed_allocation();packet,_=b.read();row=packet['source']['allocations'][-1]
        self.assertIsNotNone(row['allocationThrew']);self.assertIsNone(row['allocationReturned'])
        for key in ('taskId','resourceId'):self.assertEqual('',row[key])
        for key in ('sourceAttached','destructorBodyEntered','deleteEntered','deleteReturned'):self.assertIsNone(row[key])
        self.assertFalse(packet['source']['resourceRetirementAvailable'])
    def test_constructor_failure_deallocation_does_not_manufacture_a_complete_virtual_destructor(self):
        b=self.boundary();slot=b.allocator.allocate();b.allocator.delete(slot);b.release_product();packet,parent=b.read()
        row=packet['source']['allocations'][1];self.assertIsNotNone(row['deleteReturned']);self.assertIsNone(row['destructorBodyEntered'])
        self.assertEqual('',row['taskId']);result=lifecycle.closed(packet,parent,[b.task_id])
        self.assertNotIn(row['id'],result['allocationIds'])
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[row['id']])
    def test_return_without_actual_derived_destructor_or_complete_constructor_cannot_close(self):
        for fault in ('destructor','constructor','delete-return','delete-entry','marker'):
            b=self.boundary();b.release_product();packet,parent=b.read()
            if fault=='destructor':packet['source']['allocations'][0]['destructorBodyEntered']=None
            elif fault=='constructor':parent['source']['tasks'][0]['constructorReturned']=None
            elif fault=='delete-return':packet['source']['allocations'][0]['deleteReturned']=None
            elif fault=='delete-entry':packet['source']['allocations'][0]['deleteEntered']=None
            else:packet['source']['allocations'][0]['derivedMarkerAlive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
    def test_missing_source1_task_allocation_prefix_cannot_be_ignored(self):
        b=self.boundary();other=b.images.create();other=None;b.release_product();packet,parent=b.read()
        self.assertEqual(2,len(packet['source']['allocations']));self.assertEqual(2,len(parent['source']['tasks']))
        packet['source']['allocations'].pop()
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,parent,[b.task_id])
    def test_delayed_return_publication_preserves_its_older_original_native_clock(self):
        b=self.boundary();b.allocator.buffer_returns=True;b.release_product();original=deepcopy(b.storage.buffered[0][1]);first,_=b.read()
        self.assertLess(original['epochMs'],first['source']['clock']['epochMs']);self.assertIsNone(first['source']['allocations'][0]['deleteReturned'])
        b.storage.publish_returns();last,parent=b.read();self.assertEqual(original,last['source']['allocations'][0]['deleteReturned'])
        lifecycle.closed(last,parent,[b.task_id])
    def test_unknown_fields_addresses_types_threads_and_completion_escalation_are_refused(self):
        for fault in ('version','future','address','task-null','size-bool','size-cap','thread','pool','extra-rows','both-allocation-ends'):
            b=self.boundary();b.release_product();packet,_=b.read();h=packet['source'];row=h['allocations'][0]
            if fault=='version':h['assetImageReaderStorageHistoryVersion']=True
            elif fault=='future':h['assetImageReaderStorageHistoryVersion']=2
            elif fault=='address':row['address']='0x123456'
            elif fault=='task-null':row['taskId']=None
            elif fault=='size-bool':row['storageBytes']=True
            elif fault=='size-cap':row['storageBytes']=1048577
            elif fault=='thread':row['deleteReturned']['threadContextId']='9'*32
            elif fault=='pool':h['poolCompletionAvailable']=True
            elif fault=='extra-rows':h['allocations']*=65
            else:row['allocationThrew']=deepcopy(row['allocationReturned'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(packet)
    def test_parent_task_resource_instance_or_process_substitution_is_not_an_allocation_binding(self):
        for fault in ('task','resource','instance','process','duplicate'):
            b=self.boundary();b.release_product();packet,parent=b.read();row=packet['source']['allocations'][0]
            if fault=='task':row['taskId']='7'*32
            elif fault=='resource':row['resourceId']='7'*32
            elif fault=='instance':packet['source']['source1Instance']='7'*32
            elif fault=='process':packet['processId']=43
            else:packet['source']['allocations'].append(deepcopy(row))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.parent_links(packet,parent)
    def test_old_generation_rebind_phase_rewrite_loss_and_known_marker_resurrection_are_refused(self):
        for fault in ('generation','task','phase','loss','resurrection'):
            b=self.boundary();b.release_product();packet,_=b.read();old=packet['source'];last=deepcopy(old);row=last['allocations'][0]
            if fault=='generation':row['id']='7'*32
            elif fault=='task':row['taskId']='7'*32
            elif fault=='phase':row['deleteReturned']['epochMs']+=1
            elif fault=='loss':last['allocations']=[]
            else:row['derivedMarkerAlive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.successor(old,last)
    def test_disarm_duplicate_address_and_failure_healing_cannot_produce_clean_storage(self):
        for fault in ('disarm','duplicate','heal'):
            b=self.boundary()
            if fault=='duplicate':b.storage.returned(0,b.slot)
            else:b.storage.disarm()
            h=b.storage.snapshot();self.assertFalse(h['complete'])
            if fault=='heal':
                after=deepcopy(h);after['complete']=True
                with self.assertRaises(NativeUIError):source.successor(h,after)
            else:
                with self.assertRaises(NativeUIError):b.read()
    def test_pure_closed_join_cannot_query_write_open_process_or_claim_pool_absence(self):
        b=self.boundary();b.release_product();packet,parent=b.read();saved=deepcopy((packet,parent));queries=deepcopy(b.storage.queries)
        with (patch.object(b.reader,'read',side_effect=AssertionError('query')),patch.object(b.parent,'read',side_effect=AssertionError('parent query')),
              patch.object(PrivateFeatureState,'write',side_effect=AssertionError('write')),patch('subprocess.Popen',side_effect=AssertionError('process')),
              patch('socket.socket',side_effect=AssertionError('socket'))):
            result=lifecycle.closed(packet,parent,[b.task_id]);self.assertFalse(result['poolCompletionAvailable'])
        self.assertEqual(saved,(packet,parent));self.assertEqual(queries,b.storage.queries)
    def test_actual_probe_consumes_nonce_once_and_missing_native_getter_is_unavailable(self):
        b=self.boundary();packet,_=b.read();query=b.storage.queries[-1]
        for key in ('address','taskId','allocationId','poolEmpty','expectedSize'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{key:'requested'}))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsImageReaderStorage:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-image-reader-storage.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('storage source rewritten or replayed');
delete Test.featureIOSAssetsImageReaderStorage;applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing API invented storage completion');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
    def test_native_source_captures_generation_before_free_and_never_looks_up_address_afterward(self):
        root=Path(__file__).resolve().parents[4]
        cpp=(root/'libraries/material-networking/src/material-networking/IOSAssetsImageReaderStorageObservation.cpp').read_text()
        header=(root/'libraries/material-networking/src/material-networking/IOSAssetsImageReaderStorageObservation.h').read_text()
        texture=(root/'libraries/material-networking/src/material-networking/TextureCache.cpp').read_text()
        self.assertLess(header.index('#include <QtCore/qglobal.h>'),header.index('#if defined(Q_OS_IOS)'))
        begin=cpp.split('Observation::Token Observation::deleteEntering',1)[1].split('void Observation::deleteReturned',1)[0]
        self.assertLess(begin.index('result._row=index;'),begin.index('owner->addresses.erase(found)'))
        returned=cpp.split('void Observation::deleteReturned',1)[1].split('void Observation::disarm',1)[0]
        for forbidden in ('addresses','actual','->thread(','->property('):self.assertNotIn(forbidden,returned)
        self.assertIn('std::atomic_exchange_explicit(publication(),Pin{}',cpp)
        self.assertIn('Callback callback;if (!callback.entered)',cpp)
        for snippet in ('~ImageReader() override','::operator delete(actual,bytes);','::operator delete(actual);','__cpp_sized_deallocation'):
            self.assertIn(snippet,texture)
    def test_new_storage_and_existing_processing_native_writers_use_only_exact_private_compact_paths(self):
        # Static source qualification only. Host factory/Probe models do not
        # execute QJson/QSaveFile or establish the installed native ABI.
        root=Path(__file__).resolve().parents[4]
        cpp=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text().split('void TestScriptingInterface::saveObject(',1)[1]
        gated=cpp.split('    if (_testResultsLocation.isNull())',1)[0]
        compact=cpp.split('// Append trailing slash if needed',1)[0]
        # Locate the known diagnostic QSaveFile region, then inspect members
        # of its preceding filename condition without requiring a first clause
        # or one exact whitespace layout.
        writer=re.search(r'\bQSaveFile\s+output\s*\(\s*filepath\s*\)\s*;',cpp)
        self.assertIsNotNone(writer)
        region=cpp[cpp.index('QString filepath'):writer.start()]
        condition=re.search(r'\bif\s*\((.*?)\)\s*\{',region,re.S)
        self.assertIsNotNone(condition)
        for name in ('feature-ios-assets-image-reader-storage.json','feature-ios-assets-image-reader-processing.json'):
            self.assertRegex(condition.group(1),r'\bfilename\s*==\s*"'+re.escape(name)+'"')
        private=cpp[condition.end()+cpp.index('QString filepath'):].split('#endif',1)[0]
        for name in ('feature-ios-assets-image-reader-storage.json','feature-ios-assets-image-reader-processing.json'):
            self.assertIn(name,gated)
            line=next(line for line in compact.splitlines() if name in line and 'QJsonDocument::Compact' in line)
            self.assertIn('filename=="'+name+'"',line)
        self.assertIn('QFileInfo(filepath).isSymLink()',private)
        self.assertIn('output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)',private)
        self.assertIn('output.setDirectWriteFallback(false)',private)
