"""Complete shared Worlds steps using real owners and declared native models.

Normal token recipes, HTTP, JavaScript, journals and PNG decoders are real.
SDK, Qt, GPU, OS and acquisition clocks are explicitly modeled, not qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.engine import matches
from ios.adapters.navigation_quiet_image import NavigationQuietImage
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.self_tests import test_ios_navigation_whole_feature as first
from ios.self_tests import test_ios_navigation_feature_transfer as transfer
from ios.self_tests import test_ios_navigation_quiet_period as quiet
from ios.self_tests.navigation_feature_restart_fixture import RestartWorld
from ios.self_tests.navigation_feature_missing_fixture import MissingWidget
from ios.self_tests.navigation_feature_next_ui_fixture import NextUI


class NavigationWholeRestartTests(unittest.TestCase):
    actor=first.NavigationWholeFeatureTests.actor
    install=transfer.NavigationFeatureTransferTests.install
    inputs=quiet.NavigationQuietPeriodTests.inputs

    def setUp(self):
        with patch.object(first,'Whole',RestartWorld):first.NavigationWholeFeatureTests.setUp(self)
        h=self.h
        # Whole preparation's deliberately minimal factory is no longer used.
        # Actual lifecycle source binding remains independent of scene facts.
        h.runtime._sources=h.lifecycle.sources
        MissingWidget(h,self);self.sources['dialogs']=h.sources['dialogs']
        self.whole.prepare();self.install()

    def restored_images(self):
        h=self.h
        call=dict(process_context=h.flow.transferred_owner().archive())
        self.inputs(call)
        def image(selector,client,run,role,request,root,lock,*,process_context,owner_files,directory_proof,previous,quiet=False):
            self.assertTrue(quiet)
            return NavigationQuietImage(PrivateFeatureState(h.root/('ios-navigation-quiet-'+role+'-'+request[4:]+'.json')),
                root,process_context['restart']['input']['newBinding'],run,role,request,lock,lambda:self.new.sdk.okay,
                native=self.new.native,sources=self.new.sources,fixture=h.fixture,frame_factory=self.new.gpu.factory,
                epoch_ms=h.now,monotonic=h.mono,sleep=self.new.sdk.gpu.sleep,process_context=process_context,
                owner_files=owner_files,directory=directory_proof,previous=previous,
                input_readers=dict(keys=self.keys.reader(),pointer=self.pointer_reader,geometry=self.keys.geometry()))
        h.runtime._navigation_restored_image=image

    def test_all_fifteen_steps_and_ordinary_restore_join_both_roles_before_live_terminal_seal(self):
        self.journey(SCENARIOS['world-navigation']['steps'])

    def test_compact_normal_restart_and_restoration_join_the_same_live_terminal_sources(self):
        steps=SCENARIOS['world-navigation']['steps']
        close=deepcopy(steps[14]);close['state']=dict(steps[4]['state'],panel=False,searchResults=[])
        self.journey([steps[0],steps[2],steps[4],close,steps[11],steps[12],steps[13],steps[14]])

    def journey(self,steps):
        h=self.h;whole=self.whole;actor=self.actor();ctx=context(h.run)
        current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0));actor.publish()
        for step in steps:
            # A failed source join invalidates this composed journey. Stop at
            # that first failure instead of spending later steps on its state.
            if step['verb']=='bookmark-visit':h.flow_fixture.f.root_id='00000000-0000-4000-8000-000000000503'
            inputs=expand(step['inputs'],ctx);ticket=uuid.uuid4().hex
            h.harness.client.activate(ticket,step['verb'],inputs)
            (h.gpu if self.new is None else self.new.gpu).marker=ticket
            call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=step['verb'],inputs=inputs,fixtureUrl=h.fixture.fixture_url)
            self.assertEqual({'performed':True},whole.act(call),step['verb'])
            if step['verb']=='restart-app':self.next_ui=NextUI(self.new,self)
            current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
            self.assertTrue(matches(current['state'],expand(step['state'],ctx)),(step['verb'],current['state']))
            entry=actor.publish();self.assertEqual(ticket,entry['ticket']);self.assertEqual(current['state'],entry['facts'])
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
        with h.flow.held():self.restored_images()
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'cleanup',{})
        self.assertEqual({'performed':True},whole.cleanup(dict(contractVersion=16,runId=h.run)))
        # Actor acquires its own three genuine restored cuts and canonical
        # witness deliveries, independently of Primary's cleanup acquisitions.
        for index in range(3):
            if index:self.new.sdk.gpu.sleep(1.6)
            actor.publish()
        owner=NavigationTerminal(h.flow);description=owner.inspect();samples=[]
        for index in range(3):
            if index:self.new.sdk.gpu.sleep(1.6)
            current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
            samples.append(dict(primary=current,actor=actor.publish()))
        seal=owner.seal(description,samples);commands=deepcopy(self.new.gpu.commands)
        with h.flow.held():
            def forbidden(*_args,**_kwargs):self.fail('Historical terminal replay attempted transport')
            with patch.object(h.runtime,'_sources',side_effect=forbidden),patch.object(h.flow.client,'request',side_effect=forbidden):
                self.assertEqual(seal,owner.replay())
        self.assertEqual(commands,self.new.gpu.commands)
        self.assertTrue(all(description['roles'][role]['heldResources'] for role in ('primary','actor')))
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
