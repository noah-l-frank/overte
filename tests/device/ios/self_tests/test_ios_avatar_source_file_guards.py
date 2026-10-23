"""Immutable source-file reads keep locks and outer candidate continuity.

These are real private files and source histories with native producers
modeled. File reads must not repeatedly acquire live SDK evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_originals import IOSAvatarOriginals
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests import test_ios_avatar_sources as fixture


class AvatarSourceFileGuardTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarSourcesTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        with self.f.lock.held():
            self.original=self.f.owner()
            for _ in range(3):self.original.read()
        self.counts=deepcopy(self.f.fixture.sources);self.sequence=self.f.fixture.core.sequence
    def construct(self,guard,*,historical=False):
        f=self.f
        return IOSAvatarSources(self.original.store,f.artifacts,fixture.BINDING,f.fixture.run,'primary',f.lock,guard,
            None if historical else f.fixture.phase,readers=None if historical else f.fixture.readers(),historical=historical,
            monotonic=lambda:f.fixture.clock,epoch_ms=f.fixture.host)
    def no_queries(self):
        self.assertEqual(self.counts,self.f.fixture.sources);self.assertEqual(self.sequence,self.f.fixture.core.sequence)
    def test_live_reconstruction_checks_candidate_at_both_edges_without_sdk_queries_for_each_file(self):
        calls=[]
        def candidate():calls.append(True);return True
        with self.f.lock.held():actual=self.construct(candidate)
        self.assertEqual(self.original.frames,actual.frames);self.assertEqual(2,len(calls));self.no_queries()
    def test_candidate_switch_during_actual_old_original_read_refuses_reconstruction_before_any_query(self):
        valid=[True];read=IOSAvatarOriginals.read;visited=[];failure=None
        def changed(owner,reference):
            value=read(owner,reference);visited.append(True);valid[0]=False;return value
        with self.f.lock.held(),patch.object(IOSAvatarOriginals,'read',changed):
            try:self.construct(lambda:valid[0])
            except NativeUIError as error:failure=error
        self.assertTrue(visited);self.assertIsNotNone(failure);self.no_queries()
    def test_explicit_historical_reconstruction_never_calls_a_forbidden_live_sdk_guard(self):
        def forbidden():raise AssertionError('Historical file reads must stay SDK-free')
        with self.f.lock.held():actual=self.construct(forbidden,historical=True)
        self.assertEqual(self.original.frames,actual.frames);self.no_queries()


if __name__=='__main__':unittest.main()
