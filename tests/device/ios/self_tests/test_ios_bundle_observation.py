"""Original JS/private HTTP/AFC reader paths; deliberately synthetic native bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.bundle_observation import NativeBundleObservation,command
from ios.adapters.feature_observation import FeatureObservation
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source


class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.commands=[];self.request=None;self.value=None
        self.alive=True;self.ignored=False;self.mutate=None;self.pending=0
        self.bundle=dict(bundleContractVersion=1,bundleId='org.example.overte',executableSha256='a'*64,
            bundleSha256='b'*64,nodeCount=3,fileCount=2,totalBytes=1000)
        self.clock_source={'processId':42,'capturedEpochMs':20000}
    def send(self,request):self.commands.append(deepcopy(request));self.request=deepcopy(request)
    def original(self):
        if self.ignored or self.request is None:return ''
        self.sequence+=1;pending=self.pending>0;self.pending=max(0,self.pending-1)
        self.value=dict(bundleObservationVersion=1,commandId=self.request['commandId'],instance='c'*32,
            sequence=self.sequence,processId=42,capturedEpochMs=20000,status='pending' if pending else 'ready',
            preparedEpochMs=0 if pending else 19000,bundle={} if pending else deepcopy(self.bundle))
        if self.mutate:self.mutate(self.value)
        return json.dumps(self.value)
    def sleep(self,duration):self.clock+=duration
    def reader(self):return NativeBundleObservation(self.send,self.original,lambda:self.alive,42,lambda:dict(self.clock_source),
        monotonic=lambda:self.clock,sleep=self.sleep)


class BundleObservationTests(unittest.TestCase):
    def test_original_ready_bytes_are_not_archive_expectations_and_prepare_time_is_retained(self):
        n=Boundary();n.pending=3;reader=n.reader();value=reader.read()
        self.assertEqual(n.bundle,value['bundle']);self.assertEqual(19000,value['preparedEpochMs'])
        self.assertEqual(1,len(n.commands));self.assertEqual({'schemaVersion','commandId','action'},set(n.commands[0]))
        self.assertNotIn('bundleSha256',n.commands[0]);self.assertEqual(value['bundle'],reader.read()['bundle'])

    def test_missing_ignored_or_foreign_nonce_fails_without_resending(self):
        for fault in ('ignored','foreign','unavailable'):
            n=Boundary()
            if fault=='ignored':n.ignored=True
            elif fault=='foreign':n.mutate=lambda value:value.update(commandId='ios-'+'e'*32)
            else:n.mutate=lambda value:value.update(status='unavailable',preparedEpochMs=0,bundle={})
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):n.reader().read()
            self.assertEqual(1,len(n.commands));self.assertLessEqual(n.clock,100)

    def test_pid_instance_counter_native_time_or_original_bundle_changes_fail(self):
        for edit in ({'processId':43},{'instance':'f'*32},{'sequence':1},{'capturedEpochMs':19999},
                     {'preparedEpochMs':18000},{'bundle':dict(Boundary().bundle,bundleSha256='f'*64)}):
            n=Boundary();reader=n.reader();reader.read();n.mutate=lambda value:value.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read()

    def test_pending_source_cannot_change_instance_or_rewrite_an_existing_frame(self):
        for fault in ('instance','same-sequence'):
            n=Boundary();n.pending=1
            def change(value):
                if n.sequence>1:value.update(instance='f'*32) if fault=='instance' else value.update(sequence=1)
            n.mutate=change
            with self.assertRaises(NativeUIError):n.reader().read()

    def test_long_hash_does_not_let_stale_native_capture_or_foreign_clock_pass(self):
        for clock in ({'processId':43,'capturedEpochMs':20000},{'processId':42,'capturedEpochMs':22000},
                      {'processId':42,'capturedEpochMs':19000}):
            n=Boundary();n.clock_source=clock
            with self.assertRaises(NativeUIError):n.reader().read()

    def test_untyped_oversized_or_missing_manifest_and_bad_status_are_unavailable(self):
        for edit in ({'bundleObservationVersion':True},{'sequence':True},{'preparedEpochMs':20001},
                     {'bundle':{}},{'status':'passed'},{'expected':'b'*64}):
            n=Boundary();n.mutate=lambda value:value.update(edit)
            with self.assertRaises(NativeUIError):n.reader().read()
        n=Boundary();reader=n.reader();reader.original=lambda:'{"oversized":"'+'a'*262144+'"}'
        with self.assertRaises(NativeUIError):reader.read()

    def test_lost_foreground_late_transfer_or_regressing_monotonic_clock_fails(self):
        for fault in ('lost','late','rewind'):
            n=Boundary();original=n.original
            def read():
                value=original()
                if fault=='lost':n.alive=False
                else:n.clock=101 if fault=='late' else -1
                return value
            reader=n.reader();reader.original=read
            with self.assertRaises(NativeUIError):reader.read()

    def test_closed_ios_nonce_and_fixture_grammar_refuse_archive_paths_or_expected_values(self):
        value=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='ios-bundle-observe')
        state=FixtureState();state.set_client_command(value)
        for edit in ({'expected':'a'*64},{'path':'/private'},{'schemaVersion':True},
                     {'commandId':'a'*32},{'commandId':value['commandId']+'\n'}):
            with self.assertRaises((ValueError,NativeUIError)):command(value|edit)
            with self.assertRaises(ValueError):state.set_client_command(value|edit)

    def test_original_probe_refreshes_pending_once_and_stops_after_ready_without_fake_results(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureIOSBundleObservation:c=>{calls++;return {commandId:c.commandId,status:calls<2?'pending':'ready',bundle:{original:true}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'a'.repeat(32),action:'ios-bundle-observe'};
applyClientCommand(c);applyClientCommand(c);applyClientCommand(c);
if(calls!==2||files.length!==2||!files[1].v.bundle.original||files[1].name!=='ios-installed-bundle-observation.json')throw Error('pending source or ready dedup missing');
for(const edit of [{expected:'b'.repeat(64)},{path:'/private'},{commandId:c.commandId+'\n'},{schemaVersion:true}])applyClientCommand({...c,...edit});
if(calls!==2)throw Error('unsafe command accepted');
delete Test.featureIOSBundleObservation;applyClientCommand({...c,commandId:'ios-'+'b'.repeat(32)});
if(files.length!==3||files[2].v.available!==false)throw Error('missing source green');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_feature_transport_uses_original_afc_bundle_then_separate_native_clock(self):
        source=Boundary();clock=ClockBoundary();clock.mutate=lambda value:value.update(processId=42)
        fixture=FixtureState();echo=[b''];actions=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def read(self,_limit):return echo[0]
        class Client:
            def execute(self,session,operation,values):
                if session!='test-only' or operation!='mobile: pullFile':raise AssertionError('unexpected device command')
                path=values['remotePath']
                if path=='@org.example.overte:documents/owned-results/ios-installed-bundle-observation.json':raw=source.original()
                elif path=='@org.example.overte:documents/owned-results/feature-native-observation.json':raw=json.dumps(clock.sample)
                else:raise AssertionError('foreign private file')
                return base64.b64encode(raw.encode()).decode()
        def post(request,timeout):
            self.assertEqual(5,timeout);value=json.loads(request.data);fixture.set_client_command(value)
            actions.append(value['action']);echo[0]=json.dumps(value).encode()
            if value['action']=='ios-bundle-observe':source.send(value)
            elif value['action']=='feature-native-observe':clock.send(value)
            else:raise AssertionError('unexpected native input')
            return Response()
        target=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId='org.example.overte',
            testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://controlled.invalid:49121'))
        observer=FeatureObservation(Client(),'test-only',target,
            lambda:dict(bundleId='org.example.overte',pid=42,foreground=True),monotonic=lambda:source.clock,sleep=source.sleep)
        with patch('ios.adapters.feature_observation.post_request',side_effect=post):
            value=observer.installed_bundle().read()
        self.assertEqual(source.bundle,value['bundle']);self.assertEqual(['ios-bundle-observe','feature-native-observe'],actions)


if __name__=='__main__':unittest.main()
