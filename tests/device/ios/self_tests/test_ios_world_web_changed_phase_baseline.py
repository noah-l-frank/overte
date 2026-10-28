"""Actual normal Node/page/PNG originals; native/GPU/SDK remain host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebChangedPhaseBaselineTests(unittest.TestCase):
    def setUp(self):
        self.f=FeatureWorldWeb();self.addCleanup(self.f.close)
        self.call=dict(contractVersion=16,runId=self.f.network.run,afterSequence=0)
        self.f.primary.observe(self.call)
    def act(self,verb,**inputs):
        call=self.f.sdk.activate(verb,inputs)
        self.assertEqual(dict(performed=True),self.f.primary.act(call));return call['ticket']
    def observe(self):return self.f.primary.observe(self.call)
    def latest(self):
        flow=self.f.primary;request=flow.state['images'][-1]
        with flow.held():
            parts=flow.parts();sample=parts['sample'](request);state=deepcopy(sample.state)
            raw=VulkanWorldFrameOwner.archive_original(state['frameOwnership'],sample.frame_owner.root,
                sample.binding,sample.run,sample.role,0,sample.request,sample.lock)
        return request,state,raw
    def inputs(self):return [row for row in self.f.requests if row[1]=='POST' and row[2].endswith('/actions')]
    def test_repeated_changed_page_uses_same_prior_phase_original_and_fresh_frame_without_reinput(self):
        self.act('open');self.observe();opened,old,old_png=self.latest()
        ticket=self.act('navigate',resource='page-b.html');self.observe();first,a,png_a=self.latest();inputs=self.inputs()
        self.observe();second,b,png_b=self.latest()
        self.assertNotEqual(first,second);self.assertEqual(ticket,a['ticket']);self.assertEqual(ticket,b['ticket'])
        self.assertEqual(opened,a['qualificationInputs']['previous']['requestId'])
        self.assertEqual(opened,b['qualificationInputs']['previous']['requestId'])
        self.assertEqual(a['qualificationInputs']['previous'],b['qualificationInputs']['previous'])
        self.assertEqual('qualified',a['phase']);self.assertEqual('qualified',b['phase'])
        self.assertGreaterEqual(a['qualification']['image']['subjectChangedFraction'],.05)
        self.assertGreaterEqual(b['qualification']['image']['subjectChangedFraction'],.05)
        self.assertEqual(png_a,png_b);self.assertNotEqual(old_png,png_b)
        self.assertNotEqual(a['qualification']['frameId'],b['qualification']['frameId'])
        self.assertGreater(b['before']['index'],a['after']['index']);self.assertEqual(inputs,self.inputs())
        # Original pre-phase custody is still literal after both new captures.
        with self.f.primary.held():
            original=self.f.primary.parts()['sample'](opened)
            self.assertEqual(old,original.state)
            self.assertEqual(old_png,VulkanWorldFrameOwner.archive_original(old['frameOwnership'],original.frame_owner.root,
                original.binding,original.run,original.role,0,original.request,original.lock))
    def test_image_only_same_phase_keeps_nearest_sample_and_next_changed_phase_uses_latest_prior_ticket(self):
        self.act('open');self.observe();first,a,_raw=self.latest()
        self.observe();second,b,_raw=self.latest()
        self.assertEqual(a['ticket'],b['ticket']);self.assertFalse(b['qualificationInputs']['changed'])
        self.assertEqual(first,b['qualificationInputs']['previous']['requestId'])
        self.assertIsNone(b['qualification']['image']['subjectChangedFraction'])
        self.act('navigate',resource='page-b.html');self.observe();third,c,_raw=self.latest()
        self.assertEqual(second,c['qualificationInputs']['previous']['requestId'])
        self.observe();fourth,d,_raw=self.latest()
        self.assertEqual(second,d['qualificationInputs']['previous']['requestId'])
        self.act('back');self.observe();_last,e,_raw=self.latest()
        self.assertEqual(fourth,e['qualificationInputs']['previous']['requestId'])
        self.assertNotEqual(third,e['qualificationInputs']['previous']['requestId'])
        self.assertGreaterEqual(e['qualification']['image']['subjectChangedFraction'],.05)
    def test_changed_phase_without_earlier_qualified_image_retains_actual_missing_baseline_failure(self):
        self.act('open');self.assertEqual([],self.f.primary.state['images'])
        self.act('navigate',resource='page-b.html')
        with self.assertRaisesRegex(ValueError,'subject-change assertion requires a previous original image'):self.observe()
        _request,state,raw=self.latest();self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual('failed',state['phase']);self.assertTrue(state['qualificationInputs']['changed'])
        self.assertIsNone(state['qualificationInputs']['previous']);self.assertIsNone(state['qualification'])
    def test_real_new_phase_with_unchanged_subject_still_fails_unchanged_pixel_threshold(self):
        self.act('open');self.observe();opened,before,_raw=self.latest()
        ticket=self.act('navigate',resource='reference.html');self.assertNotEqual(ticket,before['ticket'])
        with self.assertRaisesRegex(AssertionError,'Actual feature subject pixels did not change'):self.observe()
        _request,state,raw=self.latest();self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual('failed',state['phase']);self.assertEqual(opened,state['qualificationInputs']['previous']['requestId'])
        self.assertTrue(state['qualificationInputs']['changed']);self.assertIsNone(state['qualification'])


if __name__=='__main__':unittest.main()
