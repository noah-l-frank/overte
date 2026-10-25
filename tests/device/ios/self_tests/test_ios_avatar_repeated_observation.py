"""Repeated stable-window reads retain the actual preceding activation image."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests.avatar_image_domain import ImageDomain,RUN
from ios.self_tests import test_ios_avatar_active_composed as active_fixture
from self_tests import test_account_provider as tls


class AvatarRepeatedObservationTests(unittest.TestCase):
    domain_type=ImageDomain
    prepare=active_fixture.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def test_two_scale_observations_compare_the_same_original_preceding_activation(self):
        d=self.prepare();p=d.owners['primary'];last={}
        def observe():
            for role,owner in d.owners.items():
                last[role]=owner.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=last.get(role,{}).get('sequence',0)))
        observe()
        for index,step in enumerate(SCENARIOS['avatar-people']['steps'][:3],1):
            ticket=f'{index:032x}';inputs=expand(step['inputs'],context(RUN));d.client.activate(ticket,step['verb'],inputs)
            self.assertEqual({'performed':True},p.act(dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=p.phase.fixture_url,verb=step['verb'],inputs=inputs)))
            observe()
        self.assertEqual('avatar-scale',step['verb']);before={role:value['sequence'] for role,value in last.items()}
        observe()
        for role,owner in d.owners.items():
            self.assertEqual(before[role]+1,last[role]['sequence'])
            with owner.held(paired=True):
                owner.load();observer=owner.components(owner.source_parts())['observer']
                first,current=[observer.read_record(row)['facts'] for row in observer.state['rows'][-2:]]
                self.assertEqual(first['ticket'],current['ticket']);self.assertEqual(first['imageBefore'],current['imageBefore'])
                self.assertEqual(f'{2:032x}',current['imageBefore']['ticket'])
                self.assertNotEqual(first['image'],current['image'])


if __name__=='__main__':unittest.main()
