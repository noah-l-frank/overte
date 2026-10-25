"""Public anchor/Back with both independently owned source and WDA images.

The preselected actual bundle is an explicit setup boundary. HTTP, selected JS,
host processes, private files and SDK routes execute; native views are models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import time
from ios.self_tests.tablet_web_prepared_paired import PreparedTabletPair
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletPairedNavigationTests(unittest.TestCase):
    def test_public_anchor_and_Back_keep_original_history_and_each_role_actual_screen_authority(self):
        with PreparedTabletPair(self) as pair:
            fixture=pair.fixture;b=pair.b
            initial=list(b.template['ledger']['events']);navigation=list(b.template['sources']['navigations'])
            for ticket,verb,inputs,page,loads in (
                    ('c'*32,'navigate',dict(resource='page-b.html'),'B',2),('d'*32,'back',{},'reference',3)):
                fixture.fixture.journal.activate(RUN,ticket,verb,inputs)
                started=time.monotonic()
                call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb=verb,inputs=inputs)
                self.assertEqual(dict(performed=True),fixture.primary.act(call))
                print('Actual public '+verb+' input '+str(round(time.monotonic()-started,3))+' seconds',flush=True)
                own=fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
                self.assertEqual((page,loads),(own['state']['page'],own['state']['documentLoads']));self.assertTrue(own['artifacts'])
                actor=pair.wait(ticket,lambda facts:facts['page']==page and facts['documentLoads']==loads)
                print('Actual public '+verb+' paired originals '+str(round(time.monotonic()-started,3))+' seconds',flush=True)
                self.assertEqual(loads,actor['facts']['documentLoads'])
                self.assertEqual(initial,b.template['ledger']['events'][:len(initial)]);self.assertEqual(navigation,b.template['sources']['navigations'])
            self.assertEqual([],fixture.sdk.errors)


if __name__=='__main__':unittest.main()
