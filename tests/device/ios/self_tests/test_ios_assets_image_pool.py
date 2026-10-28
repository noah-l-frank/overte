"""Behavioral counterexamples over explicit SDK producer and real host owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json,subprocess,unittest,weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_image_reader_pool as source,assets_image_pool_lifecycle as lifecycle
from ios.self_tests.assets_image_pool_fixture import Boundary,RUN
from self_tests.test_native_feature_observation import probe_source


class AssetsImagePoolTests(unittest.TestCase):
    def boundary(self,mode='worker'):
        b=Boundary(mode=mode);self.addCleanup(b.release_product);return b
    def closed(self,b):return lifecycle.closed(*b.read(),[b.task_id])
    def test_actual_storage_free_and_weak_marker_expiry_do_not_close_unreturned_pool_iteration(self):
        b=self.boundary();block=weakref.ref(b.allocator.blocks[b.slot]);b.release_product();self.assertIsNone(block())
        packet,storage,parent=b.read();self.assertIsNotNone(storage['source']['allocations'][0]['deleteReturned'])
        self.assertFalse(storage['source']['allocations'][0]['derivedMarkerAlive'])
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,storage,parent,[b.task_id])
        b.pool.release_iterations();facts=self.closed(b);self.assertTrue(facts['observedSelectedRunnablePoolEdgesClosed'])
        self.assertEqual('worker-iteration-returned',facts['observations'][0]['outcome'])
        for key in source.UNAVAILABLE:self.assertFalse(facts[key])
    def test_queue_removal_and_global_delete_do_not_close_unreturned_clear_delete_scope(self):
        b=self.boundary('clear');b.release_product()
        with self.assertRaises(NativeUIError):self.closed(b)
        b.pool.release_iterations();self.assertEqual('clear-cancel-delete-scope-returned',self.closed(b)['observations'][0]['outcome'])
    def test_successful_try_take_transfers_ownership_but_does_not_deallocate_storage(self):
        b=self.boundary('take')
        with self.assertRaises(NativeUIError):self.closed(b)
        b.release_product();facts=self.closed(b);self.assertEqual('try-take-transfer-independently-deallocated',facts['observations'][0]['outcome'])
    def test_stolen_execution_requires_actual_run_delete_and_iteration_return_after_take(self):
        b=self.boundary('steal');b.release_product()
        with self.assertRaises(NativeUIError):self.closed(b)
        b.pool.release_iterations();self.assertEqual('stolen-iteration-returned',self.closed(b)['observations'][0]['outcome'])
    def test_try_start_declined_does_not_imply_caller_storage_has_been_deallocated(self):
        b=self.boundary('declined')
        with self.assertRaises(NativeUIError):self.closed(b)
        b.release_product();self.assertEqual('try-start-declined-storage-independently-deallocated',self.closed(b)['observations'][0]['outcome'])
    def test_promotion_preserves_admission_and_requires_both_physical_queue_slots_retired(self):
        b=self.boundary('promote');b.release_product();b.pool.release_iterations();result=self.closed(b)
        self.assertEqual([1,2],result['observations'][0]['slotIds']);self.assertEqual(1,len(b.pool.admissions))
        packet,storage,parent=b.read();packet['source']['qt']['events']=[row for row in packet['source']['qt']['events'] if not(row['kind']==15 and row['slotId']==1)]
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,storage,parent,[b.task_id])
    def test_incomplete_concurrent_cut_is_retained_as_pending_then_original_older_event_can_publish(self):
        b=self.boundary();b.release_product();b.pool.release_iterations();original=deepcopy(b.pool.events[-1]);b.pool.hidden.add(original['sequence'])
        first,storage,parent=b.read();self.assertFalse(first['source']['qt']['cutComplete'])
        with self.assertRaises(NativeUIError):lifecycle.closed(first,storage,parent,[b.task_id])
        b.sleep(.1);b.pool.hidden.clear();last,storage,parent=b.read()
        self.assertEqual(original,last['source']['qt']['events'][-1]);source.successor(first['source'],last['source'])
        lifecycle.closed(last,storage,parent,[b.task_id])
    def test_address_reuse_cannot_relabel_old_admission_or_old_deallocation_generation(self):
        b=self.boundary('take');old=b.pool.registrations[0]['allocationId'];b.release_product()
        # A real new host block reuses the private allocator Slot. The old
        # registration is immutable and already retired; no pointer is exported.
        slot=b.allocator.allocate(b.slot);self.assertIs(slot,b.slot);new=b.storage.rows[-1]['id'];self.assertNotEqual(old,new)
        b.pool.registrations.append(dict(id=2,allocationId=new,live=True));b.pool.live_slots[slot]=2
        b.pool.event(3,reg=2);b.pool.take(slot,1,1);self.assertFalse(b.pool.healthy)
        with self.assertRaises(NativeUIError):self.closed(b)
    def test_overlapping_try_take_calls_are_joined_by_operation_generation_not_registration_alone(self):
        b=self.boundary('take');b.release_product();packet,storage,parent=b.read();q=packet['source']['qt'];events=q['events']
        existing=next(row for row in events if row['kind']==28)
        new=deepcopy(existing);new.update(sequence=len(events)+1,operationId=2);events.append(new)
        end=deepcopy(new);end.update(sequence=len(events)+1,kind=29,flags=0);events.append(end)
        q['reservedEvents']=len(events);q['mutationSerial']+=4
        lifecycle.closed(packet,storage,parent,[b.task_id])
        end['operationId']=1
        with self.assertRaises(NativeUIError):lifecycle.closed(packet,storage,parent,[b.task_id])
    def test_missing_api_tail_worker_slot_run_delete_or_retirement_cannot_be_replaced_by_pool_idle(self):
        b=self.boundary();b.release_product();b.pool.release_iterations();packets=b.read()
        for kind in (3,4,5,6,16,17,18,20,21,22):
            packet,storage,parent=deepcopy(packets);q=packet['source']['qt'];q['events']=[row for row in q['events'] if row['kind']!=kind]
            # A valid concurrent cut may contain holes; closure still needs all
            # original events even if a producer claims a pool is idle.
            q['cutComplete']=False
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):lifecycle.closed(packet,storage,parent,[b.task_id])
    def test_unknown_fields_requested_addresses_future_versions_and_broad_flags_are_refused(self):
        b=self.boundary();packet,_,_=b.read()
        for field in ('address','expectedTaskId','poolEmpty','globalPoolCompletionAvailable'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(dict(b.pool.queries[-1],**{field:True}))
        for fault in ('version','address','wide-flag','unsafe-steady','bool-id','pool-cap','event-cap'):
            value=deepcopy(packet);q=value['source']['qt']
            if fault=='version':q['qtRunnablePoolProtocolVersion']=2
            elif fault=='address':q['registrations'][0]['address']='0xabc'
            elif fault=='wide-flag':value['source']['globalPoolCompletionAvailable']=True
            elif fault=='unsafe-steady':q['steadyNs']=int(q['steadyNs'])
            elif fault=='bool-id':q['registrations'][0]['id']=True
            elif fault=='pool-cap':q['poolCount']=65
            else:q['reservedEvents']=2049
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_immutable_old_rows_events_and_retired_generation_cannot_heal_or_disappear(self):
        b=self.boundary();b.release_product();b.pool.release_iterations();packet,_,_=b.read();before=packet['source']
        for fault in ('event','allocation','resurrect','loss','healthy'):
            a=deepcopy(before);after=deepcopy(before)
            if fault=='event':after['qt']['events'][0]['steadyNs']=str(int(after['qt']['events'][0]['steadyNs'])+1)
            elif fault=='allocation':after['qt']['registrations'][0]['allocationId']='a'*32
            elif fault=='resurrect':after['qt']['registrations'][0]['live']=True
            elif fault=='loss':after['qt']['events']=[]
            else:a['qt']['healthy']=False;after['qt']['healthy']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.successor(a,after)
    def test_native_clock_inversion_or_cross_thread_deletion_chain_cannot_close(self):
        b=self.boundary();b.release_product();b.pool.release_iterations();saved=b.read()
        for fault in ('order','thread','parent','generation'):
            packet,storage,parent=deepcopy(saved)
            if fault=='order':next(row for row in packet['source']['qt']['events'] if row['kind']==21)['steadyNs']='1'
            elif fault=='thread':next(row for row in packet['source']['qt']['events'] if row['kind']==22)['threadSlotId']=99
            elif fault=='parent':parent['source']['instance']='a'*32
            else:packet['source']['bindings'][0]['allocationId']='a'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifecycle.closed(packet,storage,parent,[b.task_id])
    def test_pure_join_cannot_query_write_open_process_socket_or_mutate_saved_originals(self):
        b=self.boundary();b.release_product();b.pool.release_iterations();packets=b.read();saved=deepcopy(packets);queries=deepcopy(b.pool.queries)
        with (patch.object(b.reader,'read',side_effect=AssertionError('query')),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('write')),
              patch('subprocess.Popen',side_effect=AssertionError('process')),patch('socket.socket',side_effect=AssertionError('socket'))):
            self.assertTrue(lifecycle.closed(*packets,[b.task_id])['observedSelectedRunnablePoolEdgesClosed'])
        self.assertEqual(saved,packets);self.assertEqual(queries,b.pool.queries)
    def test_actual_probe_nonce_consumed_once_and_absent_sdk_getter_stays_unavailable(self):
        b=self.boundary();packet,_,_=b.read();query=b.pool.queries[-1]
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];const Test={featureIOSAssetsImageReaderPool:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-image-reader-pool.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('pool source rewritten or replayed');
delete Test.featureIOSAssetsImageReaderPool;applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('absent SDK API manufactured completion');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)
