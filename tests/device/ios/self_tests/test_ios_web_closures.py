"""Original closure parser/HTTP/AFC/probe logic; native callback source uncompiled."""
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.web_closures import IOSWebClosures, KINDS, command, drained
from self_tests.test_native_feature_observation import Boundary as ClockBoundary, probe_source

RUN = 'a' * 32
URL = 'http://controlled.invalid:49121/feature-fixture/v1/runs/' + RUN + '/'
ROOT = Path(__file__).resolve().parents[4]


class ClosureBoundary:
    def __init__(self):
        self.time = 0.; self.sequence = 0; self.commands = []; self.request = None
        self.mutate = None; self.alive = True; self.ignored = False; self.retired = 0; self.created = 1
    def send(self, value):
        self.commands.append(deepcopy(value)); self.request = value
    def original(self):
        if self.ignored:
            return ''
        self.sequence += 1
        callbacks = {k: dict(created=0, retired=0, pending=0) for k in KINDS}
        callbacks['snapshot'] = dict(created=self.created, retired=self.retired, pending=self.created-self.retired)
        descriptor = dict(handle=1, creation=2, grant=3, page=4, surface='world-entity', identitySha256='e'*64,
                          sourceUrl=URL+'tickets/'+'f'*32+'/graphics-marker.v1.html')
        row = dict(id=1, descriptor=descriptor, createdEpochMs=19000, updatedEpochMs=20000, callbacks=callbacks)
        c = self.request
        value = dict(iosWebClosureVersion=1, commandId=c['commandId'], runId=RUN, fixtureUrl=URL, instance='b'*32,
                     sequence=self.sequence, processId=42, capturedEpochMs=20000, complete=True, contexts=[row])
        if self.mutate:
            self.mutate(value)
        return json.dumps(value)
    def sleep(self, seconds):
        self.time += seconds
    def reader(self):
        return IOSWebClosures(self.send, self.original, lambda:20000, lambda:self.alive, 42,
                              monotonic=lambda:self.time, sleep=self.sleep)


