"""Full19+paired terminal on explicitly modeled SDK/Qt/OS clocks, real Node/files/PNG."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from feature_journeys import terminal
import unittest
from feature_journeys.engine import matches
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.witness import projection
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.world_web_observer import step as actor_worker_step
from ios.adapters.world_web_canonical_end import verify as canonical_end
from ios.adapters.world_web_finalization import retire_existing as canonical_cleanup


class WorldWebWholeFeatureTests(unittest.TestCase):
    def test_all19_actual_normal_actions_independent_actor_repeated_scene_seal_and_once_os_sdk_end(self):
        f=FeatureWorldWeb();self.addCleanup(f.close);call=dict(contractVersion=16,runId=f.network.run,afterSequence=0)
        primary=f.primary.observe(call);actor=f.secondary.observe(call)
        self.assertTrue(matches(primary['state'],expand(SCENARIOS['world-web']['baseline'],context(f.network.run))))
        for index,step in enumerate(SCENARIOS['world-web']['steps'],1):
            active=f.sdk.activate(step['verb'],expand(step['inputs'],context(f.network.run)))
            self.assertEqual(dict(performed=True),f.primary.act(active))
            primary=f.primary.observe(dict(call,afterSequence=primary['sequence']))
            actor=f.secondary.observe(dict(call,afterSequence=actor['sequence']))
            self.assertTrue(matches(primary['state'],expand(step['state'],context(f.network.run))))
            self.assertEqual(projection('world-web',primary['state']),projection('world-web',actor['state']))
            entry=f.network.controller.observe()['entries'][-1]
            self.assertEqual(active['ticket'],entry['ticket']);self.assertEqual(projection('world-web',actor['state']),entry['facts'])
        f.paired_cleanup()
        inputs=deepcopy(f.whole.domain.io.actions)
        description=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='inspect'))['description']
        self.assertTrue(description['roles']['primary']['heldResources']);self.assertEqual([],description['roles']['actor']['heldResources'])
        window=[]
        for index in range(3):
            primary=f.primary.observe(dict(call,afterSequence=primary['sequence']))
            actor=f.secondary.observe(dict(call,afterSequence=actor['sequence']))
            window.append(dict(primary=deepcopy(primary),actor=f.network.controller.observe()['entries'][-1]))
            if index<2:f.sdk.sleep(1.6)
        self.assertEqual(inputs,f.whole.domain.io.actions)
        seal=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='seal',description=description,samples=window))['seal']
        f.network.controller.close()
        end=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal))['end']
        native={role:model.native_calls for role,model in f.models.items()};requests=deepcopy(f.requests);stops=deepcopy(f.own)
        self.assertEqual('complete',actor_worker_step(f.secondary))
        self.assertEqual(dict(stage='finish',end=end),canonical_end(f.primary,
            dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal),dict(stage='finish',end=end)))
        self.assertEqual(dict(cleaned=True),canonical_cleanup(f.runtime,'primary',None,None))
        self.assertEqual(dict(cleaned=True),canonical_cleanup(f.runtime,'actor',None,None))
        self.assertEqual(native,{role:model.native_calls for role,model in f.models.items()});self.assertEqual(requests,f.requests);self.assertEqual(stops,f.own)
        for role in ('primary','actor'):
            self.assertFalse(f.models[role].running);self.assertFalse(f.models[role].sdk_live)
            self.assertEqual(1,sum(value==(role,'app.stop') for value in f.own))
            self.assertEqual(1,sum(selector==role and method=='DELETE' and path=='/session/'+f.sdks[role].binding['sessionId'] for selector,method,path,_body in f.requests))


if __name__=='__main__':unittest.main()
