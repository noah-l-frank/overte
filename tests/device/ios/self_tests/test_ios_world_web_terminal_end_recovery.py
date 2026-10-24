"""Actual terminal WAL/carrier recovery with explicitly modeled end evidence.

The end grammar values below are sentinels, not measured OS/native facts.
No SDK, fixture HTTP, Stop or native getter is available in this test harness.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys import terminal
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.self_tests.test_ios_world_web_terminal_seal_recovery import WorldWebTerminalSealRecoveryTests as Fixture


class WorldWebTerminalEndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def owner(self):
        owner=self.f.owner()
        if owner.state['phase']=='inspected':
            measured={};seal=self.f.f.seal(measured)
            owner.commit_seal(self.f.f.samples,measured,seal,self.f.f.roles)
            owner.state['phase']='ending';owner.save()
        return owner

    def end(self,owner):
        roles={}
        for role,prior in owner.state['seal']['description']['roles'].items():
            # The fixture uses one logical binding. Its stop/SDK must agree;
            # each role still supplies a distinct OS original grammar value.
            quiet=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',
                instance=digest([role,'modeled-instance'])[:32],processId=int(prior['binding']['processIdentity']),
                samples=3,originalSha256=digest([role,'modeled-os']),
                hostAfterFirstEpochMs=100000,hostBeforeLastEpochMs=103500,
                hostAfterFirstMonotonic=10.,hostBeforeLastMonotonic=13.5,
                osAfterFirstEpochMs=100000,osBeforeLastEpochMs=103500,
                osAfterFirstMonotonicMs=10000,osBeforeLastMonotonicMs=13500)
            roles[role]=dict(binding=deepcopy(prior['binding']),heldOriginalSha256=prior['originalSha256'],
                stopOriginalSha256=digest(['modeled-stop']),osAbsence=quiet,
                sdkDeletionOriginalSha256=digest(['modeled-sdk']),archiveSha256=digest([role,'modeled-archive']))
        value=dict(featureTerminalEndVersion=1,seal=deepcopy(owner.state['seal']),roles=roles)
        terminal.ended(value,owner.state['seal']);return value

    def test_committed_carrier_before_complete_cas_is_reopened_without_rewrite(self):
        owner=self.owner();end=self.end(owner)
        owner.write(dict(iosWorldWebTerminalEndOriginalVersion=1,end=end))
        rebuilt=self.owner();before=deepcopy(rebuilt.state['records'])
        with patch.object(rebuilt.frames,'write',side_effect=AssertionError('No repeated end carrier')):
            self.assertEqual(dict(stage='finish',end=end),rebuilt.commit_end(end))
        self.assertEqual(before,rebuilt.state['records']);self.assertEqual('complete',rebuilt.state['phase'])
        original=deepcopy(rebuilt.previous)
        self.assertEqual(dict(stage='finish',end=end),self.owner().commit_end(end))
        self.assertEqual(original,rebuilt.store.read())

    def test_saved_return_loss_recovers_exact_inode_then_commits_without_new_write(self):
        owner=self.owner();end=self.end(owner);intent=owner.intent
        class LostReturn(RuntimeError):pass
        def losing(kind,value):
            intent(kind,value)
            if value['index']==3 and value['phase']=='saved':raise LostReturn()
        owner.frames.intent=losing
        with self.assertRaises(LostReturn):owner.commit_end(end)
        rebuilt=self.owner();pending=deepcopy(rebuilt.state['pending']);path=rebuilt.frames.path(pending)
        identity=path.stat().st_ino
        with patch.object(rebuilt.frames,'write',side_effect=AssertionError('No end retry write')):
            rebuilt.recover();self.assertEqual(dict(stage='finish',end=end),rebuilt.commit_end(end))
        self.assertEqual(identity,path.stat().st_ino);self.assertEqual(3,len(rebuilt.state['records']))

    def test_replaced_end_inode_or_changed_replayed_end_cannot_complete(self):
        owner=self.owner();end=self.end(owner);owner.write(dict(iosWorldWebTerminalEndOriginalVersion=1,end=end))
        changed=deepcopy(end);changed['roles']['actor']['archiveSha256']=digest(['different'])
        with self.assertRaises(NativeUIError):owner.commit_end(changed)
        path=owner.frames.path(owner.frames.expand(owner.state['records'][2]));replacement=path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):owner.commit_end(end)
        self.assertEqual('ending',self.owner().state['phase'])

    def test_planned_end_without_observed_birth_remains_owned(self):
        owner=self.owner();end=self.end(owner);intent=owner.intent
        class LostReturn(RuntimeError):pass
        def losing(kind,value):
            intent(kind,value)
            if value['index']==3 and value['phase']=='planned':raise LostReturn()
        owner.frames.intent=losing
        with self.assertRaises(LostReturn):owner.commit_end(end)
        rebuilt=self.owner();before=deepcopy(rebuilt.previous)
        with self.assertRaises(NativeUIError):rebuilt.recover()
        with self.assertRaises(NativeUIError):rebuilt.commit_end(end)
        self.assertEqual(before,rebuilt.store.read())

    def test_finish_with_recovered_end_uses_historical_roles_without_fixture_or_stop(self):
        owner=self.owner();end=self.end(owner)
        owner.write(dict(iosWorldWebTerminalEndOriginalVersion=1,end=end))
        rebuilt=self.owner()
        @contextmanager
        def held():yield
        def forbidden():raise AssertionError('Recovered end must not query an inactive fixture')
        rebuilt.held=held;rebuilt.flow.role='primary';rebuilt.flow.phase=SimpleNamespace(status=forbidden)
        rebuilt.actor=SimpleNamespace(role='actor')
        rebuilt.roles=lambda saved,historical: (deepcopy(self.f.f.roles),{})
        rebuilt.descriptor=lambda roles:deepcopy(self.f.f.description)
        rebuilt.live=lambda samples,roles,parts,historical: {}
        # Role/end native proofs and their inventory are explicit sentinels;
        # this case isolates real end-carrier recovery and dispatch ordering.
        with (patch('ios.adapters.world_web_terminal_end.role_end',side_effect=lambda flow,sha:deepcopy(end['roles'][flow.role])),
              patch('ios.adapters.world_web_terminal.read_current_end'),
              patch('ios.adapters.world_web_terminal.WorldWebRootedInventory')):
            self.assertEqual(dict(stage='finish',end=end),rebuilt.finish(end['seal']))
        self.assertEqual('complete',rebuilt.state['phase'])

    def test_inspect_recovers_first_carrier_and_requalifies_before_phase_commit(self):
        owner=self.f.owner();owner.state.update(phase='inspecting');owner.save()
        roles=deepcopy(self.f.f.roles);calls=[]
        @contextmanager
        def held():yield
        def requalify(previous=None):
            calls.append(previous);self.assertEqual(roles,previous);return roles,{}
        owner.held=held;owner.roles=requalify;owner.descriptor=lambda value:deepcopy(self.f.f.description)
        owner.monotonic=time.monotonic
        owner.flow.run='a'*32
        with patch('ios.adapters.world_web_terminal.WorldWebRootedInventory'):
            result=owner.invoke(dict(contractVersion=1,runId='a'*32,stage='inspect'))
        self.assertEqual(dict(stage='inspect',description=self.f.f.description),result)
        self.assertEqual('inspected',owner.state['phase']);self.assertEqual(1,len(owner.state['records']))
        self.assertEqual(2,len(calls))


if __name__=='__main__':unittest.main()
