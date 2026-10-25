"""Actual Phone dispatch, common gate/module, actor/probe JS and loopback broker.

Only the native Entities, Android private files, SDK and process are synthetic.
No device is contacted. The original actor script mutates entity properties;
the original probe function independently measures the received properties.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from http.server import BaseHTTPRequestHandler,HTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

import test_create_registration
import test_feature_adapters as bound
from adapters.normal_ui import NativeUIError
from self_tests.test_phone_navigation import NativePhone
from adapters.normal_feature_state import PrivateFeatureState
from fixture.collaboration_broker import CollaborationBroker
from feature_journeys.scenarios import FOUNDATIONS
import overte_phone_collaboration as source

ROOT=Path(__file__).resolve().parents[4]
DOMAIN='12345678-1234-4234-8234-123456789abc'
NODE=r'''
const fs=require('fs'),vm=require('vm'),readline=require('readline');
const entities=new Map(),intervals=[],timeouts=[],reports=[];
const actor='aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb';
let next=0,pending={schemaVersion:1,pending:false},ignore=false,replicate=true,received=null;
const context={print(){},Agent:{sessionUUID:actor},EntityViewer:{setPosition(){},setCenterRadius(){},queryOctree(){}},
 Script:{resolvePath:p=>p,setTimeout:fn=>timeouts.push(fn),setInterval:fn=>intervals.push(fn)},
 Entities:{serversExist:()=>true,canRez:()=>true,
 addEntity:p=>{const id='entity-'+(++next);entities.set(id,{...p,lastEditedBy:actor});return id;},
 editEntity:(id,p)=>{if(!ignore)entities.set(id,{...entities.get(id),...p,lastEditedBy:actor});},
 getEntityProperties:id=>JSON.parse(JSON.stringify(entities.get(id)||{})),findEntities:()=>[...entities.keys()],deleteEntity:id=>entities.delete(id)},
 XMLHttpRequest:function(){this.open=(method,path)=>{this.method=method;this.path=path;};this.setRequestHeader=()=>{};
 this.send=raw=>{if(this.path==='actor-command'){this.readyState=4;this.status=200;this.responseText=JSON.stringify(pending);this.onreadystatechange();}
 else if(this.path==='actor-state')reports.push(JSON.parse(raw));};}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const text=fs.readFileSync(process.argv[2],'utf8');
vm.runInNewContext(text.slice(text.indexOf('    function controlledSharedObservation('),text.indexOf('    function controlledPeer(')),context);
function observed(){const props=[...entities.values()].find(p=>p.name==='OVERTE_E2E_SHARED_COLOR');
 if(replicate||received===null)received=JSON.parse(JSON.stringify(props));return context.controlledSharedObservation(received);}
observed();
readline.createInterface({input:process.stdin}).on('line',line=>{try{const input=JSON.parse(line);
 if(input.action==='edit'){ignore=!!input.ignore;replicate=input.replicate!==false;pending=input.command;intervals.forEach(fn=>fn());
 while(timeouts.length)timeouts.shift()();pending={schemaVersion:1,pending:false};}
 if(input.action==='fault'){received={...received,...input.fields};replicate=false;}
 console.log(JSON.stringify({reports:reports.splice(0),observation:observed()}));
}catch(e){console.log(JSON.stringify({error:String(e)}));}});
'''


class Producer:
    def __init__(self):
        self.child=subprocess.Popen(['node','-e',NODE,str(ROOT/'tests/device/fixture/domain_content_agent.js'),
            str(ROOT/'tests/device/probe/overte_e2e_probe.js')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.seed=self.call(dict(action='read'))
    def call(self,value):
        self.child.stdin.write(json.dumps(value)+'\n');self.child.stdin.flush();line=self.child.stdout.readline()
        if not line:raise AssertionError('Synthetic native JS producer stopped')
        result=json.loads(line)
        if 'error' in result:raise AssertionError(result['error'])
        return result
    def close(self):
        self.child.terminate();self.child.communicate(timeout=3)


class CreateCollaborationFoundationTests(unittest.TestCase):
    def setUp(self):
        setup=test_create_registration.CreateRegistrationTests();setup.setUp();self.addCleanup(setup.doCleanups)
        self.f,self.root,self.environment=setup.f,setup.root,deepcopy(setup.environment)
        self.domain_ui=NativePhone()
        self.f.target.setdefault('controls',{})['primary']={'resourceId':'owned-native-primary'}
        self.f.target['controls']['normalNavigation']=deepcopy(self.domain_ui.profile)
        self.f.adapter.read_session(bound.SELECTOR)['targetFingerprint']=self.f.adapter.snapshot_fingerprint(self.f.target)
        self.producer=Producer();self.addCleanup(self.producer.close)
        self.broker=CollaborationBroker()
        for report in self.producer.seed['reports']:self.broker.report(report)
        self.edits=[];self.ignore=False;self.ignore_submit=False;self.replicate=True;self.source_fault=lambda row:None
        self.epoch=10000;self.seq=0;self.clock=0.;self.probe_fault=lambda row:None;self.control_fault=lambda kind:None
        self.connected=True;self.navigation=[];self.ignore_entry=False
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,value):
                raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                outer.control_fault('state')
                if self.path!='/v1/collaboration-state' or self.headers.get('X-Overte-E2E-Token')!='z'*64:return self.reply(404,{})
                try:self.reply(200,outer.broker.state())
                except RuntimeError:self.reply(503,{})
            def do_POST(self):
                if self.path!='/v1/collaboration-edit' or self.headers.get('X-Overte-E2E-Token')!='z'*64:return self.reply(404,{})
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));outer.edits.append(value)
                if outer.ignore_submit:return self.reply(200,dict(accepted=True))
                command=outer.broker.submit(value)
                measured=outer.producer.call(dict(action='edit',command=command,ignore=outer.ignore,replicate=outer.replicate))
                for report in measured['reports']:outer.broker.report(report)
                # A complete input acknowledgement is deliberately returned even
                # when the actual actor or native replication ignored the input.
                self.reply(200,dict(accepted=True))
        self.server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def close():self.server.shutdown();self.server.server_close();thread.join(2)
        self.addCleanup(close)
        base='http://127.0.0.1:'+str(self.server.server_port)
        self.environment.update(OVERTE_ANDROID_E2E_COLLABORATION='1',OVERTE_E2E_DOMAIN_ID=DOMAIN,
            OVERTE_E2E_DOMAIN_URL='hifi://owned.test:40102/0,0,0',OVERTE_E2E_DOMAIN_HOST='owned.test',
            OVERTE_E2E_DOMAIN_CONTROL_TOKEN='z'*64,OVERTE_E2E_COLLABORATION_STATE_URL=base+'/v1/collaboration-state',
            OVERTE_E2E_COLLABORATION_EDIT_URL=base+'/v1/collaboration-edit')
        def read(target,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/'+source.FILE,path);self.seq+=1
            value=dict(schemaVersion=1,sampleEpochMs=self.epoch,sampleSequence=self.seq,entityCount=1,
                observation=self.producer.call(dict(action='read'))['observation']);self.source_fault(value)
            return json.dumps(value)
        def probe(*args):
            self.seq+=1
            value=dict(sampleEpochMs=self.epoch,sampleSequence=self.seq,domain=dict(id=DOMAIN if self.connected else '',connected=self.connected));self.probe_fault(value);return value
        def arrived(url):
            self.assertEqual(self.environment['OVERTE_E2E_DOMAIN_URL'],url)
            self.domain_ui.current=url
            self.navigation.append(dict(keycode=66,url=url))
            if not self.ignore_entry:self.connected=True
        self.domain_ui.arrive=arrived
        original_call=self.f.native.call
        def native_call(method,path,body=None):
            if path.endswith('/elements') or '/element/' in path or path.endswith('/appium/device/press_keycode'):
                return self.domain_ui.call(method,path,body)
            return original_call(method,path,body)
        def command(*args,**kwargs):
            raise AssertionError('Normal domain input must not use the private command channel')
        for boundary in (patch.dict(os.environ,self.environment),patch.object(self.f.adapter,'probe_snapshot',side_effect=probe),
                patch.object(self.f.fixture.adb,'read_debug_app_file',side_effect=read),
                patch.object(self.f.fixture.adb,'epoch_milliseconds',side_effect=lambda *_:self.epoch),
                patch.object(self.f.native,'call',side_effect=native_call),
                patch.object(self.f.adapter,'write_android_client_command',side_effect=command),
                patch.object(source,'PhoneCollaboration',partial(source.PhoneCollaboration,monotonic=lambda:self.clock,sleep=self.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
    def sleep(self,value):self.clock+=value
    def invoke(self,operation,values=None):return self.f.adapter.invoke(bound.SELECTOR,operation,{} if values is None else values)
    def run_module(self,name,args=(),capabilities=None):
        environment=dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(self.root/'unused-manifest'),OVERTE_DEVICE_TARGET_SELECTOR=bound.SELECTOR,
            OVERTE_DEVICE_ARTIFACT_DIR=str(self.root),OVERTE_DEVICE_CAPABILITIES_JSON=json.dumps(sorted(capabilities or self.f.adapter.advertised_capabilities(self.f.target))))
        with patch.dict(os.environ,environment):
            spec=importlib.util.spec_from_file_location('module_support',ROOT/'tests/device/module_support.py');support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
            with (patch.dict(sys.modules,{'module_support':support}),patch.object(support,'invoke',side_effect=lambda _m,_t,op,values:self.invoke(op,values)),
                    patch.object(sys,'argv',[name,*args]),redirect_stdout(io.StringIO())):
                runpy.run_path(str(ROOT/'tests/device/modules'/name),run_name='__main__')

    def test_actual_create_gate_and_entity_sync_foundation_use_independent_originals(self):
        self.connected=False
        self.assertIn('entity-sync',FOUNDATIONS['create'])
        self.run_module('feature_capability_gate.py',['--area','create'])
        self.run_module('entity_sync.py')
        result=json.loads((self.root/'entity-sync.json').read_text());self.assertEqual('orange',result['after']['value'])
        self.assertEqual(result['before']['revision']+1,result['after']['revision']);self.assertEqual(1,len(self.edits))
        self.assertNotIn('actorSessionId',json.dumps(result));self.assertEqual([],self.f.native.inputs)
        self.assertEqual(1,len(self.navigation))
        self.assertEqual(['Go to destination','PhoneAddressField','editor-enter'],self.domain_ui.inputs)

    def test_ignored_domain_entry_ack_cannot_admit_foundation_or_repair_sdk(self):
        self.connected=False;self.ignore_entry=True
        from adapters.shared_appium.adapter import AppiumAdapter
        with patch.object(AppiumAdapter,'ensure_session',side_effect=AssertionError('Session repair is forbidden')),self.assertRaises(NativeUIError):
            self.invoke('collaboration.snapshot')
        self.assertEqual(1,len(self.navigation));self.assertEqual([],self.edits)
        self.assertEqual(['Go to destination','PhoneAddressField','editor-enter'],self.domain_ui.inputs)

    def test_default_off_missing_foundation_and_invalid_configuration_cannot_green_gate(self):
        with patch.dict(os.environ,{'OVERTE_ANDROID_E2E_COLLABORATION':'0'}):
            self.assertFalse(source.OPERATIONS&set(self.f.adapter.advertised_capabilities(self.f.target)))
            with self.assertRaises(SystemExit) as exit:self.run_module('feature_capability_gate.py',['--area','create'])
            self.assertEqual(75,exit.exception.code)
            with self.assertRaises(ValueError):self.invoke('collaboration.snapshot')
        for change in (dict(OVERTE_ANDROID_E2E_COLLABORATION='yes'),dict(OVERTE_E2E_DOMAIN_ID=''),
                dict(OVERTE_E2E_COLLABORATION_EDIT_URL='http://foreign.invalid/v1/collaboration-edit'),
                dict(OVERTE_E2E_DOMAIN_CONTROL_TOKEN='short')):
            with self.subTest(change=change),patch.dict(os.environ,change),self.assertRaises((ValueError,RuntimeError)):
                self.f.adapter.advertised_capabilities(self.f.target)

    def ignored(self,actor):
        self.ignore=actor;self.replicate=actor
        with self.assertRaises(NativeUIError):self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        self.assertEqual(1,len(self.edits))
        with self.assertRaises(NativeUIError):self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        self.assertEqual(1,len(self.edits))
    def test_acknowledged_but_ignored_actor_cannot_complete_or_repeat_edit(self):self.ignored(True)
    def test_acknowledged_but_ignored_replication_cannot_complete_or_repeat_edit(self):self.ignored(False)
    def test_accepted_broker_ack_without_submission_does_not_echo_requested_value(self):
        self.ignore_submit=True
        with self.assertRaises(NativeUIError):self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        self.assertEqual(1,len(self.edits));self.assertEqual(0,self.broker.state()['revision'])

    def test_lost_edit_return_and_repeated_edit_reconstruct_without_resending(self):
        actual=source.CollaborationControl.__call__
        def lose(control,kind,payload=None):
            value=actual(control,kind,payload)
            if kind=='edit':raise NativeUIError('Synthetic loss after actual actor edit')
            return value
        values=dict(entityName=source.ENTITY,value='orange')
        with patch.object(source.CollaborationControl,'__call__',lose),self.assertRaises(NativeUIError):self.invoke('collaboration.edit',values)
        self.assertEqual(1,len(self.edits))
        self.assertEqual({'performed':True},self.invoke('collaboration.edit',values))
        self.assertEqual({'performed':True},self.invoke('collaboration.edit',values));self.assertEqual(1,len(self.edits))
        observed=self.invoke('collaboration.snapshot');self.assertEqual(1,observed['revision']);self.assertEqual('orange',observed['value'])
        self.assertNotIn('actorSessionId',observed)

    def test_reconstructed_snapshot_requires_advancing_original_sample_and_final_guard(self):
        self.invoke('collaboration.snapshot');self.source_fault=lambda row:row.update(sampleSequence=1)
        with self.assertRaises(NativeUIError):self.invoke('collaboration.snapshot')
        self.source_fault=lambda row:None;calls=[0]
        def clock(*args):
            calls[0]+=1
            if calls[0]==3:self.f.native.identity='32:15'
            return self.epoch
        with patch.object(self.f.fixture.adb,'epoch_milliseconds',side_effect=clock),self.assertRaises((ValueError,RuntimeError)):
            self.invoke('collaboration.snapshot')

    def test_reconstructed_owner_rejects_control_origin_or_credential_replacement(self):
        self.invoke('collaboration.snapshot')
        for change in (dict(OVERTE_E2E_DOMAIN_CONTROL_TOKEN='x'*64),
                dict(OVERTE_E2E_COLLABORATION_STATE_URL='http://127.0.0.1:9/v1/collaboration-state',
                    OVERTE_E2E_COLLABORATION_EDIT_URL='http://127.0.0.1:9/v1/collaboration-edit')):
            with self.subTest(change=change),patch.dict(os.environ,change),self.assertRaises(NativeUIError):self.invoke('collaboration.snapshot')

    def test_foreign_or_expected_edit_fields_never_reach_actor(self):
        for values in (dict(entityName='OTHER',value='orange'),dict(entityName=source.ENTITY,value='green'),
                dict(entityName=source.ENTITY,value='orange',expectedRevision=1)):
            with self.subTest(values=values),self.assertRaises((ValueError,RuntimeError)):self.invoke('collaboration.edit',values)
        self.assertEqual([],self.edits)

    def collaboration_store(self):
        return PrivateFeatureState(self.f.adapter.state_path(bound.SELECTOR).with_name('phone-collaboration.json'))
    def archives(self):return list(self.collaboration_store().path.parent.glob('phone-collaboration-retired-*.json'))
    def cleanup_with_base(self):
        from adapters.shared_appium.adapter import AppiumAdapter
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            try:return self.f.adapter.cleanup(bound.SELECTOR)
            finally:base.assert_called_once()

    def test_cleanup_retires_original_history_offline_and_new_sdk_session_can_reuse_selector(self):
        self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        original=self.collaboration_store().read()
        self.f.native.identity='45:20'  # A later regular feature changed process.
        with patch.dict(os.environ,{'OVERTE_ANDROID_E2E_COLLABORATION':'0'}):
            self.assertEqual({'cleaned':True},self.cleanup_with_base())
            self.assertEqual({'cleaned':True},self.cleanup_with_base())
        self.assertIsNone(self.collaboration_store().read());self.assertEqual(1,len(self.archives()))
        self.assertEqual(original,PrivateFeatureState(self.archives()[0]).read())
        state=self.f.adapter.read_session(bound.SELECTOR);state.update(sessionId='next-native-session',generation=state['generation']+1)
        call=self.f.native.call
        def sdk(method,path,body=None):
            if method=='GET' and path=='/session/next-native-session':return {'capabilities':{'syntheticOnly':True}}
            return call(method,path,body)
        with patch.object(self.f.native,'call',side_effect=sdk):
            observed=self.invoke('collaboration.snapshot');self.assertEqual(1,observed['revision'])
        current=self.collaboration_store().read();self.assertEqual('next-native-session',current['binding']['sessionId'])
        self.assertNotEqual(original['binding'],current['binding']);self.assertEqual(1,len(self.edits))

    def test_cleanup_resumes_lost_archive_or_unlink_return_without_overwriting_original(self):
        for stage in ('archive','unlink'):
            self.invoke('collaboration.snapshot');original=self.collaboration_store().read()
            if stage=='archive':
                write=PrivateFeatureState.write
                def lose(store,value,previous):
                    result=write(store,value,previous)
                    if store.path.name.startswith('phone-collaboration-retired-'):raise NativeUIError('Synthetic lost durable archive return')
                    return result
                boundary=patch.object(PrivateFeatureState,'write',lose)
            else:
                discard=PrivateFeatureState.discard
                def lose(store,previous):
                    result=discard(store,previous)
                    if store.path==self.collaboration_store().path:raise NativeUIError('Synthetic lost active unlink return')
                    return result
                boundary=patch.object(PrivateFeatureState,'discard',lose)
            with self.subTest(stage=stage),boundary,self.assertRaisesRegex(ValueError,'PHONE_COLLABORATION_CLEANUP_INCOMPLETE'):
                self.cleanup_with_base()
            self.assertEqual({'cleaned':True},self.cleanup_with_base())
            self.assertIsNone(self.collaboration_store().read())
            self.assertIn(original,[PrivateFeatureState(path).read() for path in self.archives()])

    def test_cleanup_preserves_changed_active_or_foreign_archive_and_still_attempts_base(self):
        self.invoke('collaboration.snapshot');active=self.collaboration_store();original=active.read();write=PrivateFeatureState.write
        replacement=deepcopy(original);replacement['controlIdentity']='0'*64
        def replace(store,value,previous):
            result=write(store,value,previous)
            if store.path.name.startswith('phone-collaboration-retired-'):write(active,replacement,original)
            return result
        with patch.object(PrivateFeatureState,'write',replace),self.assertRaisesRegex(ValueError,'PHONE_COLLABORATION_CLEANUP_INCOMPLETE'):
            self.cleanup_with_base()
        self.assertEqual(replacement,active.read());self.assertEqual(original,PrivateFeatureState(self.archives()[0]).read())
        # Another file occupying the exact content-derived archive path is never
        # overwritten or used as proof that the original active file retired.
        write(active,original,replacement);archive=PrivateFeatureState(self.archives()[0]);write(archive,{'foreign':True},original)
        with self.assertRaisesRegex(ValueError,'PHONE_COLLABORATION_CLEANUP_INCOMPLETE'):self.cleanup_with_base()
        self.assertEqual(original,active.read());self.assertEqual({'foreign':True},archive.read())

    def test_unresolved_no_effect_cleanup_keeps_journal_red_even_when_optin_disabled(self):
        self.ignore_submit=True
        with self.assertRaises(NativeUIError):self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        original=self.collaboration_store().read();self.assertEqual('issued',original['pending']['phase'])
        with patch.dict(os.environ,{'OVERTE_ANDROID_E2E_COLLABORATION':'0'}),self.assertRaisesRegex(ValueError,'PHONE_COLLABORATION_CLEANUP_INCOMPLETE'):
            self.cleanup_with_base()
        self.assertEqual(original,self.collaboration_store().read());self.assertEqual([],self.archives());self.assertEqual(1,len(self.edits))

    def test_cleanup_resolves_only_actual_lost_return_under_original_live_context(self):
        actual=source.CollaborationControl.__call__
        def lose(control,kind,payload=None):
            value=actual(control,kind,payload)
            if kind=='edit':raise NativeUIError('Synthetic lost actor return')
            return value
        with patch.object(source.CollaborationControl,'__call__',lose),self.assertRaises(NativeUIError):
            self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        with patch.dict(os.environ,{'OVERTE_ANDROID_E2E_COLLABORATION':'0'}):self.assertEqual({'cleaned':True},self.cleanup_with_base())
        self.assertEqual(1,len(self.edits));self.assertIsNone(self.collaboration_store().read())
        retired=PrivateFeatureState(self.archives()[0]).read();self.assertEqual(1,retired['receipt']['revision']);self.assertIsNone(retired['pending'])

    def test_unconfirmed_cleanup_cannot_adopt_a_replacement_process_after_actual_actor_effect(self):
        actual=source.CollaborationControl.__call__
        def lose(control,kind,payload=None):
            result=actual(control,kind,payload)
            if kind=='edit':raise NativeUIError('Synthetic lost return before client acquisition')
            return result
        with patch.object(source.CollaborationControl,'__call__',lose),self.assertRaises(NativeUIError):
            self.invoke('collaboration.edit',dict(entityName=source.ENTITY,value='orange'))
        original=self.collaboration_store().read();self.assertEqual(1,self.broker.state()['revision']);self.f.native.identity='45:20'
        with self.assertRaisesRegex(ValueError,'PHONE_COLLABORATION_CLEANUP_INCOMPLETE'):self.cleanup_with_base()
        self.assertEqual(original,self.collaboration_store().read());self.assertEqual([],self.archives());self.assertEqual(1,len(self.edits))

    def test_foreign_author_domain_duplicate_or_stale_received_source_is_rejected(self):
        faults=(lambda row:row.update(sampleEpochMs=4000),lambda row:row.update(entityCount=2),
            lambda row:row['observation'].update(actorSessionId='bbbbbbbb-1111-2222-3333-aaaaaaaaaaaa'),
            lambda row:row['observation'].update(revision=9),lambda row:row.update(sampleSequence=True))
        for fault in faults:
            self.clock=0.;self.source_fault=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.invoke('collaboration.snapshot')
        self.source_fault=lambda row:None;self.probe_fault=lambda row:row['domain'].update(id='foreign')
        with self.assertRaises(NativeUIError):self.invoke('collaboration.snapshot')
        self.assertEqual([],self.edits)

    def test_original_candidate_pid_session_or_target_change_prevents_result(self):
        for boundary in ('pid','session','candidate','target'):
            original=self.f.native.identity;state=self.f.adapter.read_session(bound.SELECTOR);previous=deepcopy(state);digest=self.f.fixture.adb.digest
            def fault(kind):
                if boundary=='pid':self.f.native.identity='32:15'
                elif boundary=='session':state['generation']+=1
                elif boundary=='candidate':self.f.fixture.adb.digest='0'*64
                else:self.f.target['appId']='foreign.app'
            self.control_fault=fault
            with self.subTest(boundary=boundary),self.assertRaises((ValueError,RuntimeError)):self.invoke('collaboration.snapshot')
            self.f.native.identity=original;state.clear();state.update(previous);self.f.fixture.adb.digest=digest;self.f.target['appId']=bound.PACKAGE
        self.assertEqual([],self.edits)


if __name__=='__main__':unittest.main()
