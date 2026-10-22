"""Synthetic original lease replies; actual Setting::Manager has a Qt6 check."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_history import NativeChatHistory,command,validate
from adapters.normal_ui import NativeUIError
RUN='a'*32


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.value=None;self.ignored=False;self.alive=True;self.mutate=None;self.commands=[]
        self.source=dict(scopePresent=False,retired=False,restored=False,originalKind='',originalSha256='',currentSha256='c'*64,
                         configSha256='d'*64,openedEpochMs=0,handbackEpochMs=0,closed=True)
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.value=dict(chatHistoryVersion=1,**{k:request[k] for k in ('commandId','runId','operation')},instance='b'*32,
                        sequence=self.sequence,processId=123,capturedEpochMs=self.epoch,source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value is not None else None
    def sleep(self,value):self.clock+=value
    def reader(self):return NativeChatHistory(self.send,self.read,lambda:self.epoch,lambda:self.alive,123,monotonic=lambda:self.clock,sleep=self.sleep)
    def capture(self):self.source.update(scopePresent=True,originalKind='unset',originalSha256='c'*64,openedEpochMs=self.epoch)
    def restore(self):self.source.update(restored=True,currentSha256='c'*64,handbackEpochMs=self.epoch)


class ChatHistoryTests(unittest.TestCase):
    def test_capture_restore_retire_and_new_reader_keep_original_typed_source_and_handback(self):
        b=Boundary();r=b.reader();self.assertFalse(r.perform(RUN,'inspect')['source']['scopePresent'])
        b.capture();original=r.perform(RUN,'capture');b.source['currentSha256']='e'*64;r.perform(RUN,'inspect');b.restore()
        restored=r.perform(RUN,'restore');new=b.reader();new.restore_source(restored)
        b.source.update(scopePresent=False,retired=True);retired=new.perform(RUN,'retire')
        self.assertEqual(original['source']['originalSha256'],retired['source']['originalSha256'])
        self.assertEqual(restored['source']['handbackEpochMs'],retired['source']['handbackEpochMs'])
    def test_consumed_ack_without_actual_setting_restoration_is_red(self):
        b=Boundary();b.capture();r=b.reader();r.perform(RUN,'inspect');b.source['currentSha256']='e'*64
        with self.assertRaises(NativeUIError):r.perform(RUN,'restore')
    def test_open_hidden_editor_or_keyboard_gate_cannot_be_claimed_closed_in_restore_packet(self):
        b=Boundary();b.capture();r=b.reader();r.perform(RUN,'inspect');b.restore();b.source['closed']=False
        with self.assertRaises(NativeUIError):r.perform(RUN,'restore')
    def test_original_setting_type_digest_config_and_scope_cannot_be_replaced(self):
        for key,value in (('originalKind','array'),('originalSha256','e'*64),('configSha256','e'*64),('openedEpochMs',19999)):
            b=Boundary();b.capture();r=b.reader();r.perform(RUN,'inspect');b.source[key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
    def test_handback_cannot_be_freshened_when_host_resumes(self):
        b=Boundary();b.capture();b.restore();r=b.reader();old=r.perform(RUN,'inspect');new=b.reader();new.restore_source(old)
        b.epoch+=1;b.source['handbackEpochMs']+=1
        with self.assertRaises(NativeUIError):new.perform(RUN,'inspect')
    def test_native_lease_must_be_actually_retired_and_cannot_resurrect(self):
        b=Boundary();b.capture();b.restore();r=b.reader();r.perform(RUN,'inspect')
        with self.assertRaises(NativeUIError):r.perform(RUN,'retire')
        b.source.update(scopePresent=False,retired=True);r.perform(RUN,'retire');b.source.update(scopePresent=True,retired=False)
        with self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
    def test_restore_and_retire_need_original_checkpoint_before_transport_mutation(self):
        for op in ('restore','retire'):
            b=Boundary();b.capture();b.restore()
            with self.subTest(op=op),self.assertRaises(NativeUIError):b.reader().perform(RUN,op)
            self.assertEqual([],b.commands)
    def test_missing_original_reply_is_bounded_and_not_retried(self):
        b=Boundary();b.ignored=True
        with self.assertRaises(NativeUIError):b.reader().perform(RUN,'capture')
        self.assertEqual(1,len(b.commands));self.assertLessEqual(b.clock,5)
    def test_protocol_has_no_original_or_expected_setting_write_fields(self):
        request=dict(schemaVersion=1,commandId='b'*32,action='feature-chat-history',operation='capture',runId=RUN)
        for key,value in (('history',[]),('originalKind','unset'),('config',{}),('restored',True),('schemaVersion',True)):
            with self.subTest(key=key),self.assertRaises(NativeUIError):command({**request,key:value})
    def test_wrong_pid_instance_run_counter_or_freshness_fail(self):
        for key,value in (('processId',124),('instance','e'*32),('runId','f'*32),('sequence',1),('capturedEpochMs',18000)):
            b=Boundary();r=b.reader();r.perform(RUN,'inspect');b.mutate=lambda row:row.update({key:value})
            with self.subTest(key=key),self.assertRaises(NativeUIError):r.perform(RUN,'inspect')
    def test_phone_read_only_transport_allows_original_reads_but_refuses_setting_or_cache_mutation(self):
        phone=Path(__file__).resolve().parents[1]/'adapters'/'android-phone';sys.path.insert(0,str(phone))
        from appium_adapter import readonly_feature_command
        base=dict(schemaVersion=1,commandId='b'*32,runId=RUN)
        readonly_feature_command(dict(base,action='feature-chat-history',operation='inspect'))
        readonly_feature_command(dict(base,action='feature-chat-observe',operation='inspect'))
        readonly_feature_command(dict(base,action='feature-chat-view-observe'))
        for op in ('capture','restore','retire'):
            with self.subTest(op=op),self.assertRaises((RuntimeError,ValueError)):
                readonly_feature_command(dict(base,action='feature-chat-history',operation=op))
        for op in ('observe','retire'):
            with self.subTest(op=op),self.assertRaises((RuntimeError,ValueError)):
                readonly_feature_command(dict(base,action='feature-chat-observe',operation=op))

    def test_closed_source_rejects_boolean_counter_or_fabricated_extra_fields(self):
        b=Boundary();r=b.reader();value=r.perform(RUN,'inspect')
        for key,new in (('openedEpochMs',True),('restored',True),('expectedHistory',[])):
            forged=deepcopy(value);forged['source'][key]=new
            with self.subTest(key=key),self.assertRaises(NativeUIError):validate(forged,b.commands[-1],123,b.epoch)

if __name__=='__main__':unittest.main()
