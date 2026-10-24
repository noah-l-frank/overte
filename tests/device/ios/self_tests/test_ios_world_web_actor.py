"""Independent actual source readers, local role inventories and terminal quiet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.fixtures import context
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.world_web_actor_fixture import IndependentActor


class WorldWebActorTests(unittest.TestCase):
    def test_independent_primary_sdk_echo_source_and_own_actor_inventory_then_actual_terminal_quiet(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);actor=IndependentActor(whole);self.addCleanup(actor.close)
        observer=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,whole.sdk.origins,lambda:True,role='actor',peer=actor.peer)
        _,baseline=observer.capture();before=actor.primary.state['records'][0]
        actions=whole.actions();sdk=whole.sdk;actions.act(sdk.activate('open',{}));entry=actions.state['calls'][-1]
        primary_lease=WorldWebLease(whole.scope,whole.source,entry['before'],entry['after']);actions.inputs.entity=primary_lease.packet()['returned']['returned']['entityId']
        admitted=actor.primary.capture('independent-original-admission');observer.lease=WorldWebLease(whole.scope,actor.primary,before,admitted)
        _,opened=observer.capture();self.assertTrue(opened['public']['state']['open']);self.assertEqual([],opened['public']['artifacts'])
        actions.act(sdk.activate('focus-type',dict(text=context(sdk.run)['unicode'])));actions.act(sdk.activate('submit',{}))
        _,echo=observer.capture();self.assertEqual([1,1,1],[echo['public']['state'][key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')])
        self.assertNotEqual(actor.peer.binding['targetFingerprint'],actor.primary.binding['targetFingerprint'])
        sdk.activate('cleanup',{});whole.scope.cleanup()
        retirement=WorldWebActorRetirement(PrivateFeatureState(actor.root/'ios-world-web-actor-retirement.json'),observer,sleep=sdk.sleep)
        retirement.cleanup(sdk.ticket);self.assertEqual('retired',retirement.state['phase']);proof=retirement.validate_original(retirement.original())
        self.assertEqual(['native-process-resources'],proof['scene']['remaining']);self.assertNotIn('public',proof);self.assertEqual(actor.sdk.pid,proof['retirement']['quiet']['processId'])
        # Reconstruct the exact typed whole owner after the foreground may
        # have ended; forbidden transports must never run during replay.
        from types import SimpleNamespace
        from ios.adapters.world_web_runtime import IOSWorldWebRuntime
        from ios.adapters.world_web_archived import rebuild
        from copy import deepcopy
        paths={'primary':whole.scope.root/'session.json','actor':actor.root/'session.json'}
        runtime=IOSWorldWebRuntime(SimpleNamespace(state_path=paths.__getitem__,_candidate_guard=lambda:True,_binding=lambda:True))
        flow=runtime._world_web_feature('actor',sdk.run,role='actor',client=actor.peer.phase.client,
            settings=dict(artifactRoot=str(whole.scope.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]),origins=sdk.origins,primaryTarget='primary'))
        flow.lock=actor.lock;flow.primary_lock=whole.scope.lock
        flow.state=dict(phase='cleaned',binding=deepcopy(actor.sdk.binding),primaryBinding=deepcopy(sdk.binding),phaseInstance=actor.peer.phase.previous['instance'],
            initialTicket=whole.scope.ticket,actorAdmission=None,baseline=before,lease=dict(before=before,after=admitted),beforeImage=None,images=[],retirement=None)
        flow.previous=None;flow.save();queries=deepcopy([sdk.counts,actor.sdk.counts]);inputs=deepcopy(whole.domain.io.actions)
        archived=rebuild(flow);self.assertEqual(proof,archived.validate_original(retirement.original()))
        self.assertEqual(queries,[sdk.counts,actor.sdk.counts]);self.assertEqual(inputs,whole.domain.io.actions)



if __name__=='__main__':unittest.main()
