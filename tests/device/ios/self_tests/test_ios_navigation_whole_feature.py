"""Whole Worlds composition using real journals/HTTP and declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from feature_journeys.witness import Client
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.self_tests.navigation_feature_observer_fixture import Whole
from ios.self_tests.navigation_baseline_image_fixture import Baseline,static_raster
from ios.self_tests import test_ios_navigation_whole_preparation as preparation


class NavigationWholeFeatureTests(unittest.TestCase):
    def setUp(self):
        world=Whole(self);active_raster=world.gpu.raster;baseline=Baseline(self,world=world)
        with patch.object(preparation,'Baseline',return_value=baseline):preparation.NavigationWholePreparationTests.setUp(self)
        h=self.h
        h.gpu.raster=lambda:active_raster() if h.sdk.navigation.source['challengeMarker']['present'] else static_raster(h.sdk.navigation)
        h.flow.runtime._sources=lambda _selector:dict(binding=deepcopy(h.binding),check=lambda:h.sdk.okay,native=h.sources['ui'],
            clock_source=h.native,observer=SimpleNamespace(places_model=lambda _clock:h.sources['model'],navigation_state=lambda _clock:h.navigation))
        self.whole=NavigationWholeFeature(h.flow)

    def actor(self):
        h=self.h;flow=h.flow_fixture.flow('actor');flow.client=Client(h.harness.client.url,h.harness.server.actor_token)
        flow.fixture=NavigationFixtureReader(flow.client,h.run,epoch_ms=lambda:int(h.now()),monotonic=h.mono)
        return NavigationWholeFeature(flow)

    def test_ordinary_preparation_and_public_action_join_real_separate_actor_sources_and_server_receipts(self):
        h=self.h;whole=self.whole;whole.prepare();first=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0))
        actor=self.actor();actor.publish();original=deepcopy(h.flow.store.read())
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'open',{});h.gpu.marker=ticket
        call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb='open',inputs={},fixtureUrl=h.fixture.fixture_url)
        self.assertEqual({'performed':True},whole.act(call));current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=first['sequence']))
        entry=actor.publish();self.assertTrue(current['state']['panel']);self.assertEqual(current['state'],entry['facts'])
        self.assertEqual(ticket,entry['ticket']);self.assertGreater(current['sequence'],first['sequence'])
        with h.flow.held():primary=h.flow.observer().owners()[-1]
        with actor.flow.held():peer=actor.flow.observer().owners()[-1]
        self.assertNotEqual(primary.request,peer.request);self.assertNotEqual(primary.previous,peer.previous)
        self.assertNotEqual(original,h.flow.store.read());before=deepcopy(h.flow_fixture.b.inputs)
        self.assertEqual({'performed':True},whole.act(call));self.assertEqual(before,h.flow_fixture.b.inputs)

    def test_all_first_process_steps_use_closed_public_contract_and_independent_original_publications(self):
        from feature_journeys.fixtures import context
        from feature_journeys.scenarios import SCENARIOS,expand
        from feature_journeys.engine import matches
        from ios.self_tests.navigation_feature_missing_fixture import MissingWidget
        h=self.h;whole=self.whole;MissingWidget(h,self)
        # Install this physical callback producer before the fresh whole
        # admission. Both acquisition factories must use that same reader;
        # a previously bound send method does not receive its later callback.
        self.sources['dialogs']=h.sources['dialogs']
        whole.prepare();actor=self.actor();ctx=context(h.run)
        current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0));actor.publish()
        steps=SCENARIOS['world-navigation']['steps']
        for step in steps:
            if step['verb']=='restart-app':break
            with self.subTest(verb=step['verb']):
                if step['verb']=='bookmark-visit':h.flow_fixture.f.root_id='00000000-0000-4000-8000-000000000503'
                inputs=expand(step['inputs'],ctx);ticket=uuid.uuid4().hex
                h.harness.client.activate(ticket,step['verb'],inputs);h.gpu.marker=ticket
                call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=step['verb'],inputs=inputs,fixtureUrl=h.fixture.fixture_url)
                self.assertEqual({'performed':True},whole.act(call))
                current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
                self.assertTrue(matches(current['state'],expand(step['state'],ctx)),current['state'])
                entry=actor.publish();self.assertEqual(ticket,entry['ticket']);self.assertEqual(current['state'],entry['facts'])
                self.assertTrue(all(artifact['sequence']==current['sequence'] for artifact in current['artifacts']))
        self.assertEqual('A',current['state']['location']);self.assertFalse(current['state']['addressDialog'])
        self.assertEqual(ctx['renamed'],current['state']['bookmarkName'])
