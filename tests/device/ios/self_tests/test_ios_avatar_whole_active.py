"""All selected active steps through real owners, HTTPS, JS and PNG files.

Native Qt/model/AvatarMixer/Vulkan are explicitly modeled producers. No owner,
normalizer, independent fact or retirement verdict is patched or invented.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests.avatar_image_domain import ImageDomain,RUN
from ios.self_tests import test_ios_avatar_active_composed as active_fixture
from self_tests import test_account_provider as tls


class AvatarWholeActiveTests(unittest.TestCase):
    domain_type=ImageDomain
    prepare=active_fixture.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_complete_active_scenario_owns_each_original_and_actual_independent_publication(self):
        d=self.prepare();p,a=d.owners['primary'],d.owners['actor'];latest={}
        def observe():
            for role,owner in d.owners.items():
                value=owner.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=latest.get(role,{}).get('sequence',0)))
                latest[role]=value
            self.assertEqual(latest['primary']['state'],latest['actor']['state'])
            self.assertTrue(d.client.observe()['entries'])
        observe()
        for index,step in enumerate(SCENARIOS['avatar-people']['steps'],1):
            try:
                print('Avatar active step '+str(index)+'/15: '+step['verb'],flush=True)
                verb=step['verb'];inputs=expand(step['inputs'],context(RUN));ticket=f'{index:032x}'
                d.client.activate(ticket,verb,inputs)
                if verb in ('peer-accept','peer-reject'):a.consent(a.phase.read())
                query=dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=p.phase.fixture_url,verb=verb,inputs=inputs)
                self.assertEqual({'performed':True},p.act(query))
                # The Actor alone closes its genuinely cancelled original prompt.
                if verb=='connection-cancel':
                    with a.held(paired=True):
                        a.load();parts=a.components(a.source_parts());parts['surfaces']['actor'].prepare(ticket)
                observe()
                expected=expand(step['state'],context(RUN))
                for key,wanted in expected.items():
                    actual=latest['primary']['state'][key]
                    self.assertIn(actual,wanted['oneOf']) if type(wanted) is dict and 'oneOf' in wanted else self.assertEqual(wanted,actual,(index,key))
            except Exception as error:
                error.add_note('Active Avatar step '+str(index)+': '+step['verb']);raise
        self.assertEqual('original',latest['primary']['state']['avatar']);self.assertFalse(latest['primary']['state']['bookmarked'])
        self.assertFalse(d.social.snapshot(RUN)['connected'])
        for role in ('primary','actor'):self.assertEqual(1,d.natives[role].input_log.count('login.submit'))


if __name__=='__main__':unittest.main()