class ClosureTests(unittest.TestCase):
    def test_held_callback_remains_pending_after_owner_death_until_actual_source_retires_it(self):
        boundary = ClosureBoundary(); reader = boundary.reader(); admitted = reader.read(RUN, URL)
        held = reader.read(RUN, URL)
        self.assertEqual(1, held['contexts'][0]['callbacks']['snapshot']['pending'])
        with self.assertRaises(RuntimeError):drained(held, admitted)
        # Synthetic original source is the only authority for actual last-copy retirement.
        boundary.retired = 1
        retired = reader.read(RUN, URL)
        self.assertEqual(0, drained(retired, admitted)[0]['callbacks']['snapshot']['pending'])
        self.assertEqual(1, admitted['contexts'][0]['callbacks']['snapshot']['pending'])
        self.assertEqual({'schemaVersion','commandId','action','runId','fixtureUrl'},set(boundary.commands[0]))

    def test_empty_inventory_or_unobserved_callbacks_do_not_prove_drainage(self):
        b = ClosureBoundary(); b.mutate=lambda v:v.update(contexts=[]); r=b.reader(); admitted=r.read(RUN, URL)
        with self.assertRaises(RuntimeError):drained(r.read(RUN,URL),admitted)
        b = ClosureBoundary(); b.created=0; r=b.reader(); admitted=r.read(RUN,URL)
        with self.assertRaises(RuntimeError):drained(r.read(RUN,URL),admitted)

    def test_each_callback_kind_and_new_context_prevent_premature_drainage(self):
        for kind in KINDS:
            b=ClosureBoundary(); r=b.reader(); admitted=r.read(RUN,URL); b.retired=1
            def added(v):
                row=deepcopy(v['contexts'][0]); row['id']=2; row['descriptor']['page']=5
                row['callbacks'][kind]=dict(created=2,retired=1,pending=1); v['contexts'].append(row)
            b.mutate=added
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):drained(r.read(RUN,URL),admitted)

    def test_tombstones_cannot_disappear_be_reordered_or_change_ownership(self):
        for edit in (lambda v:v.update(contexts=[]),lambda v:v['contexts'][0].update(id=2),
                     lambda v:v['contexts'][0]['descriptor'].update(grant=4),
                     lambda v:v['contexts'][0].update(createdEpochMs=19001)):
            b=ClosureBoundary(); r=b.reader(); r.read(RUN,URL); b.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):r.read(RUN,URL)

    def test_counter_regression_reused_nonce_source_birth_and_source_scope_fail(self):
        for edit in (lambda v:v.update(sequence=1),lambda v:v.update(instance='c'*32),
                     lambda v:v['contexts'][0]['callbacks']['snapshot'].update(created=0,pending=0),
                     lambda v:v['contexts'][0]['descriptor'].update(sourceUrl=URL+'tickets/'+'f'*32+'/other.html'),
                     lambda v:v['contexts'][0]['descriptor'].update(sourceUrl=URL.replace(RUN,'c'*32)+'tickets/'+'f'*32+'/index.html')):
            b=ClosureBoundary(); r=b.reader(); r.read(RUN,URL); b.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):r.read(RUN,URL)
        b=ClosureBoundary(); b.retired=1; r=b.reader(); r.read(RUN,URL); b.retired=0
        with self.assertRaises(NativeUIError):r.read(RUN,URL)

    def test_overflow_incomplete_duplicate_context_and_impossible_counts_fail(self):
        edits=(lambda v:v.update(complete=False),lambda v:v.update(processId=43),lambda v:v.update(iosWebClosureVersion=True),
               lambda v:v['contexts'][0]['callbacks']['snapshot'].update(pending=0),
               lambda v:v['contexts'][0]['callbacks']['snapshot'].update(retired=2,pending=-1),
               lambda v:v['contexts'][0]['callbacks']['snapshot'].update(created=True),
               lambda v:v['contexts'][0]['descriptor'].update(handle=2**53),
               lambda v:v['contexts'].append(deepcopy(v['contexts'][0])),
               lambda v:v.update(contexts=v['contexts']*1025),lambda v:v.update(extra='not original'))
        for edit in edits:
            b=ClosureBoundary(); b.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read(RUN,URL)

    def test_lost_delivery_or_foreign_file_is_bounded_and_never_resent(self):
        for fault in ('ignored','foreign'):
            b=ClosureBoundary()
            if fault=='ignored':b.ignored=True
            else:b.mutate=lambda v:v.update(commandId='ios-'+'e'*32)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(RUN,URL)
            self.assertEqual(1,len(b.commands));self.assertLessEqual(b.time,1.6)

    def test_old_packets_future_packets_and_lost_guards_are_not_retimed(self):
        for edit in (lambda v:v.update(capturedEpochMs=18000),lambda v:v.update(capturedEpochMs=20001),
                     lambda v:v['contexts'][0].update(updatedEpochMs=20001)):
            b=ClosureBoundary(); b.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read(RUN,URL)
        for fault in ('late','backwards','guard'):
            b=ClosureBoundary(); original=b.original
            def changed():
                raw=original()
                if fault=='guard':b.alive=False
                else:b.time=1.6 if fault=='late' else -1
                return raw
            r=b.reader();r.original=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):r.read(RUN,URL)

    def test_final_native_clock_and_guard_remain_inside_freshness_deadline(self):
        for fault in ('final-clock','final-guard','slow-final-guard','clock-regression'):
            b=ClosureBoundary();r=b.reader();calls=0
            def clock():
                nonlocal calls
                calls+=1
                if fault=='final-clock' and calls==3:return 22000
                if fault=='clock-regression' and calls==3:return 19999
                if fault=='final-guard' and calls==3:b.alive=False
                if fault=='slow-final-guard' and calls==3:b.time+=1.6
                return 20000
            r.clock_ms=clock
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):r.read(RUN,URL)

    def test_ack_duplicates_oversized_source_and_unknown_callback_kinds_fail(self):
        for raw in ('ack','duplicates','large'):
            b=ClosureBoundary();r=b.reader()
            if raw=='ack':r.original=lambda:json.dumps(dict(commandId=b.request['commandId'],performed=True))
            elif raw=='duplicates':r.original=lambda:'{"commandId":"'+b.request['commandId']+'","commandId":"'+b.request['commandId']+'"}'
            else:r.original=lambda:' '*(262144+1)
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):r.read(RUN,URL)
        b=ClosureBoundary();b.mutate=lambda v:v['contexts'][0]['callbacks'].update(arbitrary=dict(created=0,retired=0,pending=0))
        with self.assertRaises(NativeUIError):b.reader().read(RUN,URL)

    def test_actual_fixture_rejects_state_setters_and_foreign_private_roots(self):
        c=dict(schemaVersion=1,commandId='ios-'+'d'*32,action='feature-ios-web-closures',runId=RUN,fixtureUrl=URL)
        FixtureState().set_client_command(c)
        for edit in ({'expected':{}},{'reset':True},{'script':'arbitrary()'},{'schemaVersion':True},
                     {'commandId':'d'*32},{'commandId':c['commandId']+'\n'},{'fixtureUrl':URL+'?token=secret'},
                     {'fixtureUrl':URL+'?'},{'fixtureUrl':URL+'#'},{'fixtureUrl':URL.replace('controlled.invalid','secret@host')},
                     {'fixtureUrl':URL.replace(RUN,'c'*32)}):
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):command(c|edit)
            with self.assertRaises(ValueError):FixtureState().set_client_command(c|edit)

    def test_actual_probe_preserves_original_packet_and_missing_hook_fails_closed(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];
