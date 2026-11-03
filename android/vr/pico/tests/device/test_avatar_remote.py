"""Actual Pico cleanup preflight over retained independent remote originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
import test_normal_emote as existing
from adapters.pico4.avatar_remote_state import source_store


class RemoteAvatarBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.PicoEmoteTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def test_missing_root_original_or_prepared_remote_file_blocks_every_cleanup_query_and_input(self):
        f=self.fixture; adapter,native=f.instance,f.native
        store=source_store(adapter,native.target,'d'*32)
        for suffix in ('','.pending-original','.frame-000.json'):
            with self.subTest(suffix=suffix):
                path=store.path.with_name(store.path.name+suffix)
                path.write_bytes(b'original remote observation responsibility\n'); path.chmod(0o600)
                before=(list(native.events),list(native.inputs),list(native.controllers),native.running)
                with patch.object(native,'read_debug_app_file',side_effect=AssertionError('No Native query')) as read, \
                     patch.object(native,'write_debug_app_file',side_effect=AssertionError('No Native input')) as write:
                    with self.assertRaises(ValueError): adapter.cleanup(native.target)
                    self.assertEqual(0,read.call_count); self.assertEqual(0,write.call_count)
                self.assertEqual(before,(native.events,native.inputs,native.controllers,native.running))
                self.assertEqual(b'original remote observation responsibility\n',path.read_bytes())
                if suffix: self.assertFalse(store.path.exists())
                path.unlink()  # Only this test's created artifact.


def load_tests(loader, _tests, _pattern):
    # Imported fixture modules provide setup only; select every owning case once.
    return loader.loadTestsFromNames([
        'self_tests.test_pico_avatar_remote.RemoteAvatarTests',
        'self_tests.test_pico_remote_joint_pose.ProducerSourceTests',
        'self_tests.test_pico_remote_joint_pose.RemoteJointPoseTests',
        __name__ + '.RemoteAvatarBindingTests',
    ])


if __name__ == '__main__': unittest.main()
