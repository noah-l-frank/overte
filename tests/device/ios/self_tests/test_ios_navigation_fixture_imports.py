"""The declared native model emits one actual import/callback cohort.

These are producer-model checks, not normal input or iOS qualification.
HTTP response bodies are real and no archived observation is edited.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from feature_journeys.fixtures import context
from navigation_observation import viewpoint_urls
from ios.self_tests.navigation_feature_observer_fixture import Whole


class NavigationFixtureImportTests(unittest.TestCase):
    def setUp(self):self.h=Whole(self)

    def test_new_model_import_emits_marker_url_from_that_actual_http_body(self):
        h=self.h;h.flow.prepare();previous=h.navigation.read(h.run);saved=deepcopy(previous)
        ticket='c'*32;h.harness.client.activate(ticket,'directory-select',dict(destination=context(h.run)['destination']))
        h.flow_fixture.b.current=viewpoint_urls(h.harness.inputs['sceneUrl'])['B'];h.sync_navigation()
        current=h.navigation.read(h.run);imported=json.loads(h.inventory.body)['Entities'][-1]
        self.assertEqual(imported['sourceUrl'],current['source']['challengeMarker']['entity']['sourceUrl'])
        self.assertIn('/tickets/'+ticket+'/',imported['sourceUrl'])
        self.assertEqual(hashlib.sha256(h.inventory.body).hexdigest(),h.inventory.anchor['bodySha256'])
        self.assertNotEqual(previous['source']['challengeMarker']['entity']['sourceUrl'],imported['sourceUrl'])
        self.assertEqual(saved,previous)

    def test_completed_error_callback_keeps_original_event_history_without_a_live_lookup(self):
        h=self.h;initial=h.sources['replies'].read(h.run);self.assertFalse(initial['currentLookupActive'])
        status,_raw,response=h.harness.get('/api/v1/places/'+context(h.run)['hidden']);self.assertEqual(404,status)
        h.dialogs.run=h.run;h.dialogs.create(response,origin=h.harness.origin)
        active=h.sources['replies'].read(h.run);saved=deepcopy(active);self.assertTrue(active['currentLookupActive'])
        h.dialogs.respond();h.dialogs.destroy();current=h.sources['replies'].read(h.run)
        self.assertFalse(current['currentLookupActive']);self.assertEqual(active['events'],current['events']);self.assertEqual(saved,active)
