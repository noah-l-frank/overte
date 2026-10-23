"""Pure original reply admission and real lock-exit/clock boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from adapters.chat_journey.source_chunks import json_digest
from adapters.pico4.snapshot_reply_grammar import SnapshotReplyGrammar,read_pins,scope,validate_reply
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner,reply_boundary
from self_tests.test_pico_snapshot_background_owner import fixture


class SnapshotReplyGrammarTests(unittest.TestCase):
    def setUp(self):
        old=fixture()[0];self.run=old['header']['runId'];self.binding=old['header']['binding'];self.rows=deepcopy(old['state']['replies'])
        self.requests={row['request']['commandId']:row['request'] for row in self.rows};pins,digest=read_pins();self.context=scope(self.run,self.binding,123,pins,digest)
        self.calls=[];self.memo=SnapshotReplyGrammar()
    def grammar(self,row):self.calls.append(row['request']['commandId']);validate_reply(row,self.requests,123)

    def test_new_replies_run_complete_original_grammar_and_only_committed_byte_equal_prefix_is_warm(self):
        first=self.rows[:2];candidate=self.memo.validate(self.context,first,self.grammar);self.assertEqual(2,len(self.calls));self.assertIsNone(self.memo.previous)
        candidate=self.memo.validate(self.context,first,self.grammar);self.assertEqual(4,len(self.calls));self.memo.commit(candidate)
        self.memo.validate(self.context,first,self.grammar);self.assertEqual(4,len(self.calls))
        candidate=self.memo.validate(self.context,self.rows[:3],self.grammar);self.assertEqual(5,len(self.calls));self.memo.commit(candidate)
        cold=SnapshotReplyGrammar();cold.validate(self.context,self.rows[:3],self.grammar);self.assertEqual(8,len(self.calls))

    def test_mutable_alias_bool_foreign_scope_and_changed_old_reply_refuse_before_any_cached_decoder(self):
        self.memo.commit(self.memo.validate(self.context,self.rows[:2],self.grammar));baseline=deepcopy(self.memo.previous)
        for fault in ('tuple','dict-subclass','scope-subclass','bool','foreign','old-reply','pin'):
            with self.subTest(fault=fault):
                memo=SnapshotReplyGrammar();memo.previous=deepcopy(baseline);memo.sha=json_digest(memo.previous)
                current=deepcopy(self.context);rows=deepcopy(self.rows[:2]);before=len(self.calls)
                if fault=='tuple':rows=tuple(rows)
                if fault=='dict-subclass':
                    class Row(dict):pass
                    rows[0]=Row(rows[0])
                if fault=='scope-subclass':
                    class Binding(dict):
                        def __getitem__(self,key):raise AssertionError('A JSON subclass must not run code')
                    current['binding']=Binding(current['binding'])
                if fault=='bool':current['binding']['generation']=False
                if fault=='foreign':current['runId']='f'*32
                if fault=='old-reply':rows[0]['raw']+=' '
                if fault=='pin':current['scriptPins']['codeUnits']+=1
                with self.assertRaises(NativeUIError):memo.validate(current,rows,self.grammar)
                self.assertEqual(before,len(self.calls));self.assertTrue(memo.failed)
        candidate=self.memo.validate(self.context,self.rows[:2],self.grammar);candidate['scope']['scriptPins']['codeUnits']+=1
        with self.assertRaises(NativeUIError):self.memo.commit(candidate)
        self.assertEqual(baseline,self.memo.previous)

    def test_copied_candidate_uncommitted_candidate_and_mutated_input_during_new_grammar_are_not_admissions(self):
        candidate=self.memo.validate(self.context,self.rows[:2],self.grammar)
        with self.assertRaises(NativeUIError):self.memo.commit(deepcopy(candidate))
        self.assertIsNone(self.memo.previous);rows=deepcopy(self.rows[:2]);memo=SnapshotReplyGrammar()
        def mutate(row):self.grammar(row);rows[0]['anchor']['nativeEpochMs']+=1
        with self.assertRaises(NativeUIError):memo.validate(self.context,rows,mutate)
        self.assertIsNone(memo.previous);self.assertTrue(memo.failed)

    def boundary(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-reply-exit-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        o=object.__new__(PicoSnapshotCancelOwner);o.run=self.run;o.binding=deepcopy(self.binding);o.reply_grammar=SnapshotReplyGrammar()
        o.reviewed=deepcopy(self.context['scriptPins']);o._reply_scope=deepcopy(self.context);o._reply_fence=None;o._reply_depth=0;o.last_clock=None
        self.host=1.;self.native_epoch=self.fixture_epoch=20000
        o.native=SimpleNamespace(pid=123,monotonic=lambda:self.host,clock_ms=lambda:self.native_epoch,guard=lambda:True)
        phase=dict(active=True,instance='actual-phase-model',createdEpochMs=1,activations=[dict(original='capture')],capturedEpochMs=20000)
        o.source=SimpleNamespace(epoch_ms=lambda:self.fixture_epoch,status=lambda previous:dict(phase,capturedEpochMs=self.fixture_epoch))
        o.lock=ScriptSourceLock(root/'script-sources.lock');o.store=PrivateFeatureState(root/'owner.json');o.disk=dict(original='retained-header')
        o.store.write(o.disk,None);o.state=dict(source=phase,replies=deepcopy(self.rows[:2]));o.anchor=(1.,20000,20000)
        self.physical=[];o.originals=SimpleNamespace(verify=lambda:self.physical.append('original-full-inventory'))
        @reply_boundary
        def operation(owner):
            with owner.lock.held():
                owner.reply_grammar.validate(owner._reply_scope,owner.state['replies'],self.grammar);owner.fence()
                return 'original-result'
        return o,operation

    def test_commit_is_after_actual_outer_exit_and_current_pins_and_original_physical_fences_are_rechecked(self):
        o,operation=self.boundary();commit=o.reply_grammar.commit;owners=[]
        def observed(candidate):owners.append(o.lock._owner);return commit(candidate)
        with patch.object(o.reply_grammar,'commit',side_effect=observed):self.assertEqual('original-result',operation(o))
        self.assertEqual([None],owners);self.assertEqual(2,len(self.physical));self.assertIsNotNone(o.reply_grammar.previous)
        with o.lock.held():operation(o)
        self.assertEqual(1,len(owners));self.assertIsNone(o.reply_grammar.pending)
        o.reply_grammar.previous['scope']['scriptPins']['sha256']='f'*64
        with self.assertRaises(NativeUIError):operation(o)

    def test_slow_memo_commit_or_native_fixture_jump_cannot_turn_a_frozen_clock_into_an_admission(self):
        for clock in ('host','native','fixture'):
            with self.subTest(clock=clock):
                o,operation=self.boundary();commit=o.reply_grammar.commit;header=o.store.path.read_bytes()
                def late(candidate):
                    commit(candidate)
                    if clock=='host':self.host+=2
                    if clock=='native':self.native_epoch+=2000
                    if clock=='fixture':self.fixture_epoch+=2000
                with patch.object(o.reply_grammar,'commit',side_effect=late),self.assertRaises(NativeUIError):operation(o)
                self.assertTrue(o.reply_grammar.failed);self.assertIsNone(o.reply_grammar.previous);self.assertEqual(header,o.store.path.read_bytes())

    def test_pending_hash_work_is_inside_the_last_original_fence_clock_check(self):
        o,operation=self.boundary();matches=o.reply_grammar.matches
        def slow(*args):
            matches(*args);self.host+=2
        with patch.object(o.reply_grammar,'matches',side_effect=slow),self.assertRaises(NativeUIError):operation(o)
        self.assertIsNone(o.reply_grammar.previous);self.assertIsNone(o.reply_grammar.pending)

    def test_real_source_lock_exit_failure_or_changed_current_pin_refuses_before_committing(self):
        o,operation=self.boundary();held=o.lock.held
        @contextmanager
        def failed():
            with held():yield
            raise NativeUIError('Explicit original outer exit failure')
        with patch.object(o.lock,'held',side_effect=failed),self.assertRaises(NativeUIError):operation(o)
        self.assertIsNone(o.reply_grammar.previous);self.assertIsNone(o.reply_grammar.pending)
        pins,digest=read_pins();pins['codeUnits']+=1
        with patch('adapters.pico4.snapshot_cancel_owner.read_pins',return_value=(pins,digest)),self.assertRaises(NativeUIError):operation(o)
        self.assertIsNone(o.reply_grammar.previous)

    @staticmethod
    def replace_header(owner):
        path=owner.store.path;raw=path.read_bytes();old=path.stat().st_ino;replacement=path.with_suffix('.replacement')
        descriptor=os.open(replacement,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
        os.replace(replacement,path)
        if path.read_bytes()!=raw or path.stat().st_ino==old:raise AssertionError('Counter requires actual same bytes/new inode')

    def test_same_bytes_new_inode_after_actual_exit_or_during_commit_never_supplies_an_admission(self):
        for turn in ('exit','commit'):
            with self.subTest(turn=turn):
                o,operation=self.boundary();raw=o.store.path.read_bytes();original=o.store.path.stat().st_ino;commit=o.reply_grammar.commit;calls=[]
                def changed(candidate):
                    calls.append('commit');commit(candidate)
                    if turn=='commit':self.replace_header(o)
                held=o.lock.held
                @contextmanager
                def exiting():
                    with held():yield
                    if turn=='exit':self.replace_header(o)
                with patch.object(o.reply_grammar,'commit',side_effect=changed),patch.object(o.lock,'held',side_effect=exiting),self.assertRaises(NativeUIError):operation(o)
                self.assertEqual(raw,o.store.path.read_bytes());self.assertNotEqual(original,o.store.path.stat().st_ino)
                self.assertEqual([] if turn=='exit' else ['commit'],calls);self.assertTrue(o.reply_grammar.failed);self.assertIsNone(o.reply_grammar.previous)

    def test_same_inode_unchanged_bytes_with_changed_original_time_metadata_refuses(self):
        o,operation=self.boundary();raw=o.store.path.read_bytes();original=o.store.path.stat();held=o.lock.held;commit=o.reply_grammar.commit
        @contextmanager
        def changed():
            with held():yield
            os.utime(o.store.path,ns=(original.st_atime_ns,original.st_mtime_ns+1))
        with patch.object(o.lock,'held',side_effect=changed),patch.object(o.reply_grammar,'commit',wraps=commit) as committed,self.assertRaises(NativeUIError):operation(o)
        self.assertEqual(raw,o.store.path.read_bytes());self.assertEqual(original.st_ino,o.store.path.stat().st_ino)
        self.assertEqual(0,committed.call_count);self.assertTrue(o.reply_grammar.failed);self.assertIsNone(o.reply_grammar.previous)


if __name__=='__main__':unittest.main()
