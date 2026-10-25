"""Public once-only background/resume with independent process observations.

The selected-file load is the explicit PreparedTabletPair precondition. Real
adapter calls, SDK HTTP, Node app, original screen files and independent Actor
execute; native/OS views and separate boundary clocks remain host models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.self_tests.tablet_web_prepared_paired import PreparedTabletPair
from ios.self_tests.tablet_web_lifecycle_fixture import LifecyclePairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletPairedBackgroundTests(unittest.TestCase):
    def test_public_background_resume_retains_page_PID_original_graph_and_independent_actual_screen(self):
        with PreparedTabletPair(self,fixture_factory=LifecyclePairedTabletFixture) as pair:
            f,b=pair.fixture,pair.b
            ticket='c'*32;before=list(b.template['sources']['navigations']);page=b.page_identity
            f.fixture.journal.activate(RUN,ticket,'background-resume',{})
            call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb='background-resume',inputs={})
            self.assertEqual(dict(performed=True),f.primary.act(call))
            own=f.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
            self.assertTrue(own['state']['open']);self.assertEqual('reference',own['state']['page']);self.assertTrue(own['artifacts'])
            peer=pair.wait(ticket,lambda facts:facts['open'] and facts['page']=='reference')
            self.assertTrue(peer['facts']['open']);self.assertEqual(before,b.template['sources']['navigations'])
            self.assertEqual(page['source'],b.page_identity['source']);self.assertGreater(b.page_identity['creation'],page['creation'])
            self.assertNotEqual(page['nonce'],b.page_identity['nonce']);self.assertEqual(2,own['state']['documentLoads'])
            self.assertEqual(dict(backgrounds=1,activations=2,launches=1),f.lifecycle.counts)
            self.assertEqual(1,sum(operation=='mobile: backgroundApp' for operation,_ in f.lifecycle.calls))
            self.assertEqual(1,sum(operation=='mobile: activateApp' for operation,_ in f.lifecycle.calls));self.assertEqual([],f.sdk.errors)


if __name__=='__main__':unittest.main()
