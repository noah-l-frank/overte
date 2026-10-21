"""Restored-world pixels require actual camera, original PNG and one-send ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_restored_frame import IOSGraphicsRestoredFrame
from ios.self_tests.test_ios_graphics_samples import SamplesHarness
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from self_tests.test_completed_frame_lease import BINDING


class RestoredFrameTests(SamplesHarness,unittest.TestCase):
    def prepare(self):
        scene=self.scene();scene.prepare();self.original=dict(subject=deepcopy(scene.state['original']['subject']),restart=None)
        scene.restore();self.floors=dict(subject=deepcopy(scene.state['subject']),loads=deepcopy(scene.state['loads']),native=self.sdk.core_reader().read(0))
        self.graphics=deepcopy(self.floors['native']['graphics']);self.source=self.gpu.source
        def source(packet):
            self.source(packet)
            if 'renderTrace' in packet.get('source',{}):
                # This model samples actual SDK camera/pose. The adapter does
                # not transmit original/expected camera coordinates to it.
                current=self.sdk.subject_reader().read(RUN,require_avatar=True,require_camera=True)['source']['view']
                packet['source']['renderTrace']['recordedView'].update({k:deepcopy(current[k]) for k in ('position','rotation','fieldOfViewDegrees','aspectRatio')})
        self.gpu.source=source
        return self.owner()
    def owner(self,role='primary',**changes):
        values=dict(adapter=self.adapter,selector='owned',run=RUN,role=role,stage=0,lock=self.lock,root=self.root/'pixels',binding=BINDING,
            original=self.original,floors=self.floors,graphics=self.graphics,epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.clock)
        return IOSGraphicsRestoredFrame(**(values|changes))
    def archive(self,owner,value,record):
        return IOSGraphicsRestoredFrame.archive(value,record,path=owner.store.path,lock=self.lock,root=owner.root,run=RUN,role=owner.role,
            stage=owner.stage,binding=owner.binding,original=owner.original,floors=owner.floors,graphics=owner.graphics)

    def test_both_roles_keep_separate_actual_original_world_images_and_native_clocks(self):
        with self.lock.held():
            primary=self.prepare();left,raw=primary.capture(TICKET);actor=self.owner('actor');right,other=actor.capture(TICKET)
            self.assertEqual('look at',left['subjectAfter']['source']['view']['mode']);self.assertEqual([4.,0.,2.],left['subjectAfter']['source']['avatarPose']['feetPosition'])
            self.assertEqual([],left['subjectAfter']['source']['entities']);self.assertTrue(raw);self.assertTrue(other)
            self.assertNotEqual(left['capture']['requestId'],right['capture']['requestId'])
            self.assertNotEqual(left['clockJoin']['nativeBefore']['requestId'],right['clockJoin']['nativeBefore']['requestId'])
            self.assertLess(left['clockJoin']['hostAfterEpochMs'],left['clockJoin']['nativeBefore']['capturedEpochMs'])
            count=len(self.gpu.commands);self.assertEqual((left,raw),self.owner().capture(TICKET));self.assertEqual(count,len(self.gpu.commands))
            value,record=primary.previous,primary.record.read();primary.store.discard(value)
            store=primary.owner().store;store.discard(store.read())
            self.sdk.running=False;self.sdk.clock+=100
            with patch.object(self.adapter,'normal_feature_runtime',side_effect=AssertionError('No live SDK during archive')):
                self.assertEqual((left,raw),self.archive(primary,value,record))

    def test_stale_fixture_camera_pixels_cannot_claim_original_camera_restoration(self):
        with self.lock.held():
            owner=self.prepare();self.gpu.source=self.source
            with self.assertRaises(NativeUIError):owner.capture(TICKET)
            self.assertEqual('reading',self.owner().state['phase']);self.assertIsNone(owner.record.read())
            count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
            self.assertEqual(count,len(self.gpu.commands))

    def test_lost_capture_releases_its_actual_native_buffers_and_never_recaptures(self):
        with self.lock.held():
            owner=self.prepare();self.gpu.lost=True
            with self.assertRaises(NativeUIError):owner.capture(TICKET)
            self.assertEqual(1,sum(row['operation']=='read' for row in self.gpu.commands))
            self.gpu.lost=False;count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual('released',owner.owner().store.read()['phase'])

    def test_lost_committed_record_return_adopts_exact_original_without_a_new_read(self):
        with self.lock.held():
            owner=self.prepare();write=owner.record.write
            def lost(value,previous):write(value,previous);raise OSError('Synthetic lost committed image record return')
            with patch.object(owner.record,'write',side_effect=lost),self.assertRaises(OSError):owner.capture(TICKET)
            count=len(self.gpu.commands);record=owner.record.read();recovered=self.owner();row,raw=recovered.capture(TICKET)
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual(record,recovered.record.read());self.assertTrue(raw)
            self.assertEqual('ready',recovered.state['phase']);self.assertEqual(row['capture']['processId'],42)

    def test_changed_original_pixels_and_foreign_role_records_fail_after_metadata_removal(self):
        with self.lock.held():
            owner=self.prepare();row,_raw=owner.capture(TICKET);value,record=owner.previous,owner.record.read();owner.store.discard(value)
            changed=deepcopy(record);changed['requestId']='ios-'+'e'*32
            with self.assertRaises(NativeUIError):self.archive(owner,value,changed)
            (owner.root/row['owner']['name']).write_bytes(b'Foreign pixels')
            with self.assertRaises(NativeUIError):self.archive(owner,value,record)


class RestoredRestartTests(unittest.TestCase):
    def test_restart_preserves_original_old_world_and_joins_actual_new_process_pixels(self):
        from ios.self_tests.test_ios_graphics_restart import RestartHarness
        class Case(RestartHarness,unittest.TestCase):pass
        case=Case();case.setUp()
        try:
            with case.lock.held():
                restart=case.prepare();restart.act(case.call());scene=case.scene()
                from ios.adapters.graphics_preferences import IOSGraphicsPreferences
                prefs=IOSGraphicsPreferences(scene,monotonic=lambda:case.sdk.clock,sleep=case.sdk.sleep)
                prefs.cleanup();scene.restore()
                original=dict(subject=deepcopy(scene.state['original']['subject']),restart=deepcopy(restart.state['receipt']))
                floors=dict(subject=deepcopy(scene.state['subject']),loads=deepcopy(scene.state['loads']),native=case.sdk.core_reader().read(0))
                source=case.gpu.source
                def actual(packet):
                    source(packet)
                    if 'renderTrace' in packet.get('source',{}):
                        view=case.sdk.subject_reader().read(RUN,require_avatar=True,require_camera=True)['source']['view']
                        packet['source']['renderTrace']['recordedView'].update({k:deepcopy(view[k]) for k in ('position','rotation','fieldOfViewDegrees','aspectRatio')})
                case.gpu.source=actual
                owner=IOSGraphicsRestoredFrame(case.adapter,'owned',RUN,'primary',1,case.lock,case.root/'pixels',
                    BINDING|dict(processIdentity='43'),original,floors,floors['native']['graphics'],epoch_ms=case.sdk.host_epoch,monotonic=lambda:case.sdk.clock)
                row,raw=owner.capture(TICKET)
                self.assertEqual(42,owner.original['subject']['processId']);self.assertEqual(43,row['capture']['processId'])
                self.assertEqual('look at',row['subjectAfter']['source']['view']['mode']);self.assertTrue(raw)
                self.assertEqual(['app.stop','app.launch'],case.inputs)
        finally:case.doCleanups()


if __name__=='__main__':unittest.main()
