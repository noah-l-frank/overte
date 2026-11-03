"""Real Runtime source acquisition clocks versus deliberately foreign origin.

Native clocks and existing validators remain unchanged. The host policy is
selected BEFORE constructing either native producers or observation owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_sources import CHANNELS
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor,NativeCanonicalTerminalDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class ForeignHostMonotonicDomain(NativeCanonicalTerminalDomain):
    def host_monotonic(self):return self.clock[0]


class ForeignHostMonotonicFrontdoor(NativeInstalledFrontdoor):
    domain_type=ForeignHostMonotonicDomain


class AvatarExplicitHostMonotonicTests(preparation.AvatarPrepareComposedTests):
    def source(self,kind):
        frontdoor=kind(self);d=frontdoor.domain;frontdoor.set_configuration(frontdoor.configuration(8))
        declared=d.owners['primary'];runtime=IOSAvatarRuntime(frontdoor.adapter)
        # FinalDomain's genuine logged-out producer emits the null UUID. The
        # normal whole-source reader deliberately rejects that postlogout
        # shape. Complete actual ordinary account preparation before this
        # active-source prerequisite; never set loggedIn/session fields.
        owner=IOSAvatarFeature(runtime,'primary',d.client,RUN,'primary',
            dict(artifactRoot=str(declared.root),imagePolicy=declared.policy,actorTarget='actor'))
        with owner.held(paired=True):owner.initialize()
        with owner.held():owner.login()
        self.assertTrue(d.natives['primary'].account['loggedIn'])
        self.assertEqual(1,d.natives['primary'].input_log.count('login.submit'))
        self._authenticated_inputs=list(d.natives['primary'].input_log)
        return d,owner,runtime

    def test_real_runtime_six_channel_acquisitions_share_whole_host_origin_with_native_clocks_distinct(self):
        d,owner,runtime=self.source(NativeInstalledFrontdoor)
        with owner.held():
            source=runtime._avatar_sources('primary',d.client,RUN,'primary',owner.root,owner.lock)
            value=source.read();clock=value['clockJoin']
            for name in CHANNELS:
                acquisition=value['acquisitions'][name]
                self.assertLessEqual(clock['hostBeforeMonotonic'],acquisition['hostBeforeMonotonic'])
                self.assertLessEqual(acquisition['hostBeforeMonotonic'],acquisition['hostAfterMonotonic'])
                self.assertLessEqual(acquisition['hostAfterMonotonic'],clock['hostAfterMonotonic'])
                self.assertEqual(digest(value['originals'][name]),acquisition['originalSha256'])
            self.assertGreater(clock['nativeBefore']['capturedEpochMs']-clock['hostBeforeEpochMs'],86000000)
            self.assertEqual(value,source.frames[-1]);self.assertEqual(1,source.state['revision'])
            self.assertIsNone(source.state['pending'])
        self.assertEqual(self._authenticated_inputs,d.natives['primary'].input_log)

    def test_original_whole_validator_refuses_different_host_origin_with_native_brackets_and_hashes_valid(self):
        d,owner,runtime=self.source(ForeignHostMonotonicFrontdoor)
        with owner.held():
            source=runtime._avatar_sources('primary',d.client,RUN,'primary',owner.root,owner.lock)
            with self.assertRaises(NativeUIError):source.read()
            self.assertEqual('reading',source.state['phase']);self.assertEqual(0,source.state['revision'])
            partial=source.state['pending']['partial'];clock=partial['clockJoin']
            first,last=clock['nativeBefore']['capturedEpochMs'],clock['nativeAfter']['capturedEpochMs']
            for name in CHANNELS:
                packet=partial[name]['original'];acquisition=partial[name]['acquisition']
                self.assertEqual(digest(packet),acquisition['originalSha256'])
                self.assertLessEqual(first,acquisition['nativeRequestedEpochMs'])
                self.assertLessEqual(acquisition['nativeRequestedEpochMs'],packet['clockBefore']['epochMs'])
                self.assertLessEqual(packet['clockAfter']['epochMs'],acquisition['nativeAfterEpochMs'])
                self.assertLessEqual(acquisition['nativeAfterEpochMs'],last)
                self.assertFalse(clock['hostBeforeMonotonic']<=acquisition['hostBeforeMonotonic']<=clock['hostAfterMonotonic'])
                self.assertFalse(acquisition['hostBeforeMonotonic']<=acquisition['hostAfterMonotonic']<=clock['hostAfterMonotonic'])
        self.assertEqual(self._authenticated_inputs,d.natives['primary'].input_log)


if __name__=='__main__':unittest.main()
