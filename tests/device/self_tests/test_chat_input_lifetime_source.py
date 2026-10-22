"""Closed optional original input resource extension; synthetic producer seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from adapters.chat_actor_files import validate_input_lifetime
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_actor_files as actor_files


class InputLifetimeSourceTests(unittest.TestCase):
    def setUp(self):
        self.s=actor_files.ActorFileTests('test_stale_original_reply_is_preserved_while_waiting_never_relabelled')
        self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.s.actor.mutate=lambda envelope:envelope.update(inputLifetime=self.value(envelope['native']))

    @staticmethod
    def value(frame):
        return dict(inputLifetimeVersion=1,commandId=frame['commandId'],runId=frame['runId'],instance='a'*32,
            ownerRunId='',sequence=0,scriptPolls=0,releaseConsumed=False,processId=frame['processId'],
            capturedEpochMs=frame['capturedEpochMs'],command=dict(present=False,node={}),
            receipt=dict(present=False,node={}),receiptHandle=dict(open=False,node={}))

    def test_exact_original_extension_retains_original_bytes_and_legacy_has_no_release_default(self):
        frame=self.s.produce();request=self.s.store.read()['request']
        value=self.s.transport.read_input_lifetime(request)
        self.assertEqual(self.value(frame),value)
        raw=self.s.transport.last_input_lifetime_raw
        self.assertEqual(value,json.loads(raw)['inputLifetime'])
        value['scriptPolls']=100;self.assertEqual(0,json.loads(raw)['inputLifetime']['scriptPolls'])
        self.s.actor.mutate=None;self.s.produce(self.s.request(nonce='e'*32))
        with self.assertRaises(NativeUIError):self.s.transport.read_input_lifetime(self.s.store.read()['request'])
        self.assertEqual(raw,self.s.transport.last_input_lifetime_raw)

    def test_closed_rows_and_native_scope_types_never_accept_false_zero_or_foreign_query(self):
        frame=self.s.produce();baseline=self.value(frame)
        def changed(key,value):
            result=deepcopy(baseline);result[key]=value;return result
        bad=[changed('inputLifetimeVersion',True),changed('processId',124),changed('sequence',True),
            changed('sequence',1),changed('ownerRunId','e'*32),changed('scriptPolls',-1),
            changed('releaseConsumed',True),changed('commandId','e'*32),changed('runId','e'*32),
            changed('capturedEpochMs',frame['capturedEpochMs']-1),changed('instance','private body'),
            changed('command',dict(present=False,node=dict(device='1',inode='2'))),
            changed('receipt',dict(present=True,node={})),changed('receiptHandle',dict(open=True,node=dict(device='1',inode='2'))),
            {**baseline,'expected':True}]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(NativeUIError):validate_input_lifetime(value,frame)

    def test_unacquired_reply_wrong_original_and_failed_final_fd_guard_retain_existing_journal(self):
        request=self.s.request();self.s.transport.send(request);self.s.actor.tick()
        with self.assertRaises(NativeUIError):self.s.transport.read_input_lifetime(request)
        self.assertIsNone(self.s.store.read()['result']);self.s.transport.read();original=self.s.store.read()
        wrong={**request,'commandId':'e'*32}
        with self.assertRaises(NativeUIError):self.s.transport.read_input_lifetime(wrong)
        released=self.s.transport.released;calls=[0]
        result_node={key:original['result']['stamp'][key] for key in ('device','inode')}
        def lost(node):
            if node==result_node:calls[0]+=1
            return True if node==result_node and calls[0]>=2 else released(node)
        self.s.transport.released=lost
        with self.assertRaises(NativeUIError):self.s.transport.read_input_lifetime(request)
        self.assertEqual(original,self.s.store.read())
        self.assertFalse(hasattr(self.s.transport,'last_input_lifetime_raw'))

    def test_copy_and_final_guards_remain_inside_both_original_clock_bounds(self):
        self.s.produce();request=self.s.store.read()['request'];original=self.s.store.read()
        for clock in ('host','native'):
            self.s.clock=0;self.s.transport.clock_ms=lambda:20000
            def slow(value):
                result=deepcopy(value)
                if type(value) is dict and 'inputLifetimeVersion' in value:
                    if clock=='host':self.s.clock+=2
                    else:self.s.transport.clock_ms=lambda:22000
                return result
            with self.subTest(clock=clock),patch('adapters.chat_actor_files.deepcopy',slow),self.assertRaises(NativeUIError):
                self.s.transport.read_input_lifetime(request)
            self.assertEqual(original,self.s.store.read())
            self.assertFalse(hasattr(self.s.transport,'last_input_lifetime_raw'))


if __name__=='__main__':unittest.main()
