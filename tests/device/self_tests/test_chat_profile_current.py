"""Passive source/clock behavior on declared synthetic native settings seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from adapters.native_chat_profile_current import NativeChatProfileCurrent,command
from adapters.normal_ui import NativeUIError
from self_tests.test_chat_profile_owner import Boundary as ProfileBoundary
from self_tests.test_native_chat_observation import RUN


class CurrentBoundary:
    def __init__(self):
        self.epoch=20000;self.clock=0.;self.sequence=0;self.commands=[];self.value=None;self.alive=True;self.edit=None
        self.hashes=deepcopy(ProfileBoundary().hashes)
    def send(self,request):
        self.commands.append(deepcopy(request));self.sequence+=1
        self.value=dict(chatProfileCurrentVersion=1,commandId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=123,capturedEpochMs=self.epoch,current=deepcopy(self.hashes),
            settings=dict(instance='b'*32,writerInstance='c'*32,mutationSequence=0,capturedEpochMs=self.epoch),
            view=dict(instance='d'*32,sequence=self.sequence,capturedEpochMs=self.epoch))
        if self.edit:self.edit(self.value)
    def original(self):return json.dumps(self.value)
    def sleep(self,delay):self.clock+=delay
    def reader(self):return NativeChatProfileCurrent(self.send,self.original,lambda:self.epoch,lambda:self.alive,123,
        monotonic=lambda:self.clock,sleep=self.sleep)


class CurrentProfileTests(unittest.TestCase):
    def test_passive_actual_fingerprints_and_raw_originals_never_claim_original_or_restoration(self):
        source=CurrentBoundary();reader=source.reader();value=reader.read(RUN)
        self.assertEqual(source.value,value);self.assertEqual(source.original().encode(),reader.last_raw)
        self.assertEqual(hashlib.sha256(reader.last_raw).hexdigest(),reader.last_sha256)
        self.assertEqual({'schemaVersion','commandId','runId','action'},set(source.commands[0]))
        self.assertNotIn('original',value);self.assertNotIn('restored',value);self.assertNotIn('owned',value)
        original=deepcopy(reader.last);value['current']['cache']['ArmoredChat-Config']='f'*64
        self.assertEqual(original,reader.last)
        source.hashes['cache']['ArmoredChat-Config']=source.hashes['worker']['ArmoredChat-Config']='e'*64
        self.assertNotEqual(original['current'],reader.read(RUN)['current'])

    def test_unknown_source_foreign_birth_pid_run_hashes_and_unempty_physical_history_fail_without_cursor(self):
        changes=[dict(processId=124),dict(runId='f'*32),dict(chatProfileCurrentVersion=True),dict(owned=False),
            dict(current=dict(cache={},worker={},physical={}))]
        for changed in changes:
            source=CurrentBoundary();source.edit=lambda value:value.update(changed);reader=source.reader()
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last);self.assertIsNone(reader.last_raw)
        source=CurrentBoundary();source.hashes['physical']['ArmoredChat-Messages']['empty']=False;reader=source.reader()
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertIsNone(reader.last)
        source=CurrentBoundary();reader=source.reader();reader.original=lambda:json.dumps(dict(commandId=source.commands[-1]['commandId'],available=False))
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(1,len(source.commands));self.assertIsNone(reader.last)

    def test_current_source_cannot_replace_original_settings_writer_view_or_native_birth(self):
        for fault in ('instance','writer','settings','view','sequence'):
            source=CurrentBoundary();reader=source.reader();first=reader.read(RUN)
            def changed(value):
                if fault=='instance':value['instance']='f'*32
                elif fault=='writer':value['settings']['writerInstance']='f'*32
                elif fault=='settings':value['settings']['instance']='f'*32
                elif fault=='view':value['view']['instance']='f'*32
                else:value['sequence']=1
            source.edit=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_final_copies_and_guards_cannot_hide_age_with_either_original_clock_frozen(self):
        for fault in ('copy-host','copy-native','guard-native','clock-host'):
            source=CurrentBoundary();reader=source.reader();copied=[False]
            def copy(value):
                result=deepcopy(value)
                if type(value) is dict and value.get('chatProfileCurrentVersion')==1 and not copied[0]:
                    copied[0]=True
                    if fault=='copy-host':source.clock+=2
                    elif fault=='copy-native':source.epoch+=2000
                return result
            def guard():
                if copied[0] and fault=='guard-native':source.epoch+=2000
                return True
            def clock():
                if copied[0] and fault=='clock-host':source.clock+=2
                return source.epoch
            reader.guard=guard;reader.clock_ms=clock
            with self.subTest(fault=fault),patch('adapters.native_chat_profile_current.deepcopy',copy),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last);self.assertIsNone(reader.last_raw)

    def test_closed_read_command_rejects_saved_values_mutation_ops_and_wrong_nonce_before_send(self):
        base=dict(schemaVersion=1,commandId='a'*32,runId=RUN,action='feature-chat-profile-current')
        for edit in (dict(expected={}),dict(original={}),dict(operation='acquire'),dict(operation='restore'),dict(schemaVersion=True),dict(commandId='a'*32+'\n')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(base|edit)


if __name__=='__main__':unittest.main()
