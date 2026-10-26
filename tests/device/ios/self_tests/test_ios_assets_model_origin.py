"""Native parser/resource events are explicit models; codecs/probe/AFC execute.

No native parser, render, compiler, network service or device is executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import gc
import json
import subprocess
import unittest
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import pinned_resource
from fixture.serve import FixtureState
from ios.adapters import assets_model_origin as source,feature_observation
from ios.self_tests import test_ios_create_state as create,test_ios_keyboard_runtime as keyboard
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Boundary:
    def __init__(self,epoch=create.EPOCH):
        self.epoch=epoch;self.time=20;self.sequence=0;self.raw='';self.queries=[];self.mutate=None;self.delay=0;self.good=True
        raw=pinned_resource('asset-stand.fbx');self.body=raw
        clock=lambda offset:dict(epochMs=epoch+offset,monotonicMs=offset)
        self.row=dict(id='1'*32,kind='model',requestedUrl='atp:/e2e-'+RUN+'/asset-stand.fbx',effectiveUrl='atp:'+'f'*64,
            received=clock(1),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode(),
            readerCreated=clock(2),runEntered=clock(3),runReturned=clock(7),queued=clock(4),invokeReturned=clock(5),invokeAccepted=True,
            deliveryEntered=clock(8),deliveryReturned=clock(9),resourceAlive=True,readerKnown=True,readerAlive=False,modelKnown=True,parsedModelAlive=True)
        native=create.packet();create.add_model(native)
        self.state=dict(complete=True,domainId=create.DOMAIN,localSessionId=create.SESSION,tree=native['source']['tree'],
            models=[dict(entityId=create.ID,present=True,loaded=True,addedToScene=True,failed=False,
                origin=dict(modelUrl=self.row['requestedUrl'],watcherUrl=self.row['requestedUrl'],geometry=dict(readerId=self.row['id'],mappingIds=[])))],
            history=dict(assetModelOriginHistoryVersion=1,instance='2'*32,complete=True,clock=clock(10),downloads=[self.row]),resourceRetirementAvailable=False)
    def stamp(self):self.time+=1;return dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.stamp();self.state['history']['clock']=self.stamp()
        value=dict(iosAssetsModelOriginVersion=1,requestId=query['commandId'],runId=query['runId'],instance='3'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-assets-model-origin',clockBefore=before,
            clockAfter=self.stamp(),source=deepcopy(self.state))
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value);self.time+=self.delay
    def reader(self):return source.IOSAssetsModelOrigin(self.send,lambda:self.raw,lambda:self.epoch+self.time,lambda:self.good,42,
        monotonic=lambda:self.time/1000,sleep=lambda seconds:setattr(self,'time',self.time+round(seconds*1000)))


class AssetsModelOriginTests(unittest.TestCase):
    def test_actual_original_parser_body_and_model_watcher_lineage_keep_retirement_unavailable(self):
        b=Boundary();packet=b.reader().read(RUN);proof=source.parsed_input(packet,create.ID)
        self.assertEqual(len(b.body),proof['bytes']);self.assertEqual(hashlib.sha256(b.body).hexdigest(),proof['sha256'])
        self.assertEqual(b.row['effectiveUrl'],proof['effectiveUrl']);self.assertFalse(packet['source']['resourceRetirementAvailable'])
        self.assertNotIn('rendered',proof);self.assertNotIn('retired',proof);self.assertEqual(1,len(b.queries))

    def test_requested_url_or_loaded_flag_without_original_delivery_is_not_a_parsed_input(self):
        for mutate in (lambda b:b.state['models'][0]['origin']['geometry'].update(readerId=''),
            lambda b:b.row.update(deliveryEntered=None,deliveryReturned=None),lambda b:b.row.update(deliveryReturned=None),
            lambda b:b.row.update(runReturned=None),lambda b:b.row.update(invokeAccepted=False),
            lambda b:b.state['models'][0].update(failed=True),lambda b:b.state['models'][0].update(addedToScene=False)):
            b=Boundary();mutate(b);packet=b.reader().read(RUN)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.parsed_input(packet,create.ID)

    def test_original_body_hash_count_encoding_or_aggregate_overflow_is_rejected(self):
        for mutate in (lambda r:r.update(sha256='0'*64),lambda r:r.update(bytes=r['bytes']+1),
            lambda r:r.update(base64=r['base64']+'\n'),lambda r:r.update(base64=base64.b64encode(b'wrong original').decode()),
            lambda r:r.update(readerAlive=1),lambda r:r.update(invokeAccepted=1)):
            b=Boundary();mutate(b.row)
            with self.subTest(mutate=mutate),self.assertRaises((NativeUIError,ValueError)):b.reader().read(RUN)
        b=Boundary();b.state['history']['downloads']=[dict(b.row,id=str(index)*32) for index in (1,2,3)]
        with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_oversized_unretained_body_stays_diagnostic_and_incomplete(self):
        b=Boundary();b.state['complete']=b.state['history']['complete']=False;b.row.update(bytes=40000,base64=None,sha256='e'*64)
        packet=b.reader().read(RUN);self.assertIsNone(packet['source']['history']['downloads'][0]['base64'])
        with self.assertRaises(NativeUIError):source.parsed_input(packet,create.ID)
        b=Boundary();b.row['base64']=None
        with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_actual_mapping_parent_chain_is_separate_from_raw_model_input(self):
        b=Boundary();mapping=deepcopy(b.row);raw=b'filename = asset.fbx\n'
        mapping.update(id='4'*32,kind='mapping',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode(),
            requestedUrl=b.row['requestedUrl']+'.fst',effectiveUrl='atp:'+'e'*64,readerKnown=False,readerAlive=False,modelKnown=False,parsedModelAlive=False,invokeAccepted=None)
        for key in source.TIMES[1:]:mapping[key]=None
        b.state['history']['downloads'].insert(0,mapping);b.state['models'][0]['origin']['geometry']['mappingIds']=[mapping['id']]
        packet=b.reader().read(RUN);self.assertEqual([mapping['id']],source.parsed_input(packet,create.ID)['mappingIds'])
        packet['source']['models'][0]['origin']['geometry']['mappingIds']=[b.row['id']]
        with self.assertRaises(NativeUIError):source.original(packet)

    def test_missing_foreign_membership_or_invented_resource_retirement_are_not_valid_sources(self):
        for mutate in (lambda v:v['source'].update(resourceRetirementAvailable=True),
            lambda v:v['source']['models'][0].update(entityId=create.ROOT),
            lambda v:v['source']['models'][0]['origin']['geometry'].update(readerId='f'*32),
            lambda v:v['source']['history']['downloads'][0]['queued'].update(monotonicMs=0),
            lambda v:v['source']['history'].update(clock=dict(epochMs=1,monotonicMs=1))):
            b=Boundary();b.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_readonly_reentry_preserves_all_old_original_events_and_does_not_retimenative_history(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN);second=reader.read(RUN)
        self.assertEqual(first['source']['history']['downloads'],second['source']['history']['downloads'])
        for mutate in (lambda v:v['source']['history']['downloads'][0]['received'].update(epochMs=b.epoch+2),
            lambda v:v['source']['history']['downloads'][0].update(runReturned=None),
            lambda v:v['source']['history'].update(downloads=[]),lambda v:v.update(processId=43),
            lambda v:v.update(instance='5'*32),lambda v:v['source'].update(domainId=create.ROOT)):
            b.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(second,reader.last)

    def test_stale_source_lost_guard_and_unknown_command_fields_do_not_reanchor_or_dispatch(self):
        b=Boundary();b.delay=1600
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        b=Boundary();b.good=False
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        self.assertEqual([],b.queries)
        query=dict(schemaVersion=1,commandId='ios-'+'b'*32,action=source.ACTION,runId=RUN)
        for field in ('entityId','url','sha256','operation'):
            with self.assertRaises(NativeUIError):source.command(dict(query,**{field:'wanted'}))

    def test_actual_probe_and_fixture_read_only_once_and_missing_getter_stays_unavailable(self):
        b=Boundary();packet=b.reader().read(RUN);query=b.queries[-1]
        self.assertEqual(query,FixtureState().set_client_command(query))
        with self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,entityId=create.ID))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelOrigin:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=='feature-ios-assets-model-origin.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('source changed/replayed');
applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32),url:'wanted'});if(calls!==1)throw Error('requested URL accepted');
delete Test.featureIOSAssetsModelOrigin;applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source became empty origin');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class AssetsModelOriginRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=keyboard.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.b=Boundary(20000);self.afc=[]
        def native_clock(packet):self.k.b.time=self.b.time;self.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            FixtureState().set_client_command(query);self.b.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post));execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')
    def reader(self):return self.sources['observer'].assets_model_origin(clock_source=self.sources['clock_source'])
    def test_factory_keeps_candidate_and_actual_native_original_clock_without_app_launch(self):
        before=(self.f.sessions,self.f.launches);packet=self.reader().read(RUN)
        self.assertEqual(self.b.row['sha256'],source.parsed_input(packet,create.ID)['sha256']);self.assertEqual(1,len(self.afc))
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertLess(packet['clockAfter']['epochMs'],100000)
    def test_changed_candidate_refuses_before_source_dispatch_or_afc_read(self):
        reader=self.reader();self.f.artifact.write_bytes(b'changed installed candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
    def test_wrong_process_or_background_refuses_before_source_dispatch_or_afc_read(self):
        for change in (dict(pid=43),dict(foreground=False)):
            original=deepcopy(self.f.process);reader=self.reader();self.f.process.update(change)
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=original;self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
    def test_history_two_actual_object_observation_uses_original_afc_and_native_clock(self):
        self.b.state['history']['assetModelOriginHistoryVersion']=2;self.b.row.update(resourceAlive=False,resourceObjectAlive=True)
        packet=self.reader().read(RUN);row=packet['source']['history']['downloads'][0]
        self.assertFalse(row['resourceAlive']);self.assertTrue(row['resourceObjectAlive']);self.assertEqual(1,len(self.afc))
        self.assertLess(packet['clockAfter']['epochMs'],100000);self.assertFalse(packet['source']['resourceRetirementAvailable'])


class AssetsModelOriginObjectTests(unittest.TestCase):
    def test_legacy_expired_shared_lease_keeps_actual_cached_object_inventory_unknown(self):
        b=Boundary();b.row['resourceAlive']=False;packet=b.reader().read(RUN)
        self.assertEqual(1,packet['source']['history']['assetModelOriginHistoryVersion'])
        self.assertNotIn('resourceObjectAlive',packet['source']['history']['downloads'][0]);source.parsed_input(packet,create.ID)
        self.assertFalse(packet['source']['resourceRetirementAvailable'])

    def test_distinct_real_weak_shared_lease_and_object_lifetimes_survive_cache_reinsertion(self):
        class Holder:pass
        original_lease=Holder();cached_object=Holder();lease=weakref.ref(original_lease);object_=weakref.ref(cached_object)
        b=Boundary()
        def lifetime(packet):
            history=packet['source']['history'];history['assetModelOriginHistoryVersion']=2
            history['downloads'][0].update(resourceAlive=lease() is not None,resourceObjectAlive=object_() is not None)
        b.mutate=lifetime;reader=b.reader();first=reader.read(RUN)
        del original_lease;gc.collect();second=reader.read(RUN);row=second['source']['history']['downloads'][0]
        self.assertFalse(row['resourceAlive']);self.assertTrue(row['resourceObjectAlive']);self.assertTrue(row['parsedModelAlive'])
        self.assertEqual(first['source']['history']['downloads'][0]['received'],row['received']);source.parsed_input(second,create.ID)
        del cached_object;gc.collect();third=reader.read(RUN)
        self.assertFalse(third['source']['history']['downloads'][0]['resourceObjectAlive']);self.assertTrue(third['source']['history']['downloads'][0]['parsedModelAlive'])
        self.assertFalse(third['source']['resourceRetirementAvailable'])

    def test_new_object_field_requires_history_two_and_remains_exact_boolean_original(self):
        for version,present,value in ((1,True,True),(2,False,None),(2,True,1),(True,True,True),(3,True,True)):
            b=Boundary()
            def malformed(packet):
                packet['source']['history']['assetModelOriginHistoryVersion']=version
                if present:packet['source']['history']['downloads'][0]['resourceObjectAlive']=value
            b.mutate=malformed
            with self.subTest(version=version,present=present,value=value),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_actual_object_observation_cannot_be_removed_by_a_history_version_rollback(self):
        b=Boundary();b.state['history']['assetModelOriginHistoryVersion']=2;b.row['resourceObjectAlive']=True
        reader=b.reader();original=reader.read(RUN)
        b.state['history']['assetModelOriginHistoryVersion']=1;b.row.pop('resourceObjectAlive')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(original,reader.last)

    def test_actual_probe_preserves_history_two_object_observation_without_reissuing_getter(self):
        b=Boundary();b.state['history']['assetModelOriginHistoryVersion']=2;b.row.update(resourceAlive=False,resourceObjectAlive=True)
        packet=b.reader().read(RUN);query=b.queries[-1]
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelOrigin:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('object source changed/replayed');
const history=files[0].v.source.history;if(history.assetModelOriginHistoryVersion!==2||history.downloads[0].resourceAlive!==false||history.downloads[0].resourceObjectAlive!==true)throw Error('cached QObject confused with old lease');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
