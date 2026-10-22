"""Real Pico Python route/durable files; Qt/native/settings/OS simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import uuid
from unittest.mock import patch
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_environment import NativeNavigationEnvironment,command,endpoint
from adapters.navigation_origin import NavigationOrigin,sha
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_navigation_origin import PicoNavigationOriginIO
from fixture.serve import FixtureState
from self_tests.test_native_account_observation import account,append,event
from self_tests.test_native_feature_observation import probe_source
import self_tests.test_token_places_ui as places

RUN,TICKET,RESTORE='a'*32,'b'*32,'c'*32
OWNED='https://owned.invalid:49121'
ORIGINAL='https://original.invalid/server'

class Model(places.Widgets):
    def __init__(self,root):
        super().__init__(root)
        self.selected=self.effective=self.draft=ORIGINAL
        self.present=True;self.override=False;self.login=True;self.password_empty=True
        self.acct=account();self.acct['observation']['endpointSha256']=sha(ORIGINAL)
        self.other='d'*64;self.packet=None;self.source_sequence=0;self.source_edit=None;self.source_ignored=False
        self.lose_stage=self.ignore_stage=None;self.source_instance='e'*32;self.origin_marker=1
    def raw(self):
        value=super().raw();value['controls']=[r for r in value['controls'] if r['id']=='tablet.home']
        value.update(navigationOriginControlsVersion=self.origin_marker,loginControlsVersion=2)
        if self.login:
            value['controls'] += [dict(id='login.page',token='44444444-4444-4444-8444-444444444444',enabled=True,
                focused=False,inputReady=False,profile='qml-login-v1',domain=False,waiting=False,closing=False,
                error='none',accountInstance=self.acct['observation']['instance'],credentialGeneration=self.acct['observation']['credentialGeneration'],
                endpointSha256=self.acct['observation']['endpointSha256'],nativePending=False,tokenPresent=False,
                stage='credentials',submitEndpointSha256=sha(self.draft)),
                dict(id='login.server',token=str(uuid.uuid5(uuid.NAMESPACE_URL,repr((self.draft,self.focus,self.geometry)))),
                    enabled=True,focused=self.focus=='login.server',inputReady=True)]
        return value
    def send(self,c):
        stage=3 if c['controlId']=='tablet.home' else 1 if c['action']=='replace' else 2 if c['action']=='submit' else 0
        self.calls.append(deepcopy(c))
        if not self.ignore:
            self.sequence+=1
            if stage!=self.ignore_stage:
                if stage==0:self.focus='login.server'
                elif stage==1:self.draft=c['text']
                elif stage==2:
                    self.selected=self.effective=self.draft;self.acct['observation']['endpointSha256']=sha(self.selected)
                    append(self.acct,event(sequence=self.acct['observation']['eventSequence']+1,kind='auth-endpoint-changed',
                        epoch=self.epoch(),generation=self.acct['observation']['credentialGeneration']+1))
                else:self.login=False;self.focus='';self.generation=str(uuid.uuid4())
        if stage==self.lose_stage:raise NativeUIError('Synthetic lost applied input result')
        return dict(schemaVersion=1,bridgeId=self.bridge,commandId=c['commandId'],sequence=c['sequence'],
                    performed=True,error='',processId=123,updatedEpochMs=self.epoch()),self.epoch()
    def source_send(self,r):
        if self.source_ignored:return
        self.source_sequence+=1;acct=deepcopy(self.acct);acct['observation']['capturedEpochMs']=self.epoch()
        self.packet=dict(navigationEnvironmentVersion=1,commandId=r['commandId'],runId=r['runId'],instance=self.source_instance,
            sequence=self.source_sequence,processId=123,capturedEpochMs=self.epoch(),selectedSettingPresent=self.present,
            selectedServer=self.selected,effectiveServer=self.effective,environmentOverride=self.override,otherSettingsSha256=self.other,account=acct,
            ui=dict(bridgeId=self.bridge,generation=self.generation,sequence=self.sequence,elapsedMs=100+round(self.clock*1000),
                observedEpochMs=self.epoch(),loginPageAlive=self.login,passwordEmpty=self.password_empty if self.login else None,
                serverDraftSha256=sha(self.draft) if self.login else None,serverFocused=self.focus=='login.server' if self.login else None))
        if self.source_edit:self.source_edit(self.packet)
    def reader(self):
        return NativeNavigationEnvironment(self.source_send,lambda:json.dumps(self.packet) if self.packet else '',self.epoch,self.guard,123,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def clear_private_input(self):self.private_cleared=True
    def reopen(self):self.login=True;self.draft=self.selected;self.focus='';self.generation=str(uuid.uuid4())

class NavigationOriginTests(unittest.TestCase):
    def setUp(self):
        self.fixture=places.PlacesControlTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=Model(self.fixture.root);self.fixture.navigation.io=self.model
        self.io=PicoNavigationOriginIO(self.fixture.original);self.path=self.fixture.root/'origin-owner.json'
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:synthetic-start',
            sessionId=self.model.bridge,generation=0,targetFingerprint='c'*64)
    def owner(self):
        return NavigationOrigin(self.io,self.model.reader(),self.path,RUN,self.binding,self.model.guard,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
    def test_normal_selection_original_path_restoration_and_quiet(self):
        self.assertEqual(dict(performed=True),self.owner().select(TICKET,OWNED))
        self.assertEqual(OWNED,self.model.effective);self.assertFalse(self.model.login)
        self.assertEqual(4,len(self.model.calls));self.assertEqual('submit',self.model.calls[2]['action'])
        self.assertEqual(7,len(self.owner().state['operation']['quiet']))
        before=deepcopy(self.model.calls);self.owner().select(TICKET,OWNED);self.assertEqual(before,self.model.calls)
        self.model.reopen();self.owner().select(RESTORE,OWNED,restoring=True)
        self.assertEqual(ORIGINAL,self.model.selected);self.assertEqual(8,len(self.model.calls))
        self.assertEqual(ORIGINAL,self.owner().state['original']['selectedServer'])
    def test_all_four_applied_lost_replies_resolve_without_resending(self):
        for stage in range(4):
            self.setUp();self.model.lose_stage=stage
            with self.subTest(stage=stage),self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
            self.assertEqual(stage,self.owner().state['operation']['pending']['stage'])
            self.model.lose_stage=None;self.owner().select(TICKET,OWNED);self.assertEqual(4,len(self.model.calls))
    def test_each_ignored_effect_keeps_pending_and_refuses_replacement(self):
        for stage in range(4):
            self.setUp();self.model.ignore_stage=stage
            with self.subTest(stage=stage),self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
            self.assertEqual(stage+1,len(self.model.calls))
            with self.assertRaises(NativeUIError):self.owner().select(RESTORE,OWNED,restoring=True)
            self.assertEqual(stage+1,len(self.model.calls))
    def test_credentials_password_draft_override_absent_setting_and_foreign_auth_refuse_before_input(self):
        for fault in ('token','refresh','pending','principal','password','draft','override','absent','endpoint'):
            self.setUp()
            if fault in ('token','refresh','pending'):self.model.acct['observation'][dict(token='tokenPresent',refresh='refreshPresent',pending='refreshPending')[fault]]=True
            elif fault=='principal':self.model.acct['principalSha256']='f'*64
            elif fault=='password':self.model.password_empty=False
            elif fault=='draft':self.model.draft='https://foreign.invalid'
            elif fault=='override':self.model.override=True
            elif fault=='absent':self.model.present=False
            else:self.model.acct['observation']['endpointSha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
            self.assertEqual([],self.model.calls);self.assertFalse(self.path.exists())
    def test_settings_inputs_and_clocks_cannot_drift_during_quiet(self):
        for fault in ('settings','input','clock','endpoint','account'):
            self.setUp();sleep=self.model.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='settings':self.model.other='f'*64
                elif fault=='input':self.model.sequence+=1
                elif fault=='endpoint':self.model.effective='https://foreign.invalid'
                elif fault=='account':append(self.model.acct,event(sequence=self.model.acct['observation']['eventSequence']+1,
                    kind='profile-changed',epoch=self.model.epoch(),generation=self.model.acct['observation']['credentialGeneration']))
                else:self.model.source_edit=lambda v:v['ui'].update(observedEpochMs=20000)
            self.model.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
            self.assertFalse(self.owner().state['operation']['quiet'])
    def test_source_birth_cursor_clock_pid_account_and_closed_packet_reject_replay(self):
        for edit in (lambda v:v.update(instance='f'*32),lambda v:v.update(sequence=1),lambda v:v.update(capturedEpochMs=18000),
            lambda v:v.update(processId=124),lambda v:v.update(expected='owned'),lambda v:v['account']['observation'].update(credentialGeneration=0)):
            self.setUp();reader=self.model.reader();reader.read(RUN);self.model.source_edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(RUN)
        self.setUp();self.model.source_ignored=True
        with self.assertRaises(NativeUIError):self.model.reader().read(RUN)
        self.assertLessEqual(self.model.clock,5.01)
    def test_reused_query_and_changed_original_archive_reject_recreation(self):
        self.owner().select(TICKET,OWNED);state=self.owner().state
        with patch('adapters.native_navigation_environment.uuid.uuid4',return_value=SimpleNamespace(hex=state['queries'][0])):
            with self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
        state['operation']['quiet'][0]['effectiveServer']='https://foreign.invalid'
        self.path.write_text(json.dumps(state));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner()
    def test_incomplete_journal_and_missing_original_packet_never_reconstruct_expected_baseline(self):
        self.owner().select(TICKET,OWNED);disk=json.loads(self.path.read_text())
        broken=deepcopy(disk);broken.pop('original');self.path.write_text(json.dumps(broken))
        with self.assertRaises(NativeUIError):self.owner()
        self.path.write_text(json.dumps(disk));self.owner().packet_store(disk['original']['sha256']).path.unlink()
        with self.assertRaises(NativeUIError):self.owner()

    def test_marker_and_original_pending_scope_required_before_input(self):
        self.model.origin_marker=True
        with self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
        self.assertEqual([],self.model.calls)
        self.setUp();original=self.io.deliver
        def changed(plan,text):self.model.sequence+=1;return original(plan,text)
        self.io.deliver=changed
        with self.assertRaises(NativeUIError):self.owner().select(TICKET,OWNED)
        self.assertEqual([],self.model.calls);self.assertIsNotNone(self.owner().state['operation']['pending'])
    def test_closed_private_grammar_rejects_expectations_credentials_and_non_https(self):
        r=dict(schemaVersion=1,commandId='f'*32,action='feature-navigation-environment',runId=RUN)
        fixture=FixtureState();fixture.set_client_command(r)
        for extra in ({'schemaVersion':True},{'expected':OWNED},{'url':OWNED},{'commandId':'ios-'+'f'*32}):
            with self.assertRaises((NativeUIError,ValueError)):command(r|extra)
            with self.assertRaises(ValueError):fixture.set_client_command(r|extra)
        for value in ('http://owned.invalid','https://user:secret@owned.invalid','https://owned.invalid?','https://owned.invalid/#secret'):
            with self.assertRaises((NativeUIError,ValueError)):endpoint(value)
        self.assertEqual(ORIGINAL,endpoint(ORIGINAL))
    def test_full_original_account_history_uses_bounded_hash_bound_private_archives(self):
        for index in range(1,65):
            append(self.model.acct,event(sequence=index,kind='profile-changed',epoch=20000,generation=1))
        self.owner().select(TICKET,OWNED);owner=self.owner()
        self.assertEqual(64,len(owner.state['original']['account']['observation']['events']))
        self.assertLess(self.path.stat().st_size,65536)
        reference=json.loads(self.path.read_text())['original'];archive=owner.packet_store(reference['sha256'])
        raw=archive.path.read_text();archive.path.write_text(raw.replace(ORIGINAL,'https://changed.invalid/server'))
        with self.assertRaises(NativeUIError):self.owner()

    def test_actual_private_pico_factory_joins_fixed_native_source_and_original_normal_route(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        sdk=native_fixture.NativeExecutionBindingTest();sdk.setUp();self.addCleanup(sdk.doCleanups)
        adapter=sdk.instance();adapter._scripts=lambda target:SimpleNamespace(ui=SimpleNamespace(io=self.fixture.original),binding=self.binding)
        native=SimpleNamespace(send=self.model.source_send,clock_ms=self.model.epoch,guard=self.model.guard,pid=123,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        adapter._native_feature_observer=lambda target:native
        def read(target,package,filename,*,attempts):
            self.assertEqual(('owned','org.overte.pico','files/overte-e2e/feature-navigation-environment.json',1),(target,package,filename,attempts))
            return json.dumps(self.model.packet)
        adapter.adb.read_debug_app_file=read
        from self_tests.test_navigation_origin_ray import Ray
        ray=Ray(self)
        with patch('adapters.navigation_origin.NavigationOrigin',partial(NavigationOrigin,monotonic=lambda:self.model.clock,sleep=self.model.sleep)),patch('adapters.pico4.tablet_home.bind_home',return_value=ray.home):
            owner=adapter._navigation_origin('owned',self.path,RUN,self.model.guard)
        owner.select(TICKET,OWNED);self.assertEqual(3,len(self.model.calls));self.assertEqual(1,len(ray.gestures));self.assertEqual(OWNED,self.model.effective)

    def test_original_probe_transports_actual_packet_and_absent_hook_is_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureNavigationEnvironment:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'f'.repeat(32),action:'feature-navigation-environment',runId:'a'.repeat(32)};
applyClientCommand(c);if(calls!==1||!files[0].v.original||files[0].name!=='feature-navigation-environment.json')throw Error('Missing original');
for(const edit of [{expected:'owned'},{url:'https://foreign.invalid'},{schemaVersion:true}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('Unsafe query');delete Test.featureNavigationEnvironment;
applyClientCommand({...c,commandId:'e'.repeat(32)});if(files[1].v.status!=='unavailable')throw Error('Missing hook became success');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

if __name__=='__main__':unittest.main()
