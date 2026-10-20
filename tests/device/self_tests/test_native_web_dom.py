"""Closed native Web/DOM source logic, synthetic native/DOM/OS boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_web_dom import NativeWebDOMObservation,command,validate
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32
URL='http://controlled.invalid:49121/feature-fixture/v1/runs/'+RUN+'/'


class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.request=None;self.commands=[];self.mutate=None;self.alive=True;self.ignored=False
    def send(self,value):self.request=deepcopy(value);self.commands.append(deepcopy(value))
    def original(self):
        if self.ignored:return ''
        self.sequence+=1;c=self.request
        document=dict(runId=RUN,href=URL+'tickets/'+'e'*32+'/reference.html',responseId='f'*32,readyState='complete')
        dom=dict(webDOMVersion=1,requestId=c['commandId'],instance='b'*32,sequence=self.sequence,capturedEpochMs=20000,
                 document=document,editor=dict(text='Grüße 🌍',focused=True),attempts=[],echoes=[])
        view=dict(handle='42',creation=1,grant=1,page=1,url=document['href'],nativeFinished=True,httpErrorStatus=0,
                  inlineLease=False,sourceUrl=document['href'],sourceIdentity='owned-native-view')
        value=dict(webNativeVersion=1,commandId=c['commandId'],runId=RUN,surface=c['surface'],instance='c'*32,
                   sequence=self.sequence,processId=123,capturedEpochMs=20000,status='ready',source=dict(nativeView=view,dom=dom))
        if self.mutate:self.mutate(value)
        return json.dumps(value)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,*,ios=False):return NativeWebDOMObservation(self.send,self.original,lambda:20000,lambda:self.alive,123,
        ios=ios,monotonic=lambda:self.clock,sleep=self.sleep)


class NativeWebDOMTests(unittest.TestCase):
    def test_original_raw_view_dom_are_retained_without_expected_feature_fields(self):
        n=Boundary();reader=n.reader();a=reader.read(RUN,'world',URL);b=reader.read(RUN,'world',URL)
        self.assertEqual('Grüße 🌍',a['source']['dom']['editor']['text']);self.assertGreater(b['sequence'],a['sequence'])
        self.assertEqual({'schemaVersion','commandId','action','runId','surface','fixtureUrl'},set(n.commands[0]))
        self.assertNotIn('httpStatus',a['source']);self.assertEqual(0,a['source']['nativeView']['httpErrorStatus'])
        self.assertNotIn('documentLoads',a['source']);self.assertNotIn('expected',str(n.commands))
        n=Boundary();n.mutate=lambda v:v.update(status='pending',source={}) if n.sequence<3 else None
        self.assertEqual('ready',n.reader().read(RUN,'world',URL)['status']);self.assertEqual(1,len(n.commands))

    def test_missing_ignored_or_foreign_nonce_is_bounded_and_not_resent(self):
        for fault in ('ignored','foreign'):
            n=Boundary()
            if fault=='ignored':n.ignored=True
            else:n.mutate=lambda v:v.update(commandId='d'*32)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):n.reader().read(RUN,'world',URL)
            self.assertEqual(1,len(n.commands));self.assertLessEqual(n.clock,5)

    def test_bad_process_owner_native_completion_http_status_or_dom_scope_fails(self):
        edits=[lambda v:v.update(processId=124),lambda v:v.update(runId='f'*32),
            lambda v:v['source']['nativeView'].update(nativeFinished=False),
            lambda v:v['source']['nativeView'].update(httpErrorStatus=200),
            lambda v:v['source']['nativeView'].update(url='http://foreign.invalid/'),
            lambda v:v['source']['nativeView'].update(sourceUrl='http://foreign.invalid/'),
            lambda v:v['source']['nativeView'].update(sourceUrl=URL+'tickets/../../other'),
            lambda v:v['source']['dom']['document'].update(responseId=None),
            lambda v:v['source']['dom']['document'].update(runId='f'*32)]
        for edit in edits:
            n=Boundary();n.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):n.reader().read(RUN,'world',URL)

    def test_inline_dom_label_and_success_ack_do_not_qualify_native_carrier_ownership(self):
        n=Boundary();n.mutate=lambda v:v['source']['nativeView'].update(inlineLease=True)
        with self.assertRaises(NativeUIError):n.reader().read(RUN,'tablet',URL)
        n=Boundary();reader=n.reader();reader.original=lambda:json.dumps({'commandId':n.request['commandId'],'performed':True})
        with self.assertRaises(NativeUIError):reader.read(RUN,'world',URL)

    def test_retired_view_document_counter_or_source_replacement_fails(self):
        for edit in (lambda v:v.update(instance='f'*32),lambda v:v.update(sequence=1),
                     lambda v:v['source']['nativeView'].update(page=2),
                     lambda v:v['source']['dom'].update(instance='f'*32),
                     lambda v:v['source']['dom'].update(sequence=1)):
            n=Boundary();reader=n.reader();reader.read(RUN,'world',URL);n.mutate=edit
            with self.assertRaises(NativeUIError):reader.read(RUN,'world',URL)

    def test_original_history_cannot_be_truncated_rewritten_or_filled_from_wrong_echo(self):
        n=Boundary()
        event=dict(ordinal=1,capturedEpochMs=19000,eventTimeMs=100.)
        n.mutate=lambda v:v['source']['dom']['attempts'].append(deepcopy(event))
        reader=n.reader();reader.read(RUN,'world',URL)
        n.mutate=None
        with self.assertRaises(NativeUIError):reader.read(RUN,'world',URL)
        n=Boundary()
        def forged(v):
            v['source']['dom']['echoes'].append(dict(sequence=1,surface='world',message=json.dumps(
                {'contract':'overte-web-parity-v1','action':'echo','sequence':2,'surface':'world'}),
                receivedEpochMs=19000,observedEpochMs=19001))
        n.mutate=forged
        with self.assertRaises(NativeUIError):n.reader().read(RUN,'world',URL)

    def test_stale_native_dom_regressing_clock_and_lost_guard_fail(self):
        for edit in (lambda v:v.update(capturedEpochMs=18000),lambda v:v['source']['dom'].update(capturedEpochMs=18000)):
            n=Boundary();n.mutate=edit
            with self.assertRaises(NativeUIError):n.reader().read(RUN,'world',URL)
        for fault in ('guard','late','rewind'):
            n=Boundary();original=n.original
            def changed():
                value=original()
                if fault=='guard':n.alive=False
                else:n.clock=6 if fault=='late' else -1
                return value
            reader=n.reader();reader.original=changed
            with self.assertRaises(NativeUIError):reader.read(RUN,'world',URL)

    def test_actual_fixture_grammar_rejects_expected_state_bad_ownership_and_arbitrary_source(self):
        state=FixtureState();c=dict(schemaVersion=1,commandId='ios-'+'d'*32,action='feature-web-dom-observe',
                                   runId=RUN,surface='world',fixtureUrl=URL)
        state.set_client_command(c)
        for edit in ({'expected':{}},{'script':'read any page'},{'surface':'other'},{'schemaVersion':True},
                     {'fixtureUrl':URL+'elsewhere'},{'fixtureUrl':URL.replace('controlled.invalid','user:secret@host')},
                     {'commandId':c['commandId']+'\n'}):
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):command(c|edit,ios=True)
            with self.assertRaises(ValueError):state.set_client_command(c|edit)
        n=Boundary()
        with self.assertRaises(NativeUIError):n.reader().read(RUN,'world',URL+'wrong')
        self.assertFalse(n.commands)

    def test_original_probe_only_reads_fixed_source_and_missing_hook_never_becomes_success(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureWebDOMObservation:c=>{calls++;return {commandId:c.commandId,status:calls<2?'pending':'ready',source:{original:true}};},
    saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'d'.repeat(32),action:'feature-web-dom-observe',runId:'a'.repeat(32),surface:'world',
    fixtureUrl:'http://controlled.invalid:49121/feature-fixture/v1/runs/'+'a'.repeat(32)+'/'};
applyClientCommand(c);applyClientCommand(c);
if(calls!==2||files.length!==2||!files[1].v.source.original||files[1].name!=='feature-web-dom-observation.json')throw Error('original native read missing');
for(const edit of [{expected:{}},{surface:'other'},{schemaVersion:true},{commandId:c.commandId+'\n'},{fixtureUrl:'http://user:secret@host/path'}])applyClientCommand({...c,...edit});
if(calls!==2)throw Error('unsafe source command accepted');
delete Test.featureWebDOMObservation;applyClientCommand({...c,commandId:'ios-'+'e'.repeat(32)});
if(files.length!==3||files[2].v.status!=='unavailable')throw Error('missing source became green');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
