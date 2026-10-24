"""Actual localhost/Node originals with explicitly modeled native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_actor_fixture import IndependentActor
from ios.self_tests.world_web_network_fixture import NetworkWorldWeb


@contextmanager
def actor_scene(*,wall_clock=False):
    network=NetworkWorldWeb(use_whole_snapshot=True,wall_clock=wall_clock)
    try:
        whole=network.whole;sdk=whole.sdk;actor=IndependentActor(whole)
        try:
            observer=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,sdk.origins,lambda:True,role='actor',peer=actor.peer)
            observer.capture();before=actor.primary.state['records'][0];actions=whole.actions();actions.act(sdk.activate('open',{}))
            entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
            actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
            admission=actor.primary.capture('scene-fixture-admission');observer.lease=WorldWebLease(whole.scope,actor.primary,before,admission);observer.capture()
            sdk.activate('cleanup',{});whole.scope.cleanup()
            retirement=WorldWebActorRetirement(PrivateFeatureState(actor.root/'ios-world-web-actor-retirement.json'),observer,
                sleep=sdk.sleep if wall_clock else lambda value:sdk.sleep(max(value,1.1)))
            # All ordinary publisher metadata is prepared before fresh source
            # acquisition. Actual publication rechecks the current phase and
            # its original deadline before POST; no old phase is made current.
            phase=PhaseFixtureReader(network.actor,network.run,'world-web',epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time);phase.read()
            publisher=PhaseRetirementPublisher(PrivateFeatureState(actor.root/('phase-retirement-world-web-'+network.run+'-actor.json')),actor.sdk.binding,
                phase,actor.lock,lambda:True,retirement.validate_original,stage=WEB_SCENE_STAGE,epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
            with retirement.original_round():
                original=retirement.cleanup(sdk.ticket)
                yield whole,actor,observer,retirement,original,publisher
        finally:actor.close()
    finally:network.close()
