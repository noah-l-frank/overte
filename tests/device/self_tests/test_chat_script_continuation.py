"""Exact warm native-reader ownership across bounded original source segments."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.script_source import ChatScriptSource
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_script_source as seams


class ChatScriptContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.boundary=seams.CompiledBoundary()
        self.original=self.boundary.owner(self.root);self.lock=self.original.lock

    def continuation(self,name='erase'):
        old=self.original
        with self.lock.held():return ChatScriptSource(old.run,old.role,old.binding,old.roots,old.scripts,
            PrivateFeatureState(self.root/(name+'.json')),self.lock,predecessor=old,monotonic=old.monotonic)

    def test_lazy_segment_freezes_original_only_after_final_before_role_read_and_keeps_actual_cursors(self):
        self.original.capture('a'*32,20000);next_source=self.continuation()
        self.original.capture('b'*32,20000);old=deepcopy(self.original.previous);old_frames=deepcopy(self.original.frames)
        next_source.capture('c'*32,20000)
        self.assertEqual(2,next_source.previous['chatScriptObservationVersion'])
        self.assertIs(self.original.roots,next_source.roots);self.assertIs(self.original.scripts,next_source.scripts)
        self.assertIs(self.original.successor,next_source);self.assertEqual(old,self.original.store.read());self.assertEqual(old_frames,self.original.frames)
        self.assertGreater(next_source.frames[0]['before']['sequence'],old_frames[-1]['after']['sequence'])
        self.assertGreater(next_source.frames[0]['scripts']['sequence'],old_frames[-1]['scripts']['sequence'])
        with self.lock.held():
            final=ChatScriptSource(next_source.run,next_source.role,next_source.binding,next_source.roots,next_source.scripts,
                PrivateFeatureState(self.root/'final.json'),self.lock,predecessor=next_source,monotonic=next_source.monotonic)
        final.capture('e'*32,20000)
        with self.lock.held(),self.assertRaises(NativeUIError):ChatScriptSource(final.run,final.role,final.binding,final.roots,final.scripts,
            PrivateFeatureState(self.root/'unbounded.json'),self.lock,predecessor=final,monotonic=final.monotonic)
        calls=len(self.boundary.roots.commands)
        with self.assertRaises(NativeUIError):self.original.capture('d'*32,20000)
        self.assertEqual(calls,len(self.boundary.roots.commands));self.assertEqual(old,self.original.store.read())

    def test_each_segment_keeps_existing_capacity_and_all_original_transactions(self):
        with patch('adapters.chat_journey.script_source.MAX_FRAMES',1):
            self.original.capture('a'*32,20000);new=self.continuation();new.capture('b'*32,20000)
            with self.assertRaises(NativeUIError):new.capture('c'*32,20000)
            self.assertEqual(1,len(self.original.frames));self.assertEqual(1,len(new.frames))
            self.assertEqual(1,len(self.original.history.identities));self.assertEqual(1,len(new.history.identities))

    def test_fresh_changed_compilation_or_birth_cannot_continue_same_original_code(self):
        for fault in ('compilation','birth'):
            if fault=='birth':self.setUp()
            self.original.capture('a'*32,20000);new=self.continuation()
            if fault=='birth':self.boundary.roots.instance='f'*32
            else:self.boundary.mutate=lambda value:value['source']['engines'][0]['compiled']['compilations'][0].update(scriptId=18)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):new.capture('b'*32,20000)
            self.assertTrue(new.failed);self.assertEqual(1,len(self.original.frames));self.assertEqual([],new.frames)
            self.assertEqual('reading',new.store.read()['phase'])

    def test_changed_retained_predecessor_or_reused_source_transaction_never_queries_again(self):
        self.original.capture('a'*32,20000);new=self.continuation();new.capture('b'*32,20000)
        calls=len(self.boundary.roots.commands);before=deepcopy(new.previous)
        with self.assertRaises(NativeUIError):new.capture('a'*32,20000)
        self.assertEqual(calls,len(self.boundary.roots.commands));self.assertEqual(before,new.store.read())
        self.setUp();self.original.capture('a'*32,20000);new=self.continuation();new.capture('b'*32,20000)
        current=self.original.store.read();self.original.store.write({**current,'revision':current['revision']+1},current)
        calls=len(self.boundary.roots.commands)
        with self.assertRaises(NativeUIError):new.capture('c'*32,20000)
        self.assertEqual(calls,len(self.boundary.roots.commands));self.assertEqual(1,len(new.frames))

    def test_slow_original_link_cas_cannot_query_under_either_frozen_clock(self):
        for clock in ('host','native'):
            if clock=='native':self.setUp()
            self.original.capture('a'*32,20000);new=self.continuation();write=new.store.write
            def slow(value,previous):
                write(value,previous)
                if clock=='host':self.boundary.roots.clock+=2
                else:self.boundary.roots.epoch+=2000
            new.store.write=slow;calls=len(self.boundary.roots.commands)
            with self.subTest(clock=clock),self.assertRaises(NativeUIError):new.capture('b'*32,20000)
            self.assertEqual(calls,len(self.boundary.roots.commands));self.assertEqual('reading',new.store.read()['phase'])
            self.assertEqual(1,len(self.original.frames));self.assertIs(new,self.original.successor)

    def test_existing_v2_root_other_readers_and_lost_link_receipt_cannot_be_adopted(self):
        self.original.capture('a'*32,20000);new=self.continuation();write=new.store.write
        def lost(value,previous):write(value,previous);raise OSError('Original continuation link landed, receipt lost')
        new.store.write=lost
        with self.assertRaises(NativeUIError):new.capture('b'*32,20000)
        self.assertEqual('reading',new.store.read()['phase']);self.assertIs(new,self.original.successor)
        with self.assertRaises(NativeUIError):self.continuation()
        roots,scripts=self.boundary.readers()
        with self.lock.held(),self.assertRaises(NativeUIError):ChatScriptSource(self.original.run,self.original.role,self.original.binding,
            roots,scripts,PrivateFeatureState(self.root/'foreign.json'),self.lock,predecessor=self.original)


if __name__=='__main__':unittest.main()
