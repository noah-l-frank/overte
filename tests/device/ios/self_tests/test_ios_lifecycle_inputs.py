"""Actual private input ownership/transports; Qt/native reception are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import base64
from pathlib import Path
import tempfile
import time
import unittest
import uuid
import subprocess
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import lifecycle_inputs as source,normal_input
from ios.adapters.lifecycle_input_owner import LifecycleInputOwner,project
from ios.adapters.snapshot_input_owner import SnapshotInputPending
from ios.self_tests.test_ios_lifecycle_fields import FieldBoundary
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.test_ios_tablet_back_controls import BackBoundary
from ios.adapters.tablet_back_controls import FIELDS as BACK_FIELDS
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from ios.self_tests.test_ios_installed_adapter import InstalledAdapterTests
from ios.adapters import feature_observation
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Native(FieldBoundary):
    def __init__(self,epoch_ms=lambda:time.time()*1000):
        super().__init__();self.events=[];self.epoch_ms=epoch_ms;self.epoch=int(epoch_ms());self.origin=self.epoch-1
        self.counter=0;self.queries=[];self.ignored=False;self.verify=None;self.packet=None
        self.back={key:value for key,value in BackBoundary().observed()['controls'][0].items() if key in BACK_FIELDS}
    def observed(self):
        value=super().observed();value['sampleEpochMs']=int(value['sampleEpochMs']);row=value['controls'][0]
        if self.field=='tablet.back':
            row.pop('lifecycleField');row.update(self.back);value['tabletBackControlsVersion']=1
        elif self.field=='chat.input':
            row.pop('lifecycleField');row.update(inputReady=True,text=self.census.fields[-1]['current']['text'])
            value.update(chatControlsVersion=1,chatGeneration='22222222-2222-4222-8222-222222222222')
        return value
    def stamp(self):
        self.epoch=max(self.epoch,int(self.epoch_ms()))+1
        return dict(epochMs=self.epoch,monotonicMs=self.epoch-self.origin)
    def event(self,key,kind,details):
        self.events.append(dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=key,kind=kind,clock=self.stamp(),details=deepcopy(details)))
    def post(self,request,timeout):
        query=json.loads(request.data);key=str(uuid.uuid4())
        if query['operation']=='edit':
            if self.verify:self.verify(query['input'])
            reference=project(self.observed(),self.field)
            self.event(key,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId=self.field,root=reference['root']))
        returned=Boundary.post(self,request,timeout)
        if query['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=max(int(self.receipt['status']['sampleEpochMs']),self.epoch)
            if self.ignored:self.receipt['status']['performed']=False
            self.event(key,'returned',self.receipt)
            if self.lost:raise OSError('Declared lost return after original native input')
        return returned
    def send(self,query):
        self.queries.append(deepcopy(query));self.counter+=1;before=self.stamp()
        self.packet=dict(iosNormalInputsVersion=1,profile='lifecycle',requestId=query['commandId'],runId=query['runId'],instance='b'*32,
            sequence=self.counter,processId=42,clockDomain='native-process-normal-inputs',clockBefore=before,clockAfter=self.stamp(),
            source=dict(complete=True,events=deepcopy(self.events)))
    def reader(self):
        return source.IOSLifecycleInputs(self.send,lambda:json.dumps(self.packet),lambda:self.stamp()['epochMs'],lambda:True,42,
            monotonic=lambda:self.clock,sleep=lambda _:None)


class LifecycleInputOwnerTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
        self.native=Native();self.normal=self.native.input();self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.enterContext(self.lock.held());self.enterContext(patch.object(normal_input,'urlopen',self.native.post))
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned',generation=1,targetFingerprint='c'*64)
        self.store=PrivateFeatureState(self.root/LifecycleInputOwner.store_name('primary'));self.owner=self.open()
        def before(command):
            actual=self.store.read();self.assertEqual(actual,self.owner.previous)
            self.assertEqual('issued',self.owner.current()['phase']);self.assertEqual(command,self.owner.current()['command'])
        self.native.verify=before
    def open(self):return LifecycleInputOwner(self.store,self.lock,self.binding,RUN,'primary',self.normal,lambda:True)
    def reserve(self):return self.owner.reserve(self.native.field,project(self.normal.capture(),self.native.field),operation='replace',text='Overte ä Ω 東京 '+RUN)
    def edits(self):return [row for row in self.native.requests if row['operation']=='edit']

    def test_normal_unicode_delivery_has_durable_original_command_and_no_feature_claim(self):
        original=self.reserve();result=self.owner.send()
        self.assertEqual(dict(productOutcomeRequired=True),result);self.assertEqual(1,len(self.edits()))
        self.assertEqual(original,self.edits()[0]['input']);self.assertEqual('delivered',self.open().current()['phase'])
        raw=self.native.reader().read(RUN);proof=source.delivered(raw,original,self.native.field,self.owner.root(self.owner.current()))
        self.assertEqual(self.owner.current()['receipt'],proof['originalReceipt'])
        # The boundary deliberately reports unchanged field text. Delivery does
        # not manufacture a text/focus/generation/keyboard effect.
        self.assertEqual('',self.native.census.fields[-1]['current']['text'])

    def test_lost_return_reconstructs_from_original_native_history_once_without_resending(self):
        original=self.reserve();self.native.lost=True
        with self.assertRaises(OSError):self.owner.send()
        self.assertEqual('issued',self.open().current()['phase']);self.native.lost=False
        restored=self.open();restored.recover(self.native.reader().read(RUN));count=len(self.edits())
        archived=LifecycleInputOwner.history(self.store,self.lock,self.binding,RUN,'primary')
        self.assertEqual(original,archived.validate_original(1)['command']);self.assertEqual(count,len(self.edits()))
        with self.assertRaises(SnapshotInputPending):restored.send()
        self.assertEqual(1,count)

    def test_rejected_or_unreturned_original_never_discards_or_replays_issued_input(self):
        self.reserve();self.native.ignored=True
        with self.assertRaises(NativeUIError):self.owner.send()
        packet=self.native.reader().read(RUN)
        for mutate in (lambda v:None,lambda v:v['source']['events'].pop(),lambda v:v['source'].update(complete=False)):
            value=deepcopy(packet);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):self.open().recover(value)
        self.assertEqual('issued',self.open().current()['phase']);self.assertEqual(1,len(self.edits()))

    def test_replaced_actual_field_refuses_before_native_dispatch(self):
        self.reserve();self.native.census.load('create')
        with self.assertRaises(NativeUIError):self.owner.send()
        self.assertEqual([],self.edits());self.assertEqual('reserved',self.open().current()['phase'])

    def test_foreign_run_text_or_unowned_draft_refuses_before_an_input_is_issued(self):
        reference=project(self.normal.capture(),self.native.field)
        with self.assertRaises(NativeUIError):self.owner.reserve(self.native.field,reference,operation='replace',text='Overte ä Ω 東京 '+'d'*32)
        self.assertEqual([],self.edits());self.assertIsNone(self.store.read())

    def test_raw_packet_history_nonce_root_and_native_receipt_cannot_be_substituted(self):
        original=self.reserve();self.owner.send();reader=self.native.reader();packet=reader.read(RUN)
        for mutate in (lambda v:v.update(profile='snapshot'),lambda v:v.update(iosNormalInputsVersion=True),
            lambda v:v['source']['events'][0]['details']['root']['identity'].update(fieldId='e'*32),
            lambda v:v['source']['events'][0]['details']['command'].update(commandId=str(uuid.uuid4())),
            lambda v:v['source']['events'][-1]['details']['status'].update(processId=43)):
            value=deepcopy(packet);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.delivered(value,original,self.native.field,self.owner.root(self.owner.current()))
        self.assertEqual(1,len(self.edits()))

    def test_two_current_owned_contexts_keep_distinct_original_roots(self):
        self.reserve();self.owner.send();first=self.owner.root(self.owner.current())
        self.native.census.load('scripts');self.native.field='lifecycle.scripts.filter'
        reference=project(self.normal.capture(),self.native.field)
        self.owner.reserve(self.native.field,reference,operation='replace',text='retry-'+RUN);self.owner.send()
        restored=self.open();self.assertEqual(2,len(restored.state['events']))
        self.assertNotEqual(first,restored.root(restored.current()));self.assertEqual(2,len(self.edits()))

    def test_chat_uses_its_original_unsent_reply_field_and_never_submits(self):
        self.native.census.load('chat');self.native.field='chat.input'
        reference=project(self.normal.capture(),self.native.field)
        command=self.owner.reserve(self.native.field,reference,operation='replace',text='reply-'+RUN);self.owner.send()
        packet=self.native.reader().read(RUN);source.delivered(packet,command,self.native.field,self.owner.root(self.owner.current()))
        self.assertEqual('chat',self.owner.root(self.owner.current())['identity']['editor'])
        self.assertEqual(['replace'],[row['input']['operation'] for row in self.edits()])
        self.assertEqual('',self.native.census.fields[-1]['current']['text'])

    def test_back_keeps_original_semantic_history_and_refuses_intervening_history_change(self):
        self.native.field='tablet.back';reference=project(self.normal.capture(),self.native.field)
        self.owner.reserve(self.native.field,reference);self.native.back['sourceHistorySha256']='e'*64
        with self.assertRaises(NativeUIError):self.owner.send()
        self.assertEqual([],self.edits());self.native.back['sourceHistorySha256']=reference['root']['observation']['sourceHistorySha256']
        self.owner.send();command=self.owner.current()['command'];packet=self.native.reader().read(RUN)
        proof=source.delivered(packet,command,self.native.field,self.owner.root(self.owner.current()))
        self.assertEqual('back',proof['root']['kind']);self.assertEqual('activate',command['operation'])
        self.assertNotIn('text',command);self.assertEqual(1,len(self.edits()))

    def test_actual_probe_and_fixture_consume_each_closed_nonce_once(self):
        command=self.reserve();self.owner.send();packet=self.native.reader().read(RUN)
        query=dict(schemaVersion=1,commandId=packet['requestId'],action=source.ACTION,runId=RUN)
        fixture=FixtureState();self.assertEqual(query,fixture.set_client_command(query))
        with self.assertRaises(ValueError):fixture.set_client_command(dict(query,expectedDelivered=True))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];const Test={featureIOSLifecycleInputs:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].f!=='feature-ios-lifecycle-inputs.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error('source replay or rewriting');
applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32),expectedDelivered:true});if(calls!==2)throw Error('expected outcome accepted');
delete Test.featureIOSLifecycleInputs;applyClientCommand({...q,commandId:'ios-'+'e'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source qualified');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual(1,len(self.edits()))


class LifecycleInputRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.native=Native(epoch_ms=lambda:20000);self.afc=[]
        def clock(packet):self.k.b.time=self.native.epoch-20000;self.k.native_clock(packet)
        self.f.clock.mutate=clock
        previous_execute=self.k.client.execute
        def execute(session,operation,arguments):
            if operation=='mobile: pullFile' and arguments['remotePath'].endswith('/'+source.FILE):
                self.afc.append(arguments['remotePath']);return base64.b64encode(json.dumps(self.native.packet).encode()).decode()
            return previous_execute(session,operation,arguments)
        self.k.client.execute=execute
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            self.native.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))

    def test_existing_factory_reads_exact_original_file_without_session_or_launch(self):
        before=(self.f.sessions,self.f.launches);reader=self.f.adapter._lifecycle_inputs('test-only');packet=reader.read(RUN)
        self.assertEqual([],packet['source']['events']);self.assertEqual(1,len(self.afc));self.assertEqual(1,len(self.native.queries))
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertEqual(source.ACTION+'.json',self.afc[0].rsplit('/',1)[1])

    def test_changed_candidate_blocks_source_transport(self):
        reader=self.f.adapter._lifecycle_inputs('test-only');self.f.artifact.write_bytes(b'Changed candidate after source construction')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.native.queries);self.assertEqual([],self.afc)

    def test_context_reader_cannot_escape_its_original_source_lock(self):
        runtime=self.f.adapter._lifecycle_input_runtime();before=(self.f.sessions,self.f.launches)
        with runtime.inputs('test-only',RUN) as (owner,reader):
            self.assertEqual([],owner.state['events']);reader.read(RUN)
        count=len(self.native.queries)
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(count,len(self.native.queries));self.assertEqual(before,(self.f.sessions,self.f.launches))


class LifecycleInstalledAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=InstalledAdapterTests('test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.adapter.describe('test-only')

    def test_unresolved_or_malformed_journal_blocks_ordinary_sdk_actions_before_transport(self):
        f=self.f;store=PrivateFeatureState(f.root/'ios-lifecycle-primary-inputs.json');store.write({'unresolved-input':True},None)
        before=(f.sessions,f.launches,deepcopy(f.commands),deepcopy(f.process),f.adapter.read_session('test-only'))
        for action in (lambda:f.adapter.describe('test-only'),lambda:f.adapter.invoke('test-only','app.stop',{}),lambda:f.adapter.cleanup('test-only')):
            with self.assertRaises(NativeUIError):action()
        self.assertEqual(before,(f.sessions,f.launches,deepcopy(f.commands),deepcopy(f.process),f.adapter.read_session('test-only')))
        self.assertEqual({'unresolved-input':True},store.read())
