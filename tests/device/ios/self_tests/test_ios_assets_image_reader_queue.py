"""Strict separate queue codec and declared SDK/event models; no Qt execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader_queue as source
from ios.self_tests.assets_image_reader_queue_fixture import Boundary,Holder,RUN
from self_tests.test_native_feature_observation import probe_source


class AssetsImageReaderQueueTests(unittest.TestCase):
    def running(self,*,direct=False,early=False):
        boundary=Boundary();task=boundary.create();gpu=Holder()
        boundary.invoke(task,gpu,queued=not direct,before_return=early)
        boundary.finish(task)
        return boundary,task,gpu

    def read(self,boundary,reader=None):
        reader=reader or boundary.reader()
        packet=reader.read(RUN,source1=boundary.parent.reader())
        return reader,packet

    def test_actual_source1_original_and_distinct_reversed_events_bind_without_payload_inference(self):
        boundary,task,gpu=self.running()
        second=boundary.create();boundary.invoke(second,gpu);boundary.finish(second)
        boundary.parent.queue.reverse();boundary.parent.deliver()
        reader,packet=self.read(boundary)
        rows=reader.bound_facts['entries']
        self.assertEqual([1,2],[row['eventId'] for row in rows])
        self.assertGreater(rows[0]['receiverEntered']['epochMs'],rows[1]['receiverEntered']['epochMs'])
        actual=source.parent_source.original(reader.parent_original)
        parents={row['id']:row for row in actual['source']['receivers']}
        self.assertEqual(2,len(parents))
        for row in rows:
            self.assertIn(row['receiverId'],parents)
            self.assertIsNone(parents[row['receiverId']]['dispatchId'])
        self.assertTrue(all(packet['source'][key] is False for key in source.UNAVAILABLE))
        self.assertEqual(1,len(boundary.queries));self.assertEqual(1,len(boundary.parent.queries))

    def test_direct_path_does_not_invent_queue_or_argument_destruction(self):
        boundary,task,gpu=self.running(direct=True)
        reader,packet=self.read(boundary)
        row=packet['source']['entries'][0]
        self.assertIsNone(row['eventId']);self.assertIsNone(row['receiverId'])
        self.assertTrue(all(row[key] is None for key in source.QT_PHASES))
        self.assertEqual('synchronous-invoke-scope',reader.parent_original['source']['receivers'][0]['attribution'])

    def test_cancelled_event_has_actual_destruction_without_delivery_or_receiver(self):
        boundary,task,gpu=self.running();event=boundary.parent.queue.pop()
        event.destroy_arguments();reader,packet=self.read(boundary)
        row=packet['source']['entries'][0]
        self.assertIsNotNone(row['argumentValuesDestroyed']);self.assertIsNone(row['deliveryEntered'])
        self.assertIsNone(row['receiverId']);self.assertEqual([],reader.parent_original['source']['receivers'])

    def test_delivery_and_argument_destruction_may_precede_producer_invoke_return(self):
        boundary,task,gpu=self.running(early=True);reader,packet=self.read(boundary)
        row=packet['source']['entries'][0]
        self.assertLess(row['argumentValuesDestroyed']['epochMs'],row['invokeReturned']['epochMs'])
        self.assertIsNotNone(row['receiverId'])

    def test_return_is_not_argument_destruction_and_buffered_original_clock_is_not_retimed(self):
        boundary,task,gpu=self.running();event=boundary.parent.queue.pop()
        event.deliver(destroy=False);event.destroy_arguments(publish=False)
        original=deepcopy(event.original_destruction_clock)
        reader,first=self.read(boundary)
        self.assertIsNone(first['source']['entries'][0]['argumentValuesDestroyed'])
        self.assertLess(original['epochMs'],first['source']['clock']['epochMs'])
        event.publish_destruction()
        _,last=self.read(boundary,reader)
        self.assertEqual(original,last['source']['entries'][0]['argumentValuesDestroyed'])
        self.assertFalse(last['source']['eventStorageCompletionAvailable'])

    def test_missing_or_forged_parent_reader_cannot_supply_matching_expected_ids(self):
        boundary,task,gpu=self.running();reader=boundary.reader()
        with self.assertRaises(NativeUIError):reader.read(RUN,source1={'source':{'instance':'f'*32}})
        self.assertEqual([],boundary.queries);self.assertEqual([],boundary.parent.queries)
        parent=boundary.parent.reader();original_read=parent.read
        def changed_after_capture(run):
            packet=original_read(run)
            changed=json.loads(boundary.parent.raw);changed['source']['instance']='b'*32
            boundary.parent.raw=json.dumps(changed)
            return packet
        parent.read=changed_after_capture
        with self.assertRaises(NativeUIError):reader.read(RUN,source1=parent)
        self.assertIsNone(reader.bound_facts)
        for fault in ('version','digest','span','native-after','binding-budget'):
            boundary,task,gpu=self.running();boundary.parent.deliver();reader=boundary.reader();parent=boundary.parent.reader()
            capture=parent.read
            def changed_acquisition(run):
                packet=capture(run)
                if fault=='version':parent.acquisition['iosAssetsImageReaderAcquisitionVersion']=True
                elif fault=='digest':parent.acquisition['originalSha256']='b'*64
                elif fault=='span':parent.acquisition['hostAfterMonotonic']=parent.acquisition['hostBeforeMonotonic']+1.5
                elif fault=='native-after':parent.acquisition['nativeAfterEpochMs']+=2000
                else:boundary.time+=1500  # Delay after capture; never alter an original packet clock.
                return packet
            parent.read=changed_acquisition
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,source1=parent)
            self.assertIsNone(reader.bound_facts)

    def test_foreign_source1_instance_and_parent_identity_are_refused(self):
        for fault in ('instance','task','dispatch','resource','receiver'):
            boundary,task,gpu=self.running();boundary.parent.deliver()
            def mutate(packet):
                table=packet['source'];row=table['entries'][0]
                if fault=='instance':table['source1Instance']='b'*32
                else:row[{'task':'taskId','dispatch':'dispatchId','resource':'resourceId','receiver':'receiverId'}[fault]]='b'*32
            boundary.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.read(boundary)

    def test_version_types_bounds_unknown_fields_and_invented_completion_are_refused(self):
        for fault in ('version','empty','cap','event-bool','event-duplicate','steady-float','steady-overflow',
                'method-bool','unknown','effect','before-created','return-without-enter','cancel-with-receiver'):
            boundary,task,gpu=self.running();boundary.parent.deliver()
            reader,packet=self.read(boundary);table=packet['source'];row=table['entries'][0]
            if fault=='version':table['assetImageReaderQueueHistoryVersion']=True
            elif fault=='empty':table['entries']=[]
            elif fault=='cap':table['entries']*=257
            elif fault=='event-bool':row['eventId']=True
            elif fault=='event-duplicate':table['entries'].append(dict(deepcopy(row),dispatchId='b'*32))
            elif fault=='steady-float':row['created']['steadyNs']=1.0
            elif fault=='steady-overflow':row['created']['steadyNs']=str(2**63)
            elif fault=='method-bool':row['methodIndex']=True
            elif fault=='unknown':row['wantedPayloadHash']='b'*64
            elif fault=='effect':table['gpuCompletionAvailable']=True
            elif fault=='before-created':row['deliveryEntered']['steadyNs']=str(int(row['created']['steadyNs'])-1)
            elif fault=='return-without-enter':row['deliveryEntered']=None
            else:row['deliveryEntered']=row['deliveryReturned']=None
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(packet)

    def test_history_loss_rebinding_rewrite_and_resurrection_are_refused(self):
        for fault in ('drop','rebind','rewrite','resurrect'):
            boundary,task,gpu=self.running();boundary.parent.deliver()
            if fault=='resurrect':boundary.parent.resource=None
            reader,first=self.read(boundary)
            def mutate(packet):
                row=packet['source']['entries'][0]
                if fault=='drop':packet['source']['entries']=[]
                elif fault=='rebind':row['dispatchId']='b'*32
                elif fault=='rewrite':row['created']['steadyNs']=str(int(row['created']['steadyNs'])+1)
                else:row['receiverObjectAlive']=True
            boundary.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.read(boundary,reader)
            self.assertIsNone(reader.bound_facts)

    def test_incomplete_queue_or_parent_cannot_heal_by_replacing_reader(self):
        for failure in ('queue','parent'):
            boundary,task,gpu=self.running();boundary.parent.deliver();reader=boundary.reader()
            target=boundary.value if failure=='queue' else boundary.parent.value
            target['complete']=False
            with self.assertRaises(NativeUIError):self.read(boundary,reader)
            target['complete']=True
            with self.subTest(failure=failure),self.assertRaises(NativeUIError):self.read(boundary,reader)
            self.assertIsNone(reader.bound_facts)

    def test_actual_probe_nonce_once_and_unavailable_getter_are_not_effect_evidence(self):
        boundary,task,gpu=self.running();boundary.parent.deliver();reader,packet=self.read(boundary);query=boundary.queries[-1]
        for key in ('source1Instance','dispatchId','receiverId','expectedHash','drained'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{key:'wanted'}))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsImageReaderQueue:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-image-reader-queue.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('queue source rewritten/replayed');
delete Test.featureIOSAssetsImageReaderQueue;applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing API invented drained state');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
