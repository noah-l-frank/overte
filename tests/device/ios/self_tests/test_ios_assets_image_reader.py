"""Strict source1 codec and explicitly modeled weak/TLS boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader as source
from ios.self_tests.assets_image_reader_fixture import Boundary,Holder,RUN
from self_tests.test_native_feature_observation import probe_source


class AssetsImageReaderTests(unittest.TestCase):
    def running(self):
        b=Boundary();task=b.create();b.phase(task,'runEntered');b.phase(task,'readEntered');return b,task

    def test_queued_receiver_is_not_attributed_even_for_one_matching_pending_payload(self):
        b,task=self.running();gpu=Holder();dispatch=b.invoke(task,gpu)
        b.phase(task,'readReturned');b.phase(task,'runReturned');b.deliver()
        packet=b.reader().read(RUN);facts=source.tasks(packet);receipt=facts['receivers'][0]
        self.assertIsNone(receipt['dispatchId']);self.assertEqual('unavailable-queued-or-other-producer',receipt['attribution'])
        self.assertEqual(dispatch['width'],receipt['width'])
        for key in source.UNAVAILABLE:self.assertIs(False,facts[key])

    def test_foreign_identical_queued_payload_cannot_borrow_image_reader_provenance(self):
        b,task=self.running();gpu=Holder();b.invoke(task,gpu);b.phase(task,'readReturned');b.phase(task,'runReturned')
        foreign=b.receive(gpu);b.deliver();packet=b.reader().read(RUN)
        self.assertEqual(2,len(packet['source']['receivers']))
        self.assertTrue(all(row['dispatchId'] is None for row in packet['source']['receivers']))
        self.assertIsNone(foreign['dispatchId'])

    def test_actual_modeled_synchronous_scope_is_distinct_from_queued_value_matching(self):
        b,task=self.running();gpu=Holder();dispatch=b.invoke(task,gpu,queued=False)
        b.phase(task,'readReturned');b.phase(task,'runReturned');packet=b.reader().read(RUN)
        receipt=packet['source']['receivers'][0]
        self.assertEqual(dispatch['id'],receipt['dispatchId']);self.assertEqual('synchronous-invoke-scope',receipt['attribution'])
        self.assertFalse(packet['source']['gpuCompletionAvailable'])

    def test_derived_marker_expiry_does_not_retire_independent_bytes_base_pool_or_queued_gpu(self):
        b,task=self.running();external_bytes=task.buffer;external_base=task.base;gpu=Holder()
        b.invoke(task,gpu);b.phase(task,'readReturned');b.phase(task,'runReturned')
        reader=b.reader();first=reader.read(RUN);del task;del gpu;gc.collect();last=reader.read(RUN)
        self.assertFalse(last['source']['tasks'][0]['derivedMarkerAlive'])
        self.assertTrue(last['source']['dispatches'][0]['gpuOwnersAlive'])
        self.assertEqual(b'original input',external_bytes.data);self.assertIsNotNone(external_base)
        for key in source.UNAVAILABLE:self.assertFalse(last['source'][key])
        self.assertTrue(first['source']['tasks'][0]['derivedMarkerAlive'])

    def test_raw_resource_url_query_and_userinfo_are_not_exported_as_content_provenance(self):
        b=Boundary();task=b.create();packet=b.reader().read(RUN);encoded=json.dumps(packet)
        for text in ('fixture-secret','fixture-token','example.invalid','https://'):self.assertNotIn(text,encoded)
        row=packet['source']['tasks'][0];self.assertEqual(64,len(row['resourceUrlFullyEncodedSha256']))
        self.assertGreater(row['resourceUrlFullyEncodedBytes'],0);self.assertEqual(len(task.buffer.data),row['constructorContentBytes'])
        for field in ('url','responseSha256','contentSha256'):
            broken=deepcopy(packet);broken['source']['tasks'][0][field]='wanted'
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.original(broken)

    def test_foreign_oversized_untyped_or_invented_completion_is_refused(self):
        for fault in ('version','task-cap','dispatch-cap','receiver-cap','phase-before-created','url-hash','url-length',
                'bytes-bool','gpu-bool','forged-queued-link','foreign-task','direct-dimensions','end-flag'):
            b,task=self.running();gpu=Holder();b.invoke(task,gpu,queued=fault!='direct-dimensions')
            b.phase(task,'readReturned');b.phase(task,'runReturned');b.deliver()
            packet=b.reader().read(RUN);table=packet['source'];row=table['tasks'][0]
            if fault=='version':table['assetImageReaderHistoryVersion']=True
            elif fault=='task-cap':table['tasks']=[dict(deepcopy(row),id=format(i,'032x')) for i in range(65)]
            elif fault=='dispatch-cap':table['dispatches']*=257
            elif fault=='receiver-cap':table['receivers']*=257
            elif fault=='phase-before-created':row['readEntered']=deepcopy(row['constructorEntered'])
            elif fault=='url-hash':row['resourceUrlFullyEncodedSha256']='wanted'
            elif fault=='url-length':row['resourceUrlFullyEncodedBytes']=4097
            elif fault=='bytes-bool':row['constructorContentBytes']=True
            elif fault=='gpu-bool':table['dispatches'][0]['gpuKnown']=1
            elif fault=='forged-queued-link':table['receivers'][0]['dispatchId']=table['dispatches'][0]['id']
            elif fault=='foreign-task':table['dispatches'][0]['taskId']='d'*32
            elif fault=='direct-dimensions':table['receivers'][0]['width']+=1
            else:table['decoderCompletionAvailable']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(packet)

    def test_history_loss_resurrection_rebound_and_failure_healing_are_refused(self):
        for fault in ('drop','rebind','resurrect','clock-rewrite','heal'):
            b,task=self.running();reader=b.reader()
            if fault=='resurrect':del task;gc.collect()
            if fault=='heal':b.value['complete']=False
            first=reader.read(RUN)
            def mutate(packet):
                if fault=='drop':packet['source']['tasks']=[]
                elif fault=='rebind':packet['source']['tasks'][0]['resourceId']='d'*32
                elif fault=='resurrect':packet['source']['tasks'][0]['derivedMarkerAlive']=True
                elif fault=='clock-rewrite':packet['source']['tasks'][0]['constructorEntered']['epochMs']+=1
                else:packet['source']['complete']=True
            b.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_actual_probe_consumes_nonce_once_and_missing_getter_stays_unavailable(self):
        b=Boundary();task=b.create();packet=b.reader().read(RUN);query=b.queries[-1]
        for field in ('taskId','sourceId','url','expectedHash','drained'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{field:'wanted'}))
        program="""const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsImageReader:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-image-reader.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('source rewritten/replayed');
delete Test.featureIOSAssetsImageReader;applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing getter invented empty evidence');
""".replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
