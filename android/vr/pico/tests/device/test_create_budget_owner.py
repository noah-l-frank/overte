"""Actual native collector capacity counterexample for composed v16 owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid
import json
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from feature_journeys.scenarios import SCENARIOS
from adapters.normal_ui import NativeUIError
import test_create_voxel_owner as voxel
import test_create_journey as parent
import test_create_recovery_owner as recovery
import test_create_rez_owner as rez


class CreateCompleteTests(unittest.TestCase):
    make=recovery.CreateRecoveryTests.make
    act=recovery.CreateRecoveryTests.act
    def _before_prepare(self):
        voxel.CreateVoxelJourneyTests._before_prepare(self)
        recovery.CreateRecoveryTests._before_prepare(self)
        original=parent.AdapterActor._native_feature_observer
        def native(adapter,target):
            value=original(adapter,target);send=value.send
            def deliver(command):
                # The original compact file actor used a fixed 20000 epoch.
                # This composed actor shares the advancing native source clock.
                send(command);packet=json.loads(adapter.file_raw)
                packet.update(requestedEpochMs=adapter.b.epoch(),capturedEpochMs=adapter.b.epoch())
                adapter.file_raw=json.dumps(packet)
            value.send=deliver;return value
        boundary=patch.object(parent.AdapterActor,'_native_feature_observer',native);boundary.start();self.addCleanup(boundary.stop)
    def setUp(self):
        voxel.CreateVoxelJourneyTests.setUp(self)
        rez.CreateRezOwnerTests.attach_rez(self)
    def test_original_native_capacity_refusal_preserves_pending_without_replay_or_retirement(self):
        # Mirror the independently compiled original TSI collector's exact 512
        # command inventory. The formerly compact actors had no native cap.
        original=self.b.reader;self.b.refused=set()
        def reader(kind):
            native=original(kind);send=native.send
            def deliver(command):
                if self.b.sequence[kind]>=512:
                    self.b.refused.add(kind);self.b.frames[kind]='{}';return
                send(command)
            native.send=deliver;return native
        self.b.reader=reader;self.make()
        steps=SCENARIOS['create']['steps'];self.assertEqual(21,len(steps))
        # Keep the unchanged original input order through all Model/Picker and
        # PolyVox steps. Additional genuine passive observations consume the
        # remaining inventory; no counter or original timestamp is reset.
        for step in steps[:15]:self.act(step['verb'],step['inputs']);self.make()
        self.assertEqual(15,len(self.root.state()['calls']))
        roles=('entities','callbacks','dialogs')
        while max(self.b.sequence[k] for k in roles)<512:self.root.invoke('sample')
        count=len(self.b.inputs);step=steps[15];self.assertEqual('set-rez-permission',step['verb'])
        with self.assertRaises(NativeUIError):self.act(step['verb'],step['inputs'])
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(16,len(self.root.state()['calls']))
        self.assertTrue(self.b.refused);self.assertEqual(512,max(self.b.sequence[k] for k in ('entities','callbacks','dialogs')))
        pending=self.root.state()['pending'];self.assertIsNotNone(pending);count=len(self.b.inputs)
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(count,len(self.b.inputs))
        self.reader.activate(uuid.uuid4().hex,'cleanup',{});self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(count,len(self.b.inputs))
        self.assertTrue(self.root.owned_target(self.adapter,self.adapter.target))
        self.assertEqual(self.actor.original,self.actor.server.security)


if __name__=='__main__':unittest.main()
