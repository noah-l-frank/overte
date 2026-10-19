"""Hardware-free protected-probe boundary counterexamples, not native login."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_account_probe import NativeAccountProbe,command,validate,protected_proof,bind_to_account,AccountProbeOwner,OwnedAccountProbe
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32;TICKET='b'*32;PROVIDER='c'*32


class Boundary:
    def __init__(self):
        self.clock=0.;self.commands=[];self.intents=[];self.value=None;self.sequence=0
        self.mutate=None;self.ignored=False;self.guard_ok=True;self.pending=False
        self.payload=b'{"status":"fail","error":"unauthorized"}'
        self.instance='d'*32
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;op=request['operation']
        if op=='read':
            source=dict(httpStatus=401,networkError=204,parsed=True,principalSha256=hashlib.sha256(b'').hexdigest(),
                responseSha256=hashlib.sha256(self.payload).hexdigest(),responseBytes=len(self.payload),
                tokenAttached=False,credentialGeneration=1,endpointSha256='e'*64,sentEpochMs=20000,completedEpochMs=20000)
        elif op=='release':source=dict(performed=True)
        else:source=dict(inflight=self.pending,responseBytes=7 if self.pending else 0,credentialBytes=0,released=True)
        self.value=dict(probeVersion=1,**{key:request[key] for key in ('commandId','requestId','runId','ticket','operation')},
            instance=self.instance,sequence=self.sequence,processId=123,requestedEpochMs=20000,capturedEpochMs=20000,source=source)
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value)
    def sleep(self,value):self.clock+=value
    def reader(self,**kwargs):
        return NativeAccountProbe(self.send,self.read,lambda:20000,lambda:self.guard_ok,123,intent=self.intents.append,
            monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)
    def proof(self,native):
        return dict(providerVersion=2,instance=PROVIDER,eventSequence=1,capturedEpochMs=9000000,
            kind='profile-request',runId=RUN,ticket=TICKET,requestId=native['requestId'],status=401,principal='anonymous',protectedAccess=False)


class AccountProbeTests(unittest.TestCase):
    def test_original_profile_response_is_read_once_after_persisted_intent(self):
        boundary=Boundary();reader=boundary.reader();value=reader.acquire(RUN,TICKET)
        self.assertEqual(1,len(boundary.commands));self.assertEqual(boundary.intents,boundary.commands)
        self.assertEqual(hashlib.sha256(boundary.payload).hexdigest(),value['source']['responseSha256'])
        self.assertEqual(dict(principal='anonymous',protectedAccess=False),protected_proof(value,boundary.proof(value),
            provider_instance=PROVIDER,username='e2e-'+RUN))

    def test_ignored_dispatch_and_old_files_cannot_be_replayed_into_success(self):
        boundary=Boundary();reader=boundary.reader();reader.acquire(RUN,TICKET);boundary.ignored=True
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)
        self.assertEqual(2,len(boundary.commands));self.assertEqual(2,len(boundary.intents))
        self.assertEqual(2,len(set(c['requestId'] for c in boundary.commands)))

    def test_invalid_scope_and_desired_facts_are_rejected_before_dispatch(self):
        boundary=Boundary();reader=boundary.reader()
        with self.assertRaises(NativeUIError):reader.acquire('foreign',TICKET)
        self.assertEqual([],boundary.commands)
        good=dict(schemaVersion=1,commandId='f'*32,requestId='f'*32,action='feature-account-probe',operation='read',runId=RUN,ticket=TICKET)
        for edit in ({'expected':True},{'origin':'https://foreign.invalid'},{'schemaVersion':True},{'operation':'login'}):
            with self.assertRaises(NativeUIError):command(good|edit)

    def test_failed_ownership_intent_cannot_start_the_actual_get(self):
        boundary=Boundary();reader=boundary.reader()
        def reject(_request):raise NativeUIError('No private owner')
        reader.intent=reject
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)
        self.assertEqual([],boundary.commands)

    def test_typed_actual_response_and_parse_failures_remain_unavailable(self):
        for edit in ({'parsed':False},{'httpStatus':302},{'httpStatus':True},{'responseBytes':0},
                     {'responseBytes':4097},{'networkError':500},{'networkError':6},{'tokenAttached':1},{'completedEpochMs':19999}):
            boundary=Boundary();boundary.mutate=lambda value:value['source'].update(edit)
            with self.assertRaises(NativeUIError):boundary.reader().acquire(RUN,TICKET)

    def test_forged_success_without_actual_token_or_valid_principal_fails(self):
        boundary=Boundary();reader=boundary.reader()
        boundary.mutate=lambda value:value['source'].update(httpStatus=200,networkError=0)
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)
        boundary.mutate=lambda value:value['source'].update(httpStatus=200,networkError=0,tokenAttached=True)
        value=reader.acquire(RUN,TICKET);proof=boundary.proof(value)|dict(status=200,principal='owned',protectedAccess=True)
        with self.assertRaises(NativeUIError):protected_proof(value,proof,provider_instance=PROVIDER,username='e2e-'+RUN)

    def test_foreign_peer_provider_scope_nonce_and_status_are_rejected(self):
        boundary=Boundary();value=boundary.reader().acquire(RUN,TICKET);proof=boundary.proof(value)
        for edit in ({'instance':'e'*32},{'runId':'f'*32},{'ticket':'f'*32},{'requestId':'f'*32},
                     {'status':200},{'protectedAccess':True},{'kind':'grant-issued'},{'protectedAccess':0}):
            with self.assertRaises(NativeUIError):protected_proof(value,proof|edit,provider_instance=PROVIDER,username='e2e-'+RUN)

    def test_independent_passive_account_sample_must_follow_the_original_profile_response(self):
        from self_tests.test_native_account_observation import account
        boundary=Boundary();value=boundary.reader().acquire(RUN,TICKET);observed=account()
        observed['observation']['endpointSha256']=value['source']['endpointSha256']
        actual=bind_to_account(value,observed)
        self.assertFalse(actual['protectedAccess']);self.assertFalse(actual['loginPending'])
        for edit in ({'instance':'f'*32},{'credentialGeneration':2},{'capturedEpochMs':19999},
                     {'capturedEpochMs':21501},{'credentialActive':False},{'endpointSha256':'a'*64}):
            changed=deepcopy(observed);changed['observation'].update(edit)
            with self.assertRaises(NativeUIError):bind_to_account(value,changed)

    def test_process_context_cursor_and_original_times_cannot_change_silently(self):
        for edit in ({'processId':124},{'capturedEpochMs':18499},{'requestedEpochMs':20001},{'sequence':0}):
            boundary=Boundary();boundary.mutate=lambda value:value.update(edit)
            with self.assertRaises(NativeUIError):boundary.reader().acquire(RUN,TICKET)
        boundary=Boundary();reader=boundary.reader();reader.acquire(RUN,TICKET);boundary.instance='f'*32
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)

    def test_cleanup_needs_actual_reply_drain_not_only_release_ack(self):
        boundary=Boundary();reader=boundary.reader();reader.acquire(RUN,TICKET);owned=boundary.intents[0]
        boundary.pending=True
        with self.assertRaises(NativeUIError):reader.release(owned)
        self.assertEqual(1,sum(c['operation']=='release' for c in boundary.commands))
        self.assertEqual(1,len(boundary.intents));boundary.pending=False
        self.assertFalse(reader.release(owned)['source']['inflight'])

    def test_retained_body_or_credential_copies_fail_cleanup_and_preserve_intent(self):
        for field in ('responseBytes','credentialBytes'):
            boundary=Boundary();reader=boundary.reader();reader.acquire(RUN,TICKET)
            def keep(value):
                if value['operation']=='inspect':value['source'][field]=1
            boundary.mutate=keep
            with self.assertRaises(NativeUIError):reader.release(boundary.intents[0])
            self.assertEqual(1,len(boundary.intents))

    def test_partial_document_is_polled_without_reissuing_the_network_command(self):
        boundary=Boundary();reader=boundary.reader();original=reader.original;reads=[]
        def partial():reads.append(1);return '{' if len(reads)==1 else original()
        reader.original=partial;reader.acquire(RUN,TICKET)
        self.assertEqual(1,len(boundary.commands));self.assertEqual(2,len(reads))

    def test_total_transport_budget_and_clock_regression_reject_late_results(self):
        boundary=Boundary();reader=boundary.reader();original=reader.original
        def late():boundary.clock=5.;return original()
        reader.original=late
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)
        boundary=Boundary();reader=boundary.reader();original=reader.original
        def backwards():boundary.clock=-1.;return original()
        reader.original=backwards
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)

    def test_native_epoch_regression_between_separate_ios_requests_is_not_hidden_by_new_cursor(self):
        boundary=Boundary();reader=boundary.reader(ios=True);reader.acquire(RUN,TICKET)
        def backwards(value):
            value.update(requestedEpochMs=19999,capturedEpochMs=19999)
            value['source'].update(sentEpochMs=19999,completedEpochMs=19999)
        boundary.mutate=backwards
        with self.assertRaises(NativeUIError):reader.acquire(RUN,TICKET)
        self.assertEqual(2,len(boundary.intents))

    def test_ios_native_clock_and_closed_fixture_command_preserve_original_nonce(self):
        boundary=Boundary();reader=boundary.reader(ios=True);reader.clock_ms=lambda:9000000
        value=reader.acquire(RUN,TICKET);self.assertEqual(20000,value['capturedEpochMs'])
        request=boundary.commands[0];self.assertTrue(request['commandId'].startswith('ios-'))
        fixture=FixtureState();self.assertEqual(request,fixture.set_client_command(request))
        with self.assertRaises(ValueError):fixture.set_client_command(request|dict(expected=True))

    def owned(self,boundary):
        from adapters.normal_feature_state import PrivateFeatureState
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);os.chmod(temporary.name,0o700)
        store=PrivateFeatureState(Path(temporary.name)/'account-owner.json')
        binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:1',sessionId='owned-session',
                     generation=1,targetFingerprint='c'*64)
        owner=AccountProbeOwner(store,binding,lambda:boundary.guard_ok)
        probe=boundary.reader();probe.intent=owner.intent
        return OwnedAccountProbe(probe,owner),store

    def test_actual_private_owner_survives_failed_acquisition_and_noop_cleanup(self):
        boundary=Boundary();owned,store=self.owned(boundary);boundary.ignored=True
        with self.assertRaises(NativeUIError):owned.acquire(RUN,TICKET)
        self.assertIsNotNone(store.read());boundary.ignored=False;boundary.pending=True
        with self.assertRaises(NativeUIError):owned.release()
        self.assertIsNotNone(store.read());boundary.pending=False;owned.release()
        self.assertIsNone(store.read())

    def test_owned_probe_refuses_second_acquisition_or_process_change_before_dispatch(self):
        boundary=Boundary();owned,store=self.owned(boundary);owned.acquire(RUN,TICKET)
        before=len(boundary.commands)
        with self.assertRaises(NativeUIError):owned.acquire(RUN,TICKET)
        boundary.guard_ok=False
        with self.assertRaises(NativeUIError):owned.release()
        self.assertEqual(before,len(boundary.commands));self.assertIsNotNone(store.read())

    def test_private_binding_replacement_cannot_adopt_or_clear_prior_probe(self):
        boundary=Boundary();owned,store=self.owned(boundary);owned.acquire(RUN,TICKET)
        owned.owner.binding['processIdentity']='456:2';before=len(boundary.commands)
        with self.assertRaises(NativeUIError):owned.release()
        self.assertEqual(before,len(boundary.commands));self.assertIsNotNone(store.read())

    def test_actual_javascript_dispatch_bounds_pending_and_cancels_superseded_polls(self):
        program='''
let calls=[],files=[],timers=new Map(),next=0,pending=true;
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Script={setTimeout:(fn,ms)=>{if(ms!==50)throw Error("poll");timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id)};
const Test={featureAccountProbe:c=>{calls.push(c);return pending&&c.operation==="read"?{requestId:c.requestId,pending:true}:
 {probeVersion:1,commandId:c.commandId,requestId:c.requestId,source:{actual:77}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command=(id,op="read",requestId=id)=>({schemaVersion:1,commandId:id.repeat(32),action:"feature-account-probe",
 operation:op,requestId:requestId.repeat(32),runId:"a".repeat(32),ticket:"b".repeat(32)});
applyAndroidControlCommand(command("c"));applyAndroidControlCommand(command("c"));
if(calls.length!==1||files.length||timers.size!==1)throw Error("duplicate input or pending published");
let stale=timers.values().next().value;pending=false;applyAndroidControlCommand(command("d","release","c"));stale();
if(calls.length!==2||timers.size||files.length!==1||files[0].name!=="feature-account-probe.json")throw Error("retired callback");
applyClientCommand({...command("e"),expected:true});if(calls.length!==2)throw Error("desired state accepted");
pending=true;applyClientCommand(command("f"));let count=0;
while(timers.size){let callback=timers.values().next().value;timers.clear();callback();if(++count>50)throw Error("unbounded");}
if(count!==50||files[1].v.available!==false)throw Error("missing native result green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
