"""Original native closure precedes real host metadata retirement and recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_retirement import IOSEmoteRetirement,Frozen
from ios.self_tests import test_ios_emote_retirement as retirement_fixture
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase


class FinalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture=retirement_fixture.RetirementTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.ref=f.owner().retain(f.original);self.store=PrivateFeatureState(f.root/('emote-finalization-'+RUN+'-primary.json'))
        self.paths=[f.sources.store,f.scope.store,f.entities.store,f.store];self.checks=0
        self.status=phase(3,95000);self.status.update(active=False,retiredEpochMs=94900)
    def validate(self,copies):
        self.checks+=1;f=self.fixture;value=copies[str(f.store.path)]
        old=f.owner();owner=IOSEmoteRetirement(Frozen(f.store.path,value),f.root,BINDING,BINDING,RUN,'primary',f.scope.fixture_url,'3'*32,
            f.lock,f.lock,old.policy,old.paths,lambda:True)
        owner.derive(self.ref);return True
    def owner(self,validate=None):
        f=self.fixture;return IOSEmoteFinalArchive(self.store,f.root,BINDING,RUN,'primary',f.lock,f.lock,self.paths,lambda:True,validate or self.validate)
    def test_actual_archived_native_closure_survives_retired_fixed_metadata(self):
        owner=self.owner();owner.begin(self.status);self.assertEqual({'performed':True},owner.retire())
        self.assertTrue(all(path.read() is None for path in self.paths));self.assertGreater(self.checks,4)
        self.assertEqual({'performed':True},self.owner().retire());self.assertEqual('complete',self.owner().state['phase'])
        self.assertTrue(any(self.fixture.root.glob('emote-frame-*')))
    def test_native_original_failure_or_active_phase_never_authorizes_metadata_deletion(self):
        owner=self.owner();active=deepcopy(self.status);active.update(active=True,retiredEpochMs=None)
        with self.assertRaises(NativeUIError):owner.begin(active)
        def failed(_copies):raise NativeUIError('Actual original native closure is incomplete')
        owner=self.owner(failed);owner.begin(self.status)
        with self.assertRaises(NativeUIError):owner.retire()
        self.assertTrue(all(path.read() is not None for path in self.paths));self.assertEqual('freezing',owner.state['phase'])
    def test_lost_actual_discard_return_resumes_from_retained_exact_copies(self):
        owner=self.owner();owner.begin(self.status);discard=PrivateFeatureState.discard;lost=[]
        def once(store,previous):
            discard(store,previous)
            if store.path==self.paths[0].path and not lost:lost.append(True);raise OSError('Lost actual host discard return')
        with patch.object(PrivateFeatureState,'discard',once),self.assertRaises(OSError):owner.retire()
        self.assertIsNone(self.paths[0].read());self.assertEqual({'performed':True},self.owner().retire())
        self.assertTrue(all(path.read() is None for path in self.paths))
    def test_replaced_runtime_metadata_or_archived_copy_is_never_deleted(self):
        owner=self.owner();owner.begin(self.status);owner.freeze();old=self.paths[0].read();self.paths[0].write(dict(unrelated='new-owner'),old)
        with self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual(dict(unrelated='new-owner'),self.paths[0].read())
        raw=owner.record_store(1).read();owner.record_store(1).write(dict(raw,binding=dict(BINDING,processIdentity='32')),raw)
        with self.assertRaises(NativeUIError):self.owner()


if __name__=='__main__':unittest.main()
