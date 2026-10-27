"""One normal load and live Actor through the first six common Tablet steps.

Existing public actions, independent observations, DOM/PNG evidence and common
checkpoint limits execute unchanged. Native/UI producers and separate clocks
are host models. No remaining Journey or retirement is replaced by this case.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import secrets
import unittest

from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests import test_ios_tablet_web_open_admission as admission
from ios.self_tests import test_ios_tablet_web_open_checkpoint as opened
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletHistoryCheckpointTests(unittest.TestCase):
    def test_one_normal_load_live_Actor_and_common_Unicode_bridge_clear_link_Back_checkpoints(self):
        component=admission.TabletOpenAdmissionTests();self.addCleanup(component.doCleanups)
        component.run_open(self.prefix)

    def prefix(self,f,channel,ticket,barrier,baseline):
        journey=opened.TabletOpenCheckpointTests().checkpoint(f,channel,ticket,barrier,baseline)
        b=f.boundary;primary=f.primary
        def invoke(operation,values):
            if operation=='feature.tablet-web.observe':return primary.observe(values)
            self.assertEqual('feature.tablet-web.act',operation);return primary.act(values)
        journey.invoke=invoke
        scenario=SCENARIOS['tablet-web'];original=expand(scenario['baseline'],context(RUN))
        steps=scenario['steps'][1:6]
        self.assertEqual(['focus-type','submit','clear-text','navigate','back'],[step['verb'] for step in steps])
        for index,step in enumerate(steps,2):
            verb=step['verb'];inputs=expand(step['inputs'],context(RUN));ticket=secrets.token_hex(16)
            f.fixture.journal.activate(RUN,ticket,verb,inputs);barrier=b.host()
            journey.browser_transition=(step['documentTransition'],journey.samples[-1]['state']['documentLoads'])
            journey.continuity('before',verb)
            self.assertEqual(dict(performed=True),journey.call('act',dict(
                verb=verb,inputs=inputs,ticket=ticket,fixtureUrl=b.source.fixture)))
            journey.continuity('after',verb)
            expected=expand(step['state'],context(RUN))
            expected.update({key:original[key] for key in step.get('originalFields',[])})
            actual=journey.wait(f'{index:02d}-{verb}',ticket,barrier,expected,step['evidence'])
            print(f'Actual common Tablet checkpoint {index}/6 {verb} passed: '
                f'documentLoads={actual["state"]["documentLoads"]}, '
                f'bridgeEchoes={actual["state"]["bridgeEchoes"]}',flush=True)
        self.assertEqual(6,len(journey.phases))
        self.assertTrue(all(phase['advancingSamples']>=3 for phase in journey.phases))
        self.assertEqual('reference',actual['state']['page']);self.assertEqual('',actual['state']['text'])
        self.assertEqual((1,1,1),tuple(actual['state'][key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        host=b.host_app.call('read')
        self.assertEqual(1,len(host['navigations']));self.assertEqual(1,len(host['emissions']))
        requests=[row['kind'] for row in host['pageRequests']]
        self.assertEqual(1,requests.count('navigate'));self.assertEqual(1,requests.count('back'))
        self.assertEqual([],b.ui.lifecycle_inputs);self.assertEqual([],f.sdk.errors)
        self.assertFalse(any(method=='DELETE' for method,_path in f.sdk.calls))


if __name__=='__main__':unittest.main()
