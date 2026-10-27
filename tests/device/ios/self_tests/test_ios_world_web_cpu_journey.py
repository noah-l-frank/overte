"""Nineteen ordinary input/source states with real CPU-accounted model clocks.

Node/HTML/Script, private files and durability execute. Native/Qt/WK/SDK are
explicit models. This does not supply Actor, PNG or full terminal authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import time
import unittest
from feature_journeys.contract import state
from feature_journeys.engine import matches
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.retained_host_roots import retain_owned_root


class WorldWebCpuJourneyTests(unittest.TestCase):
    def test_all_nineteen_normal_actions_and_original_states_keep_real_api_clocks(self):
        whole=ComposedWorldWeb(wall_clock=True,use_whole_snapshot=True);self.addCleanup(whole.close)
        root=retain_owned_root(whole.fixture.fixture.temp,expected_root=whole.scope.root)
        print('Retained real-clock World input originals: '+str(root),flush=True)
        sdk,source=whole.sdk,whole.source;actions=whole.actions();lease=None;times=[]
        for index,step in enumerate(SCENARIOS['world-web']['steps'],1):
            started=time.perf_counter()
            try:
                with scope(lambda:sdk.time):
                    call=sdk.activate(step['verb'],expand(step['inputs'],context(sdk.run)))
                    self.assertEqual(dict(performed=True),actions.act(call))
                    if step['verb']=='open':
                        entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,source,entry['before'],entry['after'])
                        actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
                action_seconds=time.perf_counter()-started;self.assertLess(action_seconds,25)
                started=time.perf_counter()
                # Match the actual WorldWebObserver's single read boundary:
                # Source and Lease qualify their full byte graphs on entry,
                # remain guarded through derivation and recheck on exit. The
                # outer API budget includes both entries and both exits.
                # This is still an input/state component, without PNG/Actor.
                with scope(lambda:sdk.time),source.validation_round(),lease.validation_round():
                    owned=lease.packet()
                    observed=source.derive_browser(ownership=owned['files'],directory=owned['directory'],
                        entity=owned['returned']['returned']['entityId'],origins=sdk.origins)['public']
                    state('world-web',observed,sdk.run)
                    self.assertTrue(matches(observed,expand(step['state'],context(sdk.run))),(index,step['verb'],observed))
                observe_seconds=time.perf_counter()-started;self.assertLess(observe_seconds,25)
                times.append(dict(step=index,verb=step['verb'],actionSeconds=action_seconds,observationSeconds=observe_seconds))
                print(json.dumps(times[-1]),flush=True)
            except BaseException:
                print(json.dumps(dict(failedStep=index,verb=step['verb'],completed=len(times),originals=str(root))),flush=True)
                raise
        self.assertEqual(19,len(times));self.assertFalse(observed['open']);self.assertEqual(2,observed['bridgeMessages'])
        self.assertEqual(2,observed['bridgeEchoes']);self.assertEqual(3,observed['attemptedMessages'])
        self.assertEqual(5,source.version)


if __name__=='__main__':unittest.main()
