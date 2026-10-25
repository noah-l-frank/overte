"""Actual historical observer reuses only an unchanged full original tree."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests import test_ios_tablet_web_runtime as fixture
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from ios.self_tests.test_ios_tablet_web_sources import ROOT,RUN


class HistoricalTabletProofCacheTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletWebRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        with self.f.opened():pass
        self.commands=len(self.f.fixture.native.commands)
        self.lock=ScriptSourceLock(self.f.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.history=self.f.runtime.historical_observer('private-existing-selector',RUN,'primary',self.f.fixture.binding,self.f.fixture.setup,
            ORIGINS,self.lock,fixture_url=ROOT,monotonic=lambda:0.)
        self.original=PrivateFeatureState(self.f.root/'actual-historical-proof.json');self.original.write(dict(actual=1),None)
        self.pending=PrivateFeatureState(self.f.root/'actual-new-read-intent.json');self.calls=0
    def decoder(self,value):
        self.calls+=1;need(self.pending.read() is None)
        return dict(original=deepcopy(value),actual=self.original.read())
    def read(self):return self.history.historical_proof('private-test-original',dict(original='a'*32),self.decoder)
    def test_actual_historical_factory_preserves_read_membership_and_deepcopy_without_new_product_data(self):
        with scope(fresh=True) as first:value=self.read()
        value['actual']['actual']=9
        with scope(fresh=True) as second:again=self.read()
        self.assertEqual(first,second);self.assertIn(self.original.path,second);self.assertEqual(1,self.calls)
        self.assertEqual(dict(actual=1),again['actual']);self.assertEqual(self.commands,len(self.f.fixture.native.commands))
        with self.assertRaises(NativeUIError):self.history.observer.source.bound()
    def test_new_actual_failed_query_intent_invalidates_historical_success_and_is_never_hidden(self):
        self.read();self.pending.write(dict(status='failed',actualOriginalMissing=True),None)
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(3,self.calls);self.assertEqual(self.commands,len(self.f.fixture.native.commands))
    def test_actual_original_rewrite_reexecutes_full_historical_decoder(self):
        self.read();self.original.write(dict(actual=2),dict(actual=1))
        self.assertEqual(dict(actual=2),self.read()['actual']);self.assertEqual(2,self.calls)
        self.assertEqual(self.commands,len(self.f.fixture.native.commands))


if __name__=='__main__':unittest.main()
