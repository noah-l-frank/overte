"""Native/host clock counterexamples on original synthetic SDK source packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary


class NativeClockJoinTests(unittest.TestCase):
    def source(self):
        native=Boundary();clocks=[1000000.,10.]
        def advance(value):
            epoch=20000+round((clocks[1]-10)*1000)
            value.update(capturedEpochMs=epoch,requestedEpochMs=epoch)
            value['animationFence']['requestedEpochMs']=epoch
        native.mutate=advance
        reader=native.reader(ios=True)
        window=NativeClockAcquisition(reader,epoch_ms=lambda:clocks[0],monotonic=lambda:clocks[1])
        window.begin(999999)
        clocks[0]+=100;clocks[1]+=.1
        original={'execution':dict(capturedEpochMs=20050,processId=123,original='unchanged')}
        return native,clocks,window,original

    def test_separate_clock_domains_keep_original_native_packets_and_host_acquisition(self):
        source,clocks,window,original=self.source()
        record=window.finish(original,[('execution','capturedEpochMs')])
        self.assertEqual(1000000,record['hostBeforeEpochMs']);self.assertEqual(20000,record['nativeBefore']['capturedEpochMs'])
        self.assertEqual(20050,original['execution']['capturedEpochMs']);self.assertEqual(20100,record['nativeAfter']['capturedEpochMs'])
        self.assertEqual(record,validate_join(record,original))
        self.assertEqual(2,len(source.commands))
        with self.assertRaises(NativeUIError):window.finish(original,[('execution','capturedEpochMs')])

    def test_old_original_cannot_be_relabelled_by_new_envelope_or_requested_clock(self):
        _source,_clocks,window,original=self.source();original['execution']['capturedEpochMs']=19999
        with self.assertRaises(NativeUIError):window.finish(original,[('execution','capturedEpochMs')])

    def test_foreign_pid_instance_reused_source_sequence_and_nonce_fail(self):
        for change in ({'processId':124},{'instance':'e'*32},{'sequence':1}):
            source,_clocks,window,original=self.source();previous=source.mutate
            source.mutate=lambda v: (previous(v),v.update(change))
            with self.assertRaises((NativeUIError,ValueError)):window.finish(original,[('execution','capturedEpochMs')])

    def test_host_deadline_clock_regression_and_jump_cannot_extend_native_freshness(self):
        for host,mono in ((999999.,10.1),(1002000.,12.),(1001400.,10.1),(1000100.,9.)):
            _source,clocks,window,original=self.source();clocks[:]=[host,mono]
            with self.assertRaises((NativeUIError,ValueError)):window.finish(original,[('execution','capturedEpochMs')])

    def test_original_mutation_and_removed_or_duplicate_source_clock_fail_replay(self):
        _source,_clocks,window,original=self.source()
        record=window.finish(original,[('execution','capturedEpochMs')])
        changed=deepcopy(original);changed['execution']['original']='rewritten'
        with self.assertRaises(NativeUIError):validate_join(record,changed)
        for times in ([],record['sourceTimes']*2):
            with self.assertRaises(NativeUIError):validate_join(dict(record,sourceTimes=times),original)


if __name__=='__main__':unittest.main()
