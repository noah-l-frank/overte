"""Real input/HTTP/AFC/probe ownership; explicit original native-ledger seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import avatar_inputs as ledger,feature_observation,normal_input
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests import test_ios_avatar_input_owner as fixture
from self_tests.test_native_feature_observation import probe_source


def packet(pid=31,epoch=20000):
    return dict(iosNormalInputsVersion=1,profile='avatar',requestId='ios-'+'a'*32,runId=fixture.RUN,
        instance='e'*32,sequence=1,processId=pid,clockDomain='native-process-normal-inputs',
        clockBefore=dict(epochMs=epoch,monotonicMs=2),clockAfter=dict(epochMs=epoch,monotonicMs=2),
        source=dict(complete=True,events=[]))


class AvatarInputsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.InputOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        held=self.f.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        boundary=patch.object(normal_input,'urlopen',self.f.source.post);boundary.start();self.addCleanup(boundary.stop)
        self.owner=self.f.owner();self.owner.begin(fixture.CALL);self.f.source.lost=True
        with self.assertRaises(NativeUIError):self.f.ui(self.owner).input('avatar.url-open')
        self.intent=deepcopy(self.owner.state['calls'][0]['events'][0]['intent'])
        receipt=deepcopy(self.f.source.receipt);epoch=receipt['status']['sampleEpochMs'];self.value=packet(42,epoch)
        control=next(row for row in self.intent['reference']['controls'] if row['id']==self.intent['controlId'])
        event=dict(sequence=1,eventId=str(uuid.uuid4()),inputId=str(uuid.uuid4()),kind='received',clock=dict(epochMs=epoch,monotonicMs=1),
            details=dict(outerCommandId=receipt['commandId'],command=deepcopy(self.intent['nativeCommand']),controlId=self.intent['controlId'],
                root={key:control[key] for key in ('rootId','qmlSource')}))
        returned=dict(sequence=2,eventId=str(uuid.uuid4()),inputId=event['inputId'],kind='returned',clock=dict(epochMs=epoch,monotonicMs=2),details=receipt)
        self.value['source']['events']=[event,returned]
    def test_original_return_resolves_only_saved_input_without_resending_or_measuring_avatar_effect(self):
        before=len([row for row in self.f.source.requests if row['operation']=='edit']);receipt=ledger.delivered(self.value,self.intent)
        owner=self.f.owner();owner.load();owner.delivered(self.intent,receipt)
        self.f.source.lost=False;owner.observed(self.intent,self.f.io.capture());owner.finish()
        self.assertEqual(before,len([row for row in self.f.source.requests if row['operation']=='edit']))
        self.assertEqual('popup',self.f.source.dialog);self.assertNotIn('modelLoaded',receipt)
        self.assertEqual(self.value['source']['events'][1]['details'],owner.state['calls'][0]['events'][0]['delivery']['originalReceipt'])
    def test_missing_partial_rejected_duplicate_or_foreign_original_cannot_resolve_input(self):
        for fault in ('missing','partial','rejected','duplicate','command','root','profile','outer','pid','statusTime'):
            value=deepcopy(self.value);events=value['source']['events']
            if fault=='missing':events.clear()
            elif fault=='partial':events.pop()
            elif fault=='rejected':events[1]['details']['status']['performed']=False
            elif fault=='duplicate':
                event=deepcopy(events[0]);event.update(sequence=3,eventId=str(uuid.uuid4()),inputId=str(uuid.uuid4()),clock=deepcopy(events[1]['clock']));events.append(event)
            elif fault=='command':events[0]['details']['command']['fieldToken']=str(uuid.uuid4())
            elif fault=='root':events[0]['details']['root']['rootId']=str(uuid.uuid4())
            elif fault=='profile':value['profile']='login'
            elif fault=='outer':events[1]['details']['commandId']='ios-'+'f'*32
            elif fault=='pid':events[1]['details']['status']['processId']=43
            else:events[1]['details']['status']['sampleEpochMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):ledger.delivered(value,self.intent)
        value=deepcopy(self.value);value['source']['complete']=False;ledger.original(value)
        with self.assertRaises(NativeUIError):ledger.delivered(value,self.intent)
    def test_received_history_and_birth_cannot_reset_or_rewrite_across_fresh_queries(self):
        query=dict(schemaVersion=1,commandId='ios-'+'b'*32,action=ledger.ACTION,runId=fixture.RUN)
        after=deepcopy(self.value);after.update(requestId=query['commandId'],sequence=2)
        ledger.validate(after,query,42,previous=self.value)
        for fault in ('birth','prefix','complete','sequence'):
            previous=deepcopy(self.value);value=deepcopy(after)
            if fault=='birth':value['instance']='f'*32
            elif fault=='prefix':value['source']['events'][0]['eventId']=str(uuid.uuid4())
            elif fault=='complete':previous['source']['complete']=False
            else:value['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):ledger.validate(value,query,42,previous=previous)
    def test_actual_factory_uses_original_bound_AFC_file_and_independent_native_clock(self):
        native=Native();observer=native.observer();native.value=None
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.echo=json.dumps(query).encode()
            native.value=packet(native.pid);native.value.update(requestId=query['commandId']);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+ledger.FILE},arguments)
            return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=20000))
        with patch.object(feature_observation,'post_request',side_effect=post):
            reader=observer.avatar_inputs(clock);value=reader.read(fixture.RUN)
        self.assertEqual(ledger.LIMIT,reader._limit);self.assertEqual(native.pid,value['processId'])
        self.assertEqual('avatar',value['profile']);self.assertEqual(1,reader.acquisition['iosAvatarInputsAcquisitionVersion'])
    def test_actual_fixture_and_probe_consumes_each_nonce_even_unavailable_or_lost_save(self):
        state=FixtureState();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=ledger.ACTION,runId=fixture.RUN)
        self.assertEqual(query,state.set_client_command(query))
        for fault in (dict(profile='login'),dict(expected=True),dict(schemaVersion=True)):
            with self.assertRaises(ValueError):state.set_client_command(query|fault)
        script='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[],lose=false;const original=PACKET;
const Test={featureIOSAvatarInputs:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,name)=>{files.push({v,name});if(lose)throw Error('lost save');}};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].name!=="feature-ios-avatar-inputs.json")throw Error('source replay');
applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32),expected:true});if(calls!==1)throw Error('expected accepted');
delete Test.featureIOSAvatarInputs;applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});
const count=files.length;applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});if(files.length!==count||files.at(-1).v.status!=='unavailable')throw Error('unavailable retry');
lose=true;try{applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32)});}catch(_){}
const count2=files.length;try{applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32)});}catch(_){}
if(files.length!==count2)throw Error('lost save repeated');
'''.replace('PACKET',json.dumps(packet())).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_both_actual_transport_import_orders_work_in_independent_fresh_python_processes(self):
        import sys
        for modules in (('normal_input','feature_observation','avatar_inputs'),('feature_observation','avatar_inputs','normal_input')):
            script=';'.join('import ios.adapters.'+name for name in modules)
            result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=5)
            self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
