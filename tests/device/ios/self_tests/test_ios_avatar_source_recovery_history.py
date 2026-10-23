"""Historical source recovery is an immutable prefix, never a live writer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_reads
from adapters.script_feature.history import pack
from ios.adapters.avatar_observation import source_history
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.self_tests import test_ios_avatar_source_recovery as fixture


class AvatarSourceRecoveryHistoryTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.AvatarSourceRecoveryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def completed(self):
        source = self.f.interrupt()
        recovery = IOSAvatarSourceRecovery(source)
        recovery.recover()
        source = self.f.sources()
        recovery = IOSAvatarSourceRecovery(source)
        frame = source.read()
        recovery.follow(frame)
        return source, recovery, frame

    def history(self, source, recovery):
        return source_history(source, recovery, store=PrivateFeatureState(self.f.path/'ios-avatar-primary-sources.json'),
            root=self.f.root, binding=fixture.BINDING, run=self.f.fixture.run,
            role='primary', lock=self.f.lock)

    def test_later_actual_abandonment_does_not_invalidate_older_source_and_recovery_bytes(self):
        with self.f.lock.held():
            source, recovery, first = self.completed()
            prior_source, prior_recovery = deepcopy(source.previous), deepcopy(recovery.previous)
            fresh, latest, second = self.completed()
            self.assertEqual(2, len(latest.state['records']))
            self.assertTrue(latest.follow(second))
            counts, sequence = deepcopy(self.f.fixture.sources), self.f.fixture.core.sequence
            files = {p: (p.stat().st_ino, p.read_bytes()) for p in self.f.root.rglob('*') if p.is_file()}
            historical, error = None, None
            try:
                historical = self.history(prior_source, prior_recovery)
            except NativeUIError as failure:
                error = failure
            self.assertEqual(counts, self.f.fixture.sources)
            self.assertEqual(sequence, self.f.fixture.core.sequence)
            self.assertEqual(files, {p: (p.stat().st_ino, p.read_bytes()) for p in files})
        self.assertIsNone(error, str(error))
        self.assertEqual([first], historical.frames)

    def test_historical_recovery_refuses_all_mutating_entrypoints_without_any_query(self):
        with self.f.lock.held():
            source, recovery, frame = self.completed()
            historical = self.history(source.previous, recovery.previous)
            archived = IOSAvatarSourceRecovery.archive(recovery.previous, historical)
            counts, sequence = deepcopy(self.f.fixture.sources), self.f.fixture.core.sequence
            raw, inode = recovery.store.path.read_bytes(), recovery.store.path.stat().st_ino
            allowed = []
            for name, function in (('save', archived.save), ('recover', archived.recover),
                                   ('live-follow', lambda: archived.follow(frame))):
                try:
                    function()
                except NativeUIError:
                    pass
                else:
                    allowed.append(name)
            after = (recovery.store.path.read_bytes(), recovery.store.path.stat().st_ino)
            self.assertEqual(counts, self.f.fixture.sources)
            self.assertEqual(sequence, self.f.fixture.core.sequence)
        self.assertEqual([], allowed)
        self.assertEqual((raw, inode), after)

    def test_historical_prefix_still_requires_every_old_original_and_live_decode_refuses_orphans(self):
        with self.f.lock.held():
            source, recovery, _frame = self.completed()
            prior_source, prior_recovery = deepcopy(source.previous), deepcopy(recovery.previous)
            fresh, latest, _second = self.completed()
            with self.assertRaises(NativeUIError):
                latest.decode(prior_recovery)
            old = recovery.record_store(1)
            old.path.unlink()
            with self.assertRaises((NativeUIError, FileNotFoundError)):
                self.history(prior_source, prior_recovery)

    def test_actual_current_archive_and_absent_live_parent_still_refuse_unknown_records(self):
        with self.f.lock.held():
            source, recovery, _frame = self.completed()
            prior = deepcopy(recovery.previous)
            fresh, latest, _second = self.completed()
            # The old prefix is valid history. Replacing the actual current
            # WAL with it leaves a genuine unknown second record: a fresh
            # current-owner check must not treat that rollback as history.
            latest.store.write(prior, latest.previous)
            with self.assertRaises(NativeUIError):
                IOSAvatarSourceRecovery.archive(prior, self.f.sources(historical=True))
            latest.store.path.unlink()
            with self.assertRaises(NativeUIError):
                IOSAvatarSourceRecovery(fresh)

    def test_actual_current_journal_change_during_archive_is_refused(self):
        with self.f.lock.held():
            source, recovery, _frame = self.completed()
            record = IOSAvatarSourceRecovery.record
            changed = []
            def mutate(reader, reference):
                value = record(reader, reference)
                if not changed:
                    changed.append(True)
                    replacement = deepcopy(recovery.previous)
                    replacement['payload'] = pack([dict(records=[], pending=None)])
                    recovery.store.write(replacement, recovery.previous)
                return value
            with patch.object(IOSAvatarSourceRecovery, 'record', mutate), self.assertRaises(NativeUIError):
                IOSAvatarSourceRecovery.archive(recovery.previous, self.f.sources(historical=True))
            self.assertTrue(changed)

    def test_actual_opened_partial_file_is_a_recorded_original_dependency(self):
        with self.f.lock.held():
            source = self.f.sources()
            intent = source.originals.intent
            def interrupted(kind, value):
                intent(kind, value)
                if kind == 'original' and value['phase'] == 'opened':
                    raise NativeUIError('Explicit lost empty-file return')
            source.originals.intent = interrupted
            with self.assertRaises(NativeUIError):
                source.read()
            partial = source.originals.path(source.state['pending']['original'])
            self.assertEqual(b'', partial.read_bytes())
            recovery = IOSAvatarSourceRecovery(source)
            recovery.recover()
            fresh = self.f.sources()
            fresh.read()
            with original_reads(fresh=True) as members:
                self.history(fresh.previous, recovery.previous)
        self.assertIn(partial, members)


if __name__ == '__main__':
    unittest.main()
