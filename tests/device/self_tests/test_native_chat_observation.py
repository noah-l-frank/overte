"""Original protocol/owner/probe paths on synthetic native receive boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_observation import (ChatCaptureOwner,NativeChatObservation,OwnedChatCapture,
    command,identity,received_texts,validate)
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32
BINDING=dict(scope='NATIVE_UI_COMPONENT_ONLY',processIdentity='123',sessionId='owned-source',generation=1,targetFingerprint='b'*64)
SELF=identity(RUN,'11111111-1111-4111-8111-111111111111')
PEER=identity(RUN,'22222222-2222-4222-8222-222222222222')


class Boundary:
    """Explicit synthetic native state, never a product source implementation."""
    def __init__(self):
        self.clock=0.;self.sequence=0;self.commands=[];self.value=None;self.alive=True
        self.present=False;self.retired=False;self.opened=0;self.events=[];self.mixer=True
        self.mutate=None;self.ignored=False;self.ignore_retire=False;self.store=None;self.inspect_after_retire=0
    def guard(self):return self.alive
    def sleep(self,value):self.clock+=value
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;op=request['operation']
        if op=='observe':
            if self.store is not None:
                row=self.store.read();assert row['admitted'] and row['sourceInstance']=='c'*32
            self.present=True;self.opened=self.opened or 20000
        elif op=='retire' and not self.ignore_retire:
            self.present=False;self.retired=True;self.opened=0;self.events=[]
        elif op=='inspect' and self.retired:self.inspect_after_retire+=1
        self.value=dict(chatVersion=1,**{k:request[k] for k in ('commandId','operation','runId')},
            instance='c'*32,sequence=self.sequence,processId=123,capturedEpochMs=20000,
            source=dict(scopePresent=self.present,retired=self.retired,selfSha256=SELF,
                mixerPresent=self.mixer,mixerSha256='d'*64 if self.mixer else '',openedEpochMs=self.opened,
                eventSequence=len(self.events),droppedEvents=0,events=deepcopy(self.events)))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value is not None else ''
    def event(self,*,text=None,local=False,sender=PEER,channel='domain'):
        self.events.append(dict(sequence=len(self.events)+1,capturedEpochMs=20000,senderSha256=sender,
            localOnly=local,channel=channel,text=text or context(RUN)['unicode']))
    def reader(self,**kwargs):
        return NativeChatObservation(self.send,self.read,lambda:20000,self.guard,123,
            monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)


class NativeChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=PrivateFeatureState(Path(self.temp.name)/'owner.json')
        self.native=Boundary();self.native.store=self.store;self.reader=self.native.reader()
        self.owner=ChatCaptureOwner(self.store,BINDING,self.native.guard,component_only=True)
        self.capture=OwnedChatCapture(self.reader,self.owner,RUN)

    def test_owned_original_receive_order_and_multiplicity_survive_fresh_inspections(self):
        self.capture.observe();self.native.event();self.native.event()
        value=self.capture.observe()
        self.assertEqual([context(RUN)['unicode']]*2,received_texts(value,sender_sha256=PEER,receiver_sha256=SELF,channel='domain'))
        self.assertTrue(self.store.read()['active']);self.capture.retire()
        self.assertIsNone(self.store.read());self.assertEqual(2,self.native.inspect_after_retire)
        self.assertFalse(self.native.events)

    def test_local_echo_and_other_sender_or_channel_never_become_remote_delivery(self):
        self.capture.observe();self.native.event(local=True);self.native.event(sender='e'*64);self.native.event(channel='local')
        value=self.capture.observe()
        self.assertEqual([],received_texts(value,sender_sha256=PEER,receiver_sha256=SELF,channel='domain'))
        self.assertEqual([context(RUN)['unicode']],received_texts(value,sender_sha256=PEER,receiver_sha256=SELF,channel='domain',remote=False))
        with self.assertRaises(NativeUIError):received_texts(value,sender_sha256=SELF,receiver_sha256=SELF,channel='domain')
        with self.assertRaises(NativeUIError):received_texts(value,sender_sha256=PEER,receiver_sha256=PEER,channel='domain')

    def test_sender_identity_uses_actual_uuid_bytes_and_owned_run_not_display_name(self):
        self.assertNotEqual(SELF,identity('b'*32,'11111111-1111-4111-8111-111111111111'))
        for value in ('Actual peer','{11111111-1111-4111-8111-111111111111}','00000000-0000-0000-0000-000000000000'):
            with self.assertRaises(NativeUIError):identity(RUN,value)

    def test_closed_commands_reject_expected_values_secrets_and_old_or_wrong_types(self):
        request=dict(schemaVersion=1,commandId='f'*32,action='feature-chat-observe',operation='observe',runId=RUN)
        self.assertEqual(request,command(request))
        for edit in ({'schemaVersion':True},{'commandId':'ios-'+'f'*32},{'runId':'foreign'},
                     {'operation':'send'},{'expected':[]},{'text':'private'},{'peer':PEER}):
            with self.assertRaises(NativeUIError):command(request|edit)
        self.assertEqual(request|{'commandId':'ios-'+'f'*32},command(request|{'commandId':'ios-'+'f'*32},ios=True))

    def test_missing_and_ignored_source_are_unavailable_and_intent_is_retained(self):
        self.native.ignored=True
        with self.assertRaises(NativeUIError):self.capture.observe()
        self.assertIsNotNone(self.store.read());self.assertLessEqual(self.native.clock,5)
        self.assertEqual(1,len(self.native.commands))

    def test_wrong_native_process_run_instance_and_replayed_sequence_fail(self):
        for edit in ({'processId':124},{'runId':'f'*32},{'instance':'f'*32},{'sequence':1},{'capturedEpochMs':19999}):
            with self.subTest(edit=edit):
                n=Boundary();r=n.reader();r.perform(RUN,'observe');n.mutate=lambda value:value.update(edit)
                with self.assertRaises(NativeUIError):r.perform(RUN,'inspect')

    def test_malformed_history_time_payload_multiplicity_and_flags_are_rejected(self):
        self.capture.observe();self.native.event();value=self.capture.observe();request=self.native.commands[-1]
        for edit in ({'sequence':2},{'capturedEpochMs':19999},{'capturedEpochMs':20001},
                     {'localOnly':1},{'text':'foreign private text'},{'channel':'peer'},{'senderSha256':'bad'}):
            changed=deepcopy(value);changed['source']['events'][0].update(edit)
            with self.assertRaises(NativeUIError):validate(changed,request,123,20000)
        for edit in ({'eventSequence':2},{'droppedEvents':1},{'scopePresent':False},{'retired':True},
                     {'mixerPresent':0},{'mixerSha256':''},{'openedEpochMs':20001}):
            changed=deepcopy(value);changed['source'].update(edit)
            with self.assertRaises(NativeUIError):validate(changed,request,123,20000)

    def test_original_receive_history_cannot_be_rewritten_or_retimed(self):
        self.capture.observe();self.native.event();self.capture.observe()
        for edit in ({'text':context(RUN)['retry']},{'localOnly':True},{'senderSha256':'e'*64}):
            self.native.mutate=lambda value:value['source']['events'][0].update(edit)
            with self.assertRaises(NativeUIError):self.capture.observe()

    def test_dropped_originals_cannot_be_treated_as_empty_or_complete_remote_history(self):
        self.capture.observe()
        for _ in range(128):self.native.event()
        def drop(value):
            source=value['source'];source.update(eventSequence=129,droppedEvents=1)
            for seq,event in enumerate(source['events'],2):event['sequence']=seq
        self.native.mutate=drop
        with self.assertRaises(NativeUIError):self.capture.observe()
        with self.assertRaises(NativeUIError):received_texts(self.native.value,sender_sha256=PEER,receiver_sha256=SELF,channel='domain')

    def test_false_cleanup_ack_and_missing_final_inventory_keep_intent(self):
        self.capture.observe();self.native.event();self.native.ignore_retire=True
        with self.assertRaises(NativeUIError):self.capture.retire()
        self.assertIsNotNone(self.store.read());self.assertTrue(self.native.present)
        self.native.ignore_retire=False
        def broken(value):
            if self.native.inspect_after_retire>=2:value['source']['scopePresent']=True
        self.native.mutate=broken
        with self.assertRaises(NativeUIError):self.capture.retire()
        self.assertIsNotNone(self.store.read())
        self.native.mutate=None;self.capture.retire();self.assertIsNone(self.store.read())

    def test_pending_owner_can_retire_uncertain_cache_with_same_original_source(self):
        self.owner.begin(RUN);initial=self.reader.perform(RUN,'inspect');self.owner.admit(initial)
        self.reader.perform(RUN,'observe') # Lost outer activation receipt after actual mutation.
        replacement=OwnedChatCapture(self.native.reader(),self.owner,RUN);replacement.retire()
        self.assertIsNone(self.store.read());self.assertTrue(self.native.retired)

    def test_unadmitted_owner_never_purges_foreign_native_scope(self):
        self.native.present=True;self.native.opened=20000
        with self.assertRaises(NativeUIError):self.capture.observe()
        self.assertFalse(self.store.read()['admitted'])
        with self.assertRaises(NativeUIError):self.capture.retire()
        self.assertFalse(any(c['operation']=='retire' for c in self.native.commands))
        self.assertTrue(self.native.present)

    def test_failed_durable_intent_prevents_native_cache_creation(self):
        self.store.write=lambda *_:(_ for _ in ()).throw(OSError('Synthetic journal failure'))
        with self.assertRaises(OSError):self.capture.observe()
        self.assertEqual([],self.native.commands)

    def test_source_replacement_and_changed_binding_never_adopt_cleanup(self):
        self.capture.observe();self.native.mutate=lambda value:value.update(instance='f'*32)
        replacement=OwnedChatCapture(self.native.reader(),self.owner,RUN)
        with self.assertRaises(NativeUIError):replacement.retire()
        self.assertFalse(any(c['operation']=='retire' for c in self.native.commands));self.assertIsNotNone(self.store.read())
        other=ChatCaptureOwner(self.store,BINDING|{'generation':2},self.native.guard,component_only=True)
        with self.assertRaises(NativeUIError):other.owned()

    def test_changed_native_session_uuid_and_forged_binding_types_block_adoption(self):
        self.capture.observe()
        self.native.mutate=lambda value:value['source'].update(selfSha256='f'*64)
        replacement=OwnedChatCapture(self.native.reader(),self.owner,RUN)
        with self.assertRaises(NativeUIError):replacement.retire()
        self.assertFalse(any(c['operation']=='retire' for c in self.native.commands))
        original=self.store.read();forged=deepcopy(original);forged['binding']['generation']=True
        self.store.write(forged,original)
        with self.assertRaises(NativeUIError):self.owner.owned()

    def test_lost_activation_journal_update_still_recovers_only_owned_native_cache(self):
        actual=self.store.write
        def write(value,previous):
            if value['active']:raise OSError('Synthetic active journal write failure')
            actual(value,previous)
        self.store.write=write
        with self.assertRaises(OSError):self.capture.observe()
        self.assertTrue(self.native.present);self.assertTrue(self.store.read()['admitted']);self.assertFalse(self.store.read()['active'])
        self.store.write=actual;OwnedChatCapture(self.native.reader(),self.owner,RUN).retire()
        self.assertIsNone(self.store.read())

    def test_scope_cannot_silently_disappear_or_be_resurrected_after_retirement(self):
        self.capture.observe();self.native.present=False;self.native.opened=0
        with self.assertRaises(NativeUIError):self.capture.observe()
        self.capture.retire()
        self.native.retired=False
        with self.assertRaises(NativeUIError):self.reader.perform(RUN,'inspect')

    def test_late_transport_and_regressing_monotonic_clock_do_not_pass(self):
        for fault in ('late','rewind'):
            n=Boundary();original=n.send
            def send(request):
                original(request);n.clock=6 if fault=='late' else -1
            r=NativeChatObservation(send,n.read,lambda:20000,n.guard,123,monotonic=lambda:n.clock,sleep=n.sleep)
            with self.assertRaises(NativeUIError):r.perform(RUN,'observe')

    def test_ios_native_epoch_is_retained_without_host_clock_substitution(self):
        self.native.store=None
        r=NativeChatObservation(self.native.send,self.native.read,lambda:99900000,self.native.guard,123,ios=True,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        value=r.perform(RUN,'observe');self.assertEqual(20000,value['capturedEpochMs'])
        self.assertTrue(value['commandId'].startswith('ios-'))
        self.native.mutate=lambda value:value.update(capturedEpochMs=19999)
        with self.assertRaises(NativeUIError):r.perform(RUN,'inspect')

    def test_original_javascript_deduplicates_and_missing_hook_stays_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureChatObservation:c=>{calls++;return {commandId:c.commandId,source:{events:[{original:true}]}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"feature-chat-observe",operation:"observe",runId:"b".repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files.length!==1||!files[0].v.source.events[0].original||files[0].name!=="feature-chat-observation.json")throw Error('original missing');
applyClientCommand({...c,commandId:"c".repeat(32),expected:[]});if(calls!==1)throw Error('desired facts accepted');
delete Test.featureChatObservation;applyClientCommand({...c,commandId:"ios-"+"d".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error('missing hook green');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_fixture_accepts_only_closed_ios_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);state=FixtureState()
            request=dict(schemaVersion=1,commandId='ios-'+'f'*32,action='feature-chat-observe',operation='inspect',runId=RUN)
            state.set_client_command(request)
            for edit in ({'expected':[]},{'text':'private'},{'operation':'send'},{'runId':'bad'}):
                with self.assertRaises(ValueError):state.set_client_command(request|edit)


if __name__=='__main__':unittest.main()
