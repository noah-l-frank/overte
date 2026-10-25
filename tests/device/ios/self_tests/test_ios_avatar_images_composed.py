"""Genuine owners and nine-fact normalization at modeled native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from ios.self_tests.avatar_image_domain import ImageDomain,RUN
from ios.self_tests.test_ios_avatar_active_composed import AvatarActiveComposedTests
from self_tests import test_account_provider as tls


class AvatarImagesComposedTests(unittest.TestCase):
    domain_type=ImageDomain
    prepare=AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_both_roles_original_baseline_requires_actual_png_received_peer_and_fresh_https_tables(self):
        d=self.prepare();results={}
        for role,owner in d.owners.items():
            results[role]=owner.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            self.assertEqual('original',results[role]['state']['avatar']);self.assertEqual('none',results[role]['state']['connection'])
            self.assertTrue(results[role]['artifacts']);self.assertTrue(d.http_events['primary']);self.assertTrue(d.http_events['actor'])
        self.assertEqual(results['primary']['state'],results['actor']['state'])
        self.assertTrue(d.client.observe()['entries'])


if __name__=='__main__':unittest.main()
