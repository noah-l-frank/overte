"""Minimal actual feature vertical: ordinary open/close through paired OS end.

Only SDK/Qt/WK/GPU/OS producers and their clocks are explicit host models.
The runtime, owners, local HTTP, actual Script/DOM JS, files and PNGs are real.
This does not qualify a native build, device, or real-CPU acquisition budget.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from unittest.mock import patch
from feature_journeys import terminal
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb
from ios.world_web_observer import step as actor_worker_step
from ios.adapters.world_web_canonical_end import verify as canonical_end
from ios.adapters.world_web_terminal import WorldWebTerminal


class WorldWebFeatureTerminalTests(unittest.TestCase):
    def test_normal_open_close_actual_paired_quiet_seal_and_once_stop_sdk_end(self):
        self.normal_terminal()

    def test_durable_complete_return_loss_reopens_actual_paired_terminal_without_live_reentry(self):
        self.normal_terminal(lose_complete_return=True)

    def normal_terminal(self,*,lose_complete_return=False):
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
        finish=dict(contractVersion=terminal.VERSION,runId=f.network.run,stage='finish',seal=seal)
        if lose_complete_return:
            # The actual terminal CAS and all role/Scope/Peer/OS/SDK original
            # decoders run. Only the return AFTER the complete save is lost.
            saved=WorldWebTerminal.save;lost=[]
            class LostCompleteReturn(RuntimeError):pass
            def save_then_lose(owner):
                saved(owner)
                if owner.state['phase']=='complete':
                    lost.append(deepcopy(owner.previous));raise LostCompleteReturn()
            with patch.object(WorldWebTerminal,'save',save_then_lose):
                with self.assertRaises(LostCompleteReturn):f.primary.terminal(finish)
            self.assertEqual(1,len(lost))
            rebuilt=WorldWebTerminal(f.primary)
            self.assertEqual(lost[0],rebuilt.previous)
            self.assertEqual('complete',rebuilt.state['phase'])
            self.assertIsNone(rebuilt.state['pending']);self.assertEqual(3,len(rebuilt.state['records']))
            end=deepcopy(rebuilt.state['end'])
            def originals():
                rows={}
                for root in {f.whole.scope.root,f.actor.root}:
                    for path in root.rglob('*'):
                        if path.is_file():
                            info=path.lstat()
                            rows[str(path)]=(info.st_dev,info.st_ino,info.st_mode,info.st_nlink,
                                info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                                hashlib.sha256(path.read_bytes()).hexdigest())
                return rows
            before=originals();native_before={role:model.native_calls for role,model in f.models.items()}
            requests_before=deepcopy(f.requests);stops_before=deepcopy(f.own);inputs_before=deepcopy(f.whole.domain.io.actions)
            # A newly constructed terminal must reach the historical complete
            # branch. These fatal guards reject any current-session fallback,
            # even an apparently harmless GET or an inactive fixture read.
            failure=AssertionError('Completed recovery must use retained originals')
            with (patch.object(f.runtime,'_sources',side_effect=failure),
                  patch.object(f.runtime,'_existing',side_effect=failure),
                  patch.object(f.runtime,'_retired_process_observer',side_effect=failure),
                  patch.object(f.runtime.adapter,'invoke',side_effect=failure),
                  patch.object(f.primary.phase,'status',side_effect=failure)):
                result=f.primary.terminal(finish)
                self.assertEqual(dict(stage='finish',end=end),result)
                self.assertEqual(result,canonical_end(f.primary,finish,result))
            self.assertEqual(before,originals())
            self.assertEqual(native_before,{role:model.native_calls for role,model in f.models.items()})
            self.assertEqual(requests_before,f.requests);self.assertEqual(stops_before,f.own)
            self.assertEqual(inputs_before,f.whole.domain.io.actions)
        else:end=f.primary.terminal(finish)['end']
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
