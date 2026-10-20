"""Native callback/clock boundaries are synthetic; original probe JS executes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_replies import NativeNavigationReplies,command,validate
from adapters.normal_ui import NativeUIError
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.fixtures import context
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN,TICKET='a'*32,'b'*32
ORIGIN='http://owned.invalid:49121'
INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='c'*40,sceneUrl=ORIGIN+'/scene.json')


class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.commands=[];self.request=None;self.alive=True;self.ignored=False;self.edit=None
        self.events=[];self.generation=2;self.active=True;self.last_id=None;self.cached=None
    def epoch(self):return 20000+round(self.clock*1000)
    def send(self,request):self.request=deepcopy(request);self.commands.append(deepcopy(request))
    def error(self,response='d'*32,*,origin=ORIGIN):
        self.events.append(dict(sequence=len(self.events)+1,eventId='e'*32,runId=RUN,responseId=response,origin=origin,
            httpStatus=404,networkError=203,contentNotFound=True,current=True,lookupGeneration=self.generation,callbackEpochMs=self.epoch()))
    def original(self):
        if self.ignored:return ''
        if self.request['commandId']!=self.last_id:
            self.last_id=self.request['commandId'];self.sequence+=1
            self.cached=dict(navigationReplyVersion=1,commandId=self.last_id,runId=self.request['runId'],instance='f'*32,
                sequence=self.sequence,processId=123,capturedEpochMs=self.epoch(),currentLookupGeneration=self.generation,
                currentLookupActive=self.active,events=deepcopy([e for e in self.events if e['runId']==self.request['runId']]))
        value=deepcopy(self.cached)
        if self.edit:self.edit(value)
        return json.dumps(value)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,*,ios=False):
        return NativeNavigationReplies(self.send,self.original,self.epoch,lambda:self.alive,123,
            ios=ios,monotonic=lambda:self.clock,sleep=self.sleep)
    def provider(self):
        return dict(navigationProviderVersion=1,instance='1'*32,runId=RUN,inputs=deepcopy(INPUTS),capturedEpochMs=self.epoch(),
            active=True,ticket=TICKET,failedResponses=0,responses=[dict(sequence=1,responseId='d'*32,ticket=TICKET,
                kind='missing-name',status=404,bytes=100,sha256='2'*64,completedEpochMs=self.epoch())])
    def join(self,reader=None,provider=None,*,barrier=20000):
        return (reader or self.reader()).owned_missing(RUN,owned_origin=ORIGIN,ticket=TICKET,after_epoch=barrier,
            provider_status=self.provider() if provider is None else provider,provider_instance='1'*32,provider_inputs=INPUTS)


class NativeNavigationRepliesTests(unittest.TestCase):
    def test_empty_actual_history_is_read_but_never_proves_missing_lookup(self):
        source=Boundary();reader=source.reader();self.assertEqual([],reader.read(RUN)['events'])
        with self.assertRaises(NativeUIError):source.join(reader)
        source.error();value=source.join(reader)
        self.assertEqual(source.events[0],value['native']);self.assertEqual(source.provider()['responses'][0],value['http'])
        self.assertNotIn('error',value);self.assertNotIn('state',value)

    def test_acknowledged_ignored_missing_or_foreign_nonce_is_bounded_one_send(self):
        for fault in ('ignored','foreign','missing-hook'):
            source=Boundary();source.error()
            if fault=='ignored':source.ignored=True
            elif fault=='foreign':source.edit=lambda value:value.update(commandId='0'*32)
            else:source.edit=lambda value:(value.clear(),value.update(commandId=source.request['commandId'],status='unavailable'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5.01)

    def test_origin_response_identity_current_scope_and_native_error_must_all_match(self):
        edits=(lambda v:v['events'][0].update(responseId=''),lambda v:v['events'][0].update(responseId='3'*32),
            lambda v:v['events'][0].update(origin='http://foreign.invalid'),lambda v:v.update(currentLookupActive=False),
            lambda v:v.update(currentLookupGeneration=3),lambda v:v['events'][0].update(httpStatus=500),
            lambda v:v['events'][0].update(contentNotFound=False,networkError=4),lambda v:v['events'][0].update(current=False),
            lambda v:v['events'][0].update(networkError=4))
        for edit in edits:
            source=Boundary();source.error();source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.join()

    def test_server_response_requires_its_original_owner_ticket_status_and_input_barrier(self):
        edits=(lambda v:v.update(runId='3'*32),lambda v:v.update(instance='3'*32),lambda v:v.update(active=False,ticket=None),
            lambda v:v['responses'][0].update(ticket='3'*32),lambda v:v['responses'][0].update(responseId='3'*32),
            lambda v:v['responses'][0].update(kind='directory',status=200),lambda v:v.update(responses=[]),
            lambda v:v['responses'][0].update(completedEpochMs=19000),lambda v:v['inputs'].update(sourceRevision='4'*40))
        for edit in edits:
            source=Boundary();source.error();value=source.provider();edit(value)
            with self.subTest(edit=edit),self.assertRaises((ValueError,NativeUIError)):source.join(provider=value)
        source=Boundary();source.error();source.events[0]['callbackEpochMs']=19000
        with self.assertRaises(NativeUIError):source.join()

    def test_pid_native_clock_source_identity_and_closed_packet_are_mandatory(self):
        for edit in (lambda v:v.update(processId=124),lambda v:v.update(capturedEpochMs=18000,events=[]),
                     lambda v:v.update(navigationReplyVersion=True),lambda v:v.update(runId='3'*32),
                     lambda v:v.update(expected='not-found'),lambda v:v['events'][0].update(origin='http://user:secret@owned.invalid'),
                     lambda v:v['events'][0].update(lookupGeneration=3),lambda v:v['events'][0].update(callbackEpochMs=21000)):
            source=Boundary();source.error();source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_original_native_history_cannot_be_deleted_retimed_mutated_or_replayed(self):
        for edit in (lambda v:v.update(events=[]),lambda v:v['events'][0].update(eventId='3'*32),
                     lambda v:v['events'][0].update(callbackEpochMs=19999),lambda v:v.update(instance='3'*32),
                     lambda v:v.update(sequence=1),lambda v:v.update(currentLookupGeneration=1)):
            source=Boundary();source.error();reader=source.reader();reader.read(RUN);source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(RUN)
        source=Boundary();source.error();reader=source.reader();reader.read(RUN);reader.read('3'*32);source.events=[]
        with self.assertRaises(NativeUIError):reader.read(RUN)

    def test_late_source_clock_rewind_and_lost_process_cannot_finish_as_success(self):
        for fault in ('late','rewind','guard'):
            source=Boundary();source.error();original=source.original
            def changed():
                raw=original()
                if fault=='guard':source.alive=False
                else:source.clock=6 if fault=='late' else -1
                return raw
            reader=source.reader();reader.original=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(1,len(source.commands))

    def test_private_fixture_grammar_rejects_expected_state_arbitrary_uri_and_version_alias(self):
        state=FixtureState();request=dict(schemaVersion=1,commandId='ios-'+'5'*32,action='feature-navigation-replies',runId=RUN)
        state.set_client_command(request)
        for edit in ({'expected':'not-found'},{'url':'http://anywhere.invalid'},{'schemaVersion':True},
                     {'commandId':request['commandId']+'\n'},{'runId':'foreign'}):
            with self.subTest(edit=edit),self.assertRaises((ValueError,NativeUIError)):command(request|edit,ios=True)
            with self.assertRaises(ValueError):state.set_client_command(request|edit)

    def test_original_probe_uses_fixed_native_source_and_missing_hook_is_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureNavigationReplies:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'5'.repeat(32),action:'feature-navigation-replies',runId:'a'.repeat(32)};
applyClientCommand(c);if(calls!==1||!files[0].v.original||files[0].name!=='feature-navigation-replies.json')throw Error('original source absent');
for(const edit of [{expected:'not-found'},{url:'http://foreign.invalid'},{schemaVersion:true},{commandId:c.commandId+'\n'}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('unsafe command accepted');delete Test.featureNavigationReplies;
applyClientCommand({...c,commandId:'ios-'+'6'.repeat(32)});if(files[1].v.status!=='unavailable')throw Error('missing native hook became empty success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_loopback_response_id_and_completed_write_receipt_join_only_its_synthetic_native_boundary(self):
        source=Boundary();provider=NavigationResources(INPUTS,clock_ms=source.epoch)
        server=make_server('r'*32,'p'*32,navigation_resources=provider);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}';client=Client(base+'/feature-fixture/v1','r'*32)
            run,_=client.register('world-navigation');client.activate(TICKET)
            with self.assertRaises(HTTPError) as caught:urlopen(base+DIRECTORY+'/'+context(run)['hidden'],timeout=2)
            try:raw=caught.exception.read();response=caught.exception.headers['X-Overte-Fixture-Response']
            finally:caught.exception.close()
            source.error(response,origin=base);source.events[0]['runId']=run
            status=client.navigation_status()
            result=source.reader().owned_missing(run,owned_origin=base,ticket=TICKET,after_epoch=source.epoch(),provider_status=status,
                provider_instance=provider.instance,provider_inputs=INPUTS)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),result['http']['sha256'])
            self.assertEqual(response,result['native']['responseId'])
            status['responses'][0]['responseId']='0'*32
            with self.assertRaises(NativeUIError):source.reader().owned_missing(run,owned_origin=base,ticket=TICKET,after_epoch=source.epoch(),
                provider_status=status,provider_instance=provider.instance,provider_inputs=INPUTS)
            client.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(0,server.internal_errors)


if __name__=='__main__':unittest.main()
