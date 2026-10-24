"""Minimal actual feature vertical: ordinary open/close through paired OS end.

Only SDK/Qt/WK/GPU/OS producers and their clocks are explicit host models.
The runtime, owners, local HTTP, actual Script/DOM JS, files and PNGs are real.
This does not qualify a native build, device, or real-CPU acquisition budget.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from feature_journeys import terminal
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.world_web_observer import step as actor_worker_step
from ios.adapters.world_web_canonical_end import verify as canonical_end


class WorldWebFeatureTerminalTests(unittest.TestCase):
    def test_normal_open_close_actual_paired_quiet_seal_and_once_stop_sdk_end(self):
        f=FeatureWorldWeb();self.addCleanup(f.close)
        call=dict(contractVersion=16,runId=f.network.run,afterSequence=0)
        primary=f.primary.observe(call);actor=f.secondary.observe(call)
        for verb in ('open','close'):
            self.assertEqual(dict(performed=True),f.primary.act(f.sdk.activate(verb,{})))
            primary=f.primary.observe(dict(call,afterSequence=primary['sequence']))
            actor=f.secondary.observe(dict(call,afterSequence=actor['sequence']))
        self.assertFalse(primary['state']['open']);self.assertFalse(actor['state']['open'])
        f.paired_cleanup()
        description=f.primary.terminal(dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='inspect'))['description']
        self.assertTrue(description['roles']['primary']['heldResources'])
        self.assertEqual([],description['roles']['actor']['heldResources'])
        inputs=deepcopy(f.whole.domain.io.actions);window=[]
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
        wrong=deepcopy(end);wrong['roles']['primary']['archiveSha256']='0'*64
        with self.assertRaises(NativeUIError):
            canonical_end(f.primary,dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal),dict(stage='finish',end=wrong))
        self.assertEqual(dict(stage='finish',end=end),canonical_end(f.primary,
            dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal),dict(stage='finish',end=end)))
        self.assertEqual(native,{role:model.native_calls for role,model in f.models.items()})
        self.assertEqual(requests,f.requests);self.assertEqual(stops,f.own)
        for role in ('primary','actor'):
            self.assertFalse(f.models[role].running);self.assertFalse(f.models[role].sdk_live)
            self.assertEqual(1,sum(value==(role,'app.stop') for value in f.own))
            self.assertEqual(1,sum(selector==role and method=='DELETE' and path=='/session/'+f.sdks[role].binding['sessionId']
                for selector,method,path,_body in f.requests))


if __name__=='__main__':unittest.main()
