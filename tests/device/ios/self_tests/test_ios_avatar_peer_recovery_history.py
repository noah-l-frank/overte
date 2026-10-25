"""Closed peer recovery prefixes retain private files and cannot mutate live WALs.

Receiver/renderer/native packets are explicit existing fixture models. All
filesystem ownership, writes, inodes and historical readers are actual.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources
from ios.self_tests import test_ios_peer_source_recovery as fixture
from ios.self_tests.test_ios_avatar_peer_sources import frame as avatar_frame


class AvatarPeerRecoveryHistoryTests(unittest.TestCase):
    def setup_case(self, profile='emote'):
        f = fixture.PeerRecoveryTests()
        f.setUp()
        self.addCleanup(f.tearDown)
        if profile == 'avatar':
            f.source = f.owner('avatar', 'primary')
            f.source.historical = False
            f.source.save()
        return f

    def historical(self, f, value):
        class Frozen(PrivateFeatureState):
            def read(_self):
                return deepcopy(value)
            def write(_self, *_args):
                raise AssertionError('Historical source may not write')
        return OriginalAvatarPeerSources(Frozen(f.source.store.path), f.root,
            f.source.binding, f.source.run, None, f.lock, lambda: True,
            profile=f.source.profile, role=f.source.role, historical=True,
            phase_changed=f.source.phase_changed)

    def test_actual_later_abandonment_preserves_each_closed_profiles_old_prefix(self):
        for profile in ('emote', 'avatar'):
            with self.subTest(profile=profile):
                f = self.setup_case(profile)
                f.append(avatar_frame() if profile == 'avatar' else fixture.original())
                f.pending()
                recovery = OriginalAvatarPeerRecovery(f.source)
                recovery.recover()
                source, old = deepcopy(f.source.previous), deepcopy(recovery.previous)
                f.pending()
                latest = OriginalAvatarPeerRecovery(f.source)
                latest.recover()
                self.assertEqual(2, len(latest.state['records']))
                owned = {p: (p.stat().st_ino, p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
                archive = OriginalAvatarPeerRecovery.archive(old, self.historical(f, source))
                self.assertEqual(old, archive.previous)
                self.assertEqual(1, len(archive.state['records']))
                self.assertTrue(archive.follow(archive.sources.frames[0], historical=True))
                self.assertEqual(owned, {p: (p.stat().st_ino, p.read_bytes()) for p in owned})
                with self.assertRaises(NativeUIError):
                    latest.decode(old)

    def test_historical_recovery_cannot_save_or_recover_a_live_journal(self):
        f = self.setup_case()
        f.pending()
        recovery = OriginalAvatarPeerRecovery(f.source)
        recovery.recover()
        archive = OriginalAvatarPeerRecovery.archive(recovery.previous, self.historical(f, f.source.previous))
        raw, inode = recovery.store.path.read_bytes(), recovery.store.path.stat().st_ino
        for name, function in (('save', archive.save), ('recover', archive.recover)):
            with self.subTest(entrypoint=name), self.assertRaises(NativeUIError):
                function()
        self.assertEqual((raw, inode), (recovery.store.path.read_bytes(), recovery.store.path.stat().st_ino))

    def test_actual_planned_symlink_remains_owned_and_cannot_be_cleared(self):
        f = self.setup_case('avatar')
        f.pending()
        intent = f.source.originals.intent
        def lost(kind, value):
            intent(kind, value)
            if kind == 'original' and value['phase'] == 'planned':
                f.source.originals.path(value).symlink_to(f.root/'missing-original-target')
                raise OSError('Explicit lost planned-original return')
        with patch.object(f.source.originals, 'intent', lost), self.assertRaises(OSError):
            f.source.originals.write(1, avatar_frame())
        prior = deepcopy(f.source.previous)
        with self.assertRaises(NativeUIError):
            OriginalAvatarPeerRecovery(f.source).recover()
        self.assertEqual(prior, f.source.store.read())

    def test_current_archive_and_absent_live_parent_refuse_unknown_next_record(self):
        f = self.setup_case()
        f.pending()
        recovery = OriginalAvatarPeerRecovery(f.source)
        recovery.recover()
        prior = deepcopy(recovery.previous)
        f.pending()
        latest = OriginalAvatarPeerRecovery(f.source)
        latest.recover()
        latest.store.write(prior, latest.previous)
        with self.assertRaises(NativeUIError):
            OriginalAvatarPeerRecovery.archive(prior, f.source)
        latest.store.path.unlink()
        with self.assertRaises(NativeUIError):
            OriginalAvatarPeerRecovery(f.source)

    def test_actual_current_journal_cannot_change_during_archival(self):
        f = self.setup_case()
        f.pending()
        recovery = OriginalAvatarPeerRecovery(f.source)
        recovery.recover()
        record = OriginalAvatarPeerRecovery.record
        changed = []
        def mutate(reader, reference):
            value = record(reader, reference)
            if not changed:
                changed.append(True)
                replacement = deepcopy(recovery.previous)
                replacement['payload'] = pack([dict(records=[], pending=None)])
                recovery.store.write(replacement, recovery.previous)
            return value
        with patch.object(OriginalAvatarPeerRecovery, 'record', mutate), self.assertRaises(NativeUIError):
            OriginalAvatarPeerRecovery.archive(recovery.previous, self.historical(f, f.source.previous))
        self.assertTrue(changed)


if __name__ == '__main__':
    unittest.main()
