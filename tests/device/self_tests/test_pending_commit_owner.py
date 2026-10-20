"""Synthetic native owner boundaries verify transport and effect assertions.

The C++ owner/Qt events are not executed or qualified by these host tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pending_commit_owner import NativePendingCommitOwner,command,validate
from adapters.prepared_field_commit import digest
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32
SOURCE='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'


class Boundary:
    def __init__(self,fault=''):
        self.fault=fault;self.clock=0.;self.sequence=0;self.intent=0;self.commands=[];self.intents=[]
        self.request=None;self.last_id=None;self.cached=None;self.issued={}
        self.focused=False;self.text='';self.token='d'*32;self.record=None;self.alive=True;self.edit=None
    def send(self,request):self.request=deepcopy(request);self.commands.append(deepcopy(request))
    def epoch(self):return 20000+round(self.clock*1000)
    def original(self):
        if self.fault=='ignored':return ''
        request=self.request
        if request['commandId']!=self.last_id:
            self.last_id=request['commandId'];self.sequence+=1;operation=request['operation'];performed=False
            if operation!='observe':self.intent=request['intentSequence']
            bound=operation in ('observe','release') or self.issued.get(request['observationSequence'])==(request['runId'],request['fieldToken']) and request['fieldToken']==self.token
            if bound:
                if operation=='focus':
                    performed=True
                    if self.fault!='focus-ignored':self.focused=True
                elif operation=='type':
                    performed=True
                    if self.fault!='type-ignored':self.text='retry-'+RUN
                elif operation=='hold':
                    performed=True
                    if self.fault!='hold-ignored':
                        self.record=dict(captureCommandId=request['commandId'],fieldToken=self.token,
                            created=self.epoch(),pending=True,events=[dict(sequence=1,kind='captured',reason='none',capturedEpochMs=self.epoch(),elapsedMs=0)])
                elif operation=='attempt' and self.record:
                    performed=True
                    if self.fault!='attempt-ignored':
                        kind='sent' if self.fault=='attempt-sent' else 'rejected'
                        self.record['pending']=False
                        self.record['events'].append(dict(sequence=2,kind=kind,reason='context-retired' if kind=='rejected' else 'none',
                            capturedEpochMs=self.epoch(),elapsedMs=self.epoch()-self.record['created']))
                        if kind=='sent':self.text='Overte ä Ω 東京 '+RUN
                elif operation=='release' and self.record:
                    performed=True
                    if self.fault!='release-ignored' and self.record['pending']:
                        self.record['pending']=False
                        self.record['events'].append(dict(sequence=2,kind='released',reason='none',capturedEpochMs=self.epoch(),
                            elapsedMs=self.epoch()-self.record['created']))
            commit={}
            if self.record:
                commit=dict(captureCommandId=self.record['captureCommandId'],fieldToken=self.record['fieldToken'],
                    observation=dict(pendingFieldCommitVersion=1,requestId=request['commandId'],instance='f'*32,eventId='1'*32,
                        sequence=self.sequence,processId=123,createdEpochMs=self.record['created'],capturedEpochMs=self.epoch(),
                        elapsedMs=self.epoch()-self.record['created'],pending=self.record['pending'],
                        source=dict(componentUrl=SOURCE,fieldName='scriptFilter',initialTextSha256=digest('retry-'+RUN),
                            inputSha256=digest('Overte ä Ω 東京 '+RUN),inputCodeUnits=len(('Overte ä Ω 東京 '+RUN).encode('utf-16-le'))//2),
                        events=deepcopy(self.record['events'])))
            self.cached=dict(pendingCommitOwnerVersion=1,commandId=request['commandId'],operation=operation,runId=RUN,
                instance='b'*32,sequence=self.sequence,processId=123,canonicalComponentUrl=SOURCE,capturedEpochMs=self.epoch(),
                lastIntentSequence=self.intent,performed=performed,current=dict(status='ready',token=self.token,
                    componentUrl=SOURCE,text=self.text,focused=self.focused,frame=[0,10,200,40]),commit=commit,
                resources=dict(pendingRuns=[RUN] if self.record and self.record['pending'] else [],archivedEvents=int(self.record is not None)))
            self.issued[self.sequence]=(RUN,self.token)
        value=deepcopy(self.cached)
        if self.edit:self.edit(value)
        return json.dumps(value)
    def sleep(self,seconds):self.clock+=seconds
    def owner(self,*,readonly=False,ios=False):
        return NativePendingCommitOwner(self.send,self.original,self.epoch,lambda:self.alive,123,ios=ios,
            intent=None if readonly else self.intents.append,monotonic=lambda:self.clock,sleep=self.sleep)
    def replace_context(self):self.token='e'*32;self.text='';self.focused=False


class PendingCommitOwnerTests(unittest.TestCase):
    def test_actual_source_receipts_are_retained_across_new_context_attempt_and_cleanup(self):
        boundary=Boundary();owner=boundary.owner()
        owner.focus(RUN);owner.type_owned(RUN);held=owner.hold(RUN)
        event=held['commit']['observation']['eventId'];original=deepcopy(held['commit']['observation']['events'][0])
        boundary.replace_context();retired=owner.attempt_retired(RUN,event)
        self.assertEqual('',retired['current']['text']);self.assertFalse(retired['current']['focused'])
        self.assertEqual(original,retired['commit']['observation']['events'][0])
        cleaned=owner.release_owned(RUN,event);owner.release_owned(RUN,event)
        self.assertFalse(cleaned['commit']['observation']['pending']);self.assertEqual([],cleaned['resources']['pendingRuns'])
        mutations=[c for c in boundary.commands if c['operation']!='observe']
        self.assertEqual(mutations,boundary.intents)
        self.assertNotIn('expected',str(boundary.commands));self.assertNotIn('componentUrl',str(boundary.commands))

    def test_acknowledged_focus_and_type_without_actual_effect_fail(self):
        for fault in ('focus-ignored','type-ignored'):
            boundary=Boundary(fault);owner=boundary.owner()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                owner.focus(RUN)
                owner.type_owned(RUN)
            self.assertLessEqual(boundary.clock,5.01)
            self.assertEqual(1,sum(c['operation']==('focus' if fault=='focus-ignored' else 'type') for c in boundary.commands))

    def test_acknowledged_missing_capture_stale_attempt_and_release_cannot_pass(self):
        for fault in ('hold-ignored','attempt-ignored','attempt-sent','release-ignored'):
            boundary=Boundary(fault);owner=boundary.owner();owner.focus(RUN);owner.type_owned(RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                held=owner.hold(RUN);event=held['commit']['observation']['eventId']
                if fault=='release-ignored':owner.release_owned(RUN,event)
                else:boundary.replace_context();owner.attempt_retired(RUN,event)

    def test_old_frame_token_cannot_capture_a_new_native_field(self):
        boundary=Boundary();owner=boundary.owner();owner.focus(RUN);before=owner.type_owned(RUN)
        boundary.replace_context();owner.read(RUN)
        value=owner.operate(RUN,'hold',observed=before)
        self.assertFalse(value['performed']);self.assertIsNone(boundary.record)

    def test_observer_has_no_mutation_intent_authority(self):
        boundary=Boundary();owner=boundary.owner(readonly=True);owner.read(RUN)
        count=len(boundary.commands)
        with self.assertRaises(NativeUIError):owner.operate(RUN,'focus')
        self.assertEqual(count,len(boundary.commands));self.assertEqual([],boundary.intents)

    def test_ignored_foreign_or_missing_source_is_bounded_without_resend(self):
        for fault in ('ignored','foreign','missing'):
            boundary=Boundary(fault)
            if fault=='foreign':boundary.edit=lambda v:v.update(commandId='c'*32)
            if fault=='missing':boundary.edit=lambda v:(v.clear(),v.update(pendingCommitOwnerVersion=1,commandId=boundary.request['commandId'],status='unavailable'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):boundary.owner().read(RUN)
            self.assertEqual(1,len(boundary.commands));self.assertLessEqual(boundary.clock,5)

    def test_original_owner_pid_configuration_field_and_inventory_are_not_guessable_labels(self):
        edits=[lambda v:v.update(processId=124),lambda v:v.update(instance='bad'),lambda v:v.update(capturedEpochMs=10000),
               lambda v:v['current'].update(componentUrl='file:///foreign/hifi/dialogs/TabletRunningScripts.qml'),
               lambda v:v['current'].update(text='unowned private text'),lambda v:v['current'].update(frame=[False,0,2,2]),
               lambda v:v['resources'].update(pendingRuns=[RUN]),lambda v:v.update(expected={})]
        for edit in edits:
            boundary=Boundary();boundary.edit=edit
            with self.subTest(edit=edit),self.assertRaises((ValueError,NativeUIError)):boundary.owner().read(RUN)

    def test_history_identity_capture_token_and_event_times_cannot_be_replaced(self):
        for edit in (lambda v:v['commit']['observation'].update(eventId='9'*32),
                     lambda v:v['commit'].update(fieldToken='9'*32),
                     lambda v:v['commit']['observation']['events'][0].update(capturedEpochMs=19999)):
            boundary=Boundary();owner=boundary.owner();owner.focus(RUN);owner.type_owned(RUN);owner.hold(RUN)
            boundary.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):owner.read(RUN)

    def test_closed_command_and_existing_http_fixture_reject_extra_assertions_and_unsafe_inputs(self):
        state=FixtureState();request=dict(schemaVersion=1,commandId='ios-'+'c'*32,
            action='feature-pending-commit-owner',operation='observe',runId=RUN,eventId='')
        state.set_client_command(request)
        for edit in ({'expected':{}},{'fieldPath':'any object'},{'schemaVersion':True},{'eventId':None},
                     {'operation':'attempt'},{'commandId':request['commandId']+'\n'}):
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):command(request|edit,ios=True)
            with self.assertRaises(ValueError):state.set_client_command(request|edit)

    def test_original_probe_missing_hook_never_becomes_empty_success(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];const Test={featurePendingCommitOwner:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'c'.repeat(32),action:'feature-pending-commit-owner',operation:'observe',runId:'a'.repeat(32),eventId:''};
applyClientCommand(c);if(calls!==1||!files[0].v.original||files[0].name!=='feature-pending-commit-owner.json')throw Error('original source missing');
for(const edit of [{expected:{}},{fieldPath:'any object'},{schemaVersion:true},{operation:'attempt'},{commandId:c.commandId+'\n'}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('unsafe command accepted');delete Test.featurePendingCommitOwner;
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32)});if(files.length!==2||files[1].v.status!=='unavailable')throw Error('missing owner became green');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
