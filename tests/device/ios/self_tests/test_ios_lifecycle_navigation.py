"""Real navigation WAL/transport/codecs; original Qt input is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from fixture.serve import FixtureState
from ios.adapters import lifecycle_navigation_inputs as source,lifecycle_navigation_controls as controls,normal_input,feature_observation
from ios.adapters.lifecycle_navigation_owner import LifecycleNavigationOwner
from ios.adapters.snapshot_input_owner import SnapshotInputPending
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Native(Boundary):
    def __init__(self,epoch_ms=lambda:time.time()*1000):
        super().__init__(field='hud.tablet');self.epoch_ms=epoch_ms;self.epoch=int(epoch_ms());self.origin=self.epoch-1
        self.metadata=dict(controlId=self.field,controlObject='a'*32,windowObject='b'*32,containerObject='c'*32,
            contextObject='d'*32,qmlSource='qrc:/qml/hifi/ActionBar.qml',surface='hud',inputReady=True)
        self.events=[];self.counter=0;self.queries=[];self.lost=False;self.ignored=False;self.verify=None
    def stamp(self):
        self.epoch=max(self.epoch,int(self.epoch_ms()))+1;return dict(epochMs=self.epoch,monotonicMs=self.epoch-self.origin)
    def observed(self):
        ui=super().observed();ui['sampleEpochMs']=int(self.epoch_ms());ui['tabletShown']=self.field!='hud.tablet'
        metadata=dict(self.metadata,controlId=self.field,surface='hud' if self.field=='hud.tablet' else 'tablet',token=self.token)
        ui['lifecycleNavigation']=dict(iosLifecycleNavigationVersion=1,complete=True,controls=[metadata]);return ui
    def event(self,key,kind,details):
        self.events.append(dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=key,kind=kind,clock=self.stamp(),details=deepcopy(details)))
    def post(self,request,timeout):
        query=json.loads(request.data);key=str(uuid.uuid4())
        if query['operation']=='edit':
            if self.verify:self.verify(query['input'])
            reference=controls.project(self.observed(),self.field)
            self.event(key,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId=self.field,root=reference['root']))
        result=super().post(request,timeout)
        if query['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=max(int(self.receipt['status']['sampleEpochMs']),self.epoch)
            if self.ignored:self.receipt['status']['performed']=False
            self.event(key,'returned',self.receipt)
            if self.lost:raise OSError('Declared lost original navigation return')
        return result
    def send(self,query):
        self.queries.append(deepcopy(query));self.counter+=1;before=self.stamp()
        self.packet=dict(iosNormalInputsVersion=1,profile='lifecycle-navigation',requestId=query['commandId'],runId=query['runId'],
            instance='e'*32,sequence=self.counter,processId=42,clockDomain='native-process-normal-inputs',
            clockBefore=before,clockAfter=self.stamp(),source=dict(complete=True,events=deepcopy(self.events)))
    def reader(self):
        return source.IOSLifecycleNavigationInputs(self.send,lambda:json.dumps(self.packet),lambda:self.stamp()['epochMs'],lambda:True,42,
            monotonic=lambda:self.clock,sleep=lambda _:None)


class LifecycleNavigationTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
        self.native=Native();self.normal=self.native.input();self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.enterContext(self.lock.held());self.enterContext(patch.object(normal_input,'urlopen',self.native.post))
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned',generation=1,targetFingerprint='c'*64)
        self.store=PrivateFeatureState(self.root/LifecycleNavigationOwner.store_name('primary'));self.owner=self.open()
        def before(command):
            self.assertEqual(self.store.read(),self.owner.previous);self.assertEqual('issued',self.owner.current()['phase'])
            self.assertEqual(command,self.owner.current()['command'])
        self.native.verify=before
    def open(self):return LifecycleNavigationOwner(self.store,self.lock,self.binding,RUN,'primary',self.normal,lambda:True)
    def reserve(self):return self.owner.reserve(self.native.field,controls.project(self.normal.capture(),self.native.field))
    def edits(self):return [q for q in self.native.requests if q['operation']=='edit']

    def test_durable_normal_opening_delivery_does_not_claim_editor_or_tablet_effect(self):
        command=self.reserve();before=self.native.observed();result=self.owner.send()
        self.assertEqual(dict(productOutcomeRequired=True),result);self.assertEqual('delivered',self.owner.current()['phase'])
        self.assertEqual(command,self.edits()[0]['input']);self.assertEqual(1,len(self.edits()))
        self.assertEqual(False,self.native.observed()['tabletShown']);self.assertEqual(before['controls'],self.native.observed()['controls'])
        self.assertNotIn('editor',result);self.assertNotIn('generation',result)

    def test_lost_original_is_recovered_once_without_repeat_or_retiming(self):
        self.reserve();self.native.lost=True
        with self.assertRaises(OSError):self.owner.send()
        owner=self.open();self.assertEqual('issued',owner.current()['phase'])
        packet=self.native.reader().read(RUN);saved=deepcopy(packet);owner.recover(packet)
        self.assertEqual(saved,packet);self.assertEqual(1,len(self.edits()));self.assertEqual('delivered',owner.current()['phase'])
        with self.assertRaises(SnapshotInputPending):owner.send()
        history=LifecycleNavigationOwner.history(self.store,self.lock,self.binding,RUN,'primary')
        self.assertTrue(history.validate_original(1)['productOutcomeRequired']);self.assertEqual(1,len(self.edits()))

    def test_matching_positive_inner_receipt_cannot_be_adopted_from_foreign_run_or_pid(self):
        self.reserve();self.native.lost=True
        with self.assertRaises(OSError):self.owner.send()
        packet=self.native.reader().read(RUN);before=self.store.path.read_bytes();inode=self.store.path.stat().st_ino
        for update in (dict(runId='f'*32),dict(processId=43),dict(processId=True)):
            bad=deepcopy(packet);bad.update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):self.owner.recover(bad)
            self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(inode,self.store.path.stat().st_ino)
            self.assertEqual('issued',self.owner.current()['phase']);self.assertEqual({},self.owner.state['storage'])
        self.owner.recover(packet);self.assertEqual(1,len(self.edits()))

    def test_changed_actual_source_identity_or_disabled_point_refuses_before_dispatch(self):
        for key,new in (('controlObject','f'*32),('containerObject','f'*32),('contextObject','f'*32),
                        ('windowObject','f'*32),('qmlSource','qrc:/qml/Replacement.qml'),('inputReady',False)):
            with self.subTest(key=key):
                original=deepcopy(self.native.metadata);self.reserve();self.native.metadata[key]=new
                with self.assertRaises(NativeUIError):self.owner.send()
                self.assertEqual([],self.edits());self.assertEqual('reserved',self.owner.current()['phase'])
                # Each counterexample owns a new untouched private WAL.
                self.native.metadata=original
                self.store=PrivateFeatureState(self.root/('case-'+key)/LifecycleNavigationOwner.store_name('primary'))
                self.store.path.parent.mkdir(mode=0o700)
                self.lock=ScriptSourceLock(self.store.path.parent/'script-feature-sources.lock');self.enterContext(self.lock.held());self.owner=self.open()

    def test_negative_missing_or_foreign_reception_keeps_unknown_responsibility(self):
        self.reserve();self.native.lost=True;self.native.ignored=True
        with self.assertRaises(OSError):self.owner.send()
        packet=self.native.reader().read(RUN)
        with self.assertRaises(NativeUIError):self.owner.recover(packet)
        for mutate in (lambda p:p['source'].update(events=[]),lambda p:p.update(profile='lifecycle'),
            lambda p:p.update(processId=43),lambda p:p['source']['events'][0]['details']['root'].update(contextObject='f'*32)):
            bad=deepcopy(packet);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):self.owner.recover(bad)
        self.assertEqual('issued',self.open().current()['phase']);self.assertEqual(1,len(self.edits()))
        with self.assertRaises(SnapshotInputPending):self.owner.send()

    def test_home_page_selection_and_close_keep_distinct_original_source_receipts(self):
        commands=[]
        for index,control in enumerate(('hud.tablet','tablet.home','tablet.page.2','tablet.close'),1):
            self.native.field=control;self.native.metadata.update(controlObject=uuid.uuid4().hex,
                contextObject=uuid.uuid4().hex,qmlSource='qrc:/qml/hifi/tablet/TabletHome.qml')
            commands.append(self.reserve());self.owner.send()
        packet=self.native.reader().read(RUN)
        for event,command in zip(self.owner.state['events'],commands):
            actual=source.delivered(packet,command,event['controlId'],event['reference']['root'])
            self.assertTrue(actual['productOutcomeRequired'])
        self.assertEqual(4,len(self.edits()));self.assertEqual(4,len({c['commandId'] for c in commands}))
        self.assertEqual('tablet.close',self.native.observed()['controls'][0]['id'])
        self.assertTrue(self.native.observed()['tabletShown'],'ACK alone never supplies close effect')

    def test_navigation_control_profiles_reject_arbitrary_fields_text_and_cross_feature_adoption(self):
        for control in ('login.username','snapshot.capture','scripts.url.field','chat.input','tablet.back'):
            with self.subTest(control=control),self.assertRaises(NativeUIError):
                self.owner.reserve(control,controls.project(self.native.observed(),self.native.field))
        command=self.reserve()
        with self.assertRaises(NativeUIError):source.native_command(dict(command,operation='replace',text='arbitrary'),self.native.field)
        self.assertEqual([],self.edits())
        from ios.adapters import lifecycle_inputs as fields
        packet=self.native.reader().read(RUN)
        with self.assertRaises(NativeUIError):fields.original(packet)

    def test_original_membership_rejects_missing_duplicate_or_unbound_tokens(self):
        good=self.native.observed();normal_input.observation(good,42,good['sampleEpochMs'])
        for mutate in (lambda u:u['lifecycleNavigation'].update(controls=[]),
            lambda u:u['lifecycleNavigation']['controls'].append(deepcopy(u['lifecycleNavigation']['controls'][0])),
            lambda u:u['lifecycleNavigation']['controls'][0].update(token=str(uuid.uuid4())),
            lambda u:u['lifecycleNavigation']['controls'][0].update(qmlSource='https://foreign.invalid/control.qml')):
            bad=deepcopy(good);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):normal_input.observation(bad,42,bad['sampleEpochMs'])
        incomplete=deepcopy(good);incomplete['lifecycleNavigation'].update(complete=False,controls=[])
        normal_input.observation(incomplete,42,incomplete['sampleEpochMs'])
        with self.assertRaises(NativeUIError):controls.project(incomplete,self.native.field)

    def test_additive_inventory_preserves_existing_create_and_chat_row_projections(self):
        from ios.self_tests.test_ios_chat_controls import IOSChatControlsTests
        from ios.self_tests.test_ios_create_controls import IOSCreateControlsTests
        for case in (IOSChatControlsTests,IOSCreateControlsTests):
            fixture=case();fixture.setUp()
            try:
                identities={}
                def observed():
                    value=fixture.observed();rows=[]
                    for row in value['controls']:
                        if row['id'] not in controls.IDS:continue
                        if row['id'] not in identities:identities[row['id']]=uuid.uuid4().hex
                        rows.append(dict(self.native.metadata,controlId=row['id'],controlObject=identities[row['id']],
                            token=row['token'],surface='hud' if row['id']=='hud.tablet' else 'tablet',inputReady=row['enabled']))
                    value['lifecycleNavigation']=dict(iosLifecycleNavigationVersion=1,complete=True,controls=rows);return value
                original=fixture.observed();augmented=observed();self.assertEqual(original['controls'],augmented['controls'])
                with patch.object(fixture.native,'observed',side_effect=observed):
                    if case is IOSChatControlsTests:
                        fixture.flow.select_channel('domain');fixture.flow.type('reply-'+RUN);fixture.flow.send()
                        self.assertEqual([('domain','reply-'+RUN)],fixture.widget.sent)
                    else:
                        fixture.flow.choose('create.host',1);fixture.flow.replace('create.resource','owned-resource')
                        self.assertEqual('owned-resource',fixture.widget.texts['create.resource'])
            finally:fixture.doCleanups()

    def test_real_probe_and_fixture_keep_original_profile_consume_nonce_once_and_refuse_expected_effect(self):
        packet=self.native.reader().read(RUN);query=dict(schemaVersion=1,commandId=packet['requestId'],action=source.ACTION,runId=RUN)
        self.assertEqual(query,FixtureState().set_client_command(query))
        with self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,editor='scripts'))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const packet=PACKET;let calls=0,files=[];
const Test={featureIOSLifecycleNavigationInputs:q=>{calls++;return {...packet,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=='feature-ios-lifecycle-navigation-inputs.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(packet.source))throw Error('original rewritten/replayed');
applyClientCommand({...q,commandId:'ios-'+'b'.repeat(32),editor:'scripts'});if(calls!==1)throw Error('expected effect accepted');
delete Test.featureIOSLifecycleNavigationInputs;applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source became successful');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


class LifecycleNavigationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.native=Native(epoch_ms=lambda:20000);self.afc=[]
        def clock(packet):self.k.b.time=self.native.epoch-20000;self.k.native_clock(packet)
        self.f.clock.mutate=clock;old_execute=self.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(json.dumps(self.native.packet).encode()).decode()
            return old_execute(session,operation,values)
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

    def test_canonical_factory_holds_existing_lock_and_never_creates_session_or_launch(self):
        before=(self.f.sessions,self.f.launches)
        with self.f.adapter._lifecycle_navigation_runtime().inputs('test-only',RUN) as (owner,reader):
            self.assertIsInstance(owner,LifecycleNavigationOwner);packet=reader.read(RUN)
            self.assertEqual('lifecycle-navigation',packet['profile']);self.assertEqual(1,len(self.afc))
        self.assertEqual(before,(self.f.sessions,self.f.launches))
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)):reader.read(RUN)
        self.assertEqual(1,len(self.native.queries))

    def test_changed_candidate_cannot_enter_navigation_scope_or_read_source(self):
        self.f.artifact.write_bytes(b'Changed candidate before navigation scope')
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_REJECTED'):
            with self.f.adapter._lifecycle_navigation_runtime().inputs('test-only',RUN):pass
        self.assertEqual([],self.afc);self.assertEqual([],self.native.queries)
