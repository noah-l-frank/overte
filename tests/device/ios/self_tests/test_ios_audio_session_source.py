"""OS/gate/native sources are declared models; codecs, probe and AFC run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import audio_session_source as source,feature_observation
from ios.self_tests import test_ios_keyboard_runtime as keyboard
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Boundary:
    def __init__(self,epoch=1900000000000):
        self.epoch=epoch;self.time=0;self.sequence=0;self.raw='';self.queries=[];self.mutate=None;self.delay=0;self.good=True
        self.instance=uuid.uuid4().hex;self.gate=dict(available=True,osPermission=1,gatePermission=1,outcome=2,
            foreground=True,interrupted=False,captureAllowed=True,playbackAllowed=True,outputRevision=4)
    def stamp(self):self.time+=1;return dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1
        value=dict(iosAudioSessionVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.instance,
            sequence=self.sequence,processId=42,clockDomain='native-main-ios-audio-session',clockBefore=self.stamp(),clockAfter=self.stamp(),
            lifecycle=dict(backgrounds=0,activations=1,launches=1),source=deepcopy(self.gate))
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value);self.time+=self.delay
    def reader(self):return source.IOSAudioSession(self.send,lambda:self.raw,lambda:self.epoch+self.time,lambda:self.good,42,
        monotonic=lambda:self.time/1000,sleep=lambda seconds:setattr(self,'time',self.time+round(seconds*1000)))


class AudioSessionSourceTests(unittest.TestCase):
    def test_actual_os_permission_and_cached_gate_are_separate_original_facts(self):
        b=Boundary();b.gate.update(osPermission=2);before=deepcopy(b.gate)
        value=b.reader().read(RUN);self.assertEqual('denied',source.definite_permission(value))
        self.assertEqual(1,value['source']['gatePermission']);self.assertTrue(value['source']['captureAllowed'])
        self.assertEqual(before,b.gate);self.assertEqual(1,len(b.queries))

    def test_granted_os_does_not_invent_running_gate_or_capture(self):
        b=Boundary();b.gate.update(gatePermission=2,outcome=0,captureAllowed=False,playbackAllowed=False)
        value=b.reader().read(RUN);self.assertEqual('granted',source.definite_permission(value))
        self.assertFalse(value['source']['captureAllowed']);self.assertEqual(0,value['source']['outcome'])

    def test_unknown_revoked_and_missing_native_owner_are_not_definite_permission(self):
        for permission in (0,3):
            b=Boundary();b.gate.update(osPermission=permission)
            with self.assertRaises(NativeUIError):source.definite_permission(b.reader().read(RUN))
        b=Boundary();b.gate.update(available=False,osPermission=0,captureAllowed=False,playbackAllowed=False)
        with self.assertRaises(NativeUIError):source.definite_permission(b.reader().read(RUN))

    def test_reused_nonce_identity_output_revision_and_clock_faults_keep_previous_original(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN);saved=deepcopy(reader.acquisition)
        for mutate in (lambda v:v.update(requestId=first['requestId']),lambda v:v.update(processId=43),
            lambda v:v.update(sequence=first['sequence']),lambda v:v['source'].update(outputRevision=3),
            lambda v:v['clockAfter'].update(monotonicMs=v['clockBefore']['monotonicMs']-1)):
            b.mutate=mutate
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last);self.assertEqual(saved,reader.acquisition)

    def test_boolean_enum_private_route_and_inconsistent_gate_are_not_valid_sources(self):
        for mutate in (lambda v:v.update(iosAudioSessionVersion=True),lambda v:v['source'].update(osPermission=True),
            lambda v:v['source'].update(deviceName='private route'),lambda v:v['source'].update(outcome=0),
            lambda v:v['source'].update(foreground=False),lambda v:v['source'].update(interrupted=True)):
            b=Boundary();b.mutate=mutate
            with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_late_source_and_lost_guard_never_reanchor_old_authorization(self):
        b=Boundary();b.delay=1600
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        b=Boundary();b.good=False
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        self.assertEqual([],b.queries)

    def test_actual_probe_and_fixture_accept_only_read_and_consume_nonce_once(self):
        b=Boundary();packet=b.reader().read(RUN);query=b.queries[-1]
        self.assertEqual(query,FixtureState().set_client_command(query))
        with self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,permission='granted'))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSAudioSession:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=='feature-ios-audio-session.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('source changed/replayed');
applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32),permission:'granted'});if(calls!==1)throw Error('requested state accepted');
delete Test.featureIOSAudioSession;applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing native source became permission');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class AudioSessionRuntimeTests(unittest.TestCase):
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
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read
        self.sources=self.k.fixture.runtime._sources('test-only')
    def reader(self):return self.sources['observer'].audio_session(clock_source=self.sources['clock_source'])
    def test_original_factory_native_clocks_and_afc_preserve_existing_candidate_without_launch(self):
        before=(self.f.sessions,self.f.launches);reader=self.reader();packet=reader.read(RUN)
        self.assertEqual('granted',source.definite_permission(packet));self.assertEqual(1,len(self.afc))
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertIn('iosAudioSessionAcquisitionVersion',reader.acquisition)
        self.assertLess(packet['clockAfter']['epochMs'],100000)
    def test_changed_candidate_blocks_source_before_http_or_afc(self):
        reader=self.reader();self.f.artifact.write_bytes(b'Changed original installed candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
    def test_foreign_pid_or_background_never_reads_foreground_audio_source(self):
        for change in (dict(pid=43),dict(foreground=False)):
            original=deepcopy(self.f.process);reader=self.reader();self.f.process.update(change)
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=original;self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
