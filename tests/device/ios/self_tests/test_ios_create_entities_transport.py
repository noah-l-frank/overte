"""Actual fixture/probe/HTTP/AFC paths with modeled native entity originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import decode
from fixture.serve import FixtureState
from ios.adapters import create_entities as source,feature_observation
from ios.self_tests.test_ios_create_entities import NativeBoundary,RUN
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source


class EntityTransportTests(unittest.TestCase):
    def transport(self,boundary):
        native=Native();clock=ClockBoundary();observer=native.observer()
        observer.monotonic=boundary.mono;observer.sleep=lambda seconds:setattr(boundary,'now',boundary.now+round(seconds*1000))
        observer.epoch_ms=lambda:9000
        def stamp(value):
            epoch=boundary.tick();value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            (clock if query['action']=='feature-native-observe' else boundary).send(query);return native
        def execute(session,operation,values):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation));path=values['remotePath'];native.reads.append(path)
            prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+source.FILE))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else boundary.original()
            return base64.b64encode(raw.encode()).decode()
        for seam in (patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute)):
            seam.start();self.addCleanup(seam.stop)
        return native,observer
    def test_factory_preserves_actual_return_and_tree_originals_through_native_clock_http_and_afc(self):
        boundary=NativeBoundary();id_=boundary.add();native,observer=self.transport(boundary);reader=observer.create_entities();value=reader.read(RUN)
        self.assertEqual(boundary.packet,value);self.assertEqual(id_,value['source']['calls']['events'][0]['entityId'])
        self.assertEqual(['feature-native-observe',source.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
        self.assertEqual(3,len(native.reads));self.assertNotEqual(9000,value['clockAfter']['epochMs'])
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])
    def test_bounded_original_larger_than_old_generic_limit_survives_exact_transport(self):
        boundary=NativeBoundary()
        for _ in range(512):boundary.add()
        native,observer=self.transport(boundary);value=observer.create_entities().read(RUN)
        raw=boundary.original().encode();self.assertGreater(len(raw),262144);self.assertLess(len(raw),source.LIMIT)
        self.assertEqual(boundary.packet,value);self.assertEqual(512,len(value['source']['tree']['entities']))
        self.assertEqual(1,len(boundary.commands))
        with self.assertRaises(NativeUIError):decode(raw.decode())
        self.assertEqual(value,decode(raw.decode(),limit=source.LIMIT))
        for bad in ('{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises((NativeUIError,ValueError)):decode(bad,limit=source.LIMIT)
    def test_actual_fixture_and_probe_forbid_supplied_result_scope_and_never_replay_native_read(self):
        fixture=FixtureState();query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=source.ACTION,runId=RUN)
        self.assertEqual(query,fixture.set_client_command(query))
        for extra in ({'entityId':'1'*32},{'destroyed':True},{'reset':True},{'afterSequence':0},{'schemaVersion':True}):
            with self.subTest(extra=extra),self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|extra)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),source:{calls:{complete:false},tree:{complete:false}}};
const Test={featureIOSCreateEntities:c=>{calls++;return original},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-create-entities',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files.length!==1||files[0].v!==original||files[0].name!=='feature-ios-create-entities.json')throw Error('original replaced/replayed');
for(const extra of [{entityId:'a'},{destroyed:true},{reset:true},{afterSequence:0},{schemaVersion:true}])applyClientCommand({...c,...extra,commandId:'ios-'+'d'.repeat(32)});
if(calls!==1)throw Error('wanted result admitted');
delete Test.featureIOSCreateEntities;applyClientCommand({...c,commandId:'ios-'+'c'.repeat(32)});
if(files.length!==2||files[1].v.status!=='unavailable'||files[1].v.source)throw Error('missing native original became success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
    def test_lost_or_foreign_original_sends_one_read_and_process_rollover_blocks_afc(self):
        for fault in ('missing','foreign','process'):
            boundary=NativeBoundary();native,observer=self.transport(boundary);send=boundary.send
            def changed(query):
                send(query)
                if fault=='foreign':boundary.packet['requestId']='ios-'+'0'*32
                if fault=='process':native.pid=43
            boundary.send=changed
            if fault=='missing':boundary.original=lambda:''
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):observer.create_entities().read(RUN)
            self.assertEqual(1,len(boundary.commands))
            if fault=='process':self.assertFalse(any(path.endswith('/'+source.FILE) for path in native.reads))


if __name__=='__main__':unittest.main()
