"""Public Unicode/Send inputs, actual Node callback and independent Actor facts.

Actual host SDK/HTTP/JS/files execute; native clocks/producers remain explicit
models. Previous normal file selection is the prepared boundary of this case.
This does not qualify the complete journey or terminal retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.fixtures import context
from ios.self_tests.tablet_web_prepared_paired import PreparedTabletPair
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletPairedBridgeTests(unittest.TestCase):
    def test_public_unicode_and_Send_have_independent_actual_native_call_DOM_and_VM_originals(self):
        pair=PreparedTabletPair(self);fixture=pair.fixture;b=pair.b;text=context(RUN)['unicode']
        for ticket,verb,inputs,check in (
            ('c'*32,'focus-type',dict(text=text),lambda facts:facts['text']==text),
            ('d'*32,'submit',{},lambda facts:facts['bridgeEchoes']==1 and facts['bridgeMessages']==1 and facts['attemptedMessages']==1)):
            fixture.fixture.journal.activate(RUN,ticket,verb,inputs)
            call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb=verb,inputs=inputs)
            self.assertEqual(dict(performed=True),fixture.primary.act(call))
            own=fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));self.assertTrue(check(own['state']))
            actor=pair.wait(ticket,check);self.assertEqual(own['state']['bridgeEchoes'],actor['facts']['bridgeEchoes'])
        actual=b.host_app.call('read');self.assertEqual(1,len(actual['emissions']))
        self.assertTrue(any(row['caller']['manager']['instance']==b.manager['instance'] for row in b.template['emitter']['calls']))
        self.assertEqual([],fixture.sdk.errors);self.assertEqual([],b.ui.lifecycle_inputs)


if __name__=='__main__':unittest.main()
