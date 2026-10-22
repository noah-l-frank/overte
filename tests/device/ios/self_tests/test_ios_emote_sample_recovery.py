"""Original GPU retirement after lost reads, including untouched reservations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery,validate_abandonment
from ios.self_tests import test_ios_emote_samples as sample_fixture
from ios.self_tests.test_ios_graphics_measurements import HOST,RUN,TICKET


class SampleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sample_fixture.SamplesTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.sequence=0
        def status(_previous=None):
            self.sequence+=1;now=HOST+self.fixture.gpu.clock*1000
            return dict(fixturePhaseVersion=1,instance='3'*32,sequence=self.sequence,requestId=format(self.sequence,'032x'),runId=RUN,
                area='emotes',capturedEpochMs=now,active=True,createdEpochMs=HOST-1000,retiredEpochMs=None,
                activations=[dict(sequence=1,ticket=TICKET,activatedEpochMs=HOST-900,stimulus=dict(verb='baseline',inputs={}))])
        self.fixture.phase.status=status
    def owner(self):return self.fixture.owner()
    def lose_read(self):
        real=self.fixture.gpu.send
        def lost(query):
            real(query)
            if query['operation']=='read':raise OSError('Synthetic actual issued read return lost')
        self.fixture.gpu.send=lost
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        self.fixture.gpu.send=real
    def test_lost_read_drains_original_gpu_and_retains_partial_host_inode_without_replaying_capture(self):
        self.lose_read();owner=self.owner();request=owner.state['rows'][-1]['requestId']
        partial=owner.root/owner.owner(owner.state['rows'][-1]).name;identity=partial.stat().st_ino
        recovery=IOSEmoteSampleRecovery(owner);self.assertTrue(recovery.recover())
        rebuilt=self.owner();row=rebuilt.state['rows'][-1];self.assertEqual('abandoned',row['phase'])
        sample=rebuilt.record(row);frame=unpack(sample['payload'])[0];self.assertEqual(0,frame['partialFile']['bytes'])
        self.assertEqual(identity,partial.stat().st_ino);self.assertEqual(request,sample['requestId'])
        self.assertEqual(1,sum(q['operation']=='read' for q in self.fixture.gpu.commands))
        self.assertEqual(1,sum(q['operation']=='release' for q in self.fixture.gpu.commands))
        with self.assertRaises(NativeUIError):rebuilt.archive(row)
        self.assertTrue(IOSEmoteSampleRecovery(rebuilt).recover())
    def test_failure_before_native_owner_creation_retires_only_reserved_identity_and_allocates_no_pixels(self):
        def lost_world(_):raise OSError('Synthetic world original lost before GPU acquisition')
        self.fixture.world=lost_world
        with self.assertRaises(OSError):self.owner().capture(TICKET)
        owner=self.owner();self.assertIsNone(owner.owner(owner.state['rows'][-1]).store.read())
        recovery=IOSEmoteSampleRecovery(owner);self.assertTrue(recovery.recover())
        row=self.owner().state['rows'][-1];sample=self.owner().record(row);frame=unpack(sample['payload'])[0]
        self.assertIsNone(unpack(sample['owner'])[0]);self.assertIsNone(frame['partialFile'])
        self.assertEqual('release',frame['inspection']['command']['operation'])
        self.assertEqual(0,sum(q['operation']=='read' for q in self.fixture.gpu.commands))
        self.assertEqual(1,sum(q['operation']=='release' for q in self.fixture.gpu.commands))
    def test_lost_native_retirement_return_uses_new_inspection_and_never_releases_twice(self):
        def lost_world(_):raise OSError('Synthetic original lost before owner creation')
        self.fixture.world=lost_world
        with self.assertRaises(OSError):self.owner().capture(TICKET)
        real=self.fixture.gpu.send
        def lost_release(query):
            real(query)
            if query['operation']=='release':raise OSError('Synthetic lost actual retirement return')
        self.fixture.gpu.send=lost_release
        with self.assertRaises(NativeUIError):IOSEmoteSampleRecovery(self.owner()).recover()
        self.fixture.gpu.send=real
        self.assertTrue(IOSEmoteSampleRecovery(self.owner()).recover())
        self.assertEqual(1,sum(q['operation']=='release' for q in self.fixture.gpu.commands))
        self.assertEqual(1,sum(q['operation']=='inspect' for q in self.fixture.gpu.commands))
        self.assertEqual(0,sum(q['operation']=='read' for q in self.fixture.gpu.commands))
    def test_lost_final_owner_metadata_return_adopts_original_retirement_without_new_native_read(self):
        self.lose_read();owner=self.owner();recovery=IOSEmoteSampleRecovery(owner);save=recovery.save
        def lost():
            if owner.state['phase']=='ready':raise OSError('Synthetic lost final retirement metadata return')
            save()
        with patch.object(recovery,'save',side_effect=lost),self.assertRaises(OSError):recovery.recover()
        before=len(self.fixture.gpu.commands);rebuilt=IOSEmoteSampleRecovery(self.owner())
        self.assertTrue(rebuilt.recover());self.assertEqual(before,len(self.fixture.gpu.commands))
        self.assertEqual(1,len(rebuilt.state['records']))
    def test_changed_retained_empty_inode_cannot_be_claimed_as_quiet_cleanup(self):
        self.lose_read();owner=self.owner();IOSEmoteSampleRecovery(owner).recover();row=owner.state['rows'][-1]
        path=owner.root/owner.owner(row).name;path.write_bytes(b'foreign partial bytes')
        with self.assertRaises(NativeUIError):self.owner()


if __name__=='__main__':unittest.main()
