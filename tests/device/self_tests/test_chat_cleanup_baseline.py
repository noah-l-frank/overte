"""Actual common checker/source/seal order; native/input/clock producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.cleanup_baseline import ChatCleanupBaseline
from adapters.chat_journey.source_seal import ChatSourceSeal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_cleanup_witness as seams
from self_tests.test_native_chat_observation import RUN


class ChatCleanupBaselineTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatCleanupWitnessTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.primary=self.h.observers['primary'];self.actor=self.h.publisher
        self.seals=(ChatSourceSeal(self.primary,PrivateFeatureState(self.h.root/'baseline-primary-seal.json')),
            ChatSourceSeal(self.actor,PrivateFeatureState(self.h.root/'baseline-actor-seal.json')))
        self.store=PrivateFeatureState(self.h.root/'baseline.json')
        self.owner=ChatCleanupBaseline(self.primary,self.actor,self.seals,self.store,guard=lambda:True,sleep=self.h.h.sleep)
        self.reads=[];request=self.h.h.w.actor.request
        def received(path,*args,**kwargs):
            if path=='/runs/'+RUN:
                value=self.h.h.w.journal.snapshot(RUN);self.reads.append(deepcopy(value));return value
            return request(path,*args,**kwargs)
        self.h.h.w.actor.request=received

    def refused(self):
        before=self.h.queries();value=deepcopy(self.store.read());posts=len(self.h.posts)
        with self.assertRaises(NativeUIError):self.owner.run(self.h.native.epoch)
        with self.assertRaises(NativeUIError):self.primary.read()
        with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts));self.assertEqual(value,self.store.read())

    def test_common_three_second_baseline_receives_original_actor_rows_then_seals_without_restart_or_retirement(self):
        calls=deepcopy(self.h.h.widgets.calls);value=self.owner.run(self.h.native.epoch)
        self.assertEqual('complete',value['stage']);self.assertEqual('ready',value['phase']);self.assertTrue(self.owner.completed)
        self.assertGreaterEqual(value['common']['stableSeconds'],3.0);self.assertGreaterEqual(value['common']['advancingSamples'],13)
        self.assertEqual(len(self.primary.rows),len(self.actor.rows));self.assertEqual(len(self.primary.rows),len(self.reads))
        self.assertEqual(calls,self.h.h.widgets.calls);self.assertEqual(value,self.owner.receipt(value))
        self.assertTrue(all(seal.completed and seal.previous['phase']=='sealed' for seal in self.seals))
        self.assertTrue(all(row['common']['resources']==[] and row['common']['witness']['ticket']==self.h.ticket for row in self.owner.rows))
        self.assertEqual(26,len(self.h.original.rows));self.assertTrue(self.h.original.store.path.exists());self.refused()

    def test_stale_received_journal_cannot_replace_actual_new_publisher_rows_or_be_retried(self):
        request=self.h.h.w.actor.request;old=self.h.h.w.journal.snapshot(RUN)
        self.h.h.w.actor.request=lambda path,*args,**kwargs:deepcopy(old) if path=='/runs/'+RUN else request(path,*args,**kwargs)
        with self.assertRaises(NativeUIError):self.owner.run(self.h.native.epoch)
        self.assertEqual('measuring',self.store.read()['stage']);self.assertEqual(1,len(self.h.posts))
        self.assertFalse(self.owner.completed);self.assertTrue(all(seal.failed for seal in self.seals));self.refused()

    def test_frozen_host_native_jump_after_final_complete_cas_never_qualifies_baseline_receipt(self):
        write=self.store.write
        def late(value,previous):
            write(value,previous)
            if value['stage']=='complete':self.h.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.owner.run(self.h.native.epoch)
        self.assertEqual('complete',self.store.read()['stage']);self.assertFalse(self.owner.completed)
        self.assertTrue(all(seal.failed for seal in self.seals))
        with self.assertRaises(NativeUIError):self.owner.receipt(self.store.read())
        self.refused()


if __name__=='__main__':unittest.main()
