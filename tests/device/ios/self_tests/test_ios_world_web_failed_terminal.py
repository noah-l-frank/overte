"""Incomplete setup through the actual paired feature/terminal boundaries.

SDK/Qt/WK/GPU/OS and clocks are declared models; owners, local HTTP, actual
Script/DOM execution, carriers, fsync and PNG restoration are real host code.
These cases make no physical/native or real-CPU deadline qualification claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys import terminal
from ios.adapters.world_web_canonical_end import verify as canonical_end
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.world_web_observer import step as actor_worker_step


class WorldWebFailedTerminalTests(unittest.TestCase):
    def complete_original_failure(self,*,null_return):
        f=FeatureWorldWeb();self.addCleanup(f.close);f.sdk.deny_entity_rez=null_return
        call=dict(contractVersion=16,runId=f.network.run,afterSequence=0)
        primary=f.primary.observe(call);actor=f.secondary.observe(call)
        if null_return:
            with self.assertRaises(NativeUIError):f.primary.act(f.sdk.activate('open',{}))
            self.assertTrue(f.whole.domain.running);self.assertIsNone(f.whole.domain.marker)
            self.assertEqual(dict(entityId=None),f.sdk.node_work[0]['value']['payload'])
        f.paired_cleanup()
        self.assertIsNone(f.primary.state['lease']);self.assertIsNone(f.secondary.state['lease'])
        self.assertEqual('partial-execution' if null_return else 'unloaded',f.whole.scope.state['cleanupMode'])
        self.assertFalse(f.whole.domain.running);self.assertIsNone(f.whole.domain.marker)
        if null_return:self.assertEqual(['add-returned'],[row['kind'] for row in f.sdk.entity_calls])
        else:self.assertEqual([],f.sdk.entity_calls)
        description=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='inspect'))['description']
        self.assertEqual([],description['roles']['actor']['heldResources']);inputs=deepcopy(f.whole.domain.io.actions);window=[]
        for index in range(3):
            primary=f.primary.observe(dict(call,afterSequence=primary['sequence']))
            actor=f.secondary.observe(dict(call,afterSequence=actor['sequence']))
            window.append(dict(primary=deepcopy(primary),actor=f.network.controller.observe()['entries'][-1]))
            if index<2:f.sdk.sleep(1.6)
        self.assertEqual(inputs,f.whole.domain.io.actions)
        seal=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='seal',description=description,samples=window))['seal']
        f.network.controller.close();finish=dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal)
        result=f.primary.terminal(finish);native={role:model.native_calls for role,model in f.models.items()};requests=deepcopy(f.requests);stops=deepcopy(f.own)
        self.assertEqual('complete',actor_worker_step(f.secondary));self.assertEqual(result,canonical_end(f.primary,finish,result))
        self.assertEqual(native,{role:model.native_calls for role,model in f.models.items()});self.assertEqual(requests,f.requests);self.assertEqual(stops,f.own)
        for role in ('primary','actor'):
            self.assertFalse(f.models[role].running);self.assertFalse(f.models[role].sdk_live)
            self.assertEqual(1,sum(value==(role,'app.stop') for value in f.own))
            self.assertEqual(1,sum(selector==role and method=='DELETE' and path=='/session/'+f.sdks[role].binding['sessionId']
                for selector,method,path,_body in f.requests))

    def test_unexecuted_setup_actual_paired_restoration_seal_and_once_os_sdk_end(self):
        self.complete_original_failure(null_return=False)

    def test_loaded_actual_null_return_has_no_invented_renderer_then_paired_terminal_end(self):
        self.complete_original_failure(null_return=True)


if __name__=='__main__':unittest.main()
