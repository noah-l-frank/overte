"""Real fixture/probe/HTTP/AFC routing with explicitly modeled native Qt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import pointer_state as source,feature_observation
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary,RUN
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source


class PointerTransportTests(unittest.TestCase):
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

    def test_actual_dispatch_and_end_original_survive_independent_clock_http_and_afc(self):
        boundary=NativePointerBoundary();boundary.touch('touch-begin');boundary.touch('touch-end')
        native,observer=self.transport(boundary);reader=observer.pointer_state();value=reader.read(RUN)
        self.assertEqual(boundary.packet,value);self.assertEqual(1,len(value['source']['ends']))
        self.assertEqual(['feature-native-observe',source.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
        self.assertEqual(3,len(native.reads));self.assertNotEqual(9000,value['clockAfter']['epochMs'])
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])

    def test_actual_fixture_and_probe_never_accept_requested_absence_or_replay_getter(self):
        fixture=FixtureState();query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=source.ACTION,runId=RUN)
        self.assertEqual(query,fixture.set_client_command(query))
        for extra in ({'contacts':[]},{'complete':True},{'reset':True},{'afterSequence':0},{'schemaVersion':True}):
            with self.subTest(extra=extra),self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|extra)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),source:{complete:false,contacts:[{point:5}]}};
const Test={featureIOSPointerState:c=>{calls++;return original},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-pointer-state',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files.length!==1||files[0].v!==original||files[0].name!=='feature-ios-pointer-state.json')throw Error('original replaced/replayed');
for(const extra of [{contacts:[]},{complete:true},{reset:true},{afterSequence:0},{schemaVersion:true}])applyClientCommand({...c,...extra,commandId:'ios-'+'d'.repeat(32)});
if(calls!==1)throw Error('requested pointer result admitted');
delete Test.featureIOSPointerState;applyClientCommand({...c,commandId:'ios-'+'c'.repeat(32)});
if(files.length!==2||files[1].v.status!=='unavailable'||files[1].v.source)throw Error('missing native source became drained');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_lost_or_foreign_original_is_not_reissued_and_changed_process_blocks_afc(self):
        for fault in ('missing','foreign','process'):
            boundary=NativePointerBoundary();native,observer=self.transport(boundary);send=boundary.send
            def changed(query):
                send(query)
                if fault=='foreign':boundary.packet['requestId']='ios-'+'0'*32
                if fault=='process':native.pid=43
            boundary.send=changed
            if fault=='missing':boundary.original=lambda:''
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):observer.pointer_state().read(RUN)
            self.assertEqual(1,len(boundary.requests))
            if fault=='process':self.assertFalse(any(path.endswith('/'+source.FILE) for path in native.reads))


if __name__=='__main__':unittest.main()
