"""Actual guarded Pico role factory, without native rendering or device access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import test_normal_scripts as existing
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.world_render_receipts import NativeWorldReceiptBatchFiles


class PicoGraphicsCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter=self.fixture.instance;self.native=self.fixture.native
        self.facade=PicoGraphicsBinding(self.adapter);self.lock=self.facade._lock(self.native.target)

    def source(self,role):
        return self.adapter._world_render_capture(self.native.target,read_only=True,role=role,
            require_frame_view=True,source_lock=self.lock)

    def test_role_camera_native_inventory_and_original_session_are_explicit(self):
        with self.lock.held():
            primary=self.source('primary');actor=self.source('actor')
            self.assertEqual(2,primary.owner.version);self.assertEqual('primary',primary.owner.role)
            self.assertEqual('actor',actor.owner.role);self.assertNotEqual(primary.owner.store.path,actor.owner.store.path)
            self.assertEqual('123:synthetic-start',primary.owner.binding['processIdentity'])
            self.assertTrue(primary.capture.stereo);self.assertTrue(primary.capture.require_cameras)
            self.assertIsInstance(primary.receipts,NativeWorldReceiptBatchFiles)
            self.assertIs(self.lock,primary.source_lock);self.assertIs(self.lock,actor.source_lock)
            self.assertIsNone(primary.owner.store.read());self.assertIsNone(actor.owner.store.read())
        self.assertEqual([],self.native.inputs)

    def test_an_unresolved_role_blocks_other_roles_and_legacy_capture_without_overwrite(self):
        with self.lock.held():
            primary=self.source('primary');primary.owner.intent(dict(schemaVersion=1,commandId='a'*32,action='feature-world-render-observe'))
            original=deepcopy(primary.owner.owned());actor=self.source('actor')
            with self.assertRaises(RuntimeError):actor.read(0)
            self.assertIsNone(actor.owner.store.read());self.assertEqual(original,primary.owner.owned())
        legacy=self.adapter._world_render_capture(self.native.target)
        with self.assertRaises(RuntimeError):legacy.read(0)
        self.assertIsNone(legacy.owner.store.read());self.assertEqual(original,primary.owner.store.read())
        self.assertEqual([],self.native.inputs)

    def test_missing_explicit_role_lock_or_camera_requirement_is_refused_before_capture(self):
        for changes in (dict(source_lock=None),dict(read_only=False),dict(require_frame_view=False),dict(role='peer')):
            arguments=dict(read_only=True,role='primary',require_frame_view=True,source_lock=self.lock);arguments.update(changes)
            with self.subTest(changes=list(changes)),self.assertRaises((ValueError,RuntimeError)):
                self.adapter._world_render_capture(self.native.target,**arguments)
        with self.assertRaises((ValueError,RuntimeError)):self.source('primary')
        self.assertEqual([],self.native.inputs)

    def test_candidate_loss_keeps_original_role_journal_and_performs_no_cleanup_io(self):
        with self.lock.held():
            primary=self.source('primary');primary.owner.intent(dict(schemaVersion=1,commandId='a'*32,action='feature-world-render-observe'))
            original=deepcopy(primary.owner.owned());self.native.digest='f'*64
            with self.assertRaises(RuntimeError):primary.release()
            self.assertEqual(original,primary.owner.store.read());self.assertEqual([],self.native.inputs)


if __name__=='__main__':unittest.main()
