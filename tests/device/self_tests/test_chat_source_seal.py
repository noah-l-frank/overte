"""Actual warm source locks/files/seals; native/input producers are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.source_seal import ChatSourceSeal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_cleanup_witness as seams


class ChatSourceSealTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatCleanupWitnessTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.publisher.publish();self.store=PrivateFeatureState(self.h.root/'actor-source-seal.json')
        self.seal=ChatSourceSeal(self.h.publisher,self.store)

    def refused(self):
        before=self.h.queries();root=deepcopy(self.store.read());publisher=deepcopy(self.h.store.read())
        with self.assertRaises(NativeUIError):self.h.publisher.publish()
        with self.assertRaises(NativeUIError):self.h.observers['actor'].read()
        with self.assertRaises(NativeUIError):self.seal.run()
        with self.assertRaises(NativeUIError):ChatSourceSeal(self.h.publisher,self.store)
        self.assertEqual(before,self.h.queries());self.assertEqual(root,self.store.read());self.assertEqual(publisher,self.h.store.read())

    def test_original_primary_and_actor_seals_freeze_complete_files_without_new_native_queries(self):
        primary=self.h.observers['primary'];primary.read();before=self.h.queries()
        primary_seal=ChatSourceSeal(primary,PrivateFeatureState(self.h.root/'primary-source-seal.json'))
        actor=self.seal.run();own=primary_seal.run()
        self.assertEqual('sealed',actor['phase']);self.assertEqual(4,len(actor['originals']));self.assertEqual(3,len(own['originals']))
        self.assertEqual(actor,self.seal.receipt(actor));self.assertEqual(own,primary_seal.receipt(own))
        self.assertEqual(before,self.h.queries());self.refused()
        with self.assertRaises(NativeUIError):primary.read()
        with self.assertRaises(NativeUIError):primary.bind_freeze(lambda:True)
        with self.assertRaises(NativeUIError):self.h.publisher.bind_freeze(lambda:True)
        self.assertEqual(before,self.h.queries())

    def test_identical_replaced_root_is_not_an_original_returned_receipt(self):
        receipt=self.seal.run();before=self.h.queries()
        source=self.h.observers['actor'].samples.script_source
        source.store.write(source.previous,source.previous)
        with self.assertRaises(NativeUIError):self.seal.receipt(receipt)
        self.assertEqual(before,self.h.queries());self.assertTrue(self.seal.completed)

    def test_final_result_copy_is_inside_frozen_host_native_freshness(self):
        from unittest.mock import patch
        def late(value):
            result=deepcopy(value)
            if type(value) is dict and value.get('phase')=='sealed':self.h.native.epoch+=2000
            return result
        clock=self.h.native.host
        with patch('adapters.chat_journey.source_seal.deepcopy',side_effect=late):
            with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual(clock,self.h.native.host);self.assertFalse(self.seal.completed);self.refused()

    def test_last_seal_stamp_read_is_before_final_original_native_clock(self):
        from pathlib import Path
        from unittest.mock import patch
        lstat=Path.lstat;fired=[];clock=self.h.native.host
        def late(path,*args,**kwargs):
            info=lstat(path,*args,**kwargs)
            if path==self.store.path and self.seal.seal_stamp is not None and not fired:
                fired.append(True);self.h.native.epoch+=2000
            return info
        with patch.object(Path,'lstat',new=late):
            with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual([True],fired);self.assertEqual(clock,self.h.native.host);self.assertFalse(self.seal.completed)
        self.refused()

    def unlock_fault(self,fail):
        observation=self.h.observers['actor'];final=observation.final;finished=[]
        def completed(*args):
            result=final(*args)
            if self.seal.seal_stamp is not None:finished.append(True)
            return result
        observation.final=completed
        original=self.h.observers['actor'].samples.locks[0].assert_held;fired=[];clock=self.h.native.host
        def late():
            original()
            if finished and not fired:
                fired.append(True)
                if fail:raise OSError('Original source lock exit failed')
                self.h.native.epoch+=2000
        self.h.observers['actor'].samples.locks[0].assert_held=late
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual([True],fired);self.assertEqual(clock,self.h.native.host);self.assertFalse(self.seal.completed)
        self.refused()

    def test_native_jump_during_source_lock_exit_cannot_complete_a_physical_seal(self):self.unlock_fault(False)

    def test_failed_source_lock_exit_cannot_complete_a_physical_seal(self):self.unlock_fault(True)

    def test_lost_final_seal_receipt_is_not_cold_adopted_or_replayed(self):
        write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='sealed':raise OSError('Original final seal CAS receipt lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual('sealed',self.store.read()['phase']);self.assertFalse(self.seal.completed)
        with self.assertRaises(NativeUIError):self.seal.receipt(self.store.read())
        self.refused()

    def test_frozen_host_native_jump_during_final_seal_cas_cannot_qualify_receipt(self):
        clock=self.h.native.host;write=self.store.write
        def late(value,previous):
            write(value,previous)
            if value['phase']=='sealed':self.h.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual(clock,self.h.native.host);self.assertFalse(self.seal.completed)
        with self.assertRaises(NativeUIError):self.seal.receipt(self.store.read())
        self.refused()

    def test_changed_original_source_root_after_intent_keeps_sealing_and_blocks_new_reads(self):
        write=self.store.write;source=self.h.observers['actor'].samples.script_source
        def changed(value,previous):
            write(value,previous)
            if value['phase']=='sealing':source.store.write({**source.previous,'revision':source.previous['revision']+1},source.previous)
        self.store.write=changed
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertEqual('sealing',self.store.read()['phase']);self.refused()

    def test_mutable_historical_rows_cannot_be_sealed_as_original_physical_payloads(self):
        self.h.publisher.rows[0]['payload']['actorSequence']=99
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertIsNone(self.store.read());self.refused()


def source_seal_positive_tests():
    return unittest.TestSuite([ChatSourceSealTests('test_original_primary_and_actor_seals_freeze_complete_files_without_new_native_queries')])


def source_seal_recovery_tests():
    return unittest.TestSuite(ChatSourceSealTests(name) for name in unittest.defaultTestLoader.getTestCaseNames(ChatSourceSealTests)
        if name!='test_original_primary_and_actor_seals_freeze_complete_files_without_new_native_queries')


def source_seal_admission_tests():
    return unittest.TestSuite(ChatSourceSealTests(name) for name in unittest.defaultTestLoader.getTestCaseNames(ChatSourceSealTests)
        if name in {'test_changed_original_source_root_after_intent_keeps_sealing_and_blocks_new_reads',
            'test_lost_final_seal_receipt_is_not_cold_adopted_or_replayed',
            'test_mutable_historical_rows_cannot_be_sealed_as_original_physical_payloads',
            'test_identical_replaced_root_is_not_an_original_returned_receipt',
            'test_failed_source_lock_exit_cannot_complete_a_physical_seal'})


def source_seal_freshness_tests():
    excluded={case._testMethodName for case in source_seal_admission_tests()}|{
        'test_original_primary_and_actor_seals_freeze_complete_files_without_new_native_queries'}
    return unittest.TestSuite(ChatSourceSealTests(name) for name in unittest.defaultTestLoader.getTestCaseNames(ChatSourceSealTests) if name not in excluded)


if __name__=='__main__':unittest.main()
