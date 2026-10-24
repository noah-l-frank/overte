"""Actual CPU/durability costs precede Scene3's authenticated final POST.

The native/Qt/WK producers remain explicit models. No past original clock is
retimed and the actual fixture and publisher keep their 1.5s/25s ceilings.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_actor_fixture import IndependentActor
from ios.self_tests.world_web_network_fixture import NetworkWorldWeb


class WorldWebActorCpuTests(unittest.TestCase):
    def test_real_cpu_actor_originals_then_scene_publication_without_retiming(self):
        network=NetworkWorldWeb(wall_clock=True,use_whole_snapshot=True);self.addCleanup(network.close);whole=network.whole;sdk=whole.sdk
        actor=IndependentActor(whole);self.addCleanup(actor.close)
        observer=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,sdk.origins,lambda:True,role='actor',peer=actor.peer)
        capture=observer.capture
        def measured_capture(**arguments):
            try:return capture(**arguments)
            finally:
                if actor.primary.frames and actor.peer.frames:
                    a,b=actor.primary.frames[-1]['clockJoin'],actor.peer.frames[-1]['clockJoin']
                    spans=(a['hostAfterMonotonic']-a['hostBeforeMonotonic'],b['hostBeforeMonotonic']-a['hostAfterMonotonic'],b['hostAfterMonotonic']-b['hostBeforeMonotonic'],b['hostAfterMonotonic']-a['hostBeforeMonotonic'])
                    print('actual dual-SDK seconds: primary=%.3f gap=%.3f actor=%.3f total=%.3f'%spans,flush=True)
        observer.capture=measured_capture
        with scope(lambda:sdk.time):observer.capture()
        before=actor.primary.state['records'][0];actions=whole.actions()
        with scope(lambda:sdk.time):actions.act(sdk.activate('open',{}))
        entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
        actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
        admission=actor.primary.capture('actual-cpu-actor-admission');observer.lease=WorldWebLease(whole.scope,actor.primary,before,admission)
        with scope(lambda:sdk.time):observer.capture()
        sdk.activate('cleanup',{});whole.scope.cleanup()
        retirement=WorldWebActorRetirement(PrivateFeatureState(actor.root/'ios-world-web-actor-retirement.json'),observer,sleep=sdk.sleep)
        started=time.perf_counter()
        with scope(lambda:sdk.time),retirement.original_round():
            phase=PhaseFixtureReader(network.actor,network.run,'world-web',epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time);phase.read()
            publisher=PhaseRetirementPublisher(PrivateFeatureState(actor.root/('phase-retirement-world-web-'+network.run+'-actor.json')),actor.sdk.binding,
                phase,actor.lock,lambda:True,retirement.validate_original,stage=WEB_SCENE_STAGE,epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
            self.assertTrue(publisher.resolve());original=retirement.cleanup(sdk.ticket)
            with retirement.publication_round(publisher):publisher.publish(original)
        self.assertLess(time.perf_counter()-started,25)
        self.assertIsNone(publisher.state['pending']);self.assertEqual('published',publisher.load(publisher.state['records'][-1])['mode'])


if __name__=='__main__':unittest.main()
