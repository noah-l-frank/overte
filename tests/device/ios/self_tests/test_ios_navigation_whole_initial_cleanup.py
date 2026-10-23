"""Whole original-process return, paired originals and once-only final end.

Actual Python owners, normal input recipes, HTTP, files and PNG decoders run.
Native/Qt/GPU, SDK, OS and acquisition clocks are explicit host models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.navigation_initial_restored_image import NavigationInitialRestoredImage
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.self_tests import test_ios_navigation_whole_feature as fixture
from ios.self_tests import test_ios_navigation_initial_restored_image as image_fixture
from ios.self_tests.navigation_initial_return_fixture import InitialReturnWorld
from ios.self_tests.navigation_feature_restart_fixture import RestartWorld


class InitialEndWorld(InitialReturnWorld,RestartWorld):pass


class NavigationWholeInitialCleanupTests(unittest.TestCase):
    actor=fixture.NavigationWholeFeatureTests.actor
    inputs=image_fixture.NavigationInitialRestoredImageTests.inputs

    def setUp(self):
        with patch.object(fixture,'Whole',InitialEndWorld):fixture.NavigationWholeFeatureTests.setUp(self)
        h=self.h;h.runtime._sources=h.lifecycle.sources;self.inputs()
        def image(selector,client,run,role,request,root,lock,*,admission,directory_proof,previous):
            return NavigationInitialRestoredImage(PrivateFeatureState(h.root/('ios-navigation-initial-restored-'+role+'-'+request[4:]+'.json')),
                root,h.binding,run,role,request,lock,lambda:h.sdk.okay,native=h.native,sources=self.sources,
                fixture=h.fixture,frame_factory=h.gpu.factory,epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep,
                admission=admission,directory=directory_proof,previous=previous,fixture_url=h.fixture.fixture_url,
                input_readers=dict(keys=self.keys.reader(),pointer=self.pointer_reader,geometry=self.keys.geometry()))
        h.runtime._navigation_initial_restored_image=image

    def test_normal_original_process_cleanup_seals_and_ends_without_a_fabricated_restart(self):
        self.journey(('open','close'))

    def test_owned_missing_error_cleanup_joins_original_image_history_and_canonical_end(self):
        self.journey(('open','close','navigate-missing'),canonical=True)

    def journey(self,verbs,*,canonical=False):
        from ios import navigation_observer as worker
        from ios.adapters import appium_adapter as backend
        from ios.self_tests.navigation_end_fixture import EndBoundary
        h=self.h;whole=self.whole
        if 'navigate-missing' in verbs:
            from ios.self_tests.navigation_feature_missing_fixture import MissingWidget
            self.missing_widget=MissingWidget(h,self);self.sources['dialogs']=h.sources['dialogs']
        whole.prepare();actor=self.actor();config=dict(target=h.flow.selector)
        current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0));self.assertIsNone(worker.step(actor,config))
        for verb in verbs:
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,{});h.gpu.marker=ticket
            whole.act(dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=h.fixture.fixture_url))
            current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
            self.assertIsNone(worker.step(actor,config))
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'cleanup',{})
        self.assertEqual({'performed':True},whole.cleanup(dict(contractVersion=16,runId=h.run)))
        print('NAVIGATION initial ordinary restoration complete',flush=True)
        for index in range(3):
            if index:h.sdk.gpu.sleep(1.6)
            self.assertIsNone(worker.step(actor,config))
        owner=NavigationTerminal(h.flow);description=owner.inspect();samples=[]
        for index in range(3):
            if index:h.sdk.gpu.sleep(1.6)
            current=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
            # Retain the actual Actor publish return while executing its real
            # worker boundary; no Primary facts are copied into that return.
            returned=[];publish=actor.publish
            def actual():
                value=publish();returned.append(value);return value
            with patch.object(actor,'publish',side_effect=actual):self.assertIsNone(worker.step(actor,config))
            self.assertEqual(1,len(returned));samples.append(dict(primary=current,actor=returned[0]))
        seal=owner.seal(description,samples);self.assertEqual(0,h.flow.state['stage']);self.assertEqual([],h.lifecycle.calls)
        print('NAVIGATION initial paired live seal complete',flush=True)
        with h.flow.held():bridge=EndBoundary(self,connected=dict(flow=h.flow,terminal=owner,world=h))
        ended=owner.finish(seal);self.assertEqual(1,bridge.stops);self.assertIsNone(h.lifecycle.pid)
        self.assertIsNone(bridge.sdk.read());self.assertIsNone(bridge.installed.store.read());requests=deepcopy(bridge.requests)
        print('NAVIGATION initial process and SDK end complete',flush=True)
        def forbidden(*_args,**_kwargs):self.fail('Historical initial-process replay attempted transport')
        with (patch.object(h.runtime,'_sources',side_effect=forbidden),
              patch.object(h.flow.client,'request',side_effect=forbidden),
              patch.object(actor.flow.client,'request',side_effect=forbidden),
              patch.object(backend.WebDriver,'call',side_effect=forbidden)):
            if canonical:
                from feature_journeys import terminal
                from ios.adapters.navigation_canonical_end import verify
                call=dict(contractVersion=terminal.VERSION,runId=h.run,stage='finish',seal=seal)
                result=dict(stage='finish',end=ended);self.assertEqual(result,verify(whole,call,result))
            else:self.assertEqual(ended,owner.finish(seal))
            self.assertEqual(0,worker.step(actor,config))
        self.assertEqual(requests,bridge.requests);self.assertEqual(1,sum(method=='DELETE' for method,_ in bridge.requests))


if __name__=='__main__':unittest.main()
