"""Durable original source reads; native/world/geometry remain explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.assets_model_fixture import Fixture


class AssetsModelSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary;self.owner=self.f.owned_existing_source();self.owner.select();self.o=self.f.sources(self.owner);self.o.reserve()

    def capture(self):return self.o.capture(self.o.epoch_ms())

    def test_exact_raw_queries_join_actual_native_clocks_and_preserve_host_offset(self):
        frame=self.capture();join=frame['clockJoin'];self.assertEqual(5000,join['hostBeforeEpochMs']-join['nativeBefore']['capturedEpochMs'])
        self.assertEqual(3,len([row for row in frame['queries'] if row['kind']!='clock']));self.assertEqual(len(frame['queries']),len(frame['rawRefs']))
        for reference in frame['rawRefs']:
            record=self.o.raws.read_record(reference);self.assertEqual('native',record['kind']);self.assertIsInstance(record['raw'],str)
        before=deepcopy(self.b.inputs);clocks=deepcopy(self.b.native_clock.commands);restored=self.f.sources(self.owner)
        self.assertEqual(frame,restored._cached[0]);self.assertEqual(before,self.b.inputs);self.assertEqual(clocks,self.b.native_clock.commands)
        self.assertEqual([],frame['originals']['createAfter']['source']['entities'])

    def test_saved_frame_before_parent_adoption_replays_without_new_native_queries(self):
        intent=self.o.originals.intent;failed=[False]
        def crash(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='saved' and not failed[0]:failed[0]=True;raise RuntimeError('modeled lost source frame adoption')
            return result
        self.o.originals.intent=crash
        with self.assertRaises(RuntimeError):self.capture()
        clocks=deepcopy(self.b.native_clock.commands);restored=self.f.sources(self.owner);frame=restored.recover_capture()
        self.assertEqual(clocks,self.b.native_clock.commands);self.assertEqual(frame,restored._cached[0])

    def test_interrupted_native_raw_prefix_is_owned_without_requery_or_fresh_frame(self):
        intent=self.o.raws.store.intent
        def crash(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('modeled interrupted raw writer')
            return result
        self.o.raws.store.intent=crash
        with self.assertRaises(NativeUIError):self.capture()
        self.assertFalse(self.o._cached);clocks=deepcopy(self.b.native_clock.commands);restored=self.f.sources(self.owner)
        with self.assertRaises(NativeUIError):restored.capture(restored.epoch_ms())
        with self.assertRaises(NativeUIError):restored.recover_capture()
        self.assertEqual(clocks,self.b.native_clock.commands);self.assertEqual(0,restored.raws.pending['snapshot']['bytes'])

    def test_failed_source_read_retains_raw_receipt_then_new_read_has_a_new_bracket(self):
        send=self.o.readers['work'].send
        def lost(query):send(query);raise NativeUIError('modeled lost readonly work transport')
        self.o.readers['work'].send=lost
        # Earlier raw originals survive, while this query has no observed raw
        # result. A later complete acquisition uses new query IDs and clocks.
        with self.assertRaises(NativeUIError):self.capture()
        self.assertTrue(self.o.raws.refs);self.assertFalse(self.o._cached);self.o.freeze_interrupted();self.o.readers['work'].send=send
        frame=self.capture();self.assertEqual(1,len(self.o.state['interrupted']));self.assertEqual(1,len(self.o.state['frames']));self.assertGreater(frame['clockJoin']['nativeBefore']['sequence'],1)


if __name__=='__main__':unittest.main()