const Test={featureIOSWebClosures:c=>{calls++;return {commandId:c.commandId,original:true,complete:true,contexts:[{original:true}]};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'d'.repeat(32),action:'feature-ios-web-closures',runId:'a'.repeat(32),
 fixtureUrl:'http://controlled.invalid:49121/feature-fixture/v1/runs/'+'a'.repeat(32)+'/'};
applyClientCommand(c);applyClientCommand(c);
if(calls!==2||files.length!==2||!files[1].v.original||files[1].name!=='feature-ios-web-closures.json')throw Error('native original lost');
for(const edit of [{expected:{}},{reset:true},{commandId:'d'.repeat(32)},{commandId:c.commandId+'\n'},
 {schemaVersion:true},{fixtureUrl:c.fixtureUrl+'?secret=x'}])applyClientCommand({...c,...edit});
if(calls!==2||files.length!==2)throw Error('closed command bypassed');
delete Test.featureIOSWebClosures;applyClientCommand({...c,commandId:'ios-'+'e'.repeat(32)});
if(files.length!==3||files[2].v.complete!==false||'contexts' in files[2].v)throw Error('missing source became absence');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_native_hooks_attach_leases_to_original_callbacks_before_owner_guards(self):
        # Source review only; deliberately does not compile any native code.
        view=(ROOT/'ios/web/IOSWebView.mm').read_text();snapshot=(ROOT/'ios/web/WKWebSnapshot.mm').read_text()
        header=(ROOT/'ios/web/IOSWebClosureTrace.h').read_text()
        self.assertIn('std::shared_ptr<Lease>',header);self.assertIn('~Lease()',header)
        self.assertIn('if (!owner) { return; }',snapshot)
        self.assertLess(snapshot.index('(void)featureLease'),snapshot.index('if (!owner) { return; }',snapshot.index('takeSnapshotWithConfiguration')))
        self.assertIn(', featureReadyLease',view);self.assertIn(', featureFinishedLease',view)
        self.assertNotIn('connect(reply, &QNetworkReply::readyRead, this, [feature',view)
        self.assertIn('(void)featureLease;\n#endif\n                        if (!owner',view)
        self.assertIn('Q_COREAPP_STARTUP_FUNCTION(registerIOSWebView)',view)
        self.assertIn('feature_closures::observe(command)',view)
        self.assertNotIn('rows.clear()',header);self.assertNotIn('rows.erase',header)
        self.assertIn('MAX_CONTEXTS = 1024',header)


class ClosureTransportTests(unittest.TestCase):
    def test_actual_factory_joins_private_original_afc_bytes_to_three_independent_native_clocks(self):
        source=ClosureBoundary();clock=ClockBoundary();clock.mutate=lambda v:v.update(processId=42)
        process=dict(bundleId='org.example.overte',pid=42,foreground=True);actions=[];state=FixtureState();echo=b''
        target=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId=process['bundleId'],
                    testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://controlled.invalid:49121'))
        test=self
        class Client:
            def execute(self,session,operation,values):
                test.assertEqual('owned',session);test.assertEqual('mobile: pullFile',operation)
                path=values['remotePath']
                if path.endswith('/feature-ios-web-closures.json'):raw=source.original()
                elif path.endswith('/feature-native-observation.json'):raw=json.dumps(clock.sample)
                else:raise AssertionError('foreign private diagnostic')
                return base64.b64encode(raw.encode()).decode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def read(self,_limit):return echo
        def post(request,timeout):
            nonlocal echo
            self.assertEqual(5,timeout);c=json.loads(request.data);state.set_client_command(c);actions.append(c['action'])
            echo=json.dumps(c).encode()
            if c['action']=='feature-ios-web-closures':source.send(c)
            elif c['action']=='feature-native-observe':clock.send(c)
            else:raise AssertionError('unexpected action')
            return Response()
        observer=FeatureObservation(Client(),'owned',target,lambda:deepcopy(process),
                                    monotonic=lambda:source.time,sleep=source.sleep)
        with patch('ios.adapters.feature_observation.post_request',side_effect=post):
            r=observer.web_closures();value=r.read(RUN,URL)
            self.assertEqual(42,value['processId'])
            self.assertEqual(['feature-native-observe','feature-ios-web-closures','feature-native-observe','feature-native-observe'],actions)
            self.assertEqual(20000,value['capturedEpochMs'])
            before=len(actions);process['pid']=43
            with self.assertRaises(NativeUIError):r.read(RUN,URL)
            self.assertEqual(before,len(actions))
            process['pid']=42;clock.mutate=lambda v:v.update(processId=43)
            with self.assertRaises(NativeUIError):r.read(RUN,URL)


if __name__=='__main__':unittest.main()
