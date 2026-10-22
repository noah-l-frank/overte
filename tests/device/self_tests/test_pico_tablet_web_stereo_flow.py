"""Original primary/actor composition; product/GPU/Qt/VM boundaries are host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from self_tests import test_pico_tablet_web_flow as flow_seams
from self_tests.pico_browser_render_fixture import RenderModel
from feature_journeys.scenarios import VERSION
from feature_journeys.stereo_browser_evidence import observation,PROFILE
from feature_journeys.evidence import read_private_artifact
from self_tests.test_stereo_navigation_evidence import POLICY as BASE_POLICY


class PicoTabletWebStereoFlowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=flow_seams.PicoTabletWebFlowTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=RenderModel(self.fixture.target,self.fixture.artifacts);self.addCleanup(self.model.close)
        self.fixture.target._tablet_web_stereo=lambda target,flow,journal,role:self.model.stereo(flow,journal,role)
        self.fixture.target._native_feature_observer=lambda target,**kwargs:self.model._native_feature_observer(target,read_only=True)
    def test_actual_parent_and_independent_actor_publish_separate_original_stereo_journals(self):
        f=self.fixture;f.activate();f.primary.prepare();ticket=f.act('open')
        sample=f.primary.observe(dict(contractVersion=VERSION,runId=f.run,afterSequence=0))
        inputs=sum(row['operation']=='input' for row in f.target.command_log)
        actor=f.actor.publish();self.assertEqual(sample['state'],actor['state'])
        self.assertEqual(inputs,sum(row['operation']=='input' for row in f.target.command_log))
        self.assertEqual(2,len(sample['artifacts']));self.assertEqual(2,len(actor['artifacts']))
        policy=deepcopy(BASE_POLICY);policy['profile']=PROFILE
        for role,value in (('primary',sample),('actor',actor)):
            artifacts={row['kind']:row for row in value['artifacts']}
            image=read_private_artifact(f.artifacts,artifacts['image']['name'])
            metadata=read_private_artifact(f.artifacts,artifacts['file']['name'])
            evidence,subject=observation(image,metadata,f.run,ticket,f.fixture_url,policy,value,role=role)
            self.assertEqual({'left','right'},set(evidence['eyes']));self.assertEqual(role,subject['role'])
        self.assertNotEqual(sample['artifacts'][0]['name'],actor['artifacts'][0]['name'])
        self.assertEqual(2,len(self.model.gpu.commands));self.assertEqual([],list(self.model.native_root.iterdir()))


if __name__=='__main__':unittest.main()
