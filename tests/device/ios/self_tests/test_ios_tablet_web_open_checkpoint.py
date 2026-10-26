"""First unchanged common Tablet Open checkpoint, no complete-area claim.

Normal UI selection and live independent app custody precede every page
sample. Original DOM/PNG and actor publication paths execute; native/UI and
their separate boundary clocks remain explicit host models. No retirement or
remaining Journey step is substituted by this bounded checkpoint.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests import test_ios_tablet_web_open_admission as admission
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletOpenCheckpointTests(unittest.TestCase):
    def test_normal_Open_first_common_DOM_PNG_and_independent_Actor_checkpoint(self):
        component=admission.TabletOpenAdmissionTests();self.addCleanup(component.doCleanups)
        component.run_open(self.checkpoint)

    def checkpoint(self,f,channel,ticket,barrier,baseline):
        b=f.boundary;primary=f.primary;actor_calls=[]
        def invoke(operation,values):
            self.assertEqual('feature.tablet-web.observe',operation);return primary.observe(values)
        def witness():
            channel.send('retain-current');self.assertTrue(channel.poll(60),'Own Actor page publication did not return')
            actual=channel.recv();self.assertNotIn('error',actual,actual.get('traceback'))
            if actual['publication'] is None:
                self.assertIn(actual.get('pending'),('ScriptSourceBusy','PhasePending','TabletObservationPending',
                    'TabletSourcePhaseChanged','PublicationPending'))
            else:self.assertIs(type(actual['publication']),int);actor_calls.append(actual['publication'])
            return f.controller.request('/runs/'+RUN)
        def continuity(_stage,_verb):
            runtime=primary.runtime;client,session,state,target,_scope=runtime._existing(primary.selector)
            actual=runtime.adapter._binding(primary.selector,client,session,state,target).continuity()
            self.assertEqual(int(b.binding['processIdentity']),actual['pid'])
        def forbidden(*_args,**_kwargs):self.fail('One existing Open checkpoint must not activate, retire or report a whole Journey')
        journey=Journey('tablet-web',RUN,b.source.fixture,invoke=invoke,witness=witness,activate=forbidden,
            read_artifact=lambda name:read_private_artifact(b.root,name),image_policy=dict(screen=f.settings['imagePolicy']),
            continuity=continuity,monotonic=b.mono,epoch_ms=b.host,sleep=primary.sleep,report=forbidden)
        step=SCENARIOS['tablet-web']['steps'][0];self.assertEqual('open',step['verb'])
        expected=expand(step['state'],context(RUN));original=expand(SCENARIOS['tablet-web']['baseline'],context(RUN))
        expected.update({key:original[key] for key in step.get('originalFields',[])})
        journey.sequence=baseline['sequence'];journey.last_epoch=baseline['capturedEpochMs']
        journey.browser_transition=(step['documentTransition'],baseline['state']['documentLoads'])
        value=journey.wait('01-open',ticket,barrier,expected,step['evidence'])
        self.assertTrue(value['state']['open']);self.assertEqual('reference',value['state']['page'])
        self.assertGreaterEqual(len(journey.samples),3);self.assertEqual(1,len(journey.phases))
        self.assertGreaterEqual(journey.phases[0]['advancingSamples'],3)
        self.assertGreaterEqual(len(actor_calls),3);self.assertEqual(len(actor_calls),len(set(actor_calls)))
        self.assertTrue(all(row['witness'] is not None and row['evidence'] for row in journey.samples[-3:]))
        self.assertEqual([],f.sdk.errors);self.assertEqual([],b.ui.lifecycle_inputs)
        print('Actual first common Tablet Open DOM/PNG/Actor checkpoint passed',flush=True)


if __name__=='__main__':unittest.main()
