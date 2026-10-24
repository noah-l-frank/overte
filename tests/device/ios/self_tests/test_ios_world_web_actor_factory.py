"""Actual owner factories use two SDKs; local Web data is never replicated by assumption."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.adapters.world_web_feature import IOSWorldWebFeature
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.world_web_actor_fixture import IndependentActor


class WorldWebActorFactoryTests(unittest.TestCase):
    def test_actor_uses_own_physical_sdk_and_independently_queries_existing_primary_sdk(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);actor=IndependentActor(whole);self.addCleanup(actor.close)
        paths={'primary':whole.scope.root/'session.json','actor':actor.root/'session.json'}
        runtime=IOSWorldWebRuntime(SimpleNamespace(state_path=paths.__getitem__,_candidate_guard=lambda:True,_binding=lambda:True))
        actual={'primary':whole.sdk,'actor':actor.sdk};calls=[]
        runtime._sources=lambda selector:dict(binding=deepcopy(actual[selector].binding),check=lambda:True)
        def source(selector,run,role,phase,lock):
            calls.append((selector,role,actual[selector]));sdk=actual[selector];old=getattr(sdk,'role',None);sdk.role=role
            try:return sdk.owner(PrivateFeatureState(paths[selector].with_name('ios-world-web-'+role+'-sources.json')),lock)
            finally:
                if old is None:del sdk.role
                else:sdk.role=old
        runtime._world_web_source_owner=source;runtime._world_web_marker=lambda *args:whole.scope
        flow=runtime._world_web_feature('actor',whole.sdk.run,role='actor',client=actor.peer.phase.client,
            settings=dict(artifactRoot=str(whole.scope.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]),
                origins=whole.sdk.origins,primaryTarget='primary'))
        # Reuse only the actual already-held locks for these exact physical
        # source files. No separate lock or native request is synthesized.
        flow.lock=actor.lock;flow.primary_lock=whole.scope.lock
        flow.state=dict(binding=deepcopy(actor.sdk.binding),primaryBinding=deepcopy(whole.sdk.binding),lease=None,beforeImage=None,images=[],initialTicket=whole.sdk.ticket)
        parts=flow.parts();self.assertIsInstance(flow,IOSWorldWebFeature)
        self.assertEqual([('actor','actor'),('primary','actor-primary')],[(selector,role) for selector,role,_sdk in calls])
        self.assertIs(actor.sdk,calls[0][2]);self.assertIs(whole.sdk,calls[1][2])
        self.assertEqual(actor.sdk.binding,parts['peer'].binding);self.assertEqual(whole.sdk.binding,parts['source'].binding)
        self.assertNotEqual(parts['peer'].binding['targetFingerprint'],parts['source'].binding['targetFingerprint'])
        self.assertIs(parts['peer'],parts['history'].peer);self.assertIs(parts['source'],parts['history'].source)
        self.assertEqual([],parts['peer'].frames);self.assertEqual([],parts['source'].frames)
        flow.state['primaryBinding']=deepcopy(actor.sdk.binding)
        with self.assertRaises(NativeUIError):flow.parts()


if __name__=='__main__':unittest.main()
