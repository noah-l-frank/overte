"""Actual proof-file CAS/recovery; role/native/window inputs are explicit models.

No product input, native observation or OS retirement can occur in these tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.self_tests.test_ios_world_web_terminal_seal import WorldWebTerminalSealTests as Fixture
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebTerminalSealRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def owner(self):
        owner=object.__new__(WorldWebTerminal);owner.flow=SimpleNamespace(run='a'*32)
        owner.store=PrivateFeatureState(self.f.root/'seal-coordinator.json');owner.previous=owner.store.read()
        owner.state=(owner.decode(owner.previous) if owner.previous is not None else dict(phase='inspected',description=self.f.description,
            seal=None,end=None,records=[],pending=None))
        owner.guard=lambda:need(same(owner.store.read(),owner.previous))
        owner.frames=OriginalFrameStore(self.f.root,BINDING,'a'*32,'primary',owner.guard,owner.intent,
            namespace='ios-world-web-terminal',schema_prefix='iosWorldWebTerminal')
        if owner.previous is None:owner.save();owner.write(dict(iosWorldWebTerminalRolesVersion=1,roles=self.f.roles))
        return owner

    def test_new_and_repeated_commit_read_actual_carrier_without_duplicate_write(self):
        owner=self.owner();measured=dict(source='actual storage sentinel');seal=self.f.seal(measured)
        self.assertEqual(dict(stage='seal',seal=seal),owner.commit_seal(self.f.samples,measured,seal,self.f.roles))
        self.assertEqual('sealed',owner.state['phase']);self.assertEqual(2,len(owner.state['records']))
        original=deepcopy(owner.previous);rebuilt=self.owner()
        with patch.object(rebuilt.frames,'write',side_effect=AssertionError('No repeated proof write')):
            self.assertEqual(dict(stage='seal',seal=seal),rebuilt.commit_seal(self.f.samples,measured,seal,self.f.roles))
        self.assertEqual(original,rebuilt.store.read())
        path=rebuilt.frames.path(rebuilt.frames.expand(rebuilt.state['records'][1]));replacement=path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):rebuilt.commit_seal(self.f.samples,measured,seal,self.f.roles)

    def test_precarrier_capacity_error_reuses_retained_originals_without_input_or_reset(self):
        owner=self.owner();measured=dict(largeArchivedGraph='x'*1200000);seal=self.f.seal(measured)
        owner.state['phase']='sealing';owner.save()
        with self.assertRaises(NativeUIError):owner.write(dict(iosWorldWebTerminalSealOriginalVersion=1,
            samples=self.f.samples,measured=measured,seal=seal))
        rebuilt=self.owner();self.assertEqual('sealing',rebuilt.state['phase'])
        self.assertIsNone(rebuilt.state['pending']);self.assertEqual(1,len(rebuilt.state['records']))
        rebuilt.recover();self.assertEqual(dict(stage='seal',seal=seal),rebuilt.commit_seal(self.f.samples,measured,seal,self.f.roles))
        self.assertEqual(2,len(rebuilt.state['records']));self.assertLess(rebuilt.state['records'][-1]['bytes'],10000)

    def test_lost_saved_return_recovers_actual_inode_and_never_rewrites_the_original(self):
        owner=self.owner();measured=dict(source='real saved carrier');seal=self.f.seal(measured);intent=owner.intent
        class LostReturn(RuntimeError):pass
        def losing(kind,value):
            intent(kind,value)
            if value['index']==2 and value['phase']=='saved':raise LostReturn('Actual saved notification lost')
        owner.frames.intent=losing
        with self.assertRaises(LostReturn):owner.commit_seal(self.f.samples,measured,seal,self.f.roles)
        rebuilt=self.owner();self.assertEqual('saved',rebuilt.state['pending']['phase']);self.assertEqual(1,len(rebuilt.state['records']))
        reference=deepcopy(rebuilt.state['pending']);path=rebuilt.frames.path(reference);identity=path.stat().st_ino
        with patch.object(rebuilt.frames,'write',side_effect=AssertionError('Uncertain original cannot be resent')):
            rebuilt.recover();self.assertEqual(dict(stage='seal',seal=seal),rebuilt.commit_seal(self.f.samples,measured,seal,self.f.roles))
        self.assertEqual(identity,path.stat().st_ino);self.assertEqual(reference['sha256'],rebuilt.state['records'][-1]['sha256'])

    def test_unknown_planned_delivery_stays_owned_and_cannot_recreate_a_file(self):
        owner=self.owner();measured={};seal=self.f.seal(measured);intent=owner.intent
        class LostReturn(RuntimeError):pass
        def losing(kind,value):
            intent(kind,value)
            if value['index']==2 and value['phase']=='planned':raise LostReturn('No actual inode observed')
        owner.frames.intent=losing
        with self.assertRaises(LostReturn):owner.commit_seal(self.f.samples,measured,seal,self.f.roles)
        rebuilt=self.owner();before=deepcopy(rebuilt.previous);self.assertEqual('planned',rebuilt.state['pending']['phase'])
        self.assertFalse(rebuilt.frames.path(rebuilt.state['pending']).exists())
        with self.assertRaises(NativeUIError):rebuilt.recover()
        with self.assertRaises(NativeUIError):rebuilt.commit_seal(self.f.samples,measured,seal,self.f.roles)
        self.assertEqual(before,rebuilt.store.read())


if __name__=='__main__':unittest.main()
