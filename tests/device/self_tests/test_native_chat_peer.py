"""Deliberately synthetic independent native peer replies; no device acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_peer import NativeChatPeer,command,validate
from adapters.normal_ui import NativeUIError
RUN='a'*32
POSITION=dict(x=2.25,y=0,z=2)


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.value=None;self.ignored=False;self.alive=True;self.mutate=None;self.commands=[]
        self.source=dict(selfSha256='c'*64,mixerPresent=True,mixerSha256='d'*64,leasePresent=False,admitted=False,restored=False,
                         position=deepcopy(POSITION),originalPosition={},inputSequence=0,lastInput={},handback={})
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.value=dict(chatPeerVersion=1,**{k:request[k] for k in ('commandId','runId','operation')},instance='b'*32,
                        sequence=self.sequence,processId=123,capturedEpochMs=self.epoch,source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value is not None else None
    def sleep(self,value):self.clock+=value
    def reader(self):return NativeChatPeer(self.send,self.read,lambda:self.epoch,lambda:self.alive,123,monotonic=lambda:self.clock,sleep=self.sleep)
    def admit(self):self.source.update(leasePresent=True,admitted=True,originalPosition=deepcopy(POSITION))
    def sent(self,operation='send-domain-reply'):
        self.source['inputSequence']+=1
        self.source['lastInput']=dict(sequence=self.source['inputSequence'],operation=operation,capturedEpochMs=self.epoch,
                                      position=deepcopy(self.source['position']),payloadSha256='e'*64)
    def restored(self):
        self.source.update(leasePresent=False,restored=True,position=deepcopy(POSITION),
                           handback=dict(capturedEpochMs=self.epoch,position=deepcopy(POSITION),inputSequence=self.source['inputSequence']))


class NativePeerTests(unittest.TestCase):
    def test_source_exposes_consumed_input_pose_without_any_delivery_field(self):
        b=Boundary();r=b.reader();r.perform(RUN,'inspect');b.admit();r.perform(RUN,'lease');b.sent()
        value=r.perform(RUN,'send-domain-reply')
        self.assertEqual(1,value['source']['inputSequence']);self.assertNotIn('messages',value['source']);self.assertNotIn('delivered',value['source'])
    def test_fresh_ack_reusing_an_old_send_is_rejected(self):
        b=Boundary();b.admit();b.sent();r=b.reader();r.perform(RUN,'inspect')
        with self.assertRaises(NativeUIError):r.perform(RUN,'send-domain-reply')
    def test_old_consumed_input_timestamp_cannot_be_retimed_by_outer_envelope(self):
        b=Boundary();b.admit();r=b.reader();r.perform(RUN,'inspect');b.sent();b.epoch+=1
        with self.assertRaises(NativeUIError):r.perform(RUN,'send-domain-reply')
    def test_ignored_input_is_bounded_and_never_retried(self):
        b=Boundary();r=b.reader();r.perform(RUN,'inspect');b.ignored=True
        with self.assertRaises(NativeUIError):r.perform(RUN,'lease')
        self.assertEqual(2,len(b.commands));self.assertLessEqual(b.clock,5)
    def test_source_restore_pins_original_pose_identity_and_immutable_handback(self):
        b=Boundary();b.admit();r=b.reader();r.perform(RUN,'inspect');b.sent();r.perform(RUN,'send-domain-reply');b.restored()
        original=r.perform(RUN,'restore');fresh=b.reader();fresh.restore_source(original)
        b.source['position']['x']=3
        self.assertEqual(original['source']['handback'],fresh.perform(RUN,'inspect')['source']['handback'])
        b.source['handback']['capturedEpochMs']+=1;b.epoch+=1
        with self.assertRaises(NativeUIError):fresh.perform(RUN,'inspect')
    def test_foreign_pose_or_identity_cannot_replace_bound_original(self):
        for field in ('originalPosition','selfSha256'):
            b=Boundary();b.admit();r=b.reader();r.perform(RUN,'inspect')
            if field=='originalPosition':b.source[field]['x']=3
            else:b.source[field]='f'*64
            with self.subTest(field=field),self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
    def test_foreign_run_instance_pid_sequence_and_retired_lease_fail(self):
        for field,value in (('instance','f'*32),('processId',124),('sequence',1),('runId','f'*32)):
            b=Boundary();r=b.reader();r.perform(RUN,'inspect');b.mutate=lambda row:row.update({field:value})
            with self.subTest(field=field),self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
        b=Boundary();b.admit();b.restored();r=b.reader();r.perform(RUN,'inspect');b.source['restored']=False;b.source['handback']={};b.source['leasePresent']=True
        with self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
    def test_unadmitted_send_restore_and_missing_mixer_fail_closed(self):
        b=Boundary();r=b.reader();r.perform(RUN,'inspect')
        for op in ('send-local-distant','restore'):
            with self.subTest(op=op),self.assertRaises(NativeUIError):r.perform(RUN,op)
        b.admit();r.perform(RUN,'inspect');b.sent();b.source.update(mixerPresent=False,mixerSha256='')
        with self.assertRaises(NativeUIError):r.perform(RUN,'send-domain-reply')
    def test_closed_stimulus_schema_cannot_supply_text_sender_pose_or_expected_delivery(self):
        request=dict(schemaVersion=1,commandId='b'*32,action='feature-chat-peer',operation='inspect',runId=RUN)
        for key,value in (('text','secret'),('position',POSITION),('sender','private'),('delivered',True),('schemaVersion',True)):
            with self.subTest(key=key),self.assertRaises(NativeUIError):command({**request,key:value})
    def test_closed_original_reply_rejects_boolean_numbers_and_forged_handback(self):
        b=Boundary();r=b.reader();value=r.perform(RUN,'inspect');request=b.commands[-1]
        for key,new in (('inputSequence',True),('position',dict(x=True,y=0,z=2)),('handback',dict(position=POSITION))):
            forged=deepcopy(value);forged['source'][key]=new
            with self.subTest(key=key),self.assertRaises(NativeUIError):validate(forged,request,123,b.epoch)
    def test_resume_cannot_send_without_original_source_checkpoint(self):
        b=Boundary();b.admit();b.sent()
        with self.assertRaises(NativeUIError):b.reader().perform(RUN,'send-domain-reply')
        self.assertEqual([],b.commands)

if __name__=='__main__':unittest.main()
