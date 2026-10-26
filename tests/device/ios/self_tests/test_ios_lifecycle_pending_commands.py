"""Actual pending command/original codecs; native/Qt provider is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import lifecycle_pending_commands as source,feature_observation
from self_tests.test_pending_commit_owner import Boundary as Native,RUN
from self_tests.test_native_feature_observation import probe_source
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests


class Journal:
    def __init__(self):
        self.native=Native();self.rows=[];self.sequence=0;self.query=None;self.queries=[];self.packet=None
        self.installed=True;self.complete=True;self.mutate=None;original=self.native.original
        def returned():
            raw=original();reply=json.loads(raw);command=self.native.request
            if command['operation'] in ('hold','attempt','release') and not any(row['command']['commandId']==command['commandId'] for row in self.rows):
                self.rows.append(dict(index=len(self.rows)+1,command=deepcopy(command),reply=deepcopy(reply),recordedEpochMs=self.native.epoch()))
            return raw
        self.native.original=returned
    def send(self,query):
        self.query=deepcopy(query);self.queries.append(deepcopy(query));self.sequence+=1
    def original(self):
        stamp=dict(epochMs=self.native.epoch(),monotonicMs=round(self.native.clock*1000))
        value=dict(iosLifecyclePendingCommandsVersion=1,requestId=self.query['commandId'],runId=self.query['runId'],instance='c'*32,
            sequence=self.sequence,processId=123,clockDomain='native-main-lifecycle-pending-commands',clockBefore=stamp,clockAfter=deepcopy(stamp),
            source=dict(installed=self.installed,complete=self.complete,commands=deepcopy(self.rows)))
        if self.mutate:self.mutate(value)
        self.packet=value;return json.dumps(value)
    def reader(self):
        return source.IOSLifecyclePendingCommands(self.send,self.original,self.native.epoch,lambda:True,123,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def inputs(self):
        owner=self.native.owner(ios=True);owner.focus(RUN);owner.type_owned(RUN);held=owner.hold(RUN)
        event=held['commit']['observation']['eventId'];self.native.replace_context();owner.attempt_retired(RUN,event);owner.release_owned(RUN,event)
        return owner


class LifecyclePendingCommandsTests(unittest.TestCase):
    def test_hold_attempt_release_originals_survive_later_observe_without_input_or_clock_rewrite(self):
        b=Journal();owner=b.inputs();expected=deepcopy(b.rows);mutations=len(b.native.commands)
        owner.read(RUN,'1'*32);reader=b.reader();packet=reader.read(RUN)
        self.assertEqual(expected,packet['source']['commands']);self.assertEqual(mutations+1,len(b.native.commands))
        self.assertEqual(['hold','attempt','release'],[row['command']['operation'] for row in b.rows])
        for row in expected:self.assertEqual(row['reply'],source.delivered(packet,row['command']))
        receipt=source.delivered(packet,expected[1]['command'])
        self.assertEqual('context-retired',receipt['commit']['observation']['events'][-1]['reason'])
        self.assertNotIn('generation',receipt);self.assertEqual(1,len(b.queries))

    def test_old_original_return_keeps_its_time_and_request_after_native_hold_deadline(self):
        b=Journal();owner=b.inputs();original=deepcopy(b.rows[0]);b.native.sleep(12)
        value=b.reader().read(RUN);receipt=source.delivered(value,original['command'])
        self.assertEqual(original['reply'],receipt);self.assertGreaterEqual(value['clockBefore']['epochMs']-receipt['capturedEpochMs'],12000)
        self.assertEqual(original['command']['commandId'],receipt['commit']['observation']['requestId'])
        self.assertNotEqual(value['requestId'],receipt['commandId'])

    def test_missing_negative_foreign_nonce_and_rewritten_command_cannot_supply_delivery(self):
        b=Journal();b.inputs();packet=b.reader().read(RUN);request=deepcopy(b.rows[0]['command'])
        for mutate in (lambda v:v['source'].update(installed=False),lambda v:v['source'].update(complete=False),
            lambda v:v['source'].update(commands=[]),lambda v:v['source']['commands'][0]['reply'].update(performed=False)):
            bad=deepcopy(packet);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.delivered(bad,request)
        for update in (dict(commandId='ios-'+'f'*32),dict(fieldToken='f'*32),dict(runId='f'*32)):
            with self.subTest(update=update),self.assertRaises(NativeUIError):source.delivered(packet,dict(request,**update))

    def test_source_replay_or_old_prefix_mutation_preserves_last_original(self):
        b=Journal();b.inputs();reader=b.reader();first=reader.read(RUN);saved=deepcopy(first)
        for mutate in (lambda v:v.update(sequence=1),lambda v:v.update(processId=124),
            lambda v:v['source']['commands'][0]['reply'].update(performed=False),lambda v:v['source']['commands'][0].update(index=True),
            lambda v:v['source']['commands'][0]['reply'].pop('capturedEpochMs'),
            lambda v:v['source']['commands'][0].update(recordedEpochMs=19999)):
            b.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(saved,reader.last)

    def test_actual_probe_and_fixture_consume_nonce_once_and_missing_getter_stays_unavailable(self):
        b=Journal();b.inputs();packet=b.reader().read(RUN);query=b.queries[-1]
        self.assertEqual(query,FixtureState().set_client_command(query))
        with self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,expectedRejected=True))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSLifecyclePendingCommands:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=='feature-ios-lifecycle-pending-commands.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('original rewritten/replayed');
applyClientCommand({...q,commandId:'ios-'+'e'.repeat(32),expectedRejected:true});if(calls!==1)throw Error('requested result accepted');
delete Test.featureIOSLifecyclePendingCommands;applyClientCommand({...q,commandId:'ios-'+'f'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source became absence');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


class LifecyclePendingCommandsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f;self.j=Journal();self.afc=[]
        # Select the same modeled process epoch before its first source read.
        self.j.native.clock=self.k.b.time/1000
        previous=self.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.raw.encode()).decode()
            return previous(session,operation,values)
        self.k.client.execute=execute
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            self.j.send(query);value=json.loads(self.j.original());value['processId']=42;self.raw=json.dumps(value);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))

    def test_existing_clock_bound_factory_reads_exact_file_without_session_or_launch(self):
        from ios.adapters.script_runtime import IOSScriptRuntime
        sources=IOSScriptRuntime(self.f.adapter)._sources('test-only');before=(self.f.sessions,self.f.launches)
        reader=sources['observer'].lifecycle_pending_commands(sources['clock_source']);packet=reader.read(RUN)
        self.assertEqual([],packet['source']['commands']);self.assertEqual(1,len(self.afc));self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertIn('iosLifecyclePendingCommandsAcquisitionVersion',reader.acquisition)

    def test_changed_candidate_prevents_new_original_query(self):
        from ios.adapters.script_runtime import IOSScriptRuntime
        sources=IOSScriptRuntime(self.f.adapter)._sources('test-only');reader=sources['observer'].lifecycle_pending_commands(sources['clock_source'])
        self.f.artifact.write_bytes(b'Changed candidate before pending-command read')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.afc);self.assertEqual([],self.j.queries)
