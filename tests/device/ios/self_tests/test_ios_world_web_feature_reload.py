"""Fail-fast actual factory reload at404/200; explicit SDK/Qt/GPU model clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebFeatureReloadTests(unittest.TestCase):
    def test_normal_reload_of_actual404_then_restored200_document(self):
        fixture=FeatureWorldWeb();self.addCleanup(fixture.close);flow=fixture.primary
        call=dict(contractVersion=16,runId=fixture.network.run,afterSequence=0)
        previous=flow.observe(call)
        for verb,inputs in (('open',{}),('navigate',dict(resource='recovery.html'))):
            self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate(verb,inputs)))
            previous=flow.observe(dict(call,afterSequence=previous['sequence']))
        self.assertEqual(404,previous['state']['httpStatus']);before=previous['state']['documentLoads']
        self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate('reload',{})))
        current=flow.observe(dict(call,afterSequence=previous['sequence']))
        self.assertEqual(404,current['state']['httpStatus']);self.assertGreater(current['state']['documentLoads'],before)
        # Both indistinguishable reload recipes require the conservative union
        # of actual evidence. Removing only this real image reference must not
        # turn the first checkpoint's weaker list into a missing-image bypass.
        with flow.held():
            history=flow.parts()['history'];entry=history.entries()[-1]
            self.assertIsNotNone(entry['sample'])
            with self.assertRaises(NativeUIError):history.derive(dict(entry,sample=None))
        self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate('restore-resource',{})))
        self.assertEqual(dict(performed=True),flow.act(fixture.sdk.activate('reload',{})))
        recovered=flow.observe(dict(call,afterSequence=current['sequence']))
        self.assertEqual(200,recovered['state']['httpStatus']);self.assertGreater(recovered['state']['documentLoads'],current['state']['documentLoads'])


if __name__=='__main__':unittest.main()
