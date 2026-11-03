"""Actual host locks/WAL and original API budget, explicit preparation model.

Only the preparation producer is modeled. This exercises the real new Primary
coordination helper and existing25s Budget/5s OS lock; no native/Avatar result
or complete login/Source/journey qualification is inferred from these models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile,threading,time,unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_api_entry import operation
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending


class PreparationModel(IOSAvatarFeature):
    def __init__(self,root):
        self.role='primary';self.monotonic=time.monotonic;self.sleep=time.sleep
        self.local=ScriptSourceLock(root/'primary.lock');self.peer=ScriptSourceLock(root/'actor.lock')
        self.store=PrivateFeatureState(root/'preparation-model.json');self.calls=0;self.inputs=0;self.pending=False;self.fault=None
    def prepare(self):
        self.calls+=1
        with self.local.held(),self.peer.held():
            if self.fault is not None:raise self.fault
            saved=self.store.read()
            if saved is None:
                # Explicit once-issued modeled input, not a product fact.
                saved=dict(modelPreparationVersion=1,phase='issued',inputOrdinal=1)
                self.store.write(saved,None);self.inputs+=1
                if self.pending:raise AvatarFeaturePending('Modeled original input is awaiting an independent effect')
            if self.pending:raise AvatarFeaturePending('Same modeled original effect remains pending')
            value=dict(saved,phase='complete');self.store.write(value,saved);return value
    @operation
    def call(self):return self.prepare_for_call()


class AvatarPrimaryPreparationCoordinationTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name);self.root.chmod(0o700);self.model=PreparationModel(self.root)
    def test_actual_peer_lock_busy_for_more_than5_seconds_progresses_inside_same25_second_api(self):
        m=self.model;entered=threading.Event();errors=[]
        def work():
            try:
                with ScriptSourceLock(m.peer.path).held():entered.set();time.sleep(6)
            except BaseException as error:errors.append(error);entered.set()
        thread=threading.Thread(target=work,name='avatar-model-original-peer-preparation')
        self.addCleanup(lambda:thread.join(timeout=3));thread.start();self.assertTrue(entered.wait(3))
        if errors:raise errors[0]
        checks=[]
        def sleep(seconds):
            # The failed paired acquisition must have released Primary's lock
            # before allowing the independent role to finish its own input.
            with ScriptSourceLock(m.local.path,timeout=.01).held():checks.append(True)
            time.sleep(seconds)
        m.sleep=sleep;started=time.monotonic();value=m.call();elapsed=time.monotonic()-started
        thread.join(timeout=3);self.assertFalse(thread.is_alive())
        if errors:raise errors[0]
        self.assertGreaterEqual(elapsed,5);self.assertLess(elapsed,25);self.assertTrue(checks)
        self.assertGreaterEqual(m.calls,2);self.assertEqual(1,m.inputs);self.assertEqual('complete',value['phase'])
    def test_pending_after_durable_once_input_releases_both_locks_and_resumes_same_wal(self):
        m=self.model;m.pending=True;original=time.sleep;waited=[]
        def sleep(seconds):
            with ScriptSourceLock(m.local.path,timeout=.01).held(),ScriptSourceLock(m.peer.path,timeout=.01).held():
                self.assertEqual('issued',m.store.read()['phase']);self.assertEqual(1,m.inputs);waited.append(True)
            m.pending=False;original(seconds)
        m.sleep=sleep;self.assertEqual('complete',m.call()['phase'])
        self.assertEqual([True],waited);self.assertEqual(2,m.calls);self.assertEqual(1,m.inputs)
    def test_permanent_typed_pending_cannot_renew_original25_second_budget_or_repeat_input(self):
        m=self.model;clock=[100.0];m.monotonic=lambda:clock[0];m.pending=True
        def sleep(_seconds):clock[0]+=1
        m.sleep=sleep
        with self.assertRaises(NativeUIError):m.call()
        self.assertEqual(125.0,clock[0]);self.assertEqual(25,m.calls);self.assertEqual(1,m.inputs)
        self.assertEqual('issued',m.store.read()['phase'])
    def test_foreign_source_and_clock_errors_are_never_retried_or_converted_to_pending(self):
        m=self.model;waited=[];m.sleep=lambda seconds:waited.append(seconds)
        for error in (NativeUIError('Declared foreign source refusal'),ValueError('Declared native clock refusal')):
            before=m.calls;m.fault=error
            with self.subTest(kind=type(error).__name__),self.assertRaises(type(error)) as caught:m.call()
            self.assertIs(error,caught.exception);self.assertEqual(before+1,m.calls)
            self.assertFalse(waited);self.assertEqual(0,m.inputs);self.assertIsNone(m.store.read())
    def test_actor_keeps_original_single_attempt_pending_path_for_its_existing_worker_loop(self):
        m=self.model;m.role='actor';m.pending=True;waited=[];m.sleep=lambda seconds:waited.append(seconds)
        with self.assertRaises(AvatarFeaturePending):m.call()
        self.assertEqual(1,m.calls);self.assertEqual(1,m.inputs);self.assertFalse(waited)


if __name__=='__main__':unittest.main()
