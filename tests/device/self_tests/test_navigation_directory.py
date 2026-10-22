"""Actual Python input/HTTP/journals; native/Qt provenance boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest
import uuid
from unittest.mock import patch
from urllib.request import urlopen
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_directory import NativeNavigationDirectory,command,joined_directory
from adapters.navigation_directory import NavigationDirectory
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.token_places_ui import TokenPlacesUI,sha
from adapters.script_journey.history import unpack,pack
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY,QUERY
from feature_journeys.server import make_server
from feature_journeys.fixtures import context
from feature_journeys.witness import Client
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source
import self_tests.test_token_places_ui as places

RUN='a'*32;TICKET='b'*32;HIDDEN='c'*32;OWNED='d'*32
ORIGIN='https://controlled.invalid'
INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='a'*40,sceneUrl='http://controlled.invalid/scene.json')
ROOT=Path(__file__).resolve().parents[3]
CODE=(ROOT/'scripts/system/places/places.js').read_text().encode('utf-16-le')
PROFILE=dict(sourceRevision=INPUTS['sourceRevision'],scriptUrlSha256=sha('file:///android_asset/scripts/system/places/places.js'),
    codeSha256=hashlib.sha256(CODE).hexdigest(),codeUnits=len(CODE)//2)

class Model(places.Widgets):
    def __init__(self,root):
        super().__init__(root);self.page=True
        self.provider=NavigationResources(INPUTS,clock_ms=self.epoch);self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        self.source_sequence=0;self.source_packet=None;self.source_edit=None;self.source_ignore=False
        self.reads=[];self.messages=[];self.revision=0;self.last_message=None;self.records_hash=None;self.loaded_row=None
        self.lose_control=None;self.skip_read=False;self.skip_out=False;self.skip_records=False;self.network=None
    def raw(self):
        value=super().raw()
        if self.loaded_row is not None:
            for page in value['controls']:
                if page['id']=='places.page':
                    for row in page['directory']['rows']:
                        if row['placeIdSha256']==sha(self.loaded_row['id']):
                            row['placeNameSha256']=sha(self.loaded_row['name']);row['placeAddressSha256']=sha(self.loaded_row['address'])
        return value
    def source_read(self,request):
        if self.source_ignore:return
        self.source_sequence+=1
        self.source_packet=dict(navigationDirectoryVersion=1,commandId=request['commandId'],runId=request['runId'],instance='f'*32,
            sequence=self.source_sequence,processId=123,capturedEpochMs=self.epoch(),
            ui=dict(bridgeId=self.bridge,generation=self.generation,sequence=self.sequence,elapsedMs=100+round(self.clock*1000),observedEpochMs=self.epoch()),
            reads=deepcopy(self.reads),messages=deepcopy(self.messages),roots=[dict(rootId='e'*32,alive=True,current=True,
                sourceSha256='d'*64,revision=self.revision,frameRevision=self.revision,lastMessageId=self.last_message,recordsSha256=self.records_hash)])
        if self.source_edit:self.source_edit(self.source_packet)
    def reader(self):
        return NativeNavigationDirectory(self.source_read,lambda:json.dumps(self.source_packet) if self.source_packet else '',
            self.epoch,self.guard,123,monotonic=lambda:self.clock,sleep=self.sleep)
    def received(self,body,response,origin=ORIGIN):
        if self.skip_read:return
        row=json.loads(body)['data']['places'][0];read_id=uuid.uuid4().hex
        self.reads.append(dict(readId=read_id,runId=RUN,responseId=response,origin=origin,httpStatus=200,networkError=0,
            bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),readEpochMs=self.epoch(),managerInstance='1'*32,loadGeneration=1,
            scriptUrlSha256=PROFILE['scriptUrlSha256'],code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=PROFILE['codeUnits'],
                sha256=PROFILE['codeSha256'],submittedEpochMs=19000),idSha256=sha(row['id']),nameSha256=sha(row['name']),
            addressSha256=sha(row['address']),protocolSha256=sha(row['domain']['protocol_version']),maturity=row['maturity']))
        if self.skip_out:return
        message_id=uuid.uuid4().hex
        self.messages.append(dict(messageId=message_id,readId=read_id,outgoingEpochMs=self.epoch(),recordsSha256=sha(body.decode()),
            targetRootId='e'*32,deliveredRootId=None,deliveredEpochMs=None))
        if self.skip_records:return
        self.loaded_row=deepcopy(row)
        self.messages[-1].update(deliveredRootId='e'*32,deliveredEpochMs=self.epoch())
        self.revision+=1;self.last_message=message_id;self.records_hash=self.messages[-1]['recordsSha256']
    def send(self,c):
        result=super().send(c)
        if c['controlId']=='places.refresh' and not self.ignore and not self.ignore_effect:
            if self.network:
                with urlopen(self.network+DIRECTORY+'?'+QUERY,timeout=2) as response:
                    body=response.read();header=response.headers['X-Overte-Fixture-Response']
                self.received(body,header,origin=self.network)
            else:
                with self.provider.response(DIRECTORY,QUERY) as response:status,body,header=response
                self.received(body,header)
        if (c['controlId'],c['action'])==self.lose_control:raise NativeUIError('Synthetic lost applied input reply')
        return result

class NavigationDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=places.PlacesControlTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=Model(self.fixture.root);self.fixture.navigation.io=self.model
        self.path=self.fixture.root/'directory-owner.json';self.origin=ORIGIN;self.inputs=deepcopy(INPUTS);self.run_id=RUN
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:synthetic-start',
            sessionId=self.model.bridge,generation=0,targetFingerprint='c'*64)
    def status(self):return self.model.provider.snapshot(self.run_id)
    def owner(self):
        return NavigationDirectory(lambda intent:TokenPlacesUI(PicoPlacesIO(self.fixture.original),intent,self.run_id,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep),self.model.reader(),self.status,self.path,self.run_id,self.binding,
            self.model.provider.instance,self.inputs,self.origin,PROFILE,self.model.guard,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
    def act(self,ticket,verb):
        self.model.provider.activate(self.run_id,ticket)
        return self.owner().act(ticket,verb)
    def test_normal_refresh_hidden_quiet_and_owned_results_join_same_original_read_and_new_inputs(self):
        self.assertEqual(dict(performed=True),self.act(TICKET,'refresh'));proof=deepcopy(self.owner().state['proof'])
        self.act(HIDDEN,'hidden');self.assertEqual(context(RUN)['hidden'],self.model.query)
        self.assertEqual(7,len(self.owner().state['active']['quiet']));self.assertEqual(proof,self.owner().state['proof'])
        self.act(OWNED,'owned');self.assertEqual(context(RUN)['name'],self.model.query)
        self.assertEqual(5,len(self.model.calls));self.assertEqual(1,len(self.model.reads))
        self.assertEqual(proof,self.owner().state['proof']);before=deepcopy(self.model.calls)
        self.owner().act(OWNED,'owned');self.assertEqual(before,self.model.calls)
    def test_applied_lost_refresh_focus_and_query_replies_are_never_resent(self):
        for control in (('places.refresh','activate'),('places.search','activate'),('places.search','replace')):
            self.setUp()
            if control[0]=='places.search':self.act(TICKET,'refresh')
            self.model.lose_control=control;ticket,verb=(TICKET,'refresh') if control[0]=='places.refresh' else (HIDDEN,'hidden')
            with self.subTest(control=control),self.assertRaises(NativeUIError):self.act(ticket,verb)
            count=len(self.model.calls);self.assertIsNotNone(self.owner().state['active']['pending'])
            self.model.lose_control=None;self.act(ticket,verb)
            self.assertEqual(1 if verb=='refresh' else 3,len(self.model.calls));self.assertGreaterEqual(len(self.model.calls),count)
    def test_http_only_read_only_outgoing_only_or_ignored_refresh_cannot_prove_current_qml_data(self):
        for fault in ('skip_read','skip_out','skip_records','ignore_effect'):
            self.setUp();setattr(self.model,fault,True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act(TICKET,'refresh')
            self.assertEqual(1,len(self.model.calls));self.assertIsNotNone(self.owner().state['active']['pending'])
            with self.assertRaises(NativeUIError):self.act(HIDDEN,'hidden')
            self.assertEqual(1,len(self.model.calls))
    def test_preloaded_current_model_and_old_read_cannot_replace_a_new_normal_refresh(self):
        with self.model.provider.response(DIRECTORY,QUERY) as response:status,body,header=response
        self.model.received(body,header);self.model.ignore_effect=True
        with self.assertRaises(NativeUIError):self.act(TICKET,'refresh')
        self.assertEqual(1,len(self.model.reads));self.assertEqual(1,len(self.model.calls))
        self.assertIsNotNone(self.owner().state['active']['pending']);self.assertIsNone(self.owner().state['proof'])

    def test_ignored_search_cannot_borrow_existing_directory_model_or_current_source(self):
        self.act(TICKET,'refresh');self.model.ignore_effect=True
        with self.assertRaises(NativeUIError):self.act(HIDDEN,'hidden')
        self.assertNotEqual(context(RUN)['hidden'],self.model.query)
        self.assertIsNotNone(self.owner().state['active']['pending'])
    def test_foreign_receipt_hash_source_code_protocol_and_message_or_root_cannot_pass(self):
        edits=(lambda v:v['reads'][0].update(responseId='7'*32),lambda v:v['reads'][0].update(sha256='7'*64),
            lambda v:v['reads'][0]['code'].update(sha256='7'*64),lambda v:v['reads'][0].update(protocolSha256='7'*64),
            lambda v:v['reads'][0].update(readEpochMs=19000),lambda v:v['roots'][0].update(current=False),lambda v:v['roots'][0].update(frameRevision=0),
            lambda v:v['messages'][0].update(targetRootId='',deliveredRootId=None,deliveredEpochMs=None))
        for edit in edits:
            self.setUp()
            def fault(v):
                if v['reads']:edit(v)
            self.model.source_edit=fault
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.act(TICKET,'refresh')
            self.assertEqual(1,len(self.model.calls))
    def test_native_birth_cursor_history_drop_and_packet_injection_fail_after_valid_read(self):
        for edit in (lambda v:v.update(instance='7'*32),lambda v:v.update(sequence=1),lambda v:v.update(reads=[]),
                     lambda v:v.update(expected='loaded'),lambda v:v.update(processId=124)):
            self.setUp();self.act(TICKET,'refresh');reader=self.model.reader();reader.read(RUN);self.model.source_edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(RUN)
        self.setUp();self.model.source_ignore=True
        with self.assertRaises(NativeUIError):self.model.reader().read(RUN)
        self.assertLessEqual(self.model.clock,5.01)
    def test_frozen_clock_extra_input_or_changed_original_data_cannot_finish_quiet(self):
        for fault in ('clock','input','records'):
            self.setUp();sleep=self.model.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='clock':self.model.source_edit=lambda v:v['ui'].update(observedEpochMs=20000)
                elif fault=='input':self.model.sequence+=1
                else:self.model.revision+=1
            self.model.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act(TICKET,'refresh')
            self.assertFalse(self.owner().state['active']['quiet'])
    def test_changed_maturity_tab_or_unowned_dialog_during_quiet_cannot_complete_search(self):
        for fault in ('maturity','tab','dialog','generation'):
            self.setUp();sleep=self.model.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='tab':self.model.tab=1
                elif fault=='dialog':self.model.dialog=True
                elif fault=='generation':self.model.generation=str(uuid.uuid4())
                else:
                    def mutate(value):
                        for row in value['controls']:
                            if row['id']=='places.page':row['maturity']=['everyone','teen']
                    self.model.edit=mutate
            self.model.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act(TICKET,'refresh')
            self.assertFalse(self.owner().state['active']['quiet'])

    def test_changed_original_compressed_history_and_reused_query_refuse_recreation(self):
        self.act(TICKET,'refresh');state=self.owner().state
        with patch('adapters.native_navigation_directory.uuid.uuid4',return_value=SimpleNamespace(hex=state['queries'][0])):
            with self.assertRaises(NativeUIError):self.owner().act(TICKET,'refresh')
        disk=json.loads(self.path.read_text());value=unpack(disk['payload'])[0];value['last']['native']['reads'][0]['responseId']='8'*32
        disk['payload']=pack([value]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner()
    def test_actual_loopback_response_bytes_and_completed_write_receipt_join_normal_search_pipeline(self):
        server=make_server('r'*32,'p'*32,navigation_resources=self.model.provider)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.origin=self.model.network=f'http://127.0.0.1:{server.server_port}'
            self.act(TICKET,'refresh');self.act(HIDDEN,'hidden');self.act(OWNED,'owned')
            receipt=self.model.provider.snapshot(RUN)['responses'][0]
            self.assertEqual(receipt['sha256'],self.model.reads[0]['sha256'])
            self.assertEqual(receipt['responseId'],self.model.reads[0]['responseId'])
            self.assertEqual(5,len(self.model.calls))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(0,server.internal_errors)

    def test_actual_private_pico_factory_uses_original_source_file_and_existing_normal_controls(self):
        sys.path.insert(0,str(ROOT/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        sdk=native_fixture.NativeExecutionBindingTest();sdk.setUp();self.addCleanup(sdk.doCleanups)
        adapter=sdk.instance();adapter._scripts=lambda target:SimpleNamespace(ui=SimpleNamespace(io=self.fixture.original),binding=self.binding)
        native=SimpleNamespace(send=self.model.source_read,clock_ms=self.model.epoch,guard=self.model.guard,pid=123,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        adapter._native_feature_observer=lambda target:native
        def read(target,package,filename,*,attempts):
            self.assertEqual(('owned','org.overte.pico','files/overte-e2e/feature-navigation-directory.json',1),(target,package,filename,attempts))
            return json.dumps(self.model.source_packet)
        adapter.adb.read_debug_app_file=read
        with patch('adapters.navigation_directory.NavigationDirectory',partial(NavigationDirectory,monotonic=lambda:self.model.clock,sleep=self.model.sleep)):
            owner=adapter._navigation_directory('owned',self.path,RUN,self.status,self.model.provider.instance,INPUTS,self.origin,PROFILE,self.model.guard)
        self.assertEqual(dict(performed=True),owner.act(TICKET,'refresh'));self.assertEqual(1,len(self.model.calls))

    def test_closed_probe_command_uses_original_fixed_native_packet_and_absent_hook_is_unavailable(self):
        request=dict(schemaVersion=1,commandId='9'*32,action='feature-navigation-directory',runId=RUN)
        fixture=FixtureState();fixture.set_client_command(request)
        for extra in ({'schemaVersion':True},{'expected':'loaded'},{'url':ORIGIN},{'responseId':'8'*32}):
            with self.assertRaises((ValueError,NativeUIError)):command(request|extra)
            with self.assertRaises(ValueError):fixture.set_client_command(request|extra)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureNavigationDirectory:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'9'.repeat(32),action:'feature-navigation-directory',runId:'a'.repeat(32)};
applyClientCommand(c);if(calls!==1||!files[0].v.original||files[0].name!=='feature-navigation-directory.json')throw Error('Original source missing');
applyClientCommand({...c,expected:'loaded'});if(calls!==1)throw Error('Unsafe expected value');delete Test.featureNavigationDirectory;
applyClientCommand({...c,commandId:'8'.repeat(32)});if(files[1].v.status!=='unavailable')throw Error('Absent source became success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)

if __name__=='__main__':unittest.main()
