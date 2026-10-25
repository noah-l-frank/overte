"""Sample2 changed-image facts retain their explicit Scope2 reader.

Native/Qt/GPU and marker admission are modeled, as in the independent Facts1
fixture. Source/peer/provider/PNG files and every facts predicate remain real.
The new producer classes are selected before their first original is written.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_held_samples import IOSAvatarHeldSamples
from ios.self_tests import test_ios_avatar_facts as facts_fixture
from ios.self_tests import test_ios_avatar_samples as samples_fixture


def held_samples_fixture():
    # Keep the reusable boundary local so unittest discovery does not execute
    # the inherited legacy test methods with the intentionally new writer.
    class HeldSamplesFixture(samples_fixture.AvatarSamplesTests):
        def setUp(self):
            super().setUp()
            scope=object.__new__(IOSAvatarHeldMarkerScope);scope.__dict__.update(self.scope.__dict__);self.scope=scope
            admission=patch.object(IOSAvatarHeldMarkerScope,'archive',return_value=scope);admission.start();self.addCleanup(admission.stop)
        def owner(self):
            return IOSAvatarHeldSamples(self.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
                monotonic=lambda:self.gpu.clock,epoch_ms=lambda:samples_fixture.HOST+self.gpu.clock*1000,sleep=self.gpu.sleep)
    return HeldSamplesFixture


class AvatarHeldFactsTests(unittest.TestCase):
    def setUp(self):
        for seam in (patch.object(samples_fixture,'AvatarSamplesTests',held_samples_fixture()),patch.object(facts_fixture,'IOSAvatarSamples',IOSAvatarHeldSamples)):
            seam.start();self.addCleanup(seam.stop)
        self.f=facts_fixture.AvatarFactsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_owned_wearable_changed_pixels_use_actual_new_sample_owner_without_legacy_scope_reader(self):
        facts,original=self.f.wearable_proof(image_present=True)
        self.assertEqual(2,facts.samples.VERSION);self.assertIs(facts.samples.Marker,IOSAvatarHeldMarkerScope)
        with patch.object(samples_fixture.IOSAvatarMarkerScope,'archive',side_effect=AssertionError('Sample2 cannot enter the Scope1 reader')):
            proof=facts.derive(original)
        self.assertTrue(proof['public']['state']['wearable']);self.assertGreater(proof['originals']['changed']['subjectChangedFraction'],.5)
    def test_missing_owned_wearable_in_new_actual_image_still_refuses_old_source_and_peer_presence(self):
        facts,original=self.f.wearable_proof(image_present=False)
        with self.assertRaises(NativeUIError):facts.derive(original)


if __name__=='__main__':unittest.main()
